"""经典衍生品定价与独立 Analog 风险情景网格实验。

定价由经典模型完成；量子图问题只选择相互差异足够大的代表性风险情景，
两条链路在结果中并列展示但不互相冒充。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cascaqit import GraphProblemIR

from cascaqit_finance_demo.domain.models import CaseIssue, ConstraintCheck
from cascaqit_finance_demo.domain.problem_api import (
    FinanceProblemDefinition,
    FinanceTermGroup,
)
from cascaqit_finance_demo.pricing import (
    DerivativeInput,
    DerivativePricingResult,
    price_derivative,
)


@dataclass(frozen=True)
class RiskScenarioSelection:
    """独立集实验解码出的代表性风险情景及覆盖范围。"""

    bitstring: str
    selected_scenario_ids: tuple[str, ...]
    selected_shocks: tuple[tuple[float, float], ...]
    coverage_count: int
    feasible: bool
    checks: tuple[ConstraintCheck, ...]


class DerivativesScenario:
    """将经典参考定价与 Analog 风险情景选择保持为边界清晰的两条链路。"""

    case_id = "derivatives"
    title = "衍生品定价与风险情景"
    spot_shocks = (-0.12, 0.0, 0.12)
    volatility_shocks = (-0.08, 0.0, 0.08)

    def default_input(self) -> DerivativeInput:
        """返回可确定性复现的默认产品和市场参数。"""
        return DerivativeInput()

    def validate(self, case_input: DerivativeInput) -> tuple[CaseIssue, ...]:
        """复用定价器的完整校验，并转换为场景统一问题格式。"""
        try:
            price_derivative(case_input)
        except ValueError as exc:
            return (CaseIssue("DERIVATIVE_INPUT_INVALID", "pricing", str(exc)),)
        return ()

    def price(self, case_input: DerivativeInput) -> DerivativePricingResult:
        """运行经典参考定价，不读取任何量子计数。"""
        return price_derivative(case_input)

    def build_definition(self, case_input: DerivativeInput) -> FinanceProblemDefinition:
        """构建 3×3 风险冲击网格的最大独立集 Analog Problem。"""
        issues = self.validate(case_input)
        if issues:
            raise ValueError("; ".join(issue.message for issue in issues))
        nodes = tuple(
            self._node_id(row, column) for row in range(3) for column in range(3)
        )
        positions = {
            self._node_id(row, column): (float(column) * 6.0, float(row) * 6.0)
            for row in range(3)
            for column in range(3)
        }
        edges = []
        for row in range(3):
            for column in range(3):
                node = self._node_id(row, column)
                if column < 2:
                    edges.append((node, self._node_id(row, column + 1)))
                if row < 2:
                    edges.append((node, self._node_id(row + 1, column)))
        problem = GraphProblemIR.from_edges(
            problem_id="finance.derivatives.risk_grid",
            nodes=nodes,
            edges=edges,
            positions=positions,
            metadata={
                "case_id": self.case_id,
                "role": "representative risk scenario selection",
                "pricing_source": "classic_reference_only",
            },
        )
        return FinanceProblemDefinition(
            case_id=self.case_id,
            title=self.title,
            problem_kind="graph",
            problem=problem,
            preferred_mode="analog",
            business_variables=problem.nodes,
            term_groups=(
                FinanceTermGroup(
                    "similarity",
                    "相邻风险情景",
                    "pairwise_conflict",
                    pairs=problem.edges,
                ),
            ),
            metadata={"counts_feed_pricing": False},
        )

    def decode(
        self,
        case_input: DerivativeInput,
        definition: FinanceProblemDefinition,
        candidate: Any,
    ) -> RiskScenarioSelection:
        """把节点位串还原为风险冲击，并检查相邻情景不能同时入选。"""
        del case_input
        bitstring = str(candidate.bitstring)
        if len(bitstring) != len(definition.problem.nodes):
            raise ValueError("candidate bitstring does not match scenario nodes.")
        selected = tuple(
            node for node, bit in zip(definition.problem.nodes, bitstring) if bit == "1"
        )
        selected_set = set(selected)
        violations = tuple(
            edge
            for edge in definition.problem.edges
            if edge[0] in selected_set and edge[1] in selected_set
        )
        covered = set(selected)
        for left, right in definition.problem.edges:
            if left in selected_set:
                covered.add(right)
            if right in selected_set:
                covered.add(left)
        checks = (
            ConstraintCheck(
                "independent_scenarios",
                not violations,
                str(len(violations)),
                "0",
            ),
        )
        return RiskScenarioSelection(
            bitstring=bitstring,
            selected_scenario_ids=selected,
            selected_shocks=tuple(self._shocks(node) for node in selected),
            coverage_count=len(covered),
            feasible=not violations,
            checks=checks,
        )

    @staticmethod
    def _node_id(row: int, column: int) -> str:
        """由网格行列生成稳定的风险情景节点标识。"""
        return f"risk_{row}_{column}"

    def _shocks(self, node: str) -> tuple[float, float]:
        """将节点标识还原为标的价格冲击和波动率冲击。"""
        _, row, column = node.split("_")
        return self.spot_shocks[int(column)], self.volatility_shocks[int(row)]
