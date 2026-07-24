"""七个金融场景的领域模型和统一 Problem API 适配器。"""

from cascaqit_finance_demo.cases.base import FinanceOptimizationCase
from cascaqit_finance_demo.cases.constrained_selection import (
    CollateralScenario,
    CreditLimitScenario,
    LiquidityScenario,
)
from cascaqit_finance_demo.cases.derivatives import DerivativesScenario
from cascaqit_finance_demo.cases.fraud_routing import FraudRoutingCase
from cascaqit_finance_demo.cases.portfolio import PortfolioCase
from cascaqit_finance_demo.cases.problem_scenarios import (
    FraudRoutingScenario,
    PortfolioScenario,
    SettlementScenario,
)
from cascaqit_finance_demo.cases.settlement import SettlementCase

__all__ = [
    "CollateralScenario",
    "CreditLimitScenario",
    "DerivativesScenario",
    "FinanceOptimizationCase",
    "FraudRoutingCase",
    "FraudRoutingScenario",
    "LiquidityScenario",
    "PortfolioCase",
    "PortfolioScenario",
    "SettlementCase",
    "SettlementScenario",
]
