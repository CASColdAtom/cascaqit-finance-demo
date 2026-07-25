"""经典衍生品定价与独立 Analog 风险情景网格实验。

这个场景包含两条边界明确的计算链路：

1. 经典链路根据产品类型运行 Black-Scholes、二叉树或固定随机种子的 Monte
   Carlo，得到价格与 Greeks；
2. Analog 链路把“标的价格冲击 × 波动率冲击”的 3×3 网格建成带权图，按
   绝对 P&L 权重选择彼此不相邻的风险情景。

图中每个节点是一组冲击，横向或纵向相邻表示两个情景只相差一个冲击档位。
最大带权独立集要求相邻节点不能同时入选，并尽量提高入选节点的风险权重总和。
该图可映射到中性原子阵列：节点对应原子 site，边对应需要阻塞的近邻关系，
节点权重进入局域失谐，QAA 通过 Analog Hamiltonian（模拟哈密顿量）演化采样
独立集候选。

量子计数只回答“选择哪些风险情景”，不参与期权价格或 Greeks 的计算。这样
可以展示 Analog 图优化，同时避免把风险情景选择误称为量子衍生品定价。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from cascaqit.problems import MWISProblemIR

from cascaqit_finance_demo.domain.models import CaseIssue, ConstraintCheck
from cascaqit_finance_demo.domain.problem_api import (
    FinanceGeometryEvidence,
    FinanceProblemDefinition,
    FinanceTermGroup,
)
from cascaqit_finance_demo.pricing import (
    DerivativeInput,
    DerivativePricingResult,
    price_derivative,
)


@dataclass(frozen=True)
class DerivativeRiskScenario:
    """一个可审计的产品重估情景及其 MWIS 风险权重。

    ``pnl``、Greeks 和 ``normalized_risk_weight`` 全部来自同一次压力重估。
    权重只控制风险情景选择，不会反向修改经典参考价格。
    """

    scenario_id: str
    row: int
    column: int
    spot_shock: float
    volatility_shock: float
    stressed_spot: float
    stressed_volatility: float
    stressed_price: float
    pnl: float
    delta: float
    gamma: float
    vega: float
    normalized_risk_weight: float


@dataclass(frozen=True)
class RiskScenarioSelection:
    """独立集实验解码出的代表性风险情景及覆盖范围。"""

    bitstring: str
    selected_scenario_ids: tuple[str, ...]
    selected_shocks: tuple[tuple[float, float], ...]
    selected_scenarios: tuple[DerivativeRiskScenario, ...]
    selected_risk_weight: float
    coverage_count: int
    feasible: bool
    checks: tuple[ConstraintCheck, ...]


class DerivativesScenario:
    """将经典参考定价与 Analog 风险情景选择保持为边界清晰的两条链路。

    3×3 网格使用固定的 ±12% 标的价格冲击和 ±8% 波动率冲击。冲击只是演示
    情景，不是由历史数据校准的监管压力参数。
    """

    case_id = "derivatives"
    title = "衍生品定价与风险情景"
    spot_shocks = (-0.12, 0.0, 0.12)
    volatility_shocks = (-0.08, 0.0, 0.08)
    risk_weight_floor = 0.05

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

    def risk_scenarios(
        self,
        case_input: DerivativeInput,
    ) -> tuple[DerivativeRiskScenario, ...]:
        """重估九个压力格点，并生成严格为正的相对风险权重。

        权重以绝对 P&L 为唯一主项，再归一化到 ``[0.05, 1.0]``。下限保证基准
        格点也满足 MWIS 的正权重契约；上限保留不同产品之间可比较的 Analog
        控制尺度。若所有格点 P&L 都为零，则九个节点使用相同权重。

        对向上敲出期权，如果压力后的初始标的价格已经达到障碍，则产品在情景
        起点即敲出，价格与局部 Greeks 按零处理，避免把无效市场状态送入定价器。
        """
        issues = self.validate(case_input)
        if issues:
            raise ValueError("; ".join(issue.message for issue in issues))
        base_price = self.price(case_input).reference_price
        revaluations: list[DerivativeRiskScenario] = []
        for row, volatility_shock in enumerate(self.volatility_shocks):
            for column, spot_shock in enumerate(self.spot_shocks):
                stressed_spot = case_input.spot * (1.0 + spot_shock)
                stressed_volatility = max(
                    0.01,
                    case_input.volatility + volatility_shock,
                )
                knocked_out_at_start = (
                    case_input.product == "up_and_out_call"
                    and stressed_spot >= case_input.barrier
                )
                if knocked_out_at_start:
                    stressed_price = delta = gamma = vega = 0.0
                else:
                    priced = self.price(
                        replace(
                            case_input,
                            spot=stressed_spot,
                            volatility=stressed_volatility,
                        )
                    )
                    stressed_price = priced.reference_price
                    delta = priced.delta
                    gamma = priced.gamma
                    vega = priced.vega
                pnl = stressed_price - base_price
                revaluations.append(
                    DerivativeRiskScenario(
                        scenario_id=self._node_id(row, column),
                        row=row,
                        column=column,
                        spot_shock=spot_shock,
                        volatility_shock=volatility_shock,
                        stressed_spot=stressed_spot,
                        stressed_volatility=stressed_volatility,
                        stressed_price=stressed_price,
                        pnl=pnl,
                        delta=delta,
                        gamma=gamma,
                        vega=vega,
                        # 先保存完整重估事实，下一步按全网格最大绝对 P&L 归一化。
                        normalized_risk_weight=1.0,
                    )
                )

        maximum_absolute_pnl = max(abs(item.pnl) for item in revaluations)
        return tuple(
            replace(
                item,
                normalized_risk_weight=(
                    1.0
                    if maximum_absolute_pnl == 0.0
                    else self.risk_weight_floor
                    + (1.0 - self.risk_weight_floor)
                    * abs(item.pnl)
                    / maximum_absolute_pnl
                ),
            )
            for item in revaluations
        )

    def build_definition(self, case_input: DerivativeInput) -> FinanceProblemDefinition:
        """构建 3×3 风险冲击网格的最大带权独立集 Analog Problem。

        九个节点按 6 个抽象距离单位排成方格，只连接上下左右近邻，不连接对角
        节点。``MWISProblemIR`` 的节点权重来自当前产品九格重估的绝对 P&L；
        编译器将权重映射到局域失谐，将边映射到原子相互作用。
        """
        risk_scenarios = self.risk_scenarios(case_input)
        positions = {
            self._node_id(row, column): (float(column) * 6.0, float(row) * 6.0)
            for row in range(3)
            for column in range(3)
        }
        # 每条无向边表示两个过于相似的风险情景不能同时成为代表情景。
        edges = []
        for row in range(3):
            for column in range(3):
                node = self._node_id(row, column)
                if column < 2:
                    edges.append((node, self._node_id(row, column + 1)))
                if row < 2:
                    edges.append((node, self._node_id(row + 1, column)))
        problem = MWISProblemIR.from_edges(
            problem_id="finance.derivatives.risk_grid",
            node_weights={
                item.scenario_id: item.normalized_risk_weight
                for item in risk_scenarios
            },
            edges=edges,
            positions=positions,
            metadata={
                "case_id": self.case_id,
                "role": "risk-prioritized independent scenario selection",
                "pricing_source": "classic_reference_only",
                "node_weight_source": "normalized_absolute_stressed_pnl",
                "risk_weight_floor": self.risk_weight_floor,
            },
        )
        return FinanceProblemDefinition(
            case_id=self.case_id,
            title=self.title,
            problem_kind="mwis",
            problem=problem,
            business_variables=problem.nodes,
            term_groups=(
                FinanceTermGroup(
                    "risk_priority",
                    "压力损益风险权重",
                    "objective",
                    variables=problem.nodes,
                ),
                FinanceTermGroup(
                    "similarity",
                    "相邻风险情景",
                    "pairwise_conflict",
                    pairs=problem.edges,
                ),
            ),
            analog_candidate_group_ids=("similarity",),
            geometry_evidence=FinanceGeometryEvidence(
                source="business_native",
                coordinate_unit="um",
                positions=problem.node_positions,
                expected_interactions=problem.edges,
            ),
            metadata={
                "counts_feed_pricing": False,
                "risk_weight_source": "normalized_absolute_stressed_pnl",
            },
        )

    def decode(
        self,
        case_input: DerivativeInput,
        definition: FinanceProblemDefinition,
        candidate: Any,
    ) -> RiskScenarioSelection:
        """把节点位串还原为风险冲击，并检查相邻情景不能同时入选。

        ``coverage_count`` 统计“已选节点及其一跳邻居”的数量，用于说明代表
        情景覆盖了多少网格节点。它不是概率、价格误差或风险覆盖百分比。
        """
        risk_scenarios = {
            item.scenario_id: item for item in self.risk_scenarios(case_input)
        }
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
            selected_scenarios=tuple(risk_scenarios[node] for node in selected),
            selected_risk_weight=sum(
                risk_scenarios[node].normalized_risk_weight for node in selected
            ),
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
