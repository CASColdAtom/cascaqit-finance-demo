"""把金融领域模型适配为统一 Problem API 场景定义。

``PortfolioCase``、``SettlementCase`` 和 ``FraudRoutingCase`` 负责业务建模与
QUBO 系数；本模块不重复构造系数，只补充编译模式选择所需的金融语义：

- ``business_variables`` 标记可解码回业务对象的变量；
- ``auxiliary_variables`` 标记 slack 和其他罚项辅助位；
- ``term_groups`` 说明目标、全局约束、依赖和两两业务冲突分别来自哪里；
- ``analog_candidate_group_ids`` 明确哪些完整业务分组允许进入 Analog core；
- ``geometry_evidence`` 记录布局来源和预期 interaction，供模式顾问验证图保真。

只有显式列入 ``pairwise_conflict`` 的变量对才允许被模式顾问认定为 Analog
业务相互作用。这个限制避免把普通 QUBO 二次项误解为中性原子原生业务结构。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from cascaqit_finance_demo.cases.constrained_selection import (
    CollateralScenario,
    CreditLimitScenario,
    LiquidityScenario,
)
from cascaqit_finance_demo.cases.derivatives import DerivativesScenario
from cascaqit_finance_demo.cases.fraud_routing import FraudRoutingCase
from cascaqit_finance_demo.cases.portfolio import PortfolioCase
from cascaqit_finance_demo.cases.settlement import SettlementCase
from cascaqit_finance_demo.domain.problem_api import (
    FinanceGeometryEvidence,
    FinanceProblemDefinition,
    FinanceTermGroup,
    FinanceVQEAnsatzConfig,
    coefficient_contributions_from_problem,
)


def _isolated_pair_layout(
    variables: tuple[str, ...],
    pairs: tuple[tuple[str, str], ...],
) -> dict[str, tuple[float, float]] | None:
    """为互不重叠的业务冲突对生成无补边的本地参考布局。

    每个 pair 或单变量占一个 28 μm 网格单元；pair 两端相距 6 μm。当前
    Target 的 blockade 半径为 8 μm，因此同一 pair 产生 interaction，而相邻
    单元最近仍相距 22 μm。若输入出现共享端点，当前简单嵌入不能保证图保真，
    函数返回 ``None``，上层会保留 Digital 路径而不是伪造 Hybrid 几何。
    """
    known = set(variables)
    normalized = tuple(sorted(tuple(sorted(pair)) for pair in pairs))
    endpoints = tuple(variable for pair in normalized for variable in pair)
    if any(left == right for left, right in normalized):
        return None
    if not set(endpoints) <= known or len(set(endpoints)) != len(endpoints):
        return None

    units: list[tuple[str, ...]] = [tuple(pair) for pair in normalized]
    units.extend((variable,) for variable in sorted(known - set(endpoints)))
    if len(units) > 16:
        return None

    axis = (-42.0, -14.0, 14.0, 42.0)
    positions: dict[str, tuple[float, float]] = {}
    for index, unit in enumerate(units):
        center_x = axis[index % 4]
        center_y = axis[index // 4]
        if len(unit) == 2:
            positions[unit[0]] = (center_x - 3.0, center_y)
            positions[unit[1]] = (center_x + 3.0, center_y)
        else:
            positions[unit[0]] = (center_x, center_y)
    return positions


def _positioned_qubo_definition(
    problem: Any,
    *,
    candidate_pairs: tuple[tuple[str, str], ...],
) -> tuple[Any, FinanceGeometryEvidence | None]:
    """把已构建 QUBO 与经过图保真设计的完整参考布局绑定。"""
    positions = _isolated_pair_layout(tuple(problem.variables), candidate_pairs)
    if positions is None:
        return problem, None
    positioned = replace(
        problem,
        variable_positions=tuple(sorted(positions.items())),
    )
    candidate_set = {tuple(sorted(pair)) for pair in candidate_pairs}
    quadratic_pairs = {
        tuple(sorted((left, right)))
        for left, right, _coefficient in problem.quadratic_terms
    }
    evidence = FinanceGeometryEvidence(
        source="verified_embedding",
        coordinate_unit="um",
        positions=tuple(sorted(positions.items())),
        expected_interactions=tuple(sorted(candidate_set)),
        forbidden_interactions=tuple(sorted(quadratic_pairs - candidate_set)),
    )
    return positioned, evidence


class PortfolioScenario:
    """投资组合适配器：保留稠密市场目标和全局约束的 Digital 语义。

    协方差矩阵通常产生稠密的两两风险项，持仓数、行业上限和防御资产下限又是
    全局约束；这些结构不是少量可追溯的排斥边，因此默认使用 Digital QAOA。
    """
    case_id = "portfolio"
    title = "多资产投资组合优化"

    def __init__(self) -> None:
        """创建负责实际 QUBO 构建与解码的领域模型。"""
        self.case = PortfolioCase()

    def default_input(self) -> Any:
        """转发投资组合领域模型的默认输入。"""
        return self.case.default_input()

    def validate(self, case_input: Any) -> tuple[Any, ...]:
        """转发领域层验证，保持 API 场景协议一致。"""
        return self.case.validate(case_input)

    def build_definition(self, case_input: Any) -> FinanceProblemDefinition:
        """构建 QUBO，并标注目标、全局约束与辅助变量的业务分组。"""
        problem = self.case.build_problem(case_input)
        business = tuple(problem.metadata["business_variables"])
        auxiliary = tuple(
            variable for variable in problem.variables if variable not in business
        )
        return FinanceProblemDefinition(
            case_id=self.case_id,
            title=self.title,
            problem_kind="qubo",
            problem=problem,
            business_variables=business,
            auxiliary_variables=auxiliary,
            term_groups=(
                FinanceTermGroup("market", "收益与协方差", "objective", business),
                FinanceTermGroup(
                    "constraints", "持仓和行业约束", "global_constraint", business
                ),
                FinanceTermGroup("slack", "辅助罚项", "auxiliary_penalty", auxiliary),
            ),
            coefficient_contributions=coefficient_contributions_from_problem(problem),
            # 稠密协方差让首尾变量也存在直接耦合。单层 circular CX 使逻辑顺序
            # 形成闭环，同时把参数数控制在 12 个，适配当前最多 24 次评估。
            digital_algorithms=("qaoa", "vqe"),
            published_digital_algorithms=("qaoa",),
            vqe_ansatz=FinanceVQEAnsatzConfig(
                rotation_axes=("ry",),
                entanglement="circular",
                max_layers=1,
            ),
        )

    def decode(
        self, case_input: Any, definition: FinanceProblemDefinition, candidate: Any
    ) -> Any:
        """将统一执行候选交回投资组合领域模型解码。"""
        return self.case.decode(case_input, definition.problem, candidate)


class SettlementScenario:
    """交易结算适配器：冲突项走 Analog，其余约束保留为 Digital。

    Hybrid D-A-D（Digital-Analog-Digital）中，前段 Digital 准备优化状态，中段
    Analog 用原子相互作用表达交易互斥边，后段 Digital 继续承担流动性、批次
    上限和有向依赖等 residual（剩余项）。如果布局不能支持真实冲突边，模式
    顾问会降回 Digital，而不是制造一段没有业务含义的 Analog 演化。
    """
    case_id = "settlement"
    title = "交易结算批次优化"

    def __init__(self) -> None:
        """创建交易结算 QUBO 领域模型。"""
        self.case = SettlementCase()

    def default_input(self) -> Any:
        """返回默认结算批次及流动性配置。"""
        return self.case.default_input()

    def validate(self, case_input: Any) -> tuple[Any, ...]:
        """验证交易标识、依赖、冲突和容量约束。"""
        return self.case.validate(case_input)

    def build_definition(self, case_input: Any) -> FinanceProblemDefinition:
        """构建带可追溯交易冲突对的 Hybrid Problem 定义。"""
        problem = self.case.build_problem(case_input)
        business = tuple(problem.metadata["business_variables"])
        auxiliary = tuple(
            variable for variable in problem.variables if variable not in business
        )
        by_id = {
            item.trade_id: index for index, item in enumerate(case_input.instructions)
        }
        conflict_pairs = tuple(
            (
                self.case._trade_variable(
                    by_id[left], case_input.instructions[by_id[left]]
                ),
                self.case._trade_variable(
                    by_id[right], case_input.instructions[by_id[right]]
                ),
            )
            for left, right in self.case._conflict_pairs(case_input)
        )
        problem, geometry = _positioned_qubo_definition(
            problem,
            candidate_pairs=conflict_pairs,
        )
        return FinanceProblemDefinition(
            case_id=self.case_id,
            title=self.title,
            problem_kind="qubo",
            problem=problem,
            business_variables=business,
            auxiliary_variables=auxiliary,
            term_groups=(
                FinanceTermGroup("value", "金额与优先级", "objective", business),
                FinanceTermGroup(
                    "conflicts", "交易冲突", "pairwise_conflict", pairs=conflict_pairs
                ),
                FinanceTermGroup("dependencies", "依赖关系", "dependency", business),
                FinanceTermGroup(
                    "liquidity", "流动性和批次约束", "global_constraint", business
                ),
                FinanceTermGroup(
                    "slack", "额度辅助变量", "auxiliary_penalty", auxiliary
                ),
            ),
            coefficient_contributions=coefficient_contributions_from_problem(problem),
            analog_candidate_group_ids=("conflicts",) if conflict_pairs else (),
            geometry_evidence=geometry,
        )

    def decode(
        self, case_input: Any, definition: FinanceProblemDefinition, candidate: Any
    ) -> Any:
        """将候选位串解码为结算选择并重新核算全部约束。"""
        return self.case.decode(case_input, definition.problem, candidate)


class FraudRoutingScenario:
    """反欺诈适配器：共享实体冲突可由中性原子相互作用表达。

    同一实体的告警在并行上限为一时形成明确的排斥边，适合交给 Analog
    interaction；调查席位数和告警价值仍是 Digital 项。因此推荐 Hybrid，且
    Analog 部分的每条边都能追溯到具体实体冲突。
    """
    case_id = "fraud_routing"
    title = "反欺诈调查任务编排"

    def __init__(self) -> None:
        """创建告警调查任务编排的 QUBO 领域模型。"""
        self.case = FraudRoutingCase()

    def default_input(self) -> Any:
        """返回带共享实体冲突的默认告警集合。"""
        return self.case.default_input()

    def validate(self, case_input: Any) -> tuple[Any, ...]:
        """验证告警数据、调查席位和实体并行上限。"""
        return self.case.validate(case_input)

    def build_definition(self, case_input: Any) -> FinanceProblemDefinition:
        """构建 Hybrid 定义，并把共享实体冲突映射回业务变量对。"""
        problem = self.case.build_problem(case_input)
        business = tuple(problem.metadata["business_variables"])
        auxiliary = tuple(
            variable for variable in problem.variables if variable not in business
        )
        by_id = {item.alert_id: index for index, item in enumerate(case_input.alerts)}
        conflict_pairs = tuple(
            (
                self.case._alert_variable(by_id[left], case_input.alerts[by_id[left]]),
                self.case._alert_variable(
                    by_id[right], case_input.alerts[by_id[right]]
                ),
            )
            for left, right in self.case._conflict_pairs(case_input)
        )
        problem, geometry = _positioned_qubo_definition(
            problem,
            candidate_pairs=conflict_pairs,
        )
        return FinanceProblemDefinition(
            case_id=self.case_id,
            title=self.title,
            problem_kind="qubo",
            problem=problem,
            business_variables=business,
            auxiliary_variables=auxiliary,
            term_groups=(
                FinanceTermGroup("value", "风险、金额和时效", "objective", business),
                FinanceTermGroup(
                    "conflicts",
                    "共享实体冲突",
                    "pairwise_conflict",
                    pairs=conflict_pairs,
                ),
                FinanceTermGroup("capacity", "调查席位", "global_constraint", business),
                FinanceTermGroup(
                    "slack", "席位辅助变量", "auxiliary_penalty", auxiliary
                ),
            ),
            coefficient_contributions=coefficient_contributions_from_problem(problem),
            analog_candidate_group_ids=("conflicts",) if conflict_pairs else (),
            geometry_evidence=geometry,
            metadata={"decision_scope": "investigation routing only"},
        )

    def decode(
        self, case_input: Any, definition: FinanceProblemDefinition, candidate: Any
    ) -> Any:
        """解码候选并计算风险、敞口和时效覆盖率。"""
        return self.case.decode(case_input, definition.problem, candidate)


PROBLEM_SCENARIOS = {
    "portfolio": PortfolioScenario(),
    "settlement": SettlementScenario(),
    "fraud_routing": FraudRoutingScenario(),
    "collateral": CollateralScenario(),
    "liquidity": LiquidityScenario(),
    "credit_limits": CreditLimitScenario(),
    "derivatives": DerivativesScenario(),
}
