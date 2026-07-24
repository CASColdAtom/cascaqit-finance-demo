"""投资组合输入、约束、市场编辑和 QUBO 映射单元测试。"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from cascaqit.problems import evaluate_qubo_bitstring

from cascaqit_finance_demo.cases.portfolio import PortfolioCase


def test_default_portfolio_builds_a_bounded_feasible_problem() -> None:
    """验证默认市场可行且 QUBO 变量规模处于演示边界内。"""
    case = PortfolioCase()
    case_input = case.default_input()

    assert case.validate(case_input) == ()
    points = case.exact_business_points(case_input)
    problem = case.build_problem(case_input)

    assert len(points) == 64
    assert len(problem.variables) == 12
    assert problem.validate() == ()
    assert problem.metadata["case_id"] == "portfolio"
    assert problem.metadata["base_penalty"] > problem.metadata["objective_bound"]
    assert all(len(point.asset_ids) == 4 for point in points)


def test_lowest_qubo_state_decodes_to_a_feasible_business_portfolio() -> None:
    """验证最低 QUBO 能量状态能还原为通过业务约束的资产组合。"""
    case = PortfolioCase()
    case_input = case.default_input()
    problem = case.build_problem(case_input)
    states = (
        format(value, f"0{len(problem.variables)}b")
        for value in range(2 ** len(problem.variables))
    )
    bitstring = min(states, key=lambda state: evaluate_qubo_bitstring(problem, state))

    decoded = case.decode(
        case_input,
        problem,
        SimpleNamespace(bitstring=bitstring),
    )

    assert decoded.feasible is True
    assert len(decoded.selected_asset_ids) == case_input.selected_count
    assert all(check.passed for check in decoded.checks)


def test_validation_reports_an_impossible_sector_constraint() -> None:
    """验证不可能满足的行业集中度组合在构建 Problem 前被明确拒绝。"""
    case = PortfolioCase()
    case_input = replace(case.default_input(), sector_cap=1, selected_count=8)

    issues = case.validate(case_input)

    assert {issue.code for issue in issues} == {"NO_FEASIBLE_PORTFOLIO"}


def test_editable_market_data_preserves_correlations() -> None:
    """验证编辑收益和波动率时保持原资产相关系数矩阵不变。"""
    case = PortfolioCase()
    case_input = case.default_input()
    returns = tuple(asset.expected_return + 0.01 for asset in case_input.assets)
    volatilities = tuple(asset.volatility * 1.1 for asset in case_input.assets)

    updated = case.replace_market_data(
        case_input,
        expected_returns=returns,
        volatilities=volatilities,
    )

    assert tuple(asset.expected_return for asset in updated.assets) == returns
    assert tuple(asset.volatility for asset in updated.assets) == volatilities
    assert case.validate(updated) == ()
