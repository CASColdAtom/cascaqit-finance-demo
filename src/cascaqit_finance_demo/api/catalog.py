"""场景导航元数据、前端控件契约和确定性业务输入构造。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Literal

from cascaqit_finance_demo.cases.constrained_selection import SelectionInput
from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS

ControlKind = Literal["range", "select"]
SearchStrategy = Literal["preset", "grid", "seeded_sample", "continuous"]
Algorithm = Literal["recommended", "qaoa", "vqe", "qaa"]
LayerPolicy = Literal["fixed", "adaptive"]


@dataclass(frozen=True)
class ControlSpec:
    """一个映射到场景输入字段的前端控件定义。"""

    key: str
    label: str
    kind: ControlKind
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    options: tuple[tuple[str, str], ...] = ()
    unit: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为与 TypeScript 类型一致且可直接 JSON 序列化的字典。"""
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
            "options": [
                {"value": value, "label": label} for value, label in self.options
            ],
            "unit": self.unit,
        }


@dataclass(frozen=True)
class ExecutionProfile:
    """场景在默认输入下经过确定性验收的执行参数。"""

    shots: int = 32
    seed: int = 23
    algorithm: Algorithm = "recommended"
    layer_policy: LayerPolicy = "fixed"
    layers: int = 1
    max_layers: int = 3
    min_improvement: float = 0.0
    search_strategy: SearchStrategy = "preset"
    parameter_budget: int = 2
    optimizer_starts: int = 1
    repeats: int = 1

    def to_dict(self) -> dict[str, int | float | str]:
        """使用前端约定的驼峰字段输出推荐配置。"""
        return {
            "shots": self.shots,
            "seed": self.seed,
            "algorithm": self.algorithm,
            "layerPolicy": self.layer_policy,
            "layers": self.layers,
            "maxLayers": self.max_layers,
            "minImprovement": self.min_improvement,
            "searchStrategy": self.search_strategy,
            "parameterBudget": self.parameter_budget,
            "optimizerStarts": self.optimizer_starts,
            "repeats": self.repeats,
        }


@dataclass(frozen=True)
class ScenarioSpec:
    """一个金融场景稳定的导航、说明、预设和控件元数据。"""

    case_id: str
    short_title: str
    title: str
    eyebrow: str
    description: str
    icon: str
    accent: Literal["cyan", "emerald", "amber"]
    presets: tuple[tuple[str, str], ...]
    controls: tuple[ControlSpec, ...]
    recommended_execution: ExecutionProfile = ExecutionProfile()
    vqe_execution: ExecutionProfile | None = None

    def execution_for(self, algorithm: Algorithm) -> ExecutionProfile:
        """返回算法专属默认值，避免 VQE 继承不兼容的 QAOA 参数策略。"""
        if algorithm == "vqe" and self.vqe_execution is not None:
            return self.vqe_execution
        return self.recommended_execution

    def to_dict(
        self, *, values: dict[str, Any], recommended_mode: str
    ) -> dict[str, Any]:
        """合并静态场景说明、当前控件值和实时推荐模式。"""
        return {
            "domainId": "finance",
            "caseId": self.case_id,
            "shortTitle": self.short_title,
            "title": self.title,
            "eyebrow": self.eyebrow,
            "description": self.description,
            "icon": self.icon,
            "accent": self.accent,
            "presets": [
                {"value": value, "label": label} for value, label in self.presets
            ],
            "controls": [control.to_dict() for control in self.controls],
            "values": values,
            "recommendedMode": recommended_mode,
            "recommendedExecution": self.recommended_execution.to_dict(),
            "executionFamily": "problem",
            "resultKind": "finance_optimization",
            "visualKind": "finance",
            "capabilities": ["analysis", "execution", "comparison", "audit"],
            "implementationStatus": "available",
        }


def _select(key: str, label: str, values: tuple[str, ...]) -> ControlSpec:
    """用值本身作为标签快速构造枚举选择控件。"""
    return ControlSpec(
        key,
        label,
        "select",
        options=tuple((value, value) for value in values),
    )


def _range(
    key: str,
    label: str,
    minimum: float,
    maximum: float,
    step: float,
    unit: str = "",
) -> ControlSpec:
    """构造带上下限、步长和可选单位的数值滑块控件。"""
    return ControlSpec(key, label, "range", minimum, maximum, step, unit=unit)


SCENARIO_SPECS: dict[str, ScenarioSpec] = {
    "portfolio": ScenarioSpec(
        "portfolio",
        "投资组合",
        "多资产投资组合优化",
        "DENSE COVARIANCE",
        "在收益、风险、行业集中度与防御资产下限之间选择等权资产组合。",
        "chart-no-axes-combined",
        "cyan",
        (
            ("base", "基准市场"),
            ("rates", "利率上行"),
            ("drawdown", "权益回撤"),
            ("commodity", "商品冲击"),
        ),
        (
            _range("risk_weight", "风险权重", 0.2, 0.85, 0.05),
            _select("selected_count", "持仓数量", ("3", "4", "5")),
            _select("sector_cap", "单行业上限", ("1", "2", "3")),
            _select("minimum_defensive", "防御资产下限", ("0", "1", "2")),
        ),
        # 两个起点都保留完整优化证据：第一个从已验收参数开始，第二个按 seed
        # 生成。每起点 12 次目标评估让四个预设在三次独立运行中均采到可行候选。
        ExecutionProfile(
            search_strategy="continuous",
            parameter_budget=12,
            optimizer_starts=2,
        ),
        vqe_execution=ExecutionProfile(
            shots=64,
            algorithm="vqe",
            max_layers=1,
            search_strategy="continuous",
            parameter_budget=14,
        ),
    ),
    "settlement": ScenarioSpec(
        "settlement",
        "交易结算",
        "交易结算批次优化",
        "CONFLICT GRAPH + LIQUIDITY",
        "将局域交易冲突交给原子相互作用，同时保留依赖与流动性数字约束。",
        "landmark",
        "emerald",
        (
            ("base", "日常批次"),
            ("priority", "重点客户优先"),
        ),
        (
            _range("notional_weight", "金额权重", 0.2, 0.8, 0.05),
            _range("priority_weight", "优先级权重", 0.2, 0.8, 0.05),
            _select("batch_cap", "批次上限", ("5", "6", "7", "8")),
            _range("penalty", "约束罚项倍数", 1.2, 3.5, 0.1),
        ),
    ),
    "fraud_routing": ScenarioSpec(
        "fraud_routing",
        "调查编排",
        "反欺诈调查任务编排",
        "ENTITY COLLISION ROUTING",
        "在有限调查席位下优先覆盖高风险、高金额和高时效告警。",
        "scan-search",
        "amber",
        (
            ("base", "账户接管"),
            ("ring", "团伙交易"),
            ("merchant", "商户异常"),
        ),
        (
            _range("risk_weight", "风险权重", 0.1, 0.8, 0.05),
            _range("exposure_weight", "金额权重", 0.1, 0.8, 0.05),
            _range("urgency_weight", "时效权重", 0.1, 0.8, 0.05),
            _select("slots", "调查席位", ("3", "4", "5", "6")),
            _select("entity_cap", "单实体并行上限", ("1", "2")),
        ),
    ),
    "collateral": ScenarioSpec(
        "collateral",
        "抵押品",
        "抵押品分配优化",
        "ELIGIBILITY + COVERAGE",
        "在资格、批次唯一性、覆盖价值和融资成本之间选择分配组合。",
        "layers-3",
        "cyan",
        (("base", "日常补缴"), ("haircut", "市场波动"), ("hqla", "保留优质资产")),
        (
            _range("value_weight", "业务价值权重", 0.2, 0.85, 0.05),
            _range("cost_weight", "成本权重", 0.15, 0.8, 0.05),
        ),
        # 正式 CASCAQit v1.0.5a wheel 下，三个预设使用 seeds 1/11/19 校准后，
        # 单起点 12 次 COBYLA 评估均直接产生可行业务候选。
        ExecutionProfile(
            shots=64,
            seed=19,
            search_strategy="continuous",
            parameter_budget=12,
        ),
        vqe_execution=ExecutionProfile(
            shots=64,
            algorithm="vqe",
            # 该默认预算只覆盖 p=1；p=2 需要调用方同时把预算提高到至少 18。
            max_layers=1,
            search_strategy="continuous",
            parameter_budget=12,
        ),
    ),
    "liquidity": ScenarioSpec(
        "liquidity",
        "流动性",
        "日内流动性调度",
        "TIME-ORDERED FUNDING",
        "选择跨币种融资、划拨和换汇动作，满足覆盖、时序与渠道约束。",
        "waves",
        "emerald",
        (("base", "基准流动性"),),
        (
            _range("value_weight", "覆盖价值权重", 0.2, 0.85, 0.05),
            _range("cost_weight", "成本权重", 0.15, 0.8, 0.05),
            _select("selected_count", "动作数量", ("3", "4", "5")),
            _range("minimum_units", "最低覆盖单位", 8, 16, 1),
            _select("group_cap", "单币种上限", ("1", "2", "3")),
        ),
        # 32/64 shots 在固定种子下可能没有采到可行方案；128 shots 已通过
        # 默认业务约束复核，同时仍保持现场可接受的运行时间。
        ExecutionProfile(shots=128),
        vqe_execution=ExecutionProfile(
            shots=64,
            algorithm="vqe",
            max_layers=1,
            search_strategy="continuous",
            parameter_budget=18,
        ),
    ),
    "credit_limits": ScenarioSpec(
        "credit_limits",
        "授信额度",
        "企业授信额度配置",
        "CAPITAL ALLOCATION",
        "对已准入企业配置额度档位，控制资本预算与行业集中度。",
        "building-2",
        "amber",
        (
            ("base", "稳健配置"),
            ("return", "收益优先"),
        ),
        (
            _range("value_weight", "风险调整价值权重", 0.2, 0.85, 0.05),
            _range("cost_weight", "资本成本权重", 0.15, 0.8, 0.05),
            _select("selected_count", "额度数量", ("3", "4", "5")),
            _range("maximum_units", "资本使用上限", 8, 14, 1),
            _select("group_cap", "单行业上限", ("1", "2", "3")),
        ),
        # 一层预设点在默认授信约束下没有采到可行方案。两层使用相同的固定
        # 参数语义即可得到可行业务候选，不需要把随机搜索伪装成优化器。
        ExecutionProfile(shots=128, layers=2),
        vqe_execution=ExecutionProfile(
            shots=64,
            algorithm="vqe",
            max_layers=1,
            search_strategy="continuous",
            parameter_budget=16,
        ),
    ),
    "derivatives": ScenarioSpec(
        "derivatives",
        "衍生品",
        "衍生品定价与风险情景",
        "CLASSIC PRICE + AHS GRID",
        "经典模型计算价格与 Greeks，Analog QAA 选择代表性压力情景。",
        "sigma",
        "cyan",
        (
            ("european_call", "欧式看涨"),
            ("european_put", "欧式看跌"),
            ("asian_call", "亚式期权"),
            ("up_and_out_call", "上敲出障碍期权"),
        ),
        (
            ControlSpec(
                "product",
                "产品",
                "select",
                options=(
                    ("european_call", "欧式看涨"),
                    ("european_put", "欧式看跌"),
                    ("asian_call", "亚式期权"),
                    ("up_and_out_call", "上敲出障碍期权"),
                ),
            ),
            _range("spot", "标的价格", 70, 140, 1),
            _range("strike", "执行价", 70, 140, 1),
            _range("volatility", "波动率", 0.08, 0.6, 0.01),
            _range("rate", "无风险利率", 0, 0.1, 0.005),
            _range("maturity", "期限", 0.25, 2, 0.25, "年"),
            _range("barrier", "障碍价", 105, 180, 1),
            _select("paths", "Monte Carlo 路径", ("1024", "2048", "4096")),
        ),
    ),
}


def preset_input(case_id: str, preset: str) -> Any:
    """基于场景默认输入生成确定性预设，不依赖旧桌面界面。"""
    scenario = PROBLEM_SCENARIOS[case_id]
    base = scenario.default_input()
    changes: dict[str, dict[str, Any]]
    if case_id == "portfolio":
        changes = {
            "rates": {"risk_weight": 0.68, "minimum_defensive": 1},
            "drawdown": {"risk_weight": 0.75, "minimum_defensive": 2},
            "commodity": {"risk_weight": 0.45, "sector_cap": 2},
        }
    elif case_id == "settlement":
        changes = {
            "priority": {"notional_weight": 0.35, "priority_weight": 0.65},
        }
    elif case_id == "fraud_routing":
        changes = {
            "ring": {"risk_weight": 0.65, "investigator_slots": 5},
            "merchant": {"exposure_weight": 0.5, "entity_parallel_cap": 2},
        }
    elif case_id == "collateral":
        changes = {
            "haircut": {"value_weight": 0.68, "cost_weight": 0.32},
            "hqla": {"value_weight": 0.45, "cost_weight": 0.55},
        }
    elif case_id == "liquidity":
        changes = {}
    elif case_id == "credit_limits":
        changes = {
            "return": {"value_weight": 0.75, "maximum_units": 12},
        }
    else:
        return replace(base, product=preset)

    candidate = replace(base, **changes.get(preset, {}))
    if case_id == "credit_limits" and not scenario.exact_business_points(candidate):
        candidate = replace(candidate, selected_count=3)
    return candidate


def build_case_input(case_id: str, preset: str, values: dict[str, Any]) -> Any:
    """按数据类字段类型转换控件值，并应用到指定预设输入。"""
    base = preset_input(case_id, preset)
    aliases = {
        "penalty": "penalty_multiplier",
        "slots": "investigator_slots",
        "entity_cap": "entity_parallel_cap",
    }
    fields = asdict(base)
    changes: dict[str, Any] = {}
    for key, raw in values.items():
        field_name = aliases.get(key, key)
        if field_name not in fields:
            continue
        current = fields[field_name]
        if isinstance(current, bool):
            changes[field_name] = bool(raw)
        elif isinstance(current, int):
            changes[field_name] = int(raw)
        elif isinstance(current, float):
            changes[field_name] = float(raw)
        else:
            changes[field_name] = str(raw)
    if isinstance(base, SelectionInput):
        return replace(base, **changes)
    return replace(base, **changes)


def control_values(case_id: str, case_input: Any) -> dict[str, Any]:
    """把强类型场景输入还原为前端稳定控件键值。"""
    values = asdict(case_input)
    aliases = {
        "penalty": "penalty_multiplier",
        "slots": "investigator_slots",
        "entity_cap": "entity_parallel_cap",
    }
    output = {}
    for control in SCENARIO_SPECS[case_id].controls:
        field_name = aliases.get(control.key, control.key)
        output[control.key] = values[field_name]
    return output
