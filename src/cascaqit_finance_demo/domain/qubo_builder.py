"""面向金融场景的轻量确定性 QUBO 系数构建器。

QUBO（Quadratic Unconstrained Binary Optimization，二次无约束二元优化）写成
``E(x) = offset + sum(a_i*x_i) + sum(b_ij*x_i*x_j)``，其中 ``x_i`` 只能取 0 或 1，
求解目标是最小化 ``E``。业务约束不是被删除，而是展开为能量罚项后并入目标。

本模块只负责可靠地累加系数，不决定业务目标或罚项大小。变量统一按名称排序、
变量对统一规范化，保证相同输入跨进程生成相同 Problem IR 和位串顺序。
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from cascaqit import QUBOProblemIR

from cascaqit_finance_demo.domain.problem_api import (
    CoefficientRole,
    FinanceCoefficientContribution,
)


def bounded_binary_weights(max_value: int) -> tuple[int, ...]:
    """生成最大可表示值恰为 ``max_value`` 的有界二进制权重。

    例如 ``max_value=6`` 返回 ``(1, 2, 3)``，三位可组合表示 0..6。最后一位
    允许小于标准 2 的幂，从而避免普通 ``(1, 2, 4)`` 额外表示出 7，减少无效
    松弛状态进入采样空间。
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
    """累加 QUBO 线性项和二次项，同时保持确定性的变量集合与项顺序。

    多次加入同一项会进行系数求和；``x_i*x_i`` 根据二元恒等式
    ``x_i^2 = x_i`` 自动并入线性项。构建器允许业务变量和松弛变量分阶段登记。
    """

    def __init__(self, variables: tuple[str, ...] | list[str] = ()) -> None:
        """初始化构建器，并提前登记可选的业务变量。"""
        self._variables: dict[str, None] = {}
        self._linear: dict[str, float] = {}
        self._quadratic: dict[tuple[str, str], float] = {}
        self._offset = 0.0
        self._contributions: list[FinanceCoefficientContribution] = []
        self._contribution_ids: set[str] = set()
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
    def contributions(self) -> tuple[FinanceCoefficientContribution, ...]:
        """返回按建模发生顺序排列的不可变逐系数来源账本。"""
        return tuple(self._contributions)

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

    def add_linear(
        self,
        variable: str,
        coefficient: float,
        *,
        contribution_id: str,
        group_id: str,
        source_rule: str,
        role: CoefficientRole,
    ) -> None:
        """累加变量的一次系数，并拒绝无穷或非数值系数。"""
        self.add_variable(variable)
        value = _finite(coefficient, "coefficient")
        self._linear[variable] = self._linear.get(variable, 0.0) + value
        self._record_contribution(
            contribution_id=contribution_id,
            group_id=group_id,
            source_rule=source_rule,
            term_kind="linear",
            targets=(variable,),
            coefficient=value,
            role=role,
        )

    def add_quadratic(
        self,
        left: str,
        right: str,
        coefficient: float,
        *,
        contribution_id: str,
        group_id: str,
        source_rule: str,
        role: CoefficientRole,
    ) -> None:
        """累加规范变量对的二次系数；同变量乘积按二元恒等式转为线性项。"""
        self.add_variable(left)
        self.add_variable(right)
        value = _finite(coefficient, "coefficient")
        if left == right:
            self._linear[left] = self._linear.get(left, 0.0) + value
            self._record_contribution(
                contribution_id=contribution_id,
                group_id=group_id,
                source_rule=source_rule,
                term_kind="linear",
                targets=(left,),
                coefficient=value,
                role=role,
            )
            return
        key = tuple(sorted((left, right)))
        self._quadratic[key] = self._quadratic.get(key, 0.0) + value
        self._record_contribution(
            contribution_id=contribution_id,
            group_id=group_id,
            source_rule=source_rule,
            term_kind="quadratic",
            targets=key,
            coefficient=value,
            role=role,
        )

    def add_squared_equality(
        self,
        coefficients: Mapping[str, float],
        *,
        rhs: float,
        penalty: float,
        contribution_id_prefix: str,
        group_id: str,
        source_rule: str,
        role: CoefficientRole = "constraint",
    ) -> None:
        """加入二元变量等式罚项 ``P * (sum(a_i*x_i) - rhs)^2``。

        平方项只在等式满足时为零，偏离越大罚能越高。调用方可以通过给 slack
        变量正系数编码上限，或给 slack 变量负系数编码下限。``P`` 必须由场景
        根据无约束目标尺度选择；本方法只要求它为正数。
        """
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

        # 展开 P*(sum(a_i*x_i)-rhs)^2 后：
        #   线性项为 P*(a_i^2 - 2*rhs*a_i)*x_i；
        #   交叉项为 2*P*a_i*a_j*x_i*x_j；
        #   常数项为 P*rhs^2。
        # 二元变量满足 x_i^2=x_i，所以平方对角项仍是线性项。
        items = tuple(sorted(normalized.items()))
        for variable, weight in items:
            self.add_linear(
                variable,
                penalty_value * (weight * weight - 2.0 * rhs_value * weight),
                contribution_id=f"{contribution_id_prefix}:linear:{variable}",
                group_id=group_id,
                source_rule=source_rule,
                role=role,
            )
        for index, (left, left_weight) in enumerate(items):
            for right, right_weight in items[index + 1 :]:
                self.add_quadratic(
                    left,
                    right,
                    2.0 * penalty_value * left_weight * right_weight,
                    contribution_id=(
                        f"{contribution_id_prefix}:quadratic:{left}:{right}"
                    ),
                    group_id=group_id,
                    source_rule=source_rule,
                    role=role,
                )
        offset = penalty_value * rhs_value * rhs_value
        self._offset += offset
        self._record_contribution(
            contribution_id=f"{contribution_id_prefix}:offset",
            group_id=group_id,
            source_rule=source_rule,
            term_kind="offset",
            targets=(),
            coefficient=offset,
            role=role,
        )

    def build(
        self,
        *,
        problem_id: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> QUBOProblemIR:
        """移除数值噪声项并构造不可变的 CASCAQit QUBO Problem IR。"""
        resolved_metadata = {} if metadata is None else dict(metadata)
        resolved_metadata["coefficient_contributions"] = [
            asdict(item) for item in self._contributions
        ]
        return QUBOProblemIR.from_terms(
            problem_id=problem_id,
            variables=self.variables,
            linear_terms=_without_zeros(self._linear),
            quadratic_terms=_without_zeros(self._quadratic),
            offset=self._offset,
            metadata=resolved_metadata,
        )

    def _record_contribution(
        self,
        *,
        contribution_id: str,
        group_id: str,
        source_rule: str,
        term_kind: str,
        targets: tuple[str, ...],
        coefficient: float,
        role: CoefficientRole,
    ) -> None:
        """登记一条来源记录，并在重复 ID 破坏审计唯一性时立即失败。"""
        if contribution_id in self._contribution_ids:
            raise ValueError("contribution_id must be unique within one QUBO.")
        contribution = FinanceCoefficientContribution(
            contribution_id=contribution_id,
            group_id=group_id,
            source_rule=source_rule,
            term_kind=term_kind,  # type: ignore[arg-type]
            targets=targets,
            coefficient=coefficient,
            role=role,
        )
        self._contributions.append(contribution)
        self._contribution_ids.add(contribution_id)


def _finite(value: float, field: str) -> float:
    """把数值统一转为浮点数，并阻止 NaN/Inf 污染后续能量计算。"""
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{field} must be finite.")
    return converted


def _without_zeros(terms: Mapping[Any, float]) -> dict[Any, float]:
    """删除浮点误差尺度内的零系数，减少无意义的编译项。"""
    return {key: value for key, value in terms.items() if abs(value) > 1e-14}
