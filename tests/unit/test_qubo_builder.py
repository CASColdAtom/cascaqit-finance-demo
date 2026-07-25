"""金融 QUBO 确定性构建工具的数学单元测试。"""

from __future__ import annotations

import pytest
from cascaqit.problems import evaluate_qubo_bitstring

from cascaqit_finance_demo.domain.qubo_builder import (
    QuboBuilder,
    bounded_binary_weights,
)


@pytest.mark.parametrize(
    ("maximum", "weights"),
    [(0, ()), (1, (1,)), (2, (1, 1)), (3, (1, 2)), (6, (1, 2, 3))],
)
def test_bounded_binary_weights_stop_at_requested_maximum(
    maximum: int, weights: tuple[int, ...]
) -> None:
    """验证有界二进制权重的可表示范围恰好止于业务上限。"""
    assert bounded_binary_weights(maximum) == weights
    assert sum(weights) == maximum


def test_squared_equality_matches_direct_binary_formula() -> None:
    """验证平方等式展开后的 QUBO 能量与直接代入公式完全一致。"""
    builder = QuboBuilder(["x", "y"])
    builder.add_linear(
        "x",
        -0.4,
        contribution_id="objective:x",
        group_id="objective",
        source_rule="expected_return",
        role="objective",
    )
    builder.add_squared_equality(
        {"x": 1.0, "y": 2.0},
        rhs=2.0,
        penalty=3.5,
        contribution_id_prefix="capacity",
        group_id="constraints",
        source_rule="capacity_equality",
    )
    problem = builder.build(problem_id="test.square")

    for bitstring in ("00", "01", "10", "11"):
        x, y = (int(bit) for bit in bitstring)
        expected = -0.4 * x + 3.5 * (x + 2 * y - 2) ** 2
        assert evaluate_qubo_bitstring(problem, bitstring) == pytest.approx(expected)


def test_quadratic_terms_are_normalized_and_accumulated() -> None:
    """验证反向变量对和同变量乘积分别被规范累加与线性化。"""
    builder = QuboBuilder(["a", "b"])
    builder.add_quadratic(
        "b",
        "a",
        1.25,
        contribution_id="conflict:first",
        group_id="conflicts",
        source_rule="pairwise_conflict",
        role="constraint",
    )
    builder.add_quadratic(
        "a",
        "b",
        -0.25,
        contribution_id="conflict:second",
        group_id="conflicts",
        source_rule="conflict_adjustment",
        role="constraint",
    )

    problem = builder.build(problem_id="test.quadratic")

    assert problem.quadratic_terms == (("a", "b", 1.0),)


def test_builder_records_expanded_contributions_and_preserves_conservation() -> None:
    """验证平方罚项每个展开系数都有稳定来源，且聚合值等于最终 QUBO。"""
    builder = QuboBuilder(["x", "y"])
    builder.add_linear(
        "x",
        -2.0,
        contribution_id="value:x",
        group_id="value",
        source_rule="business_value",
        role="objective",
    )
    builder.add_squared_equality(
        {"x": 1.0, "y": 2.0},
        rhs=2.0,
        penalty=3.0,
        contribution_id_prefix="limit:usd",
        group_id="liquidity",
        source_rule="currency_liquidity_limit",
    )

    problem = builder.build(problem_id="test.ledger")
    contributions = builder.contributions

    assert [item.contribution_id for item in contributions] == [
        "value:x",
        "limit:usd:linear:x",
        "limit:usd:linear:y",
        "limit:usd:quadratic:x:y",
        "limit:usd:offset",
    ]
    assert sum(
        item.coefficient
        for item in contributions
        if item.canonical_term_id == "linear.x"
    ) == pytest.approx(dict(problem.linear_terms)["x"])
    assert sum(
        item.coefficient
        for item in contributions
        if item.canonical_term_id == "quadratic.x.y"
    ) == pytest.approx(problem.quadratic_terms[0][2])
    assert sum(
        item.coefficient for item in contributions if item.canonical_term_id == "offset"
    ) == pytest.approx(problem.offset)
    assert len(problem.metadata["coefficient_contributions"]) == len(contributions)


def test_builder_rejects_duplicate_contribution_ids() -> None:
    """验证重复来源 ID 会立即失败，避免两条业务规则在账本中互相覆盖。"""
    builder = QuboBuilder(["x", "y"])
    builder.add_linear(
        "x",
        1.0,
        contribution_id="rule:duplicate",
        group_id="objective",
        source_rule="first_rule",
        role="objective",
    )

    with pytest.raises(ValueError, match="contribution_id must be unique"):
        builder.add_quadratic(
            "x",
            "y",
            2.0,
            contribution_id="rule:duplicate",
            group_id="constraints",
            source_rule="second_rule",
            role="constraint",
        )
