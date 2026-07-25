"""三个受约束选择场景的真实 Digital Problem 执行测试。"""

from __future__ import annotations

import pytest

from cascaqit_finance_demo.api.catalog import SCENARIO_SPECS, preset_input
from cascaqit_finance_demo.api.presenters import execution_payload
from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS
from cascaqit_finance_demo.quantum.problem_executor import ScenarioExecutor


@pytest.mark.parametrize("case_id", ["collateral", "liquidity", "credit_limits"])
def test_new_scenario_runs_real_digital_problem(case_id: str) -> None:
    """验证每个新增场景均经过编译、采样和业务解码，而非静态演示数据。"""
    scenario = PROBLEM_SCENARIOS[case_id]
    result = ScenarioExecutor().run(
        scenario,
        scenario.default_input(),
        mode="digital",
        parameter_sets=({"gamma_0": 0.16, "beta_0": 0.24},),
        shots=8,
        seed=19,
    )

    assert result.execution.mode == "digital"
    assert sum(result.execution.result.counts.values()) == 8
    assert result.baseline_solution is not None
    assert result.displayed_solution.feasible
    assert result.execution.optimality_claim == "not_claimed"

    payload = execution_payload(case_id, scenario.default_input(), result)
    chart = payload["business"]["chart"]
    assert chart["title"]
    assert chart["xLabel"]
    assert chart["yLabel"]
    if case_id == "liquidity":
        assert chart["kind"] == "funding-timeline"
        assert {point["x"] for point in chart["points"]} == {
            570.0,
            600.0,
            630.0,
            660.0,
            810.0,
            840.0,
            870.0,
            900.0,
        }
    if case_id == "collateral":
        assert chart["points"][0]["label"] != chart["points"][0]["id"]


@pytest.mark.parametrize(
    ("case_id", "preset"),
    [
        ("collateral", "haircut"),
        ("liquidity", "base"),
        ("credit_limits", "base"),
    ],
)
def test_recommended_execution_profile_returns_sampled_feasible_candidate(
    case_id: str,
    preset: str,
) -> None:
    """验证关键推荐配置展示真实采样可行解，而不是经典回退。"""
    scenario = PROBLEM_SCENARIOS[case_id]
    case_input = preset_input(case_id, preset)
    profile = SCENARIO_SPECS[case_id].recommended_execution

    result = ScenarioExecutor().run(
        scenario,
        case_input,
        mode="digital",
        shots=profile.shots,
        seed=profile.seed,
        layers=profile.layers,
        search_strategy=profile.search_strategy,
        parameter_budget=profile.parameter_budget,
    )

    assert result.business_candidate.feasible is True
    assert result.metadata["displayed_source"] == "best_observed"
