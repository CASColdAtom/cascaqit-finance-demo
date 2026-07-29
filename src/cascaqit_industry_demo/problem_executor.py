"""通过 CASCAQit ProblemCompiler 分析、编译并执行行业组合优化场景。

本模块是业务建模与量子运行时之间的编排层，处理六个步骤：

1. 调用场景验证输入并构造带业务语义的 Problem；
2. 让编译器分析目标机对 Digital、Hybrid、Analog 三种模式的物理可行性；
3. 将编译器项映射与领域 ``term_groups`` 交叉核对，给出模式建议；
4. 按运行计划选择 QAOA、VQE 或 QAA，并执行参数评估或连续优化；
5. 对采样候选做业务解码和约束复核，并与经典基线分开保存；
6. 记录后端、seed、shots、耗时和报告路径等审计证据。

模式名称描述编译与程序结构，不改变业务问题本身。Hybrid 只有在 Analog 段
承载真实业务冲突、Digital 段也仍有 residual 时成立；Analog 只有在完整问题
可以由 AHS 表达时成立。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import numpy as np
from cascaqit.algorithms import HardwareEfficientAnsatz, OptimizerConfig
from cascaqit.exceptions import CapabilityError
from cascaqit.problems import ProblemCompiler
from cascaqit.simulators import LocalBackend, SimulationOptions
from cascaqit.targets import MockNeutralAtomTarget, TargetSpec

from cascaqit_industry_demo.problem_api import (
    AlgorithmPlan,
    ExecutionEvidence,
    ExperimentResult,
    LayerCalibrationResult,
    LayerPolicy,
    ModeDecision,
    ModeDecisionRow,
    ProblemAlgorithm,
    ProblemDefinition,
    ProblemMode,
    ProblemScenario,
    RepeatedExperimentResult,
    RequestedAlgorithm,
    ScenarioAnalysis,
)

ParameterSearchStrategy = Literal[
    "preset", "grid", "seeded_sample", "continuous"
]


@dataclass(frozen=True)
class ProblemAlgorithmPolicy:
    """把用户选择解析为唯一、可执行且可审计的领域中性算法计划。"""

    def resolve(
        self,
        definition: ProblemDefinition,
        *,
        mode: ProblemMode,
        algorithm: RequestedAlgorithm,
        layer_policy: LayerPolicy,
        layers: int,
        max_layers: int,
        min_improvement: float,
        search_strategy: ParameterSearchStrategy,
        parameter_budget: int,
        optimizer_starts: int,
        explicit_parameters: bool,
    ) -> AlgorithmPlan:
        """校验模式、算法、层数和搜索方式，不执行隐式算法降级。"""
        if algorithm not in {"recommended", "qaoa", "vqe", "qaa"}:
            raise ValueError(f"unsupported algorithm: {algorithm!r}")
        if layer_policy not in {"fixed", "adaptive"}:
            raise ValueError(f"unsupported layer policy: {layer_policy!r}")
        recommended: ProblemAlgorithm = (
            "qaa" if mode == "analog" else "qaoa"
        )
        resolved: ProblemAlgorithm = (
            recommended if algorithm == "recommended" else algorithm
        )
        available: tuple[ProblemAlgorithm, ...]
        if mode == "digital":
            available = tuple(definition.digital_algorithms)
        elif mode == "hybrid":
            available = ("qaoa",)
        else:
            available = ("qaa",)
        if resolved not in available:
            raise ValueError(
                f"algorithm {resolved!r} is unavailable for {definition.case_id} "
                f"in {mode} mode; available algorithms: {', '.join(available)}."
            )

        if not isinstance(layers, int) or isinstance(layers, bool) or layers < 1:
            raise ValueError("layers must be a positive integer.")
        if (
            not isinstance(max_layers, int)
            or isinstance(max_layers, bool)
            or max_layers < 1
        ):
            raise ValueError("max_layers must be a positive integer.")
        threshold = float(min_improvement)
        if not math.isfinite(threshold) or threshold < 0.0:
            raise ValueError("min_improvement must be finite and non-negative.")

        ansatz = None
        if resolved == "vqe":
            vqe_config = definition.vqe_ansatz
            if vqe_config is None:
                raise RuntimeError("VQE algorithm lost its scenario ansatz contract.")
            ansatz = HardwareEfficientAnsatz(
                rotation_axes=vqe_config.rotation_axes,
                entanglement=vqe_config.entanglement,
            )

        if resolved == "qaa":
            maximum = 1
        elif resolved == "vqe":
            maximum = vqe_config.max_layers
        elif mode == "hybrid":
            maximum = 2
        else:
            maximum = 3
        if layer_policy == "fixed":
            if layers > maximum:
                raise ValueError(
                    f"{mode} {resolved} supports fixed layers from 1 to {maximum}."
                )
            resolved_max_layers = layers
        else:
            if resolved == "qaa":
                raise ValueError("Analog QAA does not support adaptive layers.")
            if max_layers > maximum:
                raise ValueError(
                    f"{mode} {resolved} supports adaptive max_layers "
                    f"from 1 to {maximum}."
                )
            if search_strategy != "continuous" or explicit_parameters:
                raise ValueError(
                    "adaptive layers require continuous optimization without explicit "
                    "parameter sets."
                )
            resolved_max_layers = max_layers

        if (
            resolved == "vqe"
            and search_strategy != "continuous"
            and not explicit_parameters
        ):
            raise ValueError("VQE currently requires continuous optimization.")
        effective_search_strategy = (
            "explicit" if explicit_parameters else search_strategy
        )
        if effective_search_strategy == "continuous":
            if resolved == "vqe":
                variables = getattr(definition.problem, "variables", ())
                parameter_count = (
                    len(variables)
                    * len(vqe_config.rotation_axes)
                    * resolved_max_layers
                )
            elif resolved == "qaoa":
                parameter_count = 2 * resolved_max_layers
            else:
                parameter_count = 2
            minimum_budget = parameter_count + 2
            if parameter_budget < minimum_budget:
                raise ValueError(
                    f"continuous {resolved} with up to {resolved_max_layers} layers "
                    f"requires parameter_budget >= {minimum_budget}; received "
                    f"{parameter_budget}."
                )
        return AlgorithmPlan(
            requested_algorithm=algorithm,
            resolved_algorithm=resolved,
            problem_hash=definition.problem.stable_hash(),
            layer_policy=layer_policy,
            requested_layers=layers,
            max_layers=resolved_max_layers,
            min_improvement=threshold,
            search_strategy=effective_search_strategy,
            parameter_budget=parameter_budget,
            optimizer_method=(
                "COBYLA" if effective_search_strategy == "continuous" else None
            ),
            per_start_evaluation_budget=(
                parameter_budget if effective_search_strategy == "continuous" else None
            ),
            optimizer_starts=optimizer_starts,
            ansatz=ansatz,
        )


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
class ProblemModeAdvisor:
    """依据编译事实、完整领域分组和几何保真选择 Problem 模式。"""

    def decide(
        self, definition: ProblemDefinition, analysis: Any
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
                published_digital_algorithms=(
                    definition.published_digital_algorithms
                ),
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
        definition: ProblemDefinition,
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
        published_digital_algorithms: tuple[Literal["qaoa", "vqe"], ...],
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
            available_algorithms=(
                tuple(published_digital_algorithms)
                if mode == "digital"
                else (("qaoa",) if mode == "hybrid" else ("qaa",))
            ),
            status=status,
            compiler_feasible=compiler_feasible,
            business_suitable=suitable,
            reason=reason,
            diagnostic_codes=ProblemModeAdvisor._diagnostic_codes(
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
    """串联行业场景的验证、分析、编译、执行、解码和审计报告。

    ``analyze`` 只验证和生成编译计划，不执行采样；``run`` 才编译并调用后端。
    默认目标和后端用于离线确定性演示，执行证据会明确标记为本地模拟，不应
    解释为真实中性原子硬件结果。
    """

    def __init__(
        self,
        *,
        target: TargetSpec | None = None,
        compiler: ProblemCompiler | None = None,
        advisor: ProblemModeAdvisor | None = None,
        algorithm_policy: ProblemAlgorithmPolicy | None = None,
    ) -> None:
        """注入目标机、Problem 编译器和模式顾问；缺省使用离线中性原子目标。"""
        self.target = target or MockNeutralAtomTarget.local_ahs_v0_1()
        self.compiler = compiler or ProblemCompiler()
        self.advisor = advisor or ProblemModeAdvisor()
        self.algorithm_policy = algorithm_policy or ProblemAlgorithmPolicy()

    def analyze(self, scenario: ProblemScenario, case_input: Any) -> ScenarioAnalysis:
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
        scenario: ProblemScenario,
        case_input: Any,
        *,
        mode: Literal["recommended", "digital", "hybrid", "analog"] = "recommended",
        algorithm: RequestedAlgorithm = "recommended",
        layer_policy: LayerPolicy = "fixed",
        parameter_sets: Sequence[Mapping[str, float]] | None = None,
        layers: int = 1,
        max_layers: int = 3,
        min_improvement: float = 0.0,
        search_strategy: ParameterSearchStrategy = "preset",
        parameter_budget: int = 2,
        optimizer_starts: int = 1,
        shots: int = 64,
        seed: int = 23,
        report_path: Path | None = None,
    ) -> ExperimentResult:
        """按指定或推荐模式执行场景，并返回业务结果与完整审计证据。

        ``mode='recommended'`` 使用模式顾问结论；显式模式仍必须同时通过编译
        可行性和业务适配检查。算法策略再校验 QAOA、VQE、QAA 与最终模式、
        场景和层数策略的组合。固定层数执行一次优化；自动选层由 CASCAQit 从
        一层开始连续执行，并按期望目标改善和早停规则选出结果。

        离散策略逐点执行；``continuous`` 使用 CASCAQit 的 SciPy 适配器做有界
        COBYLA 多起点优化。两者都保留全部真实目标评估。最佳采样候选若违反
        业务约束，展示层可以显示同次执行的经典基线用于诊断，但量子候选、经典
        基线和展示结果始终分开保存，重复运行统计也只读取量子候选。
        """
        if shots < 1:
            raise ValueError("shots must be positive.")
        if seed < 0:
            raise ValueError("seed must be non-negative.")
        if search_strategy != "continuous" and optimizer_starts != 1:
            raise ValueError(
                "optimizer_starts is available only with continuous search."
            )
        if parameter_sets is not None and optimizer_starts != 1:
            raise ValueError(
                "optimizer_starts is unavailable with explicit parameter sets."
            )
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
        plan = self.algorithm_policy.resolve(
            definition,
            mode=selected_mode,
            algorithm=algorithm,
            layer_policy=layer_policy,
            layers=layers,
            max_layers=max_layers,
            min_improvement=min_improvement,
            search_strategy=search_strategy,
            parameter_budget=parameter_budget,
            optimizer_starts=optimizer_starts,
            explicit_parameters=parameter_sets is not None,
        )
        # 高级调用方可以显式给出参数点；普通 API 则由受约束的搜索策略生成。
        # 两条路径都进入同一个 compiled.optimize()，不会改变 Problem 或解码器。
        optimizer: OptimizerConfig | None = None
        if parameter_sets is None and search_strategy == "continuous":
            points = None
            optimizer = build_optimizer_config(
                mode=selected_mode,
                layers=plan.max_layers,
                evaluation_budget=parameter_budget,
                starts=optimizer_starts,
                seed=seed,
            )
            resolved_strategy = search_strategy
        elif parameter_sets is None:
            points = generate_parameter_sets(
                selected_mode,
                layers=plan.requested_layers,
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
        layer_experiment = None
        if plan.layer_policy == "adaptive":
            if optimizer is None:
                raise RuntimeError("adaptive layer execution lost its optimizer.")
            layer_experiment = self.compiler.optimize_layers(
                definition.problem,
                mode=selected_mode,
                algorithm=plan.resolved_algorithm,
                target=self.target,
                max_layers=plan.max_layers,
                optimizer=optimizer,
                ansatz=plan.ansatz,
                min_improvement=plan.min_improvement,
                patience=1,
                initial_parameters=(
                    default_parameter_sets(selected_mode, layers=1)[0]
                    if plan.resolved_algorithm == "qaoa"
                    else None
                ),
                shots=shots,
                seed=seed,
                backend=backend,
                options=options,
            )
            execution = layer_experiment.selected_execution
        else:
            compiled = self.compiler.compile(
                definition.problem,
                mode=selected_mode,
                algorithm=plan.resolved_algorithm,
                target=self.target,
                layers=plan.requested_layers,
                ansatz=plan.ansatz,
            )
            execution = compiled.optimize(
                parameter_sets=points,
                optimizer=optimizer,
                initial_parameters=(
                    None
                    if optimizer is None or plan.resolved_algorithm == "vqe"
                    else default_parameter_sets(
                        selected_mode,
                        layers=plan.requested_layers,
                    )[0]
                ),
                shots=shots,
                seed=seed,
                backend=backend,
                options=options,
            )
        if execution.problem_hash != plan.problem_hash:
            raise RuntimeError(
                "algorithm plan and execution reference different Problems."
            )
        if plan.optimizer_method is not None:
            optimization = execution.optimization
            if optimization is None:
                raise RuntimeError("algorithm plan requires a missing optimization.")
            actual_optimizer = optimization.optimizer
            if (
                actual_optimizer.method != plan.optimizer_method
                or actual_optimizer.max_evaluations
                != plan.per_start_evaluation_budget
                or actual_optimizer.starts != plan.optimizer_starts
            ):
                raise RuntimeError(
                    "algorithm plan does not match the executed optimizer."
                )
        wall_time = perf_counter() - started

        # 后端候选只提供位串和能量；领域指标与可行性必须由场景重新计算。
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
            report_source = layer_experiment or execution
            report_source.report(
                saved_report,
                language="zh",
                title=(
                    f"{definition.title} · {selected_mode} · "
                    f"{plan.resolved_algorithm}"
                ),
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
        return ExperimentResult(
            case_id=definition.case_id,
            mode=selected_mode,
            algorithm_plan=plan,
            definition=definition,
            analysis=scenario_analysis,
            execution=execution,
            business_candidate=candidate,
            baseline_solution=baseline_solution,
            displayed_solution=displayed,
            evidence=evidence,
            layer_experiment=layer_experiment,
            report_path=saved_report,
            metadata={
                "layers": (
                    layer_experiment.selected_layers
                    if layer_experiment is not None
                    else plan.requested_layers
                ),
                "layer_policy": plan.layer_policy,
                "requested_algorithm": plan.requested_algorithm,
                "algorithm": plan.resolved_algorithm,
                "max_layers": plan.max_layers,
                "executed_layers": (
                    tuple(step.layers for step in layer_experiment.steps)
                    if layer_experiment is not None
                    else (plan.requested_layers,)
                ),
                "layer_stop_reason": (
                    layer_experiment.stop_reason
                    if layer_experiment is not None
                    else "fixed"
                ),
                "search_strategy": resolved_strategy,
                "parameter_budget": parameter_budget,
                "parameter_set_count": (
                    layer_experiment.total_evaluation_count
                    if layer_experiment is not None
                    else len(execution.parameter_history)
                ),
                "optimizer_starts": optimizer_starts if optimizer is not None else None,
                "optimizer_initialization": (
                    "validated_preset_then_seeded_random"
                    if optimizer is not None
                    else None
                ),
                "selected_evaluation_index": execution.selected_evaluation_index,
                "displayed_source": (
                    "best_observed" if displayed is candidate else "classical_baseline"
                ),
                "optimality_claim": execution.optimality_claim,
            },
        )

    def calibrate_layers(
        self,
        scenario: ProblemScenario,
        case_input: Any,
        *,
        mode: Literal["recommended", "digital", "hybrid"] = "recommended",
        algorithm: RequestedAlgorithm = "recommended",
        max_layers: int = 3,
        repeats: int = 3,
        confidence_level: float = 0.95,
        min_improvement: float = 0.0,
        parameter_budget: int = 12,
        optimizer_starts: int = 1,
        shots: int = 64,
        seed: int = 23,
        report_path: Path | None = None,
    ) -> LayerCalibrationResult:
        """用配对重复实验校准推荐层数，并复核选中层的金融约束。

        每个 repeat 在相邻层之间保持配对 seed 和层间参数迁移。层数选择完全
        采用 CASCAQit 的 Student-t 改善置信区间；金融可行率只作为发布条件，
        不反向篡改算法选出的层数。
        """
        if repeats < 2:
            raise ValueError("layer calibration repeats must be at least two.")
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
        if selected_mode == "analog":
            raise ValueError("Analog QAA does not support layer calibration.")
        decision = scenario_analysis.mode_decision.for_mode(selected_mode)
        if not decision.compiler_feasible or decision.status == "unsuitable":
            raise ValueError(decision.reason)
        definition = scenario_analysis.definition
        plan = self.algorithm_policy.resolve(
            definition,
            mode=selected_mode,
            algorithm=algorithm,
            layer_policy="adaptive",
            layers=1,
            max_layers=max_layers,
            min_improvement=min_improvement,
            search_strategy="continuous",
            parameter_budget=parameter_budget,
            optimizer_starts=optimizer_starts,
            explicit_parameters=False,
        )
        optimizer = replace(
            build_optimizer_config(
                mode=selected_mode,
                layers=plan.max_layers,
                evaluation_budget=parameter_budget,
                starts=optimizer_starts,
                seed=seed,
            ),
            seed=None,
        )
        backend = LocalBackend(
            seed=seed,
            target=self.target,
            analog_time_steps=8,
            created_at="2026-07-24T00:00:00+00:00",
        )
        options = None
        if selected_mode == "hybrid":
            options = SimulationOptions(
                dtype="complex128",
                integrator="fixed_step_krylov",
                max_steps=8,
                seed=seed,
            )
        experiment = self.compiler.optimize_layers_repeated(
            definition.problem,
            mode=selected_mode,
            algorithm=plan.resolved_algorithm,
            target=self.target,
            max_layers=plan.max_layers,
            repeats=repeats,
            optimizer=optimizer,
            ansatz=plan.ansatz,
            confidence_level=confidence_level,
            min_improvement=plan.min_improvement,
            patience=1,
            shots=shots,
            seed=seed,
            backend=backend,
            options=options,
        )
        if report_path is not None:
            saved_report = report_path.expanduser().resolve()
            saved_report.parent.mkdir(parents=True, exist_ok=True)
            experiment.report(
                saved_report,
                language="zh",
                title=(
                    f"{definition.title} · {selected_mode} · "
                    f"{plan.resolved_algorithm} 层数校准"
                ),
            )
        candidates = tuple(
            scenario.decode(
                case_input,
                definition,
                run.execution.best_observed_candidate,
            )
            for run in experiment.selected_statistics.runs
        )
        return LayerCalibrationResult(
            mode=selected_mode,
            algorithm_plan=plan,
            analysis=scenario_analysis,
            experiment=experiment,
            business_candidates=candidates,
        )

    def run_repeated(
        self,
        scenario: ProblemScenario,
        case_input: Any,
        *,
        repeats: int,
        confidence_level: float = 0.95,
        report_path: Path | None = None,
        **run_options: Any,
    ) -> RepeatedExperimentResult:
        """独立重复优化和采样，并从量子候选中选择一个代表运行。

        第 ``i`` 次运行使用 ``base_seed + i``。每次都重新分析、编译、优化和采样，
        因而统计结果反映完整量子链路对 seed 的敏感度，而不是对同一 counts 做
        重采样。该方法不读取 ``baseline_solution`` 判断成功与否。
        """
        if not isinstance(repeats, int) or isinstance(repeats, bool):
            raise TypeError("repeats must be an integer.")
        if not 2 <= repeats <= 5:
            raise ValueError("repeats must be between 2 and 5.")
        if not 0.5 < float(confidence_level) < 1.0:
            raise ValueError("confidence_level must be greater than 0.5 and below 1.0.")
        base_seed = run_options.pop("seed", 23)
        if (
            not isinstance(base_seed, int)
            or isinstance(base_seed, bool)
            or base_seed < 0
        ):
            raise ValueError("seed must be a non-negative integer.")

        runs = tuple(
            self.run(
                scenario,
                case_input,
                seed=base_seed + repeat_index,
                report_path=None,
                **run_options,
            )
            for repeat_index in range(repeats)
        )
        representative_index = min(
            range(len(runs)),
            key=lambda index: (
                not bool(getattr(runs[index].business_candidate, "feasible", True)),
                float(runs[index].execution.best_observed_candidate.objective_value),
                index,
            ),
        )
        representative = runs[representative_index]
        if report_path is not None:
            saved_report = report_path.expanduser().resolve()
            saved_report.parent.mkdir(parents=True, exist_ok=True)
            representative.execution.report(
                saved_report,
                language="zh",
                title=f"{representative.definition.title} · {representative.mode}",
            )
            representative = replace(representative, report_path=saved_report)
            mutable_runs = list(runs)
            mutable_runs[representative_index] = representative
            runs = tuple(mutable_runs)

        return RepeatedExperimentResult(
            representative=representative,
            runs=runs,
            representative_index=representative_index,
            confidence_level=float(confidence_level),
        )


def default_parameter_sets(
    mode: ProblemMode,
    *,
    layers: int = 1,
) -> tuple[dict[str, float], ...]:
    """返回适合现场演示的小规模确定性参数扫描，不依赖在线优化器。

    这些点是固定快速运行配置，不是针对每个金融实例训练得到的最优参数。Analog
    扫描退火时间和最大 Rabi 驱动；Digital 把同一组 cost/mixer 角度扩展到
    指定层数；Hybrid 使用相同参数结构，并由算法策略限制为最多两层。
    """
    _validate_search_shape(mode, layers=layers, budget=2)
    if mode == "analog":
        return (
            {"anneal_time": 0.6, "omega_max": 1.0},
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
    下生成完全一致的参数序列。Hybrid 和 Analog 只开放预设点或连续优化；
    Hybrid 多层由算法策略限制为最多两层。
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


def build_optimizer_config(
    *,
    mode: ProblemMode,
    layers: int,
    evaluation_budget: int,
    starts: int,
    seed: int,
) -> OptimizerConfig:
    """构造 Demo 允许的无梯度连续优化配置。

    ``evaluation_budget`` 是每个起点最多调用量子目标函数的次数，总上限为
    ``evaluation_budget * starts``。参数边界不在金融层重复定义，而由编译结果的
    Parameter schema 补齐，保证 Digital、Hybrid 和 Analog 使用各自真实参数域。
    """
    _validate_search_shape(mode, layers=layers, budget=evaluation_budget)
    if evaluation_budget < 4:
        raise ValueError("continuous evaluation budget must be between 4 and 24.")
    if not isinstance(starts, int) or isinstance(starts, bool) or not 1 <= starts <= 3:
        raise ValueError("optimizer starts must be between 1 and 3.")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer.")
    return OptimizerConfig(
        method="COBYLA",
        max_iterations=evaluation_budget,
        max_evaluations=evaluation_budget,
        starts=starts,
        seed=seed,
    )


def _validate_search_shape(mode: ProblemMode, *, layers: int, budget: int) -> None:
    """集中校验模式、QAOA 层数和演示评估预算。"""
    if mode not in _MODES:
        raise ValueError(f"unsupported Problem mode: {mode!r}")
    if not isinstance(layers, int) or isinstance(layers, bool) or layers < 1:
        raise ValueError("layers must be a positive integer.")
    if mode == "digital" and layers > 3:
        raise ValueError("Digital mode supports layers from 1 to 3.")
    if mode == "hybrid" and layers > 2:
        raise ValueError("Hybrid mode supports layers from 1 to 2.")
    if mode == "analog" and layers != 1:
        raise ValueError("Analog currently supports layers=1 only.")
    if not isinstance(budget, int) or isinstance(budget, bool) or not 1 <= budget <= 24:
        raise ValueError("parameter budget must be between 1 and 24.")


_MODES: tuple[ProblemMode, ...] = ("digital", "hybrid", "analog")
