"""通过 CASCAQit 统一 ProblemCompiler 分析、编译并执行金融场景。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

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


@dataclass(frozen=True)
class FinanceModeAdvisor:
    """同时依据编译器物理事实和金融项语义选择 Digital、Hybrid 或 Analog。"""

    def decide(
        self, definition: FinanceProblemDefinition, analysis: Any
    ) -> ModeDecision:
        """判断三种模式的可行性，并确保 Analog 部分确实承载业务项。"""
        plan = analysis.mapping_plan
        supported_analog_pairs = {
            tuple(sorted(candidate.targets))
            for candidate in plan.term_candidates
            if candidate.operator == "zz"
            and candidate.implementation == "analog_interaction"
            and candidate.status == "supported"
        }
        matched_pairs = tuple(
            sorted(set(definition.analog_business_pairs) & supported_analog_pairs)
        )

        physical = {mode: plan.feasibility_for(mode) for mode in _MODES}
        analog_business_pairs = set(definition.analog_business_pairs)
        analog_covers_business = bool(analog_business_pairs) and (
            analog_business_pairs <= supported_analog_pairs
        )
        analog_suitable = (
            physical["analog"].feasible
            and bool(physical["analog"].analog_term_ids)
            and not physical["analog"].digital_term_ids
            and analog_covers_business
        )
        hybrid_suitable = (
            physical["hybrid"].feasible
            and bool(matched_pairs)
            and bool(physical["hybrid"].analog_term_ids)
            and bool(physical["hybrid"].digital_term_ids)
        )

        # 只有 Analog 与 Digital 两部分都保留真实业务含义时才推荐 Hybrid。
        # 可完整模拟的图问题不应人为制造 Digital residual；以全局约束为主的问题
        # 也不能为了展示 Hybrid 而把普通罚项包装成 Analog 业务贡献。
        if definition.preferred_mode == "digital" and physical["digital"].feasible:
            recommended: ProblemMode = "digital"
            recommendation = "问题主体是稠密、全局或有方向的约束，使用 Digital。"
        elif definition.preferred_mode == "hybrid" and hybrid_suitable:
            recommended: ProblemMode = "hybrid"
            recommendation = "业务冲突项由原子相互作用承担，其余约束保留为数字项。"
        elif definition.preferred_mode == "analog" and analog_suitable:
            recommended: ProblemMode = "analog"
            recommendation = "完整业务图可由 AHS 表达，不需要 Digital residual。"
        elif hybrid_suitable:
            recommended = "hybrid"
            recommendation = "当前输入需要同时保留 Analog 业务项和 Digital residual。"
        elif analog_suitable:
            recommended = "analog"
            recommendation = "当前输入已完整适配 AHS，不再保留人工 Digital residual。"
        else:
            recommended = "digital"
            if definition.preferred_mode == "hybrid" and not matched_pairs:
                recommendation = (
                    "当前布局没有可追溯的 Analog 业务冲突项，使用 Digital。"
                )
            elif definition.preferred_mode == "hybrid":
                recommendation = (
                    "Hybrid 未同时保留有效的 Analog 业务项和 Digital residual，"
                    "使用 Digital。"
                )
            elif definition.preferred_mode == "analog":
                recommendation = "完整 AHS 映射不可行，使用 Digital 保留原问题。"
            else:
                recommendation = "问题主体是稠密、全局或有方向的约束，使用 Digital。"

        rows = tuple(
            self._row(
                mode=mode,
                definition=definition,
                feasibility=physical[mode],
                recommended=recommended,
                matched_pairs=matched_pairs,
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
    def _row(
        *,
        mode: ProblemMode,
        definition: FinanceProblemDefinition,
        feasibility: Any,
        recommended: ProblemMode,
        matched_pairs: tuple[tuple[str, str], ...],
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
            if not matched_pairs:
                reason = "没有可追溯到业务冲突的 Analog interaction。"
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
            diagnostic_codes=tuple(feasibility.diagnostic_codes),
            analog_business_pairs=matched_pairs if mode in {"hybrid", "analog"} else (),
            analog_term_count=len(feasibility.analog_term_ids),
            digital_term_count=len(feasibility.digital_term_ids),
        )


class ScenarioExecutor:
    """串联金融场景的验证、分析、编译、执行、解码和审计报告。"""

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
        """验证输入并生成不触发执行的 Problem 分析和模式建议。"""
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
        shots: int = 64,
        seed: int = 23,
        report_path: Path | None = None,
    ) -> FinanceExperimentResult:
        """按指定或推荐模式执行场景，并返回业务结果与完整审计证据。

        最佳采样候选若违反业务约束，展示层会回退到同次执行产生的经典基线，
        但两者都会保留在结果中，避免把回退结果误称为量子采样结果。
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
        compiled = self.compiler.compile(
            definition.problem,
            mode=selected_mode,
            algorithm="qaa" if selected_mode == "analog" else "qaoa",
            target=self.target,
        )
        points = tuple(parameter_sets or default_parameter_sets(selected_mode))
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
                "parameter_set_count": len(points),
                "displayed_source": (
                    "best_observed" if displayed is candidate else "classical_baseline"
                ),
                "optimality_claim": execution.optimality_claim,
            },
        )


def default_parameter_sets(mode: ProblemMode) -> tuple[dict[str, float], ...]:
    """返回适合现场演示的小规模确定性参数扫描，不依赖在线优化器。"""
    if mode == "analog":
        return (
            {"anneal_time": 0.4, "omega_max": 1.0},
            {"anneal_time": 0.7, "omega_max": 1.4},
        )
    return (
        {"gamma_0": 0.16, "beta_0": 0.24},
        {"gamma_0": 0.28, "beta_0": -0.18},
    )


_MODES: tuple[ProblemMode, ...] = ("digital", "hybrid", "analog")
