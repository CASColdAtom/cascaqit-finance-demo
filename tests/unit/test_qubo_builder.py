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
    builder.add_linear("x", -0.4)
    builder.add_squared_equality({"x": 1.0, "y": 2.0}, rhs=2.0, penalty=3.5)
    problem = builder.build(problem_id="test.square")

    for bitstring in ("00", "01", "10", "11"):
        x, y = (int(bit) for bit in bitstring)
        expected = -0.4 * x + 3.5 * (x + 2 * y - 2) ** 2
        assert evaluate_qubo_bitstring(problem, bitstring) == pytest.approx(expected)


def test_quadratic_terms_are_normalized_and_accumulated() -> None:
    """验证反向变量对和同变量乘积分别被规范累加与线性化。"""
    builder = QuboBuilder(["a", "b"])
    builder.add_quadratic("b", "a", 1.25)
    builder.add_quadratic("a", "b", -0.25)

    problem = builder.build(problem_id="test.quadratic")

    assert problem.quadratic_terms == (("a", "b", 1.0),)
