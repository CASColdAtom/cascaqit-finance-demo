"""对已生成的反欺诈告警分配有限调查资源，并映射为 QUBO。"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from typing import Any

from cascaqit import QUBOProblemIR

from cascaqit_finance_demo.domain.models import (
    CaseIssue,
    ConstraintCheck,
    FraudAlert,
    FraudRoutingInput,
    FraudRoutingSolution,
)
from cascaqit_finance_demo.domain.qubo_builder import QuboBuilder


class FraudRoutingCase:
    """构建兼顾风险、敞口、时效和实体并行上限的调查任务选择 QUBO。"""

    case_id = "fraud_routing"

    def default_input(self) -> FraudRoutingInput:
        """返回包含共享实体关系的十二条默认告警。"""
        return FraudRoutingInput(
            alerts=(
                FraudAlert("A-01", 92, 1.8, 18, "E-17", 3.0),
                FraudAlert("A-02", 73, 0.8, 7, "E-04", 2.0),
                FraudAlert("A-03", 86, 2.4, 31, "E-09", 4.0),
                FraudAlert("A-04", 58, 0.4, 4, "E-11", 1.5),
                FraudAlert("A-05", 79, 1.1, 22, "E-04", 2.5),
                FraudAlert("A-06", 65, 0.6, 11, "E-13", 2.0),
                FraudAlert("A-07", 88, 2.3, 27, "E-21", 3.5),
                FraudAlert("A-08", 69, 0.9, 14, "E-17", 2.0),
                FraudAlert("A-09", 83, 1.6, 35, "E-25", 4.0),
                FraudAlert("A-10", 61, 0.5, 8, "E-19", 1.5),
                FraudAlert("A-11", 76, 1.3, 25, "E-09", 3.0),
                FraudAlert("A-12", 71, 0.7, 16, "E-28", 2.0),
            )
        )

    def validate(self, case_input: FraudRoutingInput) -> tuple[CaseIssue, ...]:
        """验证告警字段、目标权重、席位上限以及整体可行性。"""
        issues: list[CaseIssue] = []
        alerts = case_input.alerts
        alert_ids = tuple(alert.alert_id for alert in alerts)
        if len(alerts) < 2:
            issues.append(
                CaseIssue("FRAUD_ROUTING_TOO_SMALL", "alerts", "至少需要两条告警。")
            )
        if len(alert_ids) != len(set(alert_ids)):
            issues.append(
                CaseIssue("ALERT_ID_DUPLICATE", "alerts", "告警 ID 必须唯一。")
            )
        for index, alert in enumerate(alerts):
            path = f"alerts[{index}]"
            if not alert.alert_id.strip() or alert.alert_id != alert.alert_id.strip():
                issues.append(
                    CaseIssue(
                        "ALERT_ID_INVALID", path, "告警 ID 不能为空或包含首尾空格。"
                    )
                )
            if not 0.0 <= alert.risk_score <= 100.0:
                issues.append(
                    CaseIssue("RISK_SCORE_RANGE", path, "风险分必须在 0 到 100 之间。")
                )
            numeric_positive = (
                ("exposure_m", alert.exposure_m),
                ("age_hours", alert.age_hours),
                ("estimated_hours", alert.estimated_hours),
            )
            for field, value in numeric_positive:
                if not math.isfinite(value) or value < 0.0:
                    issues.append(
                        CaseIssue(
                            "ALERT_VALUE_RANGE",
                            f"{path}.{field}",
                            "告警数值必须为有限非负数。",
                        )
                    )
            if not alert.entity_id.strip():
                issues.append(
                    CaseIssue("ENTITY_ID_INVALID", path, "关键实体不能为空。")
                )
        if not 1 <= case_input.investigator_slots <= len(alerts):
            issues.append(
                CaseIssue(
                    "INVESTIGATOR_SLOTS_RANGE",
                    "investigator_slots",
                    "调查席位超出告警数量范围。",
                )
            )
        if case_input.entity_parallel_cap not in (1, 2):
            issues.append(
                CaseIssue(
                    "ENTITY_PARALLEL_CAP_RANGE",
                    "entity_parallel_cap",
                    "单实体并行上限仅支持 1 或 2。",
                )
            )
        weights = (
            case_input.risk_weight,
            case_input.exposure_weight,
            case_input.urgency_weight,
        )
        if any(not math.isfinite(value) or value < 0.0 for value in weights):
            issues.append(
                CaseIssue(
                    "ROUTING_WEIGHT_RANGE", "weights", "目标权重必须为有限非负数。"
                )
            )
        if sum(weights) <= 0.0:
            issues.append(
                CaseIssue(
                    "ROUTING_WEIGHT_ZERO", "weights", "至少一个目标权重必须大于零。"
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
        if not issues and not self.exact_business_points(case_input):
            issues.append(
                CaseIssue(
                    "NO_FEASIBLE_ROUTING",
                    "constraints",
                    "当前席位和实体约束下没有可行编排。",
                )
            )
        return tuple(issues)

    def build_problem(self, case_input: FraudRoutingInput) -> QUBOProblemIR:
        """编码加权告警价值、固定席位数和同实体告警冲突。"""
        issues = self.validate(case_input)
        if issues:
            raise ValueError("; ".join(issue.message for issue in issues))
        variables = tuple(
            self._alert_variable(index, alert)
            for index, alert in enumerate(case_input.alerts)
        )
        builder = QuboBuilder(variables)
        values = self.business_values(case_input)
        for variable, value in zip(variables, values):
            builder.add_linear(variable, -value)

        objective_bound = builder.absolute_coefficient_sum
        penalty = (objective_bound + 1.0) * case_input.penalty_multiplier
        builder.add_squared_equality(
            dict.fromkeys(variables, 1.0),
            rhs=float(case_input.investigator_slots),
            penalty=penalty,
        )
        by_id = dict(zip((alert.alert_id for alert in case_input.alerts), variables))
        for left, right in self._conflict_pairs(case_input):
            builder.add_quadratic(by_id[left], by_id[right], penalty * 1.1)
        return builder.build(
            problem_id="finance.fraud_routing",
            metadata={
                "case_id": self.case_id,
                "business_variables": list(variables),
                "objective_bound": objective_bound,
                "base_penalty": penalty,
                "value_formula": "weighted normalized risk + exposure + urgency",
                "decision_scope": "investigation routing only",
            },
        )

    def exact_business_points(
        self, case_input: FraudRoutingInput
    ) -> tuple[FraudRoutingSolution, ...]:
        """按调查席位数组合枚举告警，形成可验证的经典基线集合。"""
        if not case_input.alerts:
            return ()
        solutions: list[FraudRoutingSolution] = []
        for selected_indices in itertools.combinations(
            range(len(case_input.alerts)), case_input.investigator_slots
        ):
            selected = set(selected_indices)
            bits = tuple(
                1 if index in selected else 0 for index in range(len(case_input.alerts))
            )
            solution = self.decode_alert_selection(case_input, bits)
            if solution.feasible:
                solutions.append(solution)
        return tuple(sorted(solutions, key=lambda item: item.business_objective))

    def decode(
        self,
        case_input: FraudRoutingInput,
        problem: QUBOProblemIR,
        candidate: Any,
    ) -> FraudRoutingSolution:
        """从 Problem 变量顺序恢复告警位，并交给业务解码器复核。"""
        bitstring = str(candidate.bitstring)
        if len(bitstring) != len(problem.variables):
            raise ValueError("candidate bitstring does not match problem variables.")
        values = dict(zip(problem.variables, bitstring))
        bits = tuple(
            int(values.get(self._alert_variable(index, alert), "0"))
            for index, alert in enumerate(case_input.alerts)
        )
        solution = self.decode_alert_selection(case_input, bits)
        return FraudRoutingSolution(
            bitstring=bitstring,
            selected_alert_ids=solution.selected_alert_ids,
            risk_coverage=solution.risk_coverage,
            exposure_coverage=solution.exposure_coverage,
            urgency_coverage=solution.urgency_coverage,
            estimated_work_hours=solution.estimated_work_hours,
            business_objective=solution.business_objective,
            feasible=solution.feasible,
            checks=solution.checks,
            exclusion_reasons=solution.exclusion_reasons,
        )

    def decode_alert_selection(
        self,
        case_input: FraudRoutingInput,
        bits: tuple[int, ...],
    ) -> FraudRoutingSolution:
        """重新计算实体并行约束、覆盖率、工时和未选原因。"""
        if len(bits) != len(case_input.alerts):
            raise ValueError("bits must match the alert count.")
        selected_alerts = tuple(
            alert for alert, bit in zip(case_input.alerts, bits) if int(bit) == 1
        )
        entity_counts = Counter(alert.entity_id for alert in selected_alerts)
        checks = (
            ConstraintCheck(
                "investigator_slots",
                len(selected_alerts) == case_input.investigator_slots,
                str(len(selected_alerts)),
                str(case_input.investigator_slots),
            ),
            ConstraintCheck(
                "entity_parallel_cap",
                max(entity_counts.values(), default=0)
                <= case_input.entity_parallel_cap,
                str(max(entity_counts.values(), default=0)),
                f"<= {case_input.entity_parallel_cap}",
            ),
        )
        values = self.business_values(case_input)
        value_by_id = {
            alert.alert_id: values[index]
            for index, alert in enumerate(case_input.alerts)
        }
        selected_ids = tuple(alert.alert_id for alert in selected_alerts)
        selected_set = set(selected_ids)
        total_risk = sum(alert.risk_score for alert in case_input.alerts)
        total_exposure = sum(alert.exposure_m for alert in case_input.alerts)
        total_urgency = sum(alert.age_hours for alert in case_input.alerts)
        exclusion_reasons = self._exclusion_reasons(
            case_input, selected_set, entity_counts
        )
        return FraudRoutingSolution(
            bitstring="".join(str(int(bit)) for bit in bits),
            selected_alert_ids=selected_ids,
            risk_coverage=(
                sum(alert.risk_score for alert in selected_alerts) / total_risk
                if total_risk
                else 0.0
            ),
            exposure_coverage=(
                sum(alert.exposure_m for alert in selected_alerts) / total_exposure
                if total_exposure
                else 0.0
            ),
            urgency_coverage=(
                sum(alert.age_hours for alert in selected_alerts) / total_urgency
                if total_urgency
                else 0.0
            ),
            estimated_work_hours=sum(
                alert.estimated_hours for alert in selected_alerts
            ),
            business_objective=-sum(value_by_id[alert_id] for alert_id in selected_ids),
            feasible=all(check.passed for check in checks),
            checks=checks,
            exclusion_reasons=exclusion_reasons,
        )

    def business_values(self, case_input: FraudRoutingInput) -> tuple[float, ...]:
        """返回界面和 QUBO 共用的透明评分，避免展示口径与优化口径分离。"""
        risk = self._min_max(tuple(alert.risk_score for alert in case_input.alerts))
        exposure = self._min_max(tuple(alert.exposure_m for alert in case_input.alerts))
        urgency = self._min_max(tuple(alert.age_hours for alert in case_input.alerts))
        total_weight = (
            case_input.risk_weight
            + case_input.exposure_weight
            + case_input.urgency_weight
        )
        return tuple(
            (
                case_input.risk_weight * risk[index]
                + case_input.exposure_weight * exposure[index]
                + case_input.urgency_weight * urgency[index]
            )
            / total_weight
            for index in range(len(case_input.alerts))
        )

    @staticmethod
    def _alert_variable(_index: int, alert: FraudAlert) -> str:
        """生成实体优先的变量名，使真实共享实体冲突在确定性布局中相邻。"""
        # 中性原子映射器按稳定变量顺序布局。实体在前可让共享实体的业务变量
        # 更容易形成可映射的近邻，同时不会制造不存在的业务冲突。
        entity = alert.entity_id.lower().replace("-", "_")
        alert_id = alert.alert_id.lower().replace("-", "_")
        return f"alert_{entity}_{alert_id}"

    @staticmethod
    def _min_max(values: tuple[float, ...]) -> tuple[float, ...]:
        """把一组业务指标缩放到 0..1；常量指标统一保留为满分。"""
        low = min(values)
        spread = max(values) - low
        if spread <= 1e-15:
            return tuple(1.0 for _ in values)
        return tuple((value - low) / spread for value in values)

    @staticmethod
    def _conflict_pairs(
        case_input: FraudRoutingInput,
    ) -> tuple[tuple[str, str], ...]:
        """在单实体并行上限为一时生成同实体告警的两两冲突。"""
        if case_input.entity_parallel_cap >= 2:
            return ()
        by_entity: dict[str, list[str]] = {}
        for alert in case_input.alerts:
            by_entity.setdefault(alert.entity_id, []).append(alert.alert_id)
        return tuple(
            sorted(
                pair
                for alert_ids in by_entity.values()
                for pair in itertools.combinations(sorted(alert_ids), 2)
            )
        )

    def _exclusion_reasons(
        self,
        case_input: FraudRoutingInput,
        selected: set[str],
        entity_counts: Counter[str],
    ) -> dict[str, str]:
        """说明未选告警受实体并行上限、席位或目标排序中的哪项影响。"""
        reasons: dict[str, str] = {}
        for alert in case_input.alerts:
            if alert.alert_id in selected:
                continue
            if entity_counts[alert.entity_id] >= case_input.entity_parallel_cap:
                reasons[alert.alert_id] = f"实体 {alert.entity_id} 并行上限"
            elif len(selected) >= case_input.investigator_slots:
                reasons[alert.alert_id] = "调查席位已满"
            else:
                reasons[alert.alert_id] = "目标值未进入当前候选"
        return reasons
