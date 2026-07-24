"""交易结算批次选择、流动性约束及其 QUBO 映射。"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from typing import Any

from cascaqit import QUBOProblemIR

from cascaqit_finance_demo.domain.models import (
    CaseIssue,
    ConstraintCheck,
    LiquidityLimit,
    SettlementInput,
    SettlementSolution,
    TradeInstruction,
)
from cascaqit_finance_demo.domain.qubo_builder import (
    QuboBuilder,
    bounded_binary_weights,
)


class SettlementCase:
    """构建合成结算批次的 QUBO，并将候选解恢复为可审计的交易选择。"""

    case_id = "settlement"

    def default_input(self) -> SettlementInput:
        """返回含币种流动性、依赖和冲突关系的默认结算指令集。"""
        # cash_units 是演示用的离散资金桶，不等同于交易名义金额；这种离散化
        # 既避免把名义金额误当可用现金，也把 QUBO 变量规模控制在 20 以内。
        instructions = (
            TradeInstruction("T-001", "CNY", 2.4, 5, 1, conflicts=("T-007",)),
            TradeInstruction("T-002", "USD", 1.8, 4, 1, requires=("T-008",)),
            TradeInstruction("T-003", "HKD", 1.1, 3, 1, conflicts=("T-006",)),
            TradeInstruction("T-004", "CNY", 2.1, 5, 1, requires=("T-001",)),
            TradeInstruction("T-005", "USD", 1.4, 2, 1, conflicts=("T-009",)),
            TradeInstruction("T-006", "HKD", 2.3, 4, 1, conflicts=("T-003",)),
            TradeInstruction("T-007", "CNY", 3.2, 3, 2, conflicts=("T-001",)),
            TradeInstruction("T-008", "USD", 0.9, 5, 1),
            TradeInstruction(
                "T-009",
                "CNY",
                1.7,
                2,
                1,
                requires=("T-004",),
                conflicts=("T-005",),
            ),
            TradeInstruction("T-010", "HKD", 2.6, 4, 1),
        )
        return SettlementInput(
            instructions=instructions,
            liquidity_limits=(
                LiquidityLimit("CNY", 3),
                LiquidityLimit("USD", 2),
                LiquidityLimit("HKD", 2),
            ),
        )

    def validate(self, case_input: SettlementInput) -> tuple[CaseIssue, ...]:
        """验证交易字段、引用关系、容量、权重和当前约束组合的可行性。"""
        issues: list[CaseIssue] = []
        instructions = case_input.instructions
        trade_ids = tuple(item.trade_id for item in instructions)
        known_ids = set(trade_ids)
        if len(instructions) < 2:
            issues.append(
                CaseIssue("SETTLEMENT_TOO_SMALL", "instructions", "至少需要两条指令。")
            )
        if len(trade_ids) != len(known_ids):
            issues.append(
                CaseIssue("TRADE_ID_DUPLICATE", "instructions", "交易 ID 必须唯一。")
            )
        for index, item in enumerate(instructions):
            path = f"instructions[{index}]"
            if not item.trade_id.strip() or item.trade_id != item.trade_id.strip():
                issues.append(
                    CaseIssue(
                        "TRADE_ID_INVALID", path, "交易 ID 不能为空或包含首尾空格。"
                    )
                )
            if not math.isfinite(item.notional_m) or item.notional_m <= 0.0:
                issues.append(
                    CaseIssue("NOTIONAL_INVALID", path, "名义金额必须为有限正数。")
                )
            if not 1 <= item.priority <= 5:
                issues.append(
                    CaseIssue("PRIORITY_RANGE", path, "业务等级必须在 1 到 5 之间。")
                )
            if item.cash_units < 1:
                issues.append(
                    CaseIssue("CASH_UNITS_RANGE", path, "流动性占用必须为正整数。")
                )
            references = set(item.requires) | set(item.conflicts)
            if item.trade_id in references:
                issues.append(
                    CaseIssue("TRADE_SELF_REFERENCE", path, "交易不能依赖或冲突自身。")
                )
            unknown = references - known_ids
            if unknown:
                issues.append(
                    CaseIssue(
                        "TRADE_REFERENCE_UNKNOWN",
                        path,
                        f"存在未知交易引用：{', '.join(sorted(unknown))}。",
                    )
                )

        limit_currencies = tuple(
            limit.currency for limit in case_input.liquidity_limits
        )
        if len(limit_currencies) != len(set(limit_currencies)):
            issues.append(
                CaseIssue(
                    "LIQUIDITY_CURRENCY_DUPLICATE",
                    "liquidity_limits",
                    "币种额度必须唯一。",
                )
            )
        if set(limit_currencies) != {item.currency for item in instructions}:
            issues.append(
                CaseIssue(
                    "LIQUIDITY_CURRENCY_MISMATCH",
                    "liquidity_limits",
                    "每个交易币种都必须且只能配置一个额度。",
                )
            )
        if any(limit.capacity_units < 1 for limit in case_input.liquidity_limits):
            issues.append(
                CaseIssue(
                    "LIQUIDITY_CAPACITY_RANGE",
                    "liquidity_limits",
                    "币种额度必须为正整数。",
                )
            )
        if not 1 <= case_input.batch_cap <= len(instructions):
            issues.append(
                CaseIssue("BATCH_CAP_RANGE", "batch_cap", "批次上限超出交易数量范围。")
            )
        weights = (case_input.notional_weight, case_input.priority_weight)
        if any(not math.isfinite(value) or value < 0.0 for value in weights):
            issues.append(
                CaseIssue(
                    "OBJECTIVE_WEIGHT_RANGE", "weights", "目标权重必须为有限非负数。"
                )
            )
        if sum(weights) <= 0.0:
            issues.append(
                CaseIssue(
                    "OBJECTIVE_WEIGHT_ZERO", "weights", "至少一个目标权重必须大于零。"
                )
            )
        if (
            not math.isfinite(case_input.penalty_multiplier)
            or case_input.penalty_multiplier <= 1.0
        ):
            issues.append(
                CaseIssue(
                    "PENALTY_MULTIPLIER_RANGE",
                    "penalty_multiplier",
                    "罚项倍数必须为大于 1 的有限数。",
                )
            )

        if not issues:
            variable_count = self._estimated_variable_count(case_input)
            if variable_count > 20:
                issues.append(
                    CaseIssue(
                        "QUBO_VARIABLE_LIMIT",
                        "constraints",
                        f"当前输入需要 {variable_count} 个变量，Demo 上限为 20。",
                    )
                )
            elif not self.exact_business_points(case_input):
                issues.append(
                    CaseIssue(
                        "NO_FEASIBLE_SETTLEMENT",
                        "constraints",
                        "当前约束下没有可行结算批次。",
                    )
                )
        return tuple(issues)

    def build_problem(self, case_input: SettlementInput) -> QUBOProblemIR:
        """编码结算价值、流动性、批量上限、前置依赖和互斥交易。"""
        issues = self.validate(case_input)
        if issues:
            raise ValueError("; ".join(issue.message for issue in issues))

        variables = tuple(
            self._trade_variable(index, item)
            for index, item in enumerate(case_input.instructions)
        )
        by_id = dict(
            zip((item.trade_id for item in case_input.instructions), variables)
        )
        builder = QuboBuilder(variables)
        values = self._business_values(case_input)
        for variable, value in zip(variables, values):
            builder.add_linear(variable, -value)

        # 单条硬约束违规的代价必须高于选中全部交易可能获得的目标收益，
        # 否则优化器可能通过主动违规换取更低能量。
        objective_bound = builder.absolute_coefficient_sum
        base_penalty = (objective_bound + 1.0) * case_input.penalty_multiplier
        for left_id, right_id in self._conflict_pairs(case_input):
            builder.add_quadratic(by_id[left_id], by_id[right_id], base_penalty)
        for item in case_input.instructions:
            for required_id in item.requires:
                # P*x_i*(1-x_j) 只在选择交易 i 却未选择前置交易 j 时产生罚能。
                builder.add_linear(by_id[item.trade_id], base_penalty * 1.1)
                builder.add_quadratic(
                    by_id[item.trade_id],
                    by_id[required_id],
                    -base_penalty * 1.1,
                )

        limits = {
            limit.currency: limit.capacity_units
            for limit in case_input.liquidity_limits
        }
        for currency, capacity in sorted(limits.items()):
            coefficients = {
                variable: float(item.cash_units)
                for item, variable in zip(case_input.instructions, variables)
                if item.currency == currency
            }
            for index, weight in enumerate(bounded_binary_weights(capacity)):
                coefficients[f"slack_liquidity_{currency}_{index:02d}"] = float(weight)
            builder.add_squared_equality(
                coefficients,
                rhs=float(capacity),
                penalty=base_penalty * 1.2,
            )

        batch_slack = self._batch_slack_weights(case_input)
        if batch_slack:
            batch_coefficients = dict.fromkeys(variables, 1.0)
            for index, weight in enumerate(batch_slack):
                batch_coefficients[f"slack_batch_{index:02d}"] = float(weight)
            builder.add_squared_equality(
                batch_coefficients,
                rhs=float(case_input.batch_cap),
                penalty=base_penalty * 1.3,
            )

        return builder.build(
            problem_id="finance.settlement",
            metadata={
                "case_id": self.case_id,
                "business_variables": list(variables),
                "bitstring_convention": "1 means selected in problem.variables order",
                "objective_bound": objective_bound,
                "base_penalty": base_penalty,
                "liquidity_unit_kind": "synthetic_integer_bucket",
                "batch_cap_encoding": (
                    "slack" if batch_slack else "implied_by_liquidity_limits"
                ),
            },
        )

    def exact_business_points(
        self, case_input: SettlementInput
    ) -> tuple[SettlementSolution, ...]:
        """枚举全部业务交易位，仅保留通过独立约束复核的结算批次。"""
        if not case_input.instructions:
            return ()
        solutions: list[SettlementSolution] = []
        for bits in itertools.product((0, 1), repeat=len(case_input.instructions)):
            solution = self.decode_trade_selection(case_input, bits)
            if solution.feasible:
                solutions.append(solution)
        return tuple(sorted(solutions, key=lambda item: item.business_objective))

    def decode(
        self,
        case_input: SettlementInput,
        problem: QUBOProblemIR,
        candidate: Any,
    ) -> SettlementSolution:
        """从完整 Problem 位串提取交易变量，再调用业务解码器复核约束。"""
        bitstring = str(candidate.bitstring)
        if len(bitstring) != len(problem.variables):
            raise ValueError("candidate bitstring does not match problem variables.")
        values = dict(zip(problem.variables, bitstring))
        trade_bits = tuple(
            int(values.get(self._trade_variable(index, item), "0"))
            for index, item in enumerate(case_input.instructions)
        )
        solution = self.decode_trade_selection(case_input, trade_bits)
        return SettlementSolution(
            bitstring=bitstring,
            selected_trade_ids=solution.selected_trade_ids,
            settled_notional_m=solution.settled_notional_m,
            business_objective=solution.business_objective,
            liquidity_used=solution.liquidity_used,
            feasible=solution.feasible,
            checks=solution.checks,
            exclusion_reasons=solution.exclusion_reasons,
        )

    def decode_trade_selection(
        self,
        case_input: SettlementInput,
        bits: tuple[int, ...],
        *,
        trade_ids: tuple[str, ...] | None = None,
    ) -> SettlementSolution:
        """按交易选择位重新计算结算金额、流动性使用和排除原因。"""
        mapped_ids = (
            tuple(item.trade_id for item in case_input.instructions)
            if trade_ids is None
            else trade_ids
        )
        if len(bits) != len(mapped_ids):
            raise ValueError("bits must match the mapped trade ids.")
        known = {item.trade_id: item for item in case_input.instructions}
        if set(mapped_ids) - set(known):
            raise ValueError("trade_ids contains an unknown settlement instruction.")
        selected_ids = tuple(
            trade_id for trade_id, bit in zip(mapped_ids, bits) if int(bit) == 1
        )
        selected = set(selected_ids)
        limits = {
            limit.currency: limit.capacity_units
            for limit in case_input.liquidity_limits
        }
        liquidity: Counter[str] = Counter()
        for trade_id in selected_ids:
            item = known[trade_id]
            liquidity[item.currency] += item.cash_units
        conflicts = self._conflict_pairs(case_input)
        conflict_failures = tuple(
            pair for pair in conflicts if pair[0] in selected and pair[1] in selected
        )
        dependency_failures = tuple(
            (item.trade_id, required)
            for item in case_input.instructions
            if item.trade_id in selected
            for required in item.requires
            if required not in selected
        )
        checks = (
            ConstraintCheck(
                "batch_cap",
                len(selected_ids) <= case_input.batch_cap,
                str(len(selected_ids)),
                f"<= {case_input.batch_cap}",
            ),
            ConstraintCheck(
                "liquidity_limits",
                all(
                    liquidity[currency] <= capacity
                    for currency, capacity in limits.items()
                ),
                ", ".join(
                    f"{currency}={liquidity[currency]}" for currency in sorted(limits)
                ),
                ", ".join(
                    f"{currency}<={limits[currency]}" for currency in sorted(limits)
                ),
            ),
            ConstraintCheck(
                "dependencies",
                not dependency_failures,
                str(len(dependency_failures)),
                "0",
            ),
            ConstraintCheck(
                "conflicts",
                not conflict_failures,
                str(len(conflict_failures)),
                "0",
            ),
        )
        values = self._business_values(case_input)
        values_by_id = {
            item.trade_id: values[index]
            for index, item in enumerate(case_input.instructions)
        }
        exclusion_reasons = self._exclusion_reasons(
            case_input, selected, liquidity, limits
        )
        return SettlementSolution(
            bitstring="".join(str(int(bit)) for bit in bits),
            selected_trade_ids=selected_ids,
            settled_notional_m=sum(
                known[trade_id].notional_m for trade_id in selected_ids
            ),
            business_objective=-sum(
                values_by_id[trade_id] for trade_id in selected_ids
            ),
            liquidity_used={
                currency: liquidity[currency] for currency in sorted(limits)
            },
            feasible=all(check.passed for check in checks),
            checks=checks,
            exclusion_reasons=exclusion_reasons,
        )

    def _business_values(self, case_input: SettlementInput) -> tuple[float, ...]:
        """归一化金额和优先级，并按用户权重生成每笔交易的目标价值。"""
        notionals = tuple(item.notional_m for item in case_input.instructions)
        priorities = tuple(float(item.priority) for item in case_input.instructions)
        normalized_notionals = self._min_max(notionals)
        normalized_priorities = self._min_max(priorities)
        total_weight = case_input.notional_weight + case_input.priority_weight
        return tuple(
            (
                case_input.notional_weight * notional
                + case_input.priority_weight * priority
            )
            / total_weight
            for notional, priority in zip(normalized_notionals, normalized_priorities)
        )

    def _estimated_variable_count(self, case_input: SettlementInput) -> int:
        """预估业务变量与容量松弛变量总数，用于提前阻止演示规模失控。"""
        return (
            len(case_input.instructions)
            + sum(
                len(bounded_binary_weights(limit.capacity_units))
                for limit in case_input.liquidity_limits
            )
            + len(self._batch_slack_weights(case_input))
        )

    @staticmethod
    def _batch_slack_weights(case_input: SettlementInput) -> tuple[int, ...]:
        """返回批量上限需要的有界松弛权重；冗余上限不再增加辅助变量。"""
        # 每笔入选交易至少消耗一个流动性单位。当 batch_cap 不严于所有币种容量
        # 之和时，流动性约束已经隐含证明批量上限，无需重复编码。
        aggregate_capacity = sum(
            limit.capacity_units for limit in case_input.liquidity_limits
        )
        if case_input.batch_cap >= aggregate_capacity:
            return ()
        return bounded_binary_weights(case_input.batch_cap)

    @staticmethod
    def _trade_variable(index: int, item: TradeInstruction) -> str:
        """生成同时包含稳定序号和业务 ID 的交易变量名。"""
        normalized_id = item.trade_id.lower().replace("-", "_")
        return f"trade_{index:02d}_{normalized_id}"

    @staticmethod
    def _min_max(values: tuple[float, ...]) -> tuple[float, ...]:
        """执行 min-max 归一化；全相等输入统一映射为 1，保留相对价值。"""
        low = min(values)
        spread = max(values) - low
        if spread <= 1e-15:
            return tuple(1.0 for _ in values)
        return tuple((value - low) / spread for value in values)

    @staticmethod
    def _conflict_pairs(case_input: SettlementInput) -> tuple[tuple[str, str], ...]:
        """汇总双向声明的交易冲突，规范顺序并去重。"""
        return tuple(
            sorted(
                {
                    tuple(sorted((item.trade_id, other)))
                    for item in case_input.instructions
                    for other in item.conflicts
                }
            )
        )

    def _exclusion_reasons(
        self,
        case_input: SettlementInput,
        selected: set[str],
        liquidity: Counter[str],
        limits: dict[str, int],
    ) -> dict[str, str]:
        """根据已选批次推导每笔未选交易最直接的业务排除原因。"""
        known = {item.trade_id: item for item in case_input.instructions}
        conflicts = {trade_id: set() for trade_id in known}
        for left, right in self._conflict_pairs(case_input):
            conflicts[left].add(right)
            conflicts[right].add(left)
        reasons: dict[str, str] = {}
        for item in case_input.instructions:
            if item.trade_id in selected:
                continue
            selected_conflicts = sorted(conflicts[item.trade_id] & selected)
            if selected_conflicts:
                reasons[item.trade_id] = f"与 {selected_conflicts[0]} 冲突"
            elif any(required not in selected for required in item.requires):
                missing = next(
                    required for required in item.requires if required not in selected
                )
                reasons[item.trade_id] = f"前置交易 {missing} 未入选"
            elif liquidity[item.currency] + item.cash_units > limits[item.currency]:
                reasons[item.trade_id] = f"{item.currency} 额度不足"
            elif len(selected) >= case_input.batch_cap:
                reasons[item.trade_id] = "批次容量已满"
            else:
                reasons[item.trade_id] = "目标值未进入当前候选"
        return reasons
