"""交易结算业务约束和 QUBO 映射单元测试。"""

from __future__ import annotations

from cascaqit_finance_demo.cases.settlement import SettlementCase
from cascaqit_finance_demo.domain.models import LiquidityLimit, SettlementInput


def test_default_settlement_problem_stays_within_demo_limit() -> None:
    """验证默认结算问题规模受控，并存在多个可行批次用于比较。"""
    case = SettlementCase()
    case_input = case.default_input()

    problem = case.build_problem(case_input)
    feasible = case.exact_business_points(case_input)

    assert len(problem.variables) == 16
    assert problem.metadata["batch_cap_encoding"] == "implied_by_liquidity_limits"
    assert len(feasible) > 1
    assert all(solution.feasible for solution in feasible)
    assert feasible[0].settled_notional_m > 0.0


def test_settlement_decoder_rechecks_all_business_constraints() -> None:
    """验证解码器从原始交易重新检查流动性、依赖、冲突和批量上限。"""
    case = SettlementCase()
    case_input = case.default_input()

    missing_dependency = case.decode_trade_selection(
        case_input,
        (0, 1, 0, 0, 0, 0, 0, 0, 0, 0),
    )
    conflict = case.decode_trade_selection(
        case_input,
        (1, 0, 0, 0, 0, 0, 1, 0, 0, 0),
    )
    over_limit = case.decode_trade_selection(
        case_input,
        (1, 0, 0, 1, 0, 0, 1, 0, 0, 0),
    )

    checks = {check.name: check for check in missing_dependency.checks}
    assert missing_dependency.feasible is False
    assert checks["dependencies"].passed is False
    checks = {check.name: check for check in conflict.checks}
    assert conflict.feasible is False
    assert checks["conflicts"].passed is False
    checks = {check.name: check for check in over_limit.checks}
    assert over_limit.feasible is False
    assert checks["liquidity_limits"].passed is False


def test_constraint_set_that_exceeds_variable_budget_is_rejected() -> None:
    """验证松弛变量导致规模超过预算时，在编译前返回明确错误。"""
    case = SettlementCase()
    default = case.default_input()
    case_input = SettlementInput(
        instructions=default.instructions,
        liquidity_limits=(
            LiquidityLimit("CNY", 8),
            LiquidityLimit("USD", 2),
            LiquidityLimit("HKD", 2),
        ),
    )

    issues = case.validate(case_input)

    assert any(issue.code == "QUBO_VARIABLE_LIMIT" for issue in issues)
