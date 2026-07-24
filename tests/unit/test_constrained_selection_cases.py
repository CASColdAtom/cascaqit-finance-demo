"""三个 Digital 受约束选择场景的业务与 Problem API 单元测试。"""

from __future__ import annotations

import pytest

from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS
from cascaqit_finance_demo.quantum.problem_executor import ScenarioExecutor


@pytest.mark.parametrize("case_id", ["collateral", "liquidity", "credit_limits"])
def test_default_selection_case_has_feasible_baseline_and_digital_policy(
    case_id: str,
) -> None:
    """验证默认输入存在经典可行基线，且模式顾问保持 Digital 策略。"""
    scenario = PROBLEM_SCENARIOS[case_id]
    case_input = scenario.default_input()
    definition = scenario.build_definition(case_input)
    analysis = ScenarioExecutor().analyze(scenario, case_input)
    feasible = scenario.exact_business_points(case_input)

    assert definition.problem.metadata["case_id"] == case_id
    assert definition.business_variables
    assert feasible
    assert feasible[0].feasible
    assert analysis.mode_decision.recommended_mode == "digital"


def test_collateral_selects_one_candidate_for_each_margin_requirement() -> None:
    """验证抵押品方案对每类保证金需求选择规定数量的候选。"""
    scenario = PROBLEM_SCENARIOS["collateral"]
    solution = scenario.exact_business_points(scenario.default_input())[0]

    assert solution.group_counts == {"BILAT-1": 1, "BILAT-2": 1, "CCP": 1}
    assert len(solution.selected_item_ids) == 3


def test_liquidity_solution_meets_floor_and_dependency() -> None:
    """验证流动性方案同时满足最低覆盖单位和融资动作前置依赖。"""
    scenario = PROBLEM_SCENARIOS["liquidity"]
    solution = scenario.exact_business_points(scenario.default_input())[0]

    assert solution.total_units >= 12
    assert len(solution.selected_item_ids) == 4
    assert all(check.passed for check in solution.checks)


def test_credit_solution_respects_capital_and_industry_caps() -> None:
    """验证授信配置不突破资本使用上限和单行业集中度上限。"""
    scenario = PROBLEM_SCENARIOS["credit_limits"]
    solution = scenario.exact_business_points(scenario.default_input())[0]

    assert solution.total_units <= 11
    assert max(solution.group_counts.values()) <= 2
