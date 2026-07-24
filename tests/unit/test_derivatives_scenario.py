"""衍生品经典参考定价与 Analog 风险网格单元测试。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS
from cascaqit_finance_demo.quantum.problem_executor import ScenarioExecutor


@pytest.mark.parametrize(
    "product",
    ["european_call", "european_put", "asian_call", "up_and_out_call"],
)
def test_reference_pricing_is_positive_and_deterministic(product: str) -> None:
    """验证四类产品价格为正，并在固定输入和随机种子下可复现。"""
    scenario = PROBLEM_SCENARIOS["derivatives"]
    case_input = replace(scenario.default_input(), product=product)

    first = scenario.price(case_input)
    second = scenario.price(case_input)

    assert first == second
    assert first.reference_price >= 0.0
    assert first.method in {"Black-Scholes", "固定 seed Monte Carlo"}


def test_risk_grid_recommends_complete_analog_problem() -> None:
    """验证完整风险图可由 AHS 表达时推荐 Analog 而非人工 Hybrid。"""
    scenario = PROBLEM_SCENARIOS["derivatives"]
    analysis = ScenarioExecutor().analyze(scenario, scenario.default_input())

    assert analysis.mode_decision.recommended_mode == "analog"
    analog = analysis.mode_decision.for_mode("analog")
    assert analog.compiler_feasible
    assert analog.digital_term_count == 0
    assert len(analysis.definition.problem.nodes) == 9
    assert analysis.definition.metadata["counts_feed_pricing"] is False


def test_analog_risk_grid_runs_without_changing_price() -> None:
    """验证 Analog 情景选择不会篡改独立经典定价链路的价格。"""
    scenario = PROBLEM_SCENARIOS["derivatives"]
    case_input = scenario.default_input()
    price_before = scenario.price(case_input)
    result = ScenarioExecutor().run(
        scenario,
        case_input,
        mode="analog",
        parameter_sets=({"anneal_time": 0.4, "omega_max": 1.0},),
        shots=8,
        seed=17,
    )
    price_after = scenario.price(case_input)

    assert result.mode == "analog"
    assert sum(result.execution.result.counts.values()) == 8
    assert price_before == price_after
    assert "reference_price" not in result.execution.to_dict()
