"""金融场景与展示层共享的强类型输入、约束检查和业务结果模型。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class CaseIssue:
    """一条可定位到稳定字段路径的输入问题，供 API 和界面统一展示。"""

    code: str
    field: str
    message: str


@dataclass(frozen=True)
class AssetInput:
    """投资组合实验中的一项合成资产及其收益、风险和行业属性。"""

    asset_id: str
    name: str
    sector: str
    expected_return: float
    volatility: float
    defensive: bool = False


@dataclass(frozen=True)
class PortfolioInput:
    """投资组合选择的规范化输入，包含市场数据、组合规模和业务约束。"""

    assets: tuple[AssetInput, ...]
    covariance: tuple[tuple[float, ...], ...]
    selected_count: int = 4
    risk_weight: float = 0.55
    sector_cap: int = 2
    minimum_defensive: int = 1
    penalty_multiplier: float = 2.0


@dataclass(frozen=True)
class ConstraintCheck:
    """从解码后的业务选择重新计算的一条约束检查，而非直接信任量子结果。"""

    name: str
    passed: bool
    actual: str
    expected: str


@dataclass(frozen=True)
class PortfolioPoint:
    """一组可行的等权重资产组合，用作有效前沿图点和经典基线。"""

    bitstring: str
    asset_ids: tuple[str, ...]
    expected_return: float
    volatility: float
    objective_value: float


@dataclass(frozen=True)
class PortfolioSolution:
    """量子候选解解码后的投资组合，并携带独立复核的业务指标与约束。"""

    bitstring: str
    selected_asset_ids: tuple[str, ...]
    expected_return: float
    volatility: float
    objective_value: float
    feasible: bool
    checks: tuple[ConstraintCheck, ...]


@dataclass(frozen=True)
class ExecutionEvidence:
    """执行审计证据，明确后端、随机种子、耗时及是否访问硬件或网络。"""

    backend: str
    execution_kind: Literal["local_simulation", "hardware", "cloud"]
    result_hash: str
    seed: int
    shots: int
    wall_time_seconds: float
    hardware_execution: bool
    cloud_execution: bool
    network_accessed: bool


@dataclass(frozen=True)
class TradeInstruction:
    """一条合成结算指令，记录业务价值、离散流动性消耗、依赖和冲突。"""

    trade_id: str
    currency: str
    notional_m: float
    priority: int
    cash_units: int
    requires: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()


@dataclass(frozen=True)
class LiquidityLimit:
    """一个币种桶的整数流动性上限，用于构造可精确编码的 QUBO 约束。"""

    currency: str
    capacity_units: int


@dataclass(frozen=True)
class SettlementInput:
    """一次批量结算优化的业务输入和目标权重。"""

    instructions: tuple[TradeInstruction, ...]
    liquidity_limits: tuple[LiquidityLimit, ...]
    batch_cap: int = 7
    notional_weight: float = 0.6
    priority_weight: float = 0.4
    penalty_multiplier: float = 2.0


@dataclass(frozen=True)
class SettlementSolution:
    """解码后的结算候选，包含重新核算的流动性、依赖、冲突与批量上限。"""

    bitstring: str
    selected_trade_ids: tuple[str, ...]
    settled_notional_m: float
    business_objective: float
    liquidity_used: Mapping[str, int]
    feasible: bool
    checks: tuple[ConstraintCheck, ...]
    exclusion_reasons: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FraudAlert:
    """一条等待分配调查资源的合成反欺诈告警。"""

    alert_id: str
    risk_score: float
    exposure_m: float
    age_hours: float
    entity_id: str
    estimated_hours: float


@dataclass(frozen=True)
class FraudRoutingInput:
    """在有限调查席位下进行告警编排所需的输入、权重和并行约束。"""

    alerts: tuple[FraudAlert, ...]
    investigator_slots: int = 4
    risk_weight: float = 0.5
    exposure_weight: float = 0.3
    urgency_weight: float = 0.2
    entity_parallel_cap: int = 1
    penalty_multiplier: float = 2.0


@dataclass(frozen=True)
class FraudRoutingSolution:
    """解码后的调查编排候选，包含重新计算的风险、敞口与时效覆盖率。"""

    bitstring: str
    selected_alert_ids: tuple[str, ...]
    risk_coverage: float
    exposure_coverage: float
    urgency_coverage: float
    estimated_work_hours: float
    business_objective: float
    feasible: bool
    checks: tuple[ConstraintCheck, ...]
    exclusion_reasons: Mapping[str, str] = field(default_factory=dict)
