"""把金融侧 QUBO 模型适配为统一 Problem API 场景定义。"""

from __future__ import annotations

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
    FinanceProblemDefinition,
    FinanceTermGroup,
)


class PortfolioScenario:
    """投资组合适配器：保留稠密市场目标和全局约束的 Digital 语义。"""
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
            preferred_mode="digital",
            business_variables=business,
            auxiliary_variables=auxiliary,
            term_groups=(
                FinanceTermGroup("market", "收益与协方差", "objective", business),
                FinanceTermGroup(
                    "constraints", "持仓和行业约束", "global_constraint", business
                ),
                FinanceTermGroup("slack", "辅助罚项", "auxiliary_penalty", auxiliary),
            ),
        )

    def decode(
        self, case_input: Any, definition: FinanceProblemDefinition, candidate: Any
    ) -> Any:
        """将统一执行候选交回投资组合领域模型解码。"""
        return self.case.decode(case_input, definition.problem, candidate)


class SettlementScenario:
    """交易结算适配器：冲突项走 Analog，其余约束保留为 Digital。"""
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
        return FinanceProblemDefinition(
            case_id=self.case_id,
            title=self.title,
            problem_kind="qubo",
            problem=problem,
            preferred_mode="hybrid",
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
        )

    def decode(
        self, case_input: Any, definition: FinanceProblemDefinition, candidate: Any
    ) -> Any:
        """将候选位串解码为结算选择并重新核算全部约束。"""
        return self.case.decode(case_input, definition.problem, candidate)


class FraudRoutingScenario:
    """反欺诈适配器：共享实体冲突可由中性原子相互作用表达。"""
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
        return FinanceProblemDefinition(
            case_id=self.case_id,
            title=self.title,
            problem_kind="qubo",
            problem=problem,
            preferred_mode="hybrid",
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
