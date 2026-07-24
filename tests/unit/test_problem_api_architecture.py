"""金融 Problem API 架构中的模式选择和降级规则单元测试。"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from cascaqit import QUBOProblemIR

from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS
from cascaqit_finance_demo.domain.problem_api import (
    FinanceProblemDefinition,
    FinanceTermGroup,
)
from cascaqit_finance_demo.quantum.problem_executor import (
    FinanceModeAdvisor,
    ScenarioExecutor,
)


@pytest.mark.parametrize(
    ("case_id", "expected_mode"),
    [
        ("portfolio", "digital"),
        ("settlement", "hybrid"),
        ("fraud_routing", "hybrid"),
        ("collateral", "digital"),
        ("liquidity", "digital"),
        ("credit_limits", "digital"),
        ("derivatives", "analog"),
    ],
)
def test_default_scenario_mode_matrix(case_id: str, expected_mode: str) -> None:
    """验证七个默认场景的推荐模式与业务结构设计保持一致。"""
    scenario = PROBLEM_SCENARIOS[case_id]

    analysis = ScenarioExecutor().analyze(scenario, scenario.default_input())

    assert analysis.mode_decision.recommended_mode == expected_mode


def test_portfolio_recommends_digital_even_when_hybrid_compiles() -> None:
    """验证编译可行不等于业务适合，稠密投资组合仍推荐 Digital。"""
    scenario = PROBLEM_SCENARIOS["portfolio"]
    analysis = ScenarioExecutor().analyze(scenario, scenario.default_input())

    assert analysis.mode_decision.recommended_mode == "digital"
    assert analysis.mode_decision.for_mode("digital").compiler_feasible
    assert analysis.mode_decision.for_mode("analog").status == "unsuitable"


def test_settlement_recommends_hybrid_only_with_business_conflict_mapping() -> None:
    """验证交易冲突真实映射为 Analog 项后才允许推荐 Hybrid。"""
    scenario = PROBLEM_SCENARIOS["settlement"]
    analysis = ScenarioExecutor().analyze(scenario, scenario.default_input())

    hybrid = analysis.mode_decision.for_mode("hybrid")
    assert analysis.mode_decision.recommended_mode == "hybrid"
    assert hybrid.analog_business_pairs
    assert hybrid.analog_term_count > 0
    assert hybrid.digital_term_count > 0


def test_fraud_recommends_hybrid_for_shared_entity_conflicts() -> None:
    """验证共享实体冲突与 Digital 席位约束并存时推荐 Hybrid。"""
    scenario = PROBLEM_SCENARIOS["fraud_routing"]
    analysis = ScenarioExecutor().analyze(scenario, scenario.default_input())

    assert analysis.mode_decision.recommended_mode == "hybrid"
    assert analysis.mode_decision.for_mode("hybrid").analog_business_pairs


def test_fraud_falls_back_to_digital_when_parallel_conflicts_disappear() -> None:
    """验证实体冲突消失后 Hybrid 失去业务意义并回退 Digital。"""
    scenario = PROBLEM_SCENARIOS["fraud_routing"]
    case_input = replace(scenario.default_input(), entity_parallel_cap=2)

    analysis = ScenarioExecutor().analyze(scenario, case_input)

    assert analysis.mode_decision.recommended_mode == "digital"
    assert analysis.mode_decision.for_mode("hybrid").status == "unsuitable"


def test_executor_runs_real_problem_result_and_rejects_unsuitable_mode() -> None:
    """验证执行器拒绝业务不适配模式，而非只依据编译可行性运行。"""
    scenario = PROBLEM_SCENARIOS["portfolio"]
    result = ScenarioExecutor().run(
        scenario,
        scenario.default_input(),
        shots=16,
        seed=11,
    )

    assert result.mode == "digital"
    assert result.execution.mode == "digital"
    assert sum(result.execution.result.counts.values()) == 16
    assert result.business_candidate.bitstring
    assert result.baseline_solution is not None

    with pytest.raises(ValueError, match="Target|unavailable"):
        ScenarioExecutor().run(
            scenario,
            scenario.default_input(),
            mode="analog",
            shots=8,
        )


def test_hybrid_without_digital_residual_uses_complete_analog_path() -> None:
    """验证没有 Digital residual 的图问题直接使用完整 Analog 路径。"""
    definition = _definition(preferred_mode="hybrid")
    analysis = _analysis(
        analog_ids=("pair.ab",),
        hybrid_analog_ids=("pair.ab",),
        hybrid_digital_ids=(),
    )

    decision = FinanceModeAdvisor().decide(definition, analysis)

    assert decision.recommended_mode == "analog"
    assert decision.for_mode("hybrid").status == "unsuitable"
    assert "Digital residual" in decision.for_mode("hybrid").reason


def test_complete_business_graph_prefers_analog_without_artificial_residual() -> None:
    """验证完整业务图不会为制造 Hybrid 展示而添加人工数字残差。"""
    definition = _definition(preferred_mode="analog")
    analysis = _analysis(
        analog_ids=("pair.ab",),
        hybrid_analog_ids=("pair.ab",),
        hybrid_digital_ids=("linear.a",),
    )

    decision = FinanceModeAdvisor().decide(definition, analysis)

    assert decision.recommended_mode == "analog"
    assert decision.for_mode("hybrid").status == "comparable"


def test_analog_preference_can_move_to_hybrid_when_residual_is_required() -> None:
    """验证存在不可模拟的真实剩余项时，Analog 首选可合理转为 Hybrid。"""
    definition = _definition(preferred_mode="analog")
    analysis = _analysis(
        analog_ids=(),
        analog_feasible=False,
        hybrid_analog_ids=("pair.ab",),
        hybrid_digital_ids=("linear.a",),
    )

    decision = FinanceModeAdvisor().decide(definition, analysis)

    assert decision.recommended_mode == "hybrid"
    assert decision.for_mode("hybrid").status == "recommended"


def _definition(*, preferred_mode: str) -> FinanceProblemDefinition:
    """构造最小测试 Problem 定义，精确控制冲突项和首选模式。"""
    problem = QUBOProblemIR.from_terms(
        problem_id="finance.mode-policy",
        variables=("a", "b"),
        linear_terms={"a": -1.0, "b": -1.0},
        quadratic_terms={("a", "b"): 2.0},
    )
    return FinanceProblemDefinition(
        case_id="mode-policy",
        title="模式策略",
        problem_kind="qubo",
        problem=problem,
        preferred_mode=preferred_mode,  # type: ignore[arg-type]
        business_variables=("a", "b"),
        term_groups=(
            FinanceTermGroup(
                "conflict",
                "业务冲突",
                "pairwise_conflict",
                pairs=(("a", "b"),),
            ),
        ),
    )


def _analysis(
    *,
    analog_ids: tuple[str, ...],
    analog_feasible: bool = True,
    hybrid_analog_ids: tuple[str, ...],
    hybrid_digital_ids: tuple[str, ...],
) -> SimpleNamespace:
    """构造模式顾问所需的最小编译分析替身，隔离编译器实现细节。"""
    feasibility = {
        "digital": SimpleNamespace(
            feasible=True,
            diagnostic_codes=(),
            analog_term_ids=(),
            digital_term_ids=("linear.a", "linear.b", "pair.ab"),
        ),
        "hybrid": SimpleNamespace(
            feasible=True,
            diagnostic_codes=(),
            analog_term_ids=hybrid_analog_ids,
            digital_term_ids=hybrid_digital_ids,
        ),
        "analog": SimpleNamespace(
            feasible=analog_feasible,
            diagnostic_codes=() if analog_feasible else ("ANALOG_INCOMPLETE",),
            analog_term_ids=analog_ids,
            digital_term_ids=(),
        ),
    }
    mapping_plan = SimpleNamespace(
        term_candidates=(
            SimpleNamespace(
                operator="zz",
                implementation="analog_interaction",
                status="supported",
                targets=("a", "b"),
            ),
        ),
        feasibility_for=feasibility.__getitem__,
    )
    return SimpleNamespace(mapping_plan=mapping_plan)
