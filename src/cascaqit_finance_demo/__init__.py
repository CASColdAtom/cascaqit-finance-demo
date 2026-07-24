"""基于 CASCAQit 统一 Problem API 构建的金融量子实验集合。

顶层包只暴露场景和执行入口，具体金融建模、编译策略与展示转换分别由
``cases``、``quantum`` 和 ``api`` 子包负责。
"""

from cascaqit_finance_demo.cases.constrained_selection import (
    CollateralScenario,
    CreditLimitScenario,
    LiquidityScenario,
)
from cascaqit_finance_demo.cases.derivatives import DerivativesScenario
from cascaqit_finance_demo.cases.problem_scenarios import (
    FraudRoutingScenario,
    PortfolioScenario,
    SettlementScenario,
)
from cascaqit_finance_demo.quantum import FinanceModeAdvisor, ScenarioExecutor

__all__ = [
    "CollateralScenario",
    "CreditLimitScenario",
    "DerivativesScenario",
    "FinanceModeAdvisor",
    "FraudRoutingScenario",
    "LiquidityScenario",
    "PortfolioScenario",
    "ScenarioExecutor",
    "SettlementScenario",
]
