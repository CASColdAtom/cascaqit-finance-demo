"""面向金融场景的轻量确定性 QUBO 系数构建器。"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from cascaqit import QUBOProblemIR


def bounded_binary_weights(max_value: int) -> tuple[int, ...]:
    """生成最大可表示值恰为 ``max_value`` 的有界二进制权重。

    最后一位允许小于标准 2 的幂，从而避免松弛变量表示出业务上不存在的容量。
    """
    if not isinstance(max_value, int) or isinstance(max_value, bool):
        raise TypeError("max_value must be an integer.")
    if max_value < 0:
        raise ValueError("max_value must be non-negative.")
    if max_value == 0:
        return ()
    weights: list[int] = []
    represented = 0
    next_weight = 1
    while represented < max_value:
        weight = min(next_weight, max_value - represented)
        weights.append(weight)
        represented += weight
        next_weight *= 2
    return tuple(weights)


class QuboBuilder:
    """累加 QUBO 线性项和二次项，同时保持确定性的变量集合与项顺序。"""

    def __init__(self, variables: tuple[str, ...] | list[str] = ()) -> None:
        """初始化构建器，并提前登记可选的业务变量。"""
        self._variables: dict[str, None] = {}
        self._linear: dict[str, float] = {}
        self._quadratic: dict[tuple[str, str], float] = {}
        self._offset = 0.0
        for variable in variables:
            self.add_variable(variable)

    @property
    def variables(self) -> tuple[str, ...]:
        """返回按名称排序的全部变量，确保跨进程构建结果一致。"""
        return tuple(sorted(self._variables))

    @property
    def linear_terms(self) -> dict[str, float]:
        """返回线性系数副本，防止调用方修改内部累加状态。"""
        return dict(self._linear)

    @property
    def quadratic_terms(self) -> dict[tuple[str, str], float]:
        """返回按规范变量对存储的二次系数副本。"""
        return dict(self._quadratic)

    @property
    def offset(self) -> float:
        """返回当前与变量无关的常数偏移。"""
        return self._offset

    @property
    def absolute_coefficient_sum(self) -> float:
        """返回目标系数绝对值上界，用于把硬约束罚项放到目标收益之上。"""
        return sum(abs(value) for value in self._linear.values()) + sum(
            abs(value) for value in self._quadratic.values()
        )

    def add_variable(self, name: str) -> None:
        """登记一个无首尾空格的非空变量名；重复登记不会产生副本。"""
        if not isinstance(name, str) or not name.strip() or name != name.strip():
            raise ValueError("variable names must be non-empty trimmed strings.")
        self._variables[name] = None

    def add_linear(self, variable: str, coefficient: float) -> None:
        """累加变量的一次系数，并拒绝无穷或非数值系数。"""
        self.add_variable(variable)
        value = _finite(coefficient, "coefficient")
        self._linear[variable] = self._linear.get(variable, 0.0) + value

    def add_quadratic(self, left: str, right: str, coefficient: float) -> None:
        """累加规范变量对的二次系数；同变量乘积按二元恒等式转为线性项。"""
        self.add_variable(left)
        self.add_variable(right)
        if left == right:
            self.add_linear(left, coefficient)
            return
        key = tuple(sorted((left, right)))
        value = _finite(coefficient, "coefficient")
        self._quadratic[key] = self._quadratic.get(key, 0.0) + value

    def add_squared_equality(
        self,
        coefficients: Mapping[str, float],
        *,
        rhs: float,
        penalty: float,
    ) -> None:
        """加入二元变量等式罚项 ``penalty * (sum(a_i*x_i) - rhs)^2``。"""
        if not coefficients:
            raise ValueError("coefficients must not be empty.")
        normalized = {
            variable: _finite(value, f"coefficient[{variable}]")
            for variable, value in coefficients.items()
        }
        rhs_value = _finite(rhs, "rhs")
        penalty_value = _finite(penalty, "penalty")
        if penalty_value <= 0.0:
            raise ValueError("penalty must be positive.")

        # 二元变量满足 x^2 == x，因此平方展开的对角项合并到线性系数；
        # 非对角交叉项带有系数 2，并按变量名排序后累加。
        items = tuple(sorted(normalized.items()))
        for variable, weight in items:
            self.add_linear(
                variable,
                penalty_value * (weight * weight - 2.0 * rhs_value * weight),
            )
        for index, (left, left_weight) in enumerate(items):
            for right, right_weight in items[index + 1 :]:
                self.add_quadratic(
                    left,
                    right,
                    2.0 * penalty_value * left_weight * right_weight,
                )
        self._offset += penalty_value * rhs_value * rhs_value

    def build(
        self,
        *,
        problem_id: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> QUBOProblemIR:
        """移除数值噪声项并构造不可变的 CASCAQit QUBO Problem IR。"""
        return QUBOProblemIR.from_terms(
            problem_id=problem_id,
            variables=self.variables,
            linear_terms=_without_zeros(self._linear),
            quadratic_terms=_without_zeros(self._quadratic),
            offset=self._offset,
            metadata={} if metadata is None else dict(metadata),
        )


def _finite(value: float, field: str) -> float:
    """把数值统一转为浮点数，并阻止 NaN/Inf 污染后续能量计算。"""
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{field} must be finite.")
    return converted


def _without_zeros(terms: Mapping[Any, float]) -> dict[Any, float]:
    """删除浮点误差尺度内的零系数，减少无意义的编译项。"""
    return {key: value for key, value in terms.items() if abs(value) > 1e-14}
