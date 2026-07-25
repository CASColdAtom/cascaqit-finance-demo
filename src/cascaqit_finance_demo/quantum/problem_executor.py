"""通过 CASCAQit 统一 ProblemCompiler 分析、编译并执行金融场景。

本模块是业务建模与量子运行时之间的编排层，处理六个步骤：

1. 调用场景验证输入并构造带业务语义的 Problem；
2. 让编译器分析目标机对 Digital、Hybrid、Analog 三种模式的物理可行性；
3. 将编译器项映射与金融 ``term_groups`` 交叉核对，给出模式建议；
4. 以 QAOA（Digital/Hybrid）或 QAA（Analog）编译程序并扫描参数；
5. 对采样候选做业务解码和约束复核，并与经典基线分开保存；
6. 记录后端、seed、shots、耗时和报告路径等审计证据。

模式名称描述编译与程序结构，不改变业务问题本身。Hybrid 只有在 Analog 段
承载真实业务冲突、Digital 段也仍有 residual 时成立；Analog 只有在完整问题
可以由 AHS 表达时成立。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import numpy as np
from cascaqit.exceptions import CapabilityError
from cascaqit.problems import ProblemCompiler
from cascaqit.simulators import LocalBackend, SimulationOptions
from cascaqit.targets import MockNeutralAtomTarget, TargetSpec

from cascaqit_finance_demo.domain.models import ExecutionEvidence
from cascaqit_finance_demo.domain.problem_api import (
    FinanceExperimentResult,
    FinanceProblemDefinition,
    FinanceScenario,
    ModeDecision,
    ModeDecisionRow,
    ProblemMode,
    ScenarioAnalysis,
)

ParameterSearchStrategy = Literal["preset", "grid", "seeded_sample"]


@dataclass(frozen=True)
class _AnalogBusinessEvidence:
    """模式顾问内部使用的完整分组与几何核对结果。"""

    matched_pairs: tuple[tuple[str, str], ...]
    covered_group_ids: tuple[str, ...]
    missing_contribution_ids: tuple[str, ...]
    unexpected_interaction_pairs: tuple[tuple[str, str], ...]
    geometry_status: Literal["verified", "missing", "distorted"]
    geometry_source: Literal["business_native", "verified_embedding"] | None
    layout_policy: str
    declared_contribution_count: int
    covered_contribution_count: int


@dataclass(frozen=True)
class FinanceModeAdvisor:
    """依据编译事实、完整业务分组和几何保真选择 Problem 模式。"""

    def decide(
        self, definition: FinanceProblemDefinition, analysis: Any
    ) -> ModeDecision:
        """判断三种模式；Hybrid 不能靠单条偶然命中的冲突边通过门禁。"""
        plan = analysis.mapping_plan
        supported_analog_pairs = {
            tuple(sorted(candidate.targets))
            for candidate in plan.term_candidates
            if candidate.operator == "zz"
            and candidate.implementation == "analog_interaction"
            and candidate.status == "supported"
        }
        expected_pairs = set(definition.analog_business_pairs)
        matched_pairs = tuple(sorted(expected_pairs & supported_analog_pairs))
        evidence = self._business_evidence(
            definition,
            plan,
            supported_analog_pairs=supported_analog_pairs,
            matched_pairs=matched_pairs,
        )

        # 每种模式读取自己的项分配，防止用 Hybrid 可行性推断 Analog 可行性。
        physical = {mode: plan.feasibility_for(mode) for mode in _MODES}
        unexpected_by_mode = {
            mode: self._unexpected_analog_term_ids(
                plan,
                analog_term_ids=physical[mode].analog_term_ids,
                expected_pairs=expected_pairs,
            )
            for mode in ("hybrid", "analog")
        }
        core_complete = (
            bool(definition.analog_candidate_group_ids)
            and not evidence.missing_contribution_ids
            and set(evidence.covered_group_ids)
            == set(definition.analog_candidate_group_ids)
        )
        geometry_verified = evidence.geometry_status == "verified"
        analog_suitable = (
            physical["analog"].feasible
            and bool(physical["analog"].analog_term_ids)
            and not physical["analog"].digital_term_ids
            and core_complete
            and geometry_verified
            and not unexpected_by_mode["analog"]
        )
        hybrid_suitable = (
            physical["hybrid"].feasible
            and bool(physical["hybrid"].analog_term_ids)
            and bool(physical["hybrid"].digital_term_ids)
            and core_complete
            and geometry_verified
            and not unexpected_by_mode["hybrid"]
        )

        # 优先级只作用于已经通过完整门禁的模式。完整 AHS 问题没有 Digital
        # residual，因此不会为了展示 D-A-D 人工制造 Hybrid block。
        if hybrid_suitable:
            recommended: ProblemMode = "hybrid"
            recommendation = "业务冲突项由原子相互作用承担，其余约束保留为数字项。"
        elif analog_suitable:
            recommended = "analog"
            recommendation = "完整业务图可由 AHS 表达，不需要 Digital residual。"
        elif physical["digital"].feasible:
            recommended = "digital"
            if evidence.missing_contribution_ids:
                recommendation = (
                    "Analog core 未完整覆盖全部业务贡献，使用 Digital 保留原问题。"
                )
            elif evidence.geometry_status != "verified" and (
                definition.analog_candidate_group_ids
            ):
                recommendation = (
                    "原子几何未通过业务图保真检查，使用 Digital 保留原问题。"
                )
            else:
                recommendation = "问题主体是稠密、全局或有方向的约束，使用 Digital。"
        else:
            # 推荐模式必须始终可执行。输入规模或 Target 能力可能让三条链路
            # 同时失败，此时返回明确能力错误，不能把 Digital 当作无条件兜底。
            diagnostics = tuple(
                dict.fromkeys(
                    code
                    for mode in _MODES
                    for code in physical[mode].diagnostic_codes
                )
            )
            suffix = f"（{', '.join(diagnostics)}）" if diagnostics else ""
            raise CapabilityError(
                f"当前 Target 无法完整编译该金融 Problem{suffix}。",
                code="FINANCE_NO_EXECUTABLE_MODE",
                stage="finance_mode_advisor",
            )

        rows = tuple(
            self._row(
                mode=mode,
                feasibility=physical[mode],
                recommended=recommended,
                evidence=evidence,
                unexpected_analog_term_ids=unexpected_by_mode.get(mode, ()),
                analog_suitable=analog_suitable,
                hybrid_suitable=hybrid_suitable,
            )
            for mode in _MODES
        )
        return ModeDecision(
            recommended_mode=recommended,
            reason=recommendation,
            rows=rows,
        )

    @staticmethod
    def _business_evidence(
        definition: FinanceProblemDefinition,
        plan: Any,
        *,
        supported_analog_pairs: set[tuple[str, str]],
        matched_pairs: tuple[tuple[str, str], ...],
    ) -> _AnalogBusinessEvidence:
        """逐 contribution 验证 core group，并核对实际物理 interaction 图。"""
        active_pairs = {
            tuple(sorted((item.left, item.right)))
            for item in plan.interactions
            if item.reference_coefficient > 0.0
        }
        expected_pairs = set(definition.analog_business_pairs)
        missing_ids: list[str] = []
        covered_group_ids: list[str] = []
        declared_count = 0
        covered_count = 0
        for group in definition.analog_candidate_groups:
            group_complete = bool(group.pairs)
            for pair in group.pairs:
                normalized = tuple(sorted(pair))
                declared_count += 1
                contribution_id = f"{group.group_id}:{normalized[0]}:{normalized[1]}"
                if normalized in supported_analog_pairs and normalized in active_pairs:
                    covered_count += 1
                else:
                    group_complete = False
                    missing_ids.append(contribution_id)
            if group_complete:
                covered_group_ids.append(group.group_id)

        geometry = definition.geometry_evidence
        layout_policy = str(plan.layout.layout_policy)
        if geometry is None:
            geometry_status: Literal["verified", "missing", "distorted"] = "missing"
            geometry_source = None
        else:
            declared_positions = dict(geometry.positions)
            actual_positions = {
                site.logical_id: tuple(site.position) for site in plan.layout.sites
            }
            exact_layout = (
                layout_policy == "provided" and declared_positions == actual_positions
            )
            interaction_graph_exact = (
                not (expected_pairs - active_pairs)
                and not (active_pairs - expected_pairs)
            )
            geometry_status = (
                "verified" if exact_layout and interaction_graph_exact else "distorted"
            )
            geometry_source = geometry.source

        return _AnalogBusinessEvidence(
            matched_pairs=matched_pairs,
            covered_group_ids=tuple(covered_group_ids),
            missing_contribution_ids=tuple(missing_ids),
            unexpected_interaction_pairs=tuple(sorted(active_pairs - expected_pairs)),
            geometry_status=geometry_status,
            geometry_source=geometry_source,
            layout_policy=layout_policy,
            declared_contribution_count=declared_count,
            covered_contribution_count=covered_count,
        )

    @staticmethod
    def _unexpected_analog_term_ids(
        plan: Any,
        *,
        analog_term_ids: Sequence[str],
        expected_pairs: set[tuple[str, str]],
    ) -> tuple[str, ...]:
        """找出进入 Analog 但不属于声明 core pair 的二体 Hamiltonian 项。"""
        by_term = {candidate.term_id: candidate for candidate in plan.term_candidates}
        unexpected = []
        for term_id in analog_term_ids:
            candidate = by_term.get(term_id)
            if candidate is None or candidate.operator != "zz":
                continue
            if tuple(sorted(candidate.targets)) not in expected_pairs:
                unexpected.append(term_id)
        return tuple(sorted(unexpected))

    @staticmethod
    def _row(
        *,
        mode: ProblemMode,
        feasibility: Any,
        recommended: ProblemMode,
        evidence: _AnalogBusinessEvidence,
        unexpected_analog_term_ids: tuple[str, ...],
        analog_suitable: bool,
        hybrid_suitable: bool,
    ) -> ModeDecisionRow:
        """把单一模式的编译事实和业务判断整理为可展示的决策行。"""
        compiler_feasible = bool(feasibility.feasible)
        if not compiler_feasible:
            status: Literal["recommended", "comparable", "unsuitable"] = "unsuitable"
            suitable = False
            reason = "Target 无法完整编译该模式。"
        elif mode == recommended:
            status = "recommended"
            suitable = True
            reason = "当前场景的推荐执行模式。"
        elif mode == "hybrid" and not hybrid_suitable:
            status = "unsuitable"
            suitable = False
            if evidence.missing_contribution_ids:
                reason = "Analog core 没有完整覆盖全部业务贡献。"
            elif evidence.geometry_status != "verified":
                reason = "原子几何没有通过业务 interaction 图保真检查。"
            elif unexpected_analog_term_ids:
                reason = "Analog 包含未声明的业务二体项。"
            else:
                reason = "Analog 业务项或 Digital residual 为空，不构成 Hybrid。"
        elif mode == "analog" and not analog_suitable:
            status = "unsuitable"
            suitable = False
            reason = "Analog 不能完整表达该场景的主要业务结构。"
        else:
            status = "comparable"
            suitable = True
            reason = "可运行对照实验，但不是默认方式。"
        return ModeDecisionRow(
            mode=mode,
            algorithm="qaa" if mode == "analog" else "qaoa",
            status=status,
            compiler_feasible=compiler_feasible,
            business_suitable=suitable,
            reason=reason,
            diagnostic_codes=FinanceModeAdvisor._diagnostic_codes(
                feasibility,
                evidence=evidence,
                unexpected_analog_term_ids=unexpected_analog_term_ids,
                mode=mode,
            ),
            analog_business_pairs=(
                evidence.matched_pairs if mode in {"hybrid", "analog"} else ()
            ),
            covered_group_ids=(
                evidence.covered_group_ids if mode in {"hybrid", "analog"} else ()
            ),
            missing_contribution_ids=(
                evidence.missing_contribution_ids
                if mode in {"hybrid", "analog"}
                else ()
            ),
            unexpected_analog_term_ids=(
                unexpected_analog_term_ids if mode in {"hybrid", "analog"} else ()
            ),
            unexpected_interaction_pairs=(
                evidence.unexpected_interaction_pairs
                if mode in {"hybrid", "analog"}
                else ()
            ),
            geometry_status=(
                evidence.geometry_status if mode in {"hybrid", "analog"} else "missing"
            ),
            geometry_source=(
                evidence.geometry_source if mode in {"hybrid", "analog"} else None
            ),
            layout_policy=evidence.layout_policy,
            declared_contribution_count=(
                evidence.declared_contribution_count
                if mode in {"hybrid", "analog"}
                else 0
            ),
            covered_contribution_count=(
                evidence.covered_contribution_count
                if mode in {"hybrid", "analog"}
                else 0
            ),
            analog_term_count=len(feasibility.analog_term_ids),
            digital_term_count=len(feasibility.digital_term_ids),
        )

    @staticmethod
    def _diagnostic_codes(
        feasibility: Any,
        *,
        evidence: _AnalogBusinessEvidence,
        unexpected_analog_term_ids: tuple[str, ...],
        mode: ProblemMode,
    ) -> tuple[str, ...]:
        """合并编译器诊断和金融业务门禁诊断，供 API 与界面直接展示。"""
        codes = list(feasibility.diagnostic_codes)
        if mode in {"hybrid", "analog"}:
            if evidence.geometry_status == "missing":
                codes.append("FINANCE_GEOMETRY_MISSING")
            elif evidence.geometry_status == "distorted":
                codes.append("FINANCE_GEOMETRY_DISTORTED")
            if evidence.missing_contribution_ids:
                codes.append("FINANCE_ANALOG_CONTRIBUTION_MISSING")
            if evidence.unexpected_interaction_pairs:
                codes.append("FINANCE_INTERACTION_UNEXPECTED")
            if unexpected_analog_term_ids:
                codes.append("FINANCE_ANALOG_TERM_UNEXPECTED")
        return tuple(dict.fromkeys(codes))


class ScenarioExecutor:
    """串联金融场景的验证、分析、编译、执行、解码和审计报告。

    ``analyze`` 只验证和生成编译计划，不执行采样；``run`` 才编译并调用后端。
    默认目标和后端用于离线确定性演示，执行证据会明确标记为本地模拟，不应
    解释为真实中性原子硬件结果。
    """

    def __init__(
        self,
        *,
        target: TargetSpec | None = None,
        compiler: ProblemCompiler | None = None,
        advisor: FinanceModeAdvisor | None = None,
    ) -> None:
        """注入目标机、Problem 编译器和模式顾问；缺省使用离线中性原子目标。"""
        self.target = target or MockNeutralAtomTarget.local_ahs_v0_1()
        self.compiler = compiler or ProblemCompiler()
        self.advisor = advisor or FinanceModeAdvisor()

    def analyze(self, scenario: FinanceScenario, case_input: Any) -> ScenarioAnalysis:
        """验证输入并生成不触发执行的 Problem 分析和模式建议。

        分析结果包含变量到物理项的候选映射、每种模式的诊断码以及业务模式
        建议。这个阶段不会产生 counts，也不会运行模拟器。
        """
        issues = scenario.validate(case_input)
        if issues:
            raise ValueError("; ".join(issue.message for issue in issues))
        definition = scenario.build_definition(case_input)
        analysis = self.compiler.analyze(definition.problem, target=self.target)
        return ScenarioAnalysis(
            definition=definition,
            problem_analysis=analysis,
            mode_decision=self.advisor.decide(definition, analysis),
        )

    def run(
        self,
        scenario: FinanceScenario,
        case_input: Any,
        *,
        mode: Literal["recommended", "digital", "hybrid", "analog"] = "recommended",
        parameter_sets: Sequence[Mapping[str, float]] | None = None,
        layers: int = 1,
        search_strategy: ParameterSearchStrategy = "preset",
        parameter_budget: int = 2,
        shots: int = 64,
        seed: int = 23,
        report_path: Path | None = None,
    ) -> FinanceExperimentResult:
        """按指定或推荐模式执行场景，并返回业务结果与完整审计证据。

        ``mode='recommended'`` 使用模式顾问结论；显式模式仍必须同时通过编译
        可行性和业务适配检查。Digital 可以选择 QAOA 层数与参数搜索方法，
        Hybrid 当前只支持一层，Analog 使用固定的一层执行语义。

        每个参数点执行给定 ``shots`` 次采样，``optimize`` 根据观测结果选出最佳
        候选。最佳采样候选若违反业务约束，展示层会回退到同次执行产生的经典
        基线，但 ``business_candidate``、``baseline_solution`` 和
        ``displayed_solution`` 三者分别保留，避免把回退结果误称为量子采样结果。
        """
        if shots < 1:
            raise ValueError("shots must be positive.")
        if seed < 0:
            raise ValueError("seed must be non-negative.")
        scenario_analysis = self.analyze(scenario, case_input)
        selected_mode = (
            scenario_analysis.mode_decision.recommended_mode
            if mode == "recommended"
            else mode
        )
        decision = scenario_analysis.mode_decision.for_mode(selected_mode)
        if not decision.compiler_feasible:
            codes = ", ".join(decision.diagnostic_codes) or "unknown"
            raise ValueError(f"{selected_mode} mode is unavailable: {codes}")
        if decision.status == "unsuitable":
            raise ValueError(decision.reason)

        definition = scenario_analysis.definition
        # QAA 对应完整 Analog 退火；Digital 和 D-A-D Hybrid 都走 QAOA 优化协议。
        compiled = self.compiler.compile(
            definition.problem,
            mode=selected_mode,
            algorithm="qaa" if selected_mode == "analog" else "qaoa",
            target=self.target,
            layers=layers,
        )
        # 高级调用方可以显式给出参数点；普通 API 则由受约束的搜索策略生成。
        # 两条路径都进入同一个 compiled.optimize()，不会改变 Problem 或解码器。
        if parameter_sets is None:
            points = generate_parameter_sets(
                selected_mode,
                layers=layers,
                strategy=search_strategy,
                budget=parameter_budget,
                seed=seed,
            )
            resolved_strategy = search_strategy
        else:
            points = tuple(dict(point) for point in parameter_sets)
            if not points:
                raise ValueError("parameter_sets must not be empty.")
            resolved_strategy = "explicit"
        backend = LocalBackend(
            seed=seed,
            target=self.target,
            analog_time_steps=8,
            created_at="2026-07-24T00:00:00+00:00",
        )
        options = None
        if selected_mode != "digital":
            options = SimulationOptions(
                # 12-site 反欺诈布局在 Hybrid 状态交接时会累积浮点误差，
                # complex64 可能无法通过归一化检查，因此统一使用 complex128。
                dtype="complex128",
                integrator="fixed_step_krylov",
                max_steps=8,
                seed=seed,
            )
        started = perf_counter()
        execution = compiled.optimize(
            parameter_sets=points,
            shots=shots,
            seed=seed,
            backend=backend,
            options=options,
        )
        wall_time = perf_counter() - started

        # 后端候选只提供位串和能量；金融指标与可行性必须由场景重新计算。
        candidate = scenario.decode(
            case_input,
            definition,
            execution.best_observed_candidate,
        )
        baseline_solution = None
        if execution.baseline is not None and execution.baseline.bitstring is not None:
            baseline_solution = scenario.decode(
                case_input,
                definition,
                execution.baseline,
            )
        displayed = candidate
        # 回退只影响界面展示来源，不覆盖或删除真实采样候选。
        if not getattr(candidate, "feasible", True) and baseline_solution is not None:
            displayed = baseline_solution

        saved_report: Path | None = None
        if report_path is not None:
            saved_report = report_path.expanduser().resolve()
            saved_report.parent.mkdir(parents=True, exist_ok=True)
            execution.report(
                saved_report,
                language="zh",
                title=f"{definition.title} · {selected_mode}",
            )
        evidence = ExecutionEvidence(
            backend="LocalBackend",
            execution_kind="local_simulation",
            result_hash=execution.result.stable_hash(),
            seed=seed,
            shots=shots,
            wall_time_seconds=wall_time,
            hardware_execution=False,
            cloud_execution=False,
            network_accessed=False,
        )
        return FinanceExperimentResult(
            case_id=definition.case_id,
            mode=selected_mode,
            definition=definition,
            analysis=scenario_analysis,
            execution=execution,
            business_candidate=candidate,
            baseline_solution=baseline_solution,
            displayed_solution=displayed,
            evidence=evidence,
            report_path=saved_report,
            metadata={
                "layers": layers,
                "search_strategy": resolved_strategy,
                "parameter_budget": parameter_budget,
                "parameter_set_count": len(points),
                "selected_evaluation_index": execution.selected_evaluation_index,
                "displayed_source": (
                    "best_observed" if displayed is candidate else "classical_baseline"
                ),
                "optimality_claim": execution.optimality_claim,
            },
        )


def default_parameter_sets(
    mode: ProblemMode,
    *,
    layers: int = 1,
) -> tuple[dict[str, float], ...]:
    """返回适合现场演示的小规模确定性参数扫描，不依赖在线优化器。

    这些点是固定演示配置，不是针对每个金融实例训练得到的最优参数。Analog
    扫描退火时间和最大 Rabi 驱动；Digital 把同一组 cost/mixer 角度扩展到
    指定层数，Hybrid 当前只允许一层。
    """
    _validate_search_shape(mode, layers=layers, budget=2)
    if mode == "analog":
        return (
            {"anneal_time": 0.4, "omega_max": 1.0},
            {"anneal_time": 0.7, "omega_max": 1.4},
        )
    base_points = ((0.16, 0.24), (0.28, -0.18))
    return tuple(
        {
            **{f"gamma_{index}": gamma for index in range(layers)},
            **{f"beta_{index}": beta for index in range(layers)},
        }
        for gamma, beta in base_points
    )


def generate_parameter_sets(
    mode: ProblemMode,
    *,
    layers: int = 1,
    strategy: ParameterSearchStrategy = "preset",
    budget: int = 2,
    seed: int = 23,
) -> tuple[dict[str, float], ...]:
    """按模式、层数和预算生成可复现的参数点。

    ``preset`` 保留两组人工校验过的演示参数；``grid`` 用于观察一层 Digital
    QAOA 的二维目标面；``seeded_sample`` 面向多层 Digital QAOA，在固定 seed
    下生成完全一致的参数序列。当前 Hybrid 和 Analog 仍只开放预设点，避免把
    尚未实现的多层 Hybrid 或连续优化伪装成可用能力。
    """
    _validate_search_shape(mode, layers=layers, budget=budget)
    if strategy not in {"preset", "grid", "seeded_sample"}:
        raise ValueError(f"unsupported parameter search strategy: {strategy!r}")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer.")

    if strategy == "preset":
        presets = default_parameter_sets(mode, layers=layers)
        if budget > len(presets):
            raise ValueError("preset search supports at most 2 parameter points.")
        return presets[:budget]

    if mode != "digital":
        raise ValueError(f"{strategy} search is currently available only for Digital.")

    if strategy == "grid":
        if layers != 1:
            raise ValueError("grid search currently supports Digital layers=1 only.")
        # 构造接近方形的二维网格，并按 beta/gamma 交错展开。这样较小预算也不会
        # 退化成完全相同的参数点，同时保持生成结果可解释、可复现。
        gamma_count = max(1, int(math.floor(math.sqrt(budget))))
        beta_count = int(math.ceil(budget / gamma_count))
        gammas = np.linspace(0.0, math.pi, gamma_count)
        betas = np.linspace(-math.pi / 2.0, math.pi / 2.0, beta_count)
        return tuple(
            {"gamma_0": float(gamma), "beta_0": float(beta)}
            for beta in betas
            for gamma in gammas
        )[:budget]

    rng = np.random.default_rng(seed)
    points: list[dict[str, float]] = []
    for _ in range(budget):
        gammas = rng.uniform(0.0, math.pi, size=layers)
        betas = rng.uniform(-math.pi / 2.0, math.pi / 2.0, size=layers)
        points.append(
            {
                **{
                    f"gamma_{index}": float(value)
                    for index, value in enumerate(gammas)
                },
                **{
                    f"beta_{index}": float(value)
                    for index, value in enumerate(betas)
                },
            }
        )
    return tuple(points)


def _validate_search_shape(mode: ProblemMode, *, layers: int, budget: int) -> None:
    """集中校验模式、QAOA 层数和演示评估预算。"""
    if mode not in _MODES:
        raise ValueError(f"unsupported Problem mode: {mode!r}")
    if not isinstance(layers, int) or isinstance(layers, bool) or layers < 1:
        raise ValueError("layers must be a positive integer.")
    if mode == "digital" and layers > 3:
        raise ValueError("Digital demo supports layers from 1 to 3.")
    if mode != "digital" and layers != 1:
        raise ValueError(f"{mode.capitalize()} currently supports layers=1 only.")
    if not isinstance(budget, int) or isinstance(budget, bool) or not 1 <= budget <= 24:
        raise ValueError("parameter budget must be between 1 and 24.")


_MODES: tuple[ProblemMode, ...] = ("digital", "hybrid", "analog")
