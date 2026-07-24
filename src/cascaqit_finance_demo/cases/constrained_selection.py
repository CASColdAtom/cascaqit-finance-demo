"""抵押品、流动性和授信三个 Digital 场景共用的受约束选择模型。"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from cascaqit import QUBOProblemIR

from cascaqit_finance_demo.domain.models import CaseIssue, ConstraintCheck
from cascaqit_finance_demo.domain.problem_api import (
    FinanceProblemDefinition,
    FinanceTermGroup,
)
from cascaqit_finance_demo.domain.qubo_builder import (
    QuboBuilder,
    bounded_binary_weights,
)


@dataclass(frozen=True)
class SelectionItem:
    """一个可选业务动作，包含分组、价值、成本和离散资源用量。"""

    item_id: str
    label: str
    group: str
    value: float
    cost: float
    units: int
    detail: str


@dataclass(frozen=True)
class SelectionInput:
    """通用选择 QUBO 可理解的规范输入，覆盖数量、分组、资源和关系约束。"""

    items: tuple[SelectionItem, ...]
    selected_count: int | None = None
    group_exact: Mapping[str, int] = field(default_factory=dict)
    group_cap: int | None = None
    maximum_units: int | None = None
    minimum_units: int | None = None
    conflicts: tuple[tuple[str, str], ...] = ()
    dependencies: tuple[tuple[str, str], ...] = ()
    value_weight: float = 0.65
    cost_weight: float = 0.35
    penalty_multiplier: float = 2.2


@dataclass(frozen=True)
class SelectionSolution:
    """从源输入重新计算业务约束后的选择结果。"""

    bitstring: str
    selected_item_ids: tuple[str, ...]
    total_value: float
    total_cost: float
    total_units: int
    group_counts: Mapping[str, int]
    feasible: bool
    checks: tuple[ConstraintCheck, ...]
    exclusion_reasons: Mapping[str, str] = field(default_factory=dict)


class ConstrainedSelectionCase:
    """抵押品、流动性和授信场景复用的 QUBO 构建与解码基类。"""

    case_id = "selection"
    title = "受约束选择"
    item_kind = "项目"

    def default_input(self) -> SelectionInput:
        """由具体金融场景提供默认候选项和业务约束。"""
        raise NotImplementedError

    def validate(self, case_input: SelectionInput) -> tuple[CaseIssue, ...]:
        """验证候选项、关系引用、资源上下限和约束组合可行性。"""
        issues: list[CaseIssue] = []
        ids = tuple(item.item_id for item in case_input.items)
        if len(ids) < 2:
            issues.append(CaseIssue("ITEMS_TOO_SMALL", "items", "至少需要两个候选项。"))
        if len(ids) != len(set(ids)):
            issues.append(
                CaseIssue("ITEM_ID_DUPLICATE", "items", "候选项 ID 必须唯一。")
            )
        for index, item in enumerate(case_input.items):
            if (
                not item.item_id.strip()
                or not item.label.strip()
                or not item.group.strip()
            ):
                issues.append(
                    CaseIssue(
                        "ITEM_TEXT_INVALID",
                        f"items[{index}]",
                        "候选项名称和分组不能为空。",
                    )
                )
            if not all(math.isfinite(value) for value in (item.value, item.cost)):
                issues.append(
                    CaseIssue(
                        "ITEM_VALUE_INVALID",
                        f"items[{index}]",
                        "价值和成本必须为有限数。",
                    )
                )
            if item.units < 0:
                issues.append(
                    CaseIssue(
                        "ITEM_UNITS_INVALID",
                        f"items[{index}].units",
                        "资源单位不能为负数。",
                    )
                )
        if case_input.selected_count is not None and not (
            1 <= case_input.selected_count <= len(ids)
        ):
            issues.append(
                CaseIssue("COUNT_RANGE", "selected_count", "选择数量超出候选范围。")
            )
        known = set(ids)
        for left, right in (*case_input.conflicts, *case_input.dependencies):
            if left not in known or right not in known or left == right:
                issues.append(
                    CaseIssue(
                        "RELATION_INVALID",
                        "relations",
                        "冲突或依赖关系引用了无效候选项。",
                    )
                )
        if case_input.maximum_units is not None and case_input.maximum_units < 0:
            issues.append(
                CaseIssue("MAX_UNITS_RANGE", "maximum_units", "资源上限不能为负数。")
            )
        if case_input.minimum_units is not None and case_input.minimum_units < 0:
            issues.append(
                CaseIssue("MIN_UNITS_RANGE", "minimum_units", "资源下限不能为负数。")
            )
        if not issues and not self.exact_business_points(case_input):
            issues.append(
                CaseIssue(
                    "NO_FEASIBLE_SELECTION", "constraints", "当前约束下没有可行方案。"
                )
            )
        return tuple(issues)

    def build_problem(self, case_input: SelectionInput) -> QUBOProblemIR:
        """将价值成本目标及数量、分组、资源和关系约束统一编码为 QUBO。"""
        issues = self.validate(case_input)
        if issues:
            raise ValueError("; ".join(issue.message for issue in issues))
        variables = tuple(self._variable(item) for item in case_input.items)
        by_id = dict(zip((item.item_id for item in case_input.items), variables))
        builder = QuboBuilder(variables)
        values = self._normalize(tuple(item.value for item in case_input.items))
        costs = self._normalize(tuple(item.cost for item in case_input.items))
        for variable, value, cost in zip(variables, values, costs):
            builder.add_linear(
                variable,
                case_input.cost_weight * cost - case_input.value_weight * value,
            )

        objective_bound = builder.absolute_coefficient_sum
        penalty = (objective_bound + 1.0) * case_input.penalty_multiplier
        if case_input.selected_count is not None:
            builder.add_squared_equality(
                dict.fromkeys(variables, 1.0),
                rhs=float(case_input.selected_count),
                penalty=penalty,
            )

        by_group: dict[str, list[str]] = {}
        for item, variable in zip(case_input.items, variables):
            by_group.setdefault(item.group, []).append(variable)
        for group, required in sorted(case_input.group_exact.items()):
            builder.add_squared_equality(
                dict.fromkeys(by_group.get(group, ()), 1.0),
                rhs=float(required),
                penalty=penalty * 1.1,
            )
        if case_input.group_cap is not None:
            for group, group_variables in sorted(by_group.items()):
                if len(group_variables) <= case_input.group_cap:
                    continue
                coefficients = dict.fromkeys(group_variables, 1.0)
                for index, weight in enumerate(
                    bounded_binary_weights(case_input.group_cap)
                ):
                    coefficients[f"slack_group_{group}_{index:02d}"] = float(weight)
                builder.add_squared_equality(
                    coefficients,
                    rhs=float(case_input.group_cap),
                    penalty=penalty * 1.15,
                )

        units = {
            variable: float(item.units)
            for item, variable in zip(case_input.items, variables)
        }
        if case_input.maximum_units is not None:
            coefficients = dict(units)
            for index, weight in enumerate(
                bounded_binary_weights(case_input.maximum_units)
            ):
                coefficients[f"slack_max_units_{index:02d}"] = float(weight)
            builder.add_squared_equality(
                coefficients,
                rhs=float(case_input.maximum_units),
                penalty=penalty * 1.2,
            )
        if case_input.minimum_units is not None:
            coefficients = dict(units)
            extra = (
                sum(item.units for item in case_input.items) - case_input.minimum_units
            )
            for index, weight in enumerate(bounded_binary_weights(max(0, extra))):
                coefficients[f"slack_min_units_{index:02d}"] = -float(weight)
            builder.add_squared_equality(
                coefficients,
                rhs=float(case_input.minimum_units),
                penalty=penalty * 1.2,
            )
        for left, right in case_input.conflicts:
            builder.add_quadratic(by_id[left], by_id[right], penalty * 1.25)
        for child, parent in case_input.dependencies:
            builder.add_linear(by_id[child], penalty * 1.1)
            builder.add_quadratic(by_id[child], by_id[parent], -penalty * 1.1)

        return builder.build(
            problem_id=f"finance.{self.case_id}",
            metadata={
                "case_id": self.case_id,
                "business_variables": list(variables),
                "objective_bound": objective_bound,
                "base_penalty": penalty,
                "item_kind": self.item_kind,
            },
        )

    def build_definition(self, case_input: SelectionInput) -> FinanceProblemDefinition:
        """为 QUBO 补充金融项分组和 Digital 首选模式，形成统一 Problem 定义。"""
        problem = self.build_problem(case_input)
        business = tuple(problem.metadata["business_variables"])
        auxiliary = tuple(
            variable for variable in problem.variables if variable not in business
        )
        by_id = {item.item_id: self._variable(item) for item in case_input.items}
        conflicts = tuple(
            (by_id[left], by_id[right]) for left, right in case_input.conflicts
        )
        return FinanceProblemDefinition(
            case_id=self.case_id,
            title=self.title,
            problem_kind="qubo",
            problem=problem,
            preferred_mode="digital",
            business_variables=business,
            auxiliary_variables=auxiliary,
            term_groups=(
                FinanceTermGroup("objective", "业务价值与成本", "objective", business),
                FinanceTermGroup(
                    "conflicts",
                    "业务冲突",
                    "pairwise_conflict",
                    pairs=conflicts,
                ),
                FinanceTermGroup(
                    "constraints",
                    "数量、分组和资源约束",
                    "global_constraint",
                    business,
                ),
                FinanceTermGroup(
                    "dependencies",
                    "前置依赖",
                    "dependency",
                    business,
                ),
                FinanceTermGroup("slack", "辅助变量", "auxiliary_penalty", auxiliary),
            ),
        )

    def decode(
        self,
        case_input: SelectionInput,
        definition: FinanceProblemDefinition,
        candidate: Any,
    ) -> SelectionSolution:
        """从完整 Problem 位串提取业务候选位，并忽略松弛变量。"""
        bitstring = str(candidate.bitstring)
        if len(bitstring) != len(definition.problem.variables):
            raise ValueError("candidate bitstring does not match problem variables.")
        values = dict(zip(definition.problem.variables, bitstring))
        bits = tuple(
            int(values.get(self._variable(item), "0")) for item in case_input.items
        )
        solution = self.decode_selection(case_input, bits)
        return SelectionSolution(
            bitstring=bitstring,
            selected_item_ids=solution.selected_item_ids,
            total_value=solution.total_value,
            total_cost=solution.total_cost,
            total_units=solution.total_units,
            group_counts=solution.group_counts,
            feasible=solution.feasible,
            checks=solution.checks,
            exclusion_reasons=solution.exclusion_reasons,
        )

    def decode_selection(
        self,
        case_input: SelectionInput,
        bits: tuple[int, ...],
    ) -> SelectionSolution:
        """按业务位重新核算总价值、成本、资源、分组、冲突和依赖。"""
        if len(bits) != len(case_input.items):
            raise ValueError("bits must match the candidate item count.")
        selected = tuple(
            item for item, bit in zip(case_input.items, bits) if int(bit) == 1
        )
        selected_ids = {item.item_id for item in selected}
        group_counts = Counter(item.group for item in selected)
        checks: list[ConstraintCheck] = []
        if case_input.selected_count is not None:
            checks.append(
                ConstraintCheck(
                    "selected_count",
                    len(selected) == case_input.selected_count,
                    str(len(selected)),
                    str(case_input.selected_count),
                )
            )
        for group, required in sorted(case_input.group_exact.items()):
            checks.append(
                ConstraintCheck(
                    f"group_exact:{group}",
                    group_counts[group] == required,
                    str(group_counts[group]),
                    str(required),
                )
            )
        if case_input.group_cap is not None:
            checks.append(
                ConstraintCheck(
                    "group_cap",
                    max(group_counts.values(), default=0) <= case_input.group_cap,
                    str(max(group_counts.values(), default=0)),
                    f"<= {case_input.group_cap}",
                )
            )
        total_units = sum(item.units for item in selected)
        if case_input.maximum_units is not None:
            checks.append(
                ConstraintCheck(
                    "maximum_units",
                    total_units <= case_input.maximum_units,
                    str(total_units),
                    f"<= {case_input.maximum_units}",
                )
            )
        if case_input.minimum_units is not None:
            checks.append(
                ConstraintCheck(
                    "minimum_units",
                    total_units >= case_input.minimum_units,
                    str(total_units),
                    f">= {case_input.minimum_units}",
                )
            )
        conflict_violations = tuple(
            (left, right)
            for left, right in case_input.conflicts
            if left in selected_ids and right in selected_ids
        )
        checks.append(
            ConstraintCheck(
                "conflicts",
                not conflict_violations,
                str(len(conflict_violations)),
                "0",
            )
        )
        dependency_violations = tuple(
            (child, parent)
            for child, parent in case_input.dependencies
            if child in selected_ids and parent not in selected_ids
        )
        checks.append(
            ConstraintCheck(
                "dependencies",
                not dependency_violations,
                str(len(dependency_violations)),
                "0",
            )
        )
        return SelectionSolution(
            bitstring="".join(str(int(bit)) for bit in bits),
            selected_item_ids=tuple(item.item_id for item in selected),
            total_value=sum(item.value for item in selected),
            total_cost=sum(item.cost for item in selected),
            total_units=total_units,
            group_counts=dict(sorted(group_counts.items())),
            feasible=all(check.passed for check in checks),
            checks=tuple(checks),
            exclusion_reasons=self._exclusion_reasons(case_input, selected_ids),
        )

    def exact_business_points(
        self, case_input: SelectionInput
    ) -> tuple[SelectionSolution, ...]:
        """穷举小规模选择空间，按价值优先、成本次优生成经典基线。"""
        solutions = []
        for bits in itertools.product((0, 1), repeat=len(case_input.items)):
            solution = self.decode_selection(case_input, bits)
            if solution.feasible:
                solutions.append(solution)
        return tuple(
            sorted(
                solutions,
                key=lambda item: (-item.total_value, item.total_cost, item.bitstring),
            )
        )

    @staticmethod
    def _normalize(values: tuple[float, ...]) -> tuple[float, ...]:
        """将不同量纲的价值或成本缩放到 0..1，供统一目标权重组合。"""
        low = min(values)
        spread = max(values) - low
        if spread <= 1e-15:
            return tuple(1.0 for _ in values)
        return tuple((value - low) / spread for value in values)

    @staticmethod
    def _variable(item: SelectionItem) -> str:
        """把业务候选 ID 转换为稳定且可读的 QUBO 变量名。"""
        normalized = item.item_id.lower().replace("-", "_")
        return f"item_{normalized}"

    @staticmethod
    def _exclusion_reasons(
        case_input: SelectionInput,
        selected_ids: set[str],
    ) -> dict[str, str]:
        """根据冲突与名额状态解释候选项未被选择的直接原因。"""
        reasons = {}
        for item in case_input.items:
            if item.item_id in selected_ids:
                continue
            if any(
                item.item_id in pair and set(pair) & selected_ids
                for pair in case_input.conflicts
            ):
                reasons[item.item_id] = "与已选项冲突"
            elif (
                case_input.selected_count is not None
                and len(selected_ids) >= case_input.selected_count
            ):
                reasons[item.item_id] = "选择数量已满"
            else:
                reasons[item.item_id] = "目标值未进入当前候选"
        return reasons


class CollateralScenario(ConstrainedSelectionCase):
    """在多个保证金需求之间分配合格抵押品的 Digital 场景。"""
    case_id = "collateral"
    title = "抵押品分配优化"
    item_kind = "抵押品分配候选"

    def default_input(self) -> SelectionInput:
        """返回覆盖 CCP、双边和流动性储备需求的抵押品候选。"""
        return SelectionInput(
            items=(
                SelectionItem(
                    "COL-01",
                    "国债批次 A -> CCP",
                    "CCP",
                    9.4,
                    1.2,
                    4,
                    "HQLA / 2% haircut",
                ),
                SelectionItem(
                    "COL-02", "政策债 B -> CCP", "CCP", 8.7, 0.9, 3, "HQLA / 4% haircut"
                ),
                SelectionItem(
                    "COL-03",
                    "信用债 C -> 双边一",
                    "BILAT-1",
                    7.5,
                    0.7,
                    3,
                    "AA+ / 8% haircut",
                ),
                SelectionItem(
                    "COL-04",
                    "现金 D -> 双边一",
                    "BILAT-1",
                    9.8,
                    2.1,
                    4,
                    "Cash / 0% haircut",
                ),
                SelectionItem(
                    "COL-05",
                    "股票篮子 E -> 双边二",
                    "BILAT-2",
                    6.2,
                    0.5,
                    2,
                    "Equity / 18% haircut",
                ),
                SelectionItem(
                    "COL-06",
                    "黄金 F -> 双边二",
                    "BILAT-2",
                    8.1,
                    1.0,
                    3,
                    "Gold / 10% haircut",
                ),
                SelectionItem(
                    "COL-07",
                    "国债批次 A -> 双边二",
                    "BILAT-2",
                    9.0,
                    1.4,
                    4,
                    "Same lot as COL-01",
                ),
                SelectionItem(
                    "COL-08",
                    "信用债 C -> CCP",
                    "CCP",
                    7.1,
                    0.8,
                    3,
                    "Same lot as COL-03",
                ),
            ),
            group_exact={"CCP": 1, "BILAT-1": 1, "BILAT-2": 1},
            conflicts=(("COL-01", "COL-07"), ("COL-03", "COL-08")),
            value_weight=0.58,
            cost_weight=0.42,
        )


class LiquidityScenario(ConstrainedSelectionCase):
    """选择日内融资动作以满足流动性下限和前置依赖的 Digital 场景。"""
    case_id = "liquidity"
    title = "日内流动性调度"
    item_kind = "流动性动作"

    def default_input(self) -> SelectionInput:
        """返回带时点、币种、冲突和依赖关系的流动性动作。"""
        return SelectionInput(
            items=(
                SelectionItem(
                    "LIQ-01",
                    "09:30 CNY 内部划拨",
                    "CNY",
                    7.8,
                    0.2,
                    3,
                    "09:30 / internal",
                ),
                SelectionItem(
                    "LIQ-02", "10:00 CNY 质押回购", "CNY", 9.2, 1.1, 4, "10:00 / repo"
                ),
                SelectionItem(
                    "LIQ-03",
                    "10:30 USD 同业拆入",
                    "USD",
                    8.9,
                    1.4,
                    4,
                    "10:30 / interbank",
                ),
                SelectionItem(
                    "LIQ-04",
                    "11:00 USD 外汇掉期",
                    "USD",
                    7.6,
                    0.9,
                    3,
                    "11:00 / FX swap",
                ),
                SelectionItem(
                    "LIQ-05",
                    "13:30 HKD 内部划拨",
                    "HKD",
                    6.8,
                    0.3,
                    2,
                    "13:30 / internal",
                ),
                SelectionItem(
                    "LIQ-06",
                    "14:00 HKD 同业拆入",
                    "HKD",
                    8.0,
                    1.0,
                    3,
                    "14:00 / interbank",
                ),
                SelectionItem(
                    "LIQ-07", "14:30 CNY 票据融资", "CNY", 7.2, 0.8, 3, "14:30 / bill"
                ),
                SelectionItem(
                    "LIQ-08",
                    "15:00 USD 外汇掉期续作",
                    "USD",
                    8.4,
                    1.2,
                    4,
                    "15:00 / FX swap",
                ),
            ),
            selected_count=4,
            minimum_units=12,
            group_cap=2,
            conflicts=(("LIQ-03", "LIQ-04"),),
            dependencies=(("LIQ-08", "LIQ-04"),),
            value_weight=0.7,
            cost_weight=0.3,
        )


class CreditLimitScenario(ConstrainedSelectionCase):
    """在资本消耗和行业集中度约束下配置企业授信档位的 Digital 场景。"""
    case_id = "credit_limits"
    title = "企业授信额度配置"
    item_kind = "已准入额度档位"

    def default_input(self) -> SelectionInput:
        """返回跨制造、科技、消费和能源行业的授信候选档位。"""
        return SelectionInput(
            items=(
                SelectionItem(
                    "CR-01", "制造企业 A / 低档", "制造", 7.2, 1.8, 2, "PD 0.8%"
                ),
                SelectionItem(
                    "CR-02", "制造企业 B / 中档", "制造", 8.4, 2.7, 3, "PD 1.2%"
                ),
                SelectionItem(
                    "CR-03", "制造企业 C / 高档", "制造", 9.1, 3.5, 4, "PD 1.9%"
                ),
                SelectionItem(
                    "CR-04", "科技企业 D / 低档", "科技", 7.8, 2.0, 2, "PD 1.1%"
                ),
                SelectionItem(
                    "CR-05", "科技企业 E / 中档", "科技", 9.3, 3.2, 4, "PD 2.0%"
                ),
                SelectionItem(
                    "CR-06", "消费企业 F / 低档", "消费", 6.9, 1.5, 2, "PD 0.7%"
                ),
                SelectionItem(
                    "CR-07", "消费企业 G / 中档", "消费", 8.0, 2.4, 3, "PD 1.0%"
                ),
                SelectionItem(
                    "CR-08", "能源企业 H / 中档", "能源", 8.6, 2.9, 3, "PD 1.6%"
                ),
            ),
            selected_count=4,
            maximum_units=11,
            group_cap=2,
            conflicts=(("CR-02", "CR-03"),),
            value_weight=0.62,
            cost_weight=0.38,
        )
