import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ScenarioSpec } from "./types";

export type Language = "zh" | "en";

const zh = {
  productTitle: "中科酷原金融量子实验台",
  productSubtitle: "CASCAQit FINANCIAL QUANTUM WORKBENCH",
  serviceOnline: "实验服务在线",
  syntheticData: "合成演示数据",
  auditReady: "执行可审计",
  experiments: "金融场景",
  execution: "实验执行",
  loadingService: "正在连接实验服务",
  loadingView: "加载实验视图",
  loadFailed: "无法加载金融场景",
  emptyCatalog: "API 未返回场景目录",
  parametersAndExecution: "参数与执行",
  experimentInput: "实验输入",
  demoPreset: "演示预设",
  executionMode: "执行模式",
  parameterPoints: "参数点",
  fast: "快速",
  comparison: "对照",
  running: "执行中",
  analyzing: "分析中",
  runExperiment: "运行",
  resetScenario: "重置当前场景",
  buildingMapping: "正在建立 Problem 映射",
  resultsView: "结果视图",
  businessResult: "业务结果",
  scenarioSituation: "场景态势",
  problemMapping: "Problem 映射",
  quantumExperiment: "量子实验",
  auditEvidence: "审计证据",
  lastExecution: "最近执行",
  analyzingStatus: "分析中",
  recommendedPath: "推荐链路",
  comparisonPath: "对比链路",
  compilingExecutingSampling: "编译 · 执行 · 采样",
  waitingResult: "等待实验结果",
  currentSolution: "当前业务方案",
  businessConstraintReview: "业务约束复核",
  inputRecords: "输入记录",
  scenarioInputSlice: "场景输入切片",
  businessObject: "业务对象",
  group: "分组",
  primaryMetric: "主指标",
  secondaryMetric: "次指标",
  description: "说明",
  modeDecision: "模式决策",
  recommended: "推荐",
  comparable: "可比较",
  unsuitable: "不适用",
  stateDimension: "状态空间维度",
  businessGroups: "业务项组",
  canonicalIdentity: "规范标识",
  graphMatrix: "QUBO / 图结构矩阵",
  termAssignment: "Hamiltonian 项分配",
  operator: "算符",
  variable: "变量",
  logical: "逻辑",
  implementation: "实现",
  variables: "变量",
  pairs: "变量对",
  dadTimeline: "D-A-D 执行时间线",
  atomRegister: "中性原子排列",
  controlWaveforms: "Rabi / Detuning / Phase 控制波形",
  waveformNote: "分轨仅用于避免曲线重叠；平线表示该控制量在当前实验段内保持恒定。",
  finalSampling: "末端采样分布",
  parameterObjective: "参数点目标值",
  digitalCircuit: "数字量子线路",
  parameterizedCircuit: "参数化通用门线路",
  logicalLayers: "QAOA 逻辑层",
  circuitRepresentation: "线路表示",
  universalGates: "通用门",
  logicalLayer: "逻辑层",
  previousCircuit: "上一段线路",
  nextCircuit: "下一段线路",
  circuitDescription: (qubits: number, gates: number) =>
    `${qubits} 个逻辑量子位，当前显示 ${gates} 个门操作。`,
  localSimulationEvidence: "本地数值模拟，非量子真机",
  executionBoundary: "未使用量子硬件或云端执行，不声明全局最优",
  verified: "已核验",
  structuredAudit: "结构化审计载荷",
  selected: "入选",
  notSelected: "未选",
  timeAxis: "时间 / μs",
  waveformLane: "控制通道",
  parameterPointAxis: "参数点",
  correlation: "相关系数",
  priceChange: "价格变化",
  positiveCorrelation: "正相关",
  negativeCorrelation: "负相关",
  profit: "盈利",
  loss: "亏损",
  settlementConflict: "结算冲突",
  dependency: "前置依赖",
  entityRelation: "实体关联",
  coverage: "覆盖",
  units: "单位",
  optionalAction: "可选动作",
  capitalCost: "资本成本",
  riskAdjustedValue: "风险调整价值",
  efficiency: "效率",
} as const;

type MessageDictionary = {
  [K in keyof typeof zh]: (typeof zh)[K] extends (...args: infer Args) => string
    ? (...args: Args) => string
    : string;
};

const en: MessageDictionary = {
  productTitle: "CASColdAtom Financial Quantum Workbench",
  productSubtitle: "CASCAQit FINANCIAL QUANTUM WORKBENCH",
  serviceOnline: "Execution Service Online",
  syntheticData: "Synthetic Demo Data",
  auditReady: "Auditable Execution",
  experiments: "Financial Scenarios",
  execution: "Experiment Execution",
  loadingService: "Connecting to Experiment Service",
  loadingView: "Loading Experiment View",
  loadFailed: "Unable to Load Financial Scenarios",
  emptyCatalog: "The API Returned No Scenarios",
  parametersAndExecution: "Parameters and Execution",
  experimentInput: "Experiment Input",
  demoPreset: "Demo Preset",
  executionMode: "Execution Mode",
  parameterPoints: "Parameter Points",
  fast: "Fast",
  comparison: "Comparison",
  running: "Running",
  analyzing: "Analyzing",
  runExperiment: "RUN",
  resetScenario: "Reset Current Scenario",
  buildingMapping: "Building Problem Mapping",
  resultsView: "Result Views",
  businessResult: "Business Result",
  scenarioSituation: "Scenario View",
  problemMapping: "Problem Mapping",
  quantumExperiment: "Quantum Experiment",
  auditEvidence: "Audit Evidence",
  lastExecution: "Last Execution",
  analyzingStatus: "Analyzing",
  recommendedPath: "Recommended Path",
  comparisonPath: "Comparison Path",
  compilingExecutingSampling: "Compiling · Executing · Sampling",
  waitingResult: "Waiting for Experiment Results",
  currentSolution: "Current Business Solution",
  businessConstraintReview: "Business Constraint Review",
  inputRecords: "Input Records",
  scenarioInputSlice: "Scenario Input Slice",
  businessObject: "Business Object",
  group: "Group",
  primaryMetric: "Primary Metric",
  secondaryMetric: "Secondary Metric",
  description: "Description",
  modeDecision: "Mode Decision",
  recommended: "Recommended",
  comparable: "Comparable",
  unsuitable: "Unsuitable",
  stateDimension: "State-space Dimension",
  businessGroups: "Business Groups",
  canonicalIdentity: "Canonical Identity",
  graphMatrix: "QUBO / Graph Matrix",
  termAssignment: "Hamiltonian Term Assignment",
  operator: "Operator",
  variable: "Variables",
  logical: "Logical",
  implementation: "Implementation",
  variables: "variables",
  pairs: "pairs",
  dadTimeline: "D-A-D Execution Timeline",
  atomRegister: "Neutral-atom Register",
  controlWaveforms: "Rabi / Detuning / Phase Control Waveforms",
  waveformNote:
    "Channels are vertically separated to avoid overlap; a flat line means the control remains constant during this block.",
  finalSampling: "Final Sample Distribution",
  parameterObjective: "Parameter-point Objective",
  digitalCircuit: "Digital Quantum Circuit",
  parameterizedCircuit: "Parameterized Universal-gate Circuit",
  logicalLayers: "QAOA Logical Layers",
  circuitRepresentation: "Circuit Representation",
  universalGates: "Universal Gates",
  logicalLayer: "Logical Layers",
  previousCircuit: "Previous Circuit Segment",
  nextCircuit: "Next Circuit Segment",
  circuitDescription: (qubits: number, gates: number) =>
    `${qubits} logical qubits with ${gates} gate operations currently visible.`,
  localSimulationEvidence: "Local numerical simulation, not quantum hardware",
  executionBoundary:
    "No quantum hardware or cloud execution; no global optimum is claimed",
  verified: "Verified",
  structuredAudit: "Structured Audit Payload",
  selected: "Selected",
  notSelected: "Not Selected",
  timeAxis: "Time / μs",
  waveformLane: "Control Channel",
  parameterPointAxis: "Parameter Point",
  correlation: "Correlation",
  priceChange: "Price Change",
  positiveCorrelation: "Positive",
  negativeCorrelation: "Negative",
  profit: "Profit",
  loss: "Loss",
  settlementConflict: "Settlement Conflict",
  dependency: "Dependency",
  entityRelation: "Entity Relation",
  coverage: "Coverage",
  units: "units",
  optionalAction: "Optional Action",
  capitalCost: "Capital Cost",
  riskAdjustedValue: "Risk-adjusted Value",
  efficiency: "Efficiency",
};

type MessageKey = keyof typeof zh;

const scenarioEnglish: Record<
  string,
  {
    shortTitle: string;
    title: string;
    description: string;
    presets: Record<string, string>;
    controls: Record<string, string>;
    options?: Record<string, string>;
  }
> = {
  portfolio: {
    shortTitle: "Portfolio",
    title: "Multi-asset Portfolio Optimization",
    description:
      "Select an equal-weight portfolio under return, risk, sector concentration, and defensive-asset constraints.",
    presets: {
      base: "Baseline Market",
      rates: "Rising Rates",
      drawdown: "Equity Drawdown",
      commodity: "Commodity Shock",
    },
    controls: {
      risk_weight: "Risk Weight",
      selected_count: "Number of Holdings",
      sector_cap: "Per-sector Limit",
      minimum_defensive: "Minimum Defensive Assets",
    },
  },
  settlement: {
    shortTitle: "Settlement",
    title: "Trade Settlement Batch Optimization",
    description:
      "Map local trade conflicts to atom interactions while retaining dependency and liquidity constraints digitally.",
    presets: {
      base: "Routine Batch",
      tight: "Tight Liquidity",
      priority: "Priority Clients",
    },
    controls: {
      notional_weight: "Notional Weight",
      priority_weight: "Priority Weight",
      batch_cap: "Batch Limit",
      penalty: "Constraint Penalty",
    },
  },
  fraud_routing: {
    shortTitle: "Investigation",
    title: "Fraud Investigation Task Routing",
    description:
      "Prioritize high-risk, high-exposure, and time-sensitive alerts under limited investigator capacity.",
    presets: {
      base: "Account Takeover",
      ring: "Transaction Ring",
      merchant: "Merchant Anomaly",
    },
    controls: {
      risk_weight: "Risk Weight",
      exposure_weight: "Exposure Weight",
      urgency_weight: "Urgency Weight",
      slots: "Investigator Slots",
      entity_cap: "Per-entity Concurrency",
    },
  },
  collateral: {
    shortTitle: "Collateral",
    title: "Collateral Allocation Optimization",
    description:
      "Select allocations under eligibility, batch uniqueness, coverage value, and funding cost constraints.",
    presets: {
      base: "Routine Margin Call",
      haircut: "Market Volatility",
      hqla: "Preserve HQLA",
    },
    controls: {
      value_weight: "Business Value Weight",
      cost_weight: "Cost Weight",
    },
  },
  liquidity: {
    shortTitle: "Liquidity",
    title: "Intraday Liquidity Scheduling",
    description:
      "Select funding, transfer, and FX actions across currencies under coverage, timing, and channel constraints.",
    presets: {
      base: "Baseline Liquidity",
      eod: "End-of-day Stress",
      fx: "Cross-currency Shortfall",
    },
    controls: {
      value_weight: "Coverage Value Weight",
      cost_weight: "Cost Weight",
      selected_count: "Number of Actions",
      minimum_units: "Minimum Coverage Units",
      group_cap: "Per-currency Limit",
    },
  },
  credit_limits: {
    shortTitle: "Credit Limits",
    title: "Corporate Credit Limit Allocation",
    description:
      "Assign limit tiers to approved firms while controlling capital budget and sector concentration.",
    presets: {
      base: "Prudent Allocation",
      return: "Return Priority",
      concentration: "Lower Concentration",
    },
    controls: {
      value_weight: "Risk-adjusted Value Weight",
      cost_weight: "Capital Cost Weight",
      selected_count: "Number of Limits",
      maximum_units: "Capital Usage Limit",
      group_cap: "Per-sector Limit",
    },
  },
  derivatives: {
    shortTitle: "Derivatives",
    title: "Derivatives Pricing and Risk Scenarios",
    description:
      "Price and compute Greeks classically, then use Analog QAA to select representative stress scenarios.",
    presets: {
      european_call: "European Call",
      european_put: "European Put",
      asian_call: "Asian Call",
      up_and_out_call: "Up-and-out Barrier Call",
    },
    controls: {
      product: "Product",
      spot: "Spot Price",
      strike: "Strike Price",
      volatility: "Volatility",
      rate: "Risk-free Rate",
      maturity: "Maturity",
      barrier: "Barrier Price",
      paths: "Monte Carlo Paths",
    },
    options: {
      european_call: "European Call",
      european_put: "European Put",
      asian_call: "Asian Call",
      up_and_out_call: "Up-and-out Barrier Call",
    },
  },
};

const contentEnglish: Record<string, string> = {
  "资产相关性矩阵": "Asset Correlation Matrix",
  "交易冲突与前置依赖": "Trade Conflicts and Dependencies",
  "告警与关键实体网络": "Alerts and Key Entities",
  "抵押品与保证金需求流": "Collateral and Margin Flow",
  "日内资金动作与累计覆盖": "Intraday Funding Actions and Cumulative Coverage",
  "资本效率与行业集中度": "Capital Efficiency and Sector Concentration",
  "衍生品压力情景损益": "Derivatives Stress-scenario P&L",
  "由当前协方差与波动率计算，显示组合风险的稠密连接。":
    "Computed from current covariance and volatility inputs to expose dense portfolio-risk relationships.",
  "实线表示不可同批结算，虚线箭头表示前置依赖。":
    "Solid lines mark incompatible settlements; dashed arrows mark dependencies.",
  "共享实体形成局域冲突，节点大小表示告警风险。":
    "Shared entities create local conflicts; node size represents alert risk.",
  "流宽表示覆盖单位，运行后高亮当前分配路径。":
    "Flow width represents coverage units; the selected allocation is highlighted after execution.",
  "散点为可选动作，折线为各币种候选资金的累计覆盖。":
    "Points are available actions; lines show cumulative candidate funding by currency.",
  "横轴为资本成本，纵轴为风险调整价值，气泡大小表示资本占用。":
    "The axes show capital cost and risk-adjusted value; bubble size represents capital usage.",
  "每个格点由经典定价链重估；Analog 只选择代表情景。":
    "Each cell is repriced classically; Analog selects representative scenarios only.",
  "可行组合与当前候选": "Feasible Portfolios and Current Candidate",
  "结算金额与流动性占用": "Settlement Notional and Liquidity Usage",
  "调查风险与金额覆盖": "Investigation Risk and Exposure Coverage",
  "抵押品候选业务价值": "Collateral Candidate Business Value",
  "入选资金动作时序": "Selected Funding-action Timeline",
  "额度档位资本效率": "Credit-tier Capital Efficiency",
  "Analog 代表风险情景": "Representative Analog Risk Scenarios",
  "业务约束": "Business Constraints",
  "业务目标": "Business Objective",
  "业务价值": "Business Value",
  "业务价值与成本": "Business Value and Cost",
  "业务价值权重": "Business Value Weight",
  "业务冲突": "Business Conflicts",
  "业务复核": "Business Review",
  "入选资产": "Selected Assets",
  "入选指令": "Selected Instructions",
  "入选告警": "Selected Alerts",
  "入选合计": "Selected Total",
  "原始输入复核": "Original-input Review",
  "人工复核": "Manual Review",
  "可行组合": "Feasible Portfolio",
  "当前持仓": "Current Holdings",
  "当前批次": "Current Batch",
  "当前席位": "Current Slots",
  "当前方案": "Current Solution",
  "持仓和行业约束": "Holdings and Sector Constraints",
  "持仓数量": "Number of Holdings",
  "防御资产下限": "Minimum Defensive Assets",
  "风险权重": "Risk Weight",
  "收益与协方差": "Return and Covariance",
  "未进入当前候选": "Not in the Current Candidate",
  "目标值未进入当前候选": "Objective Value Not in the Current Candidate",
  "等权组合": "Equal-weight Portfolio",
  "组合年化": "Annualized Portfolio",
  "辅助罚项": "Auxiliary Penalty",
  "辅助变量": "Auxiliary Variables",
  "通过": "Passed",
  "防御资产": "Defensive Assets",
  "风险资产": "Risk Assets",
  "交易数": "Trade Count",
  "交易冲突": "Trade Conflicts",
  "优先级权重": "Priority Weight",
  "依赖关系": "Dependencies",
  "批次上限": "Batch Limit",
  "流动性与依赖": "Liquidity and Dependencies",
  "流动性和批次约束": "Liquidity and Batch Constraints",
  "约束": "Constraints",
  "约束罚项倍数": "Constraint Penalty Multiplier",
  "结算金额": "Settlement Notional",
  "越低越优": "Lower Is Better",
  "金额与优先级": "Notional and Priority",
  "金额权重": "Notional Weight",
  "额度辅助变量": "Capacity Auxiliary Variables",
  "名义金额 / m": "Notional / m",
  "流动性占用 / 资金单位": "Liquidity Usage / Funding Units",
  "共享实体冲突": "Shared-entity Conflicts",
  "单实体并行上限": "Per-entity Concurrency Limit",
  "席位辅助变量": "Slot Auxiliary Variables",
  "时效权重": "Urgency Weight",
  "调查席位": "Investigator Slots",
  "调查席位已满": "Investigator Capacity Reached",
  "调查任务": "Investigation Tasks",
  "涉案金额": "Exposure",
  "涉案金额 / m": "Exposure / m",
  "金额覆盖": "Exposure Coverage",
  "预计工时": "Estimated Hours",
  "风险、金额和时效": "Risk, Exposure, and Urgency",
  "风险分": "Risk Score",
  "风险覆盖": "Risk Coverage",
  "与已选项冲突": "Conflicts with a Selected Item",
  "候选资产": "Candidate Assets",
  "总成本": "Total Cost",
  "成本权重": "Cost Weight",
  "保证金需求桶": "Margin-demand Bucket",
  "前置依赖": "Prerequisite Dependency",
  "数量、分组和资源约束": "Count, Group, and Resource Constraints",
  "资源单位": "Resource Units",
  "资源成本": "Resource Cost",
  "动作数量": "Number of Actions",
  "单币种上限": "Per-currency Limit",
  "最低覆盖单位": "Minimum Coverage Units",
  "覆盖价值权重": "Coverage Value Weight",
  "选择数量已满": "Selection Limit Reached",
  "单行业上限": "Per-sector Limit",
  "资本使用上限": "Capital Usage Limit",
  "资本成本权重": "Capital Cost Weight",
  "额度数量": "Number of Credit Limits",
  "风险调整价值权重": "Risk-adjusted Value Weight",
  "Analog 候选": "Analog Candidates",
  "Delta 曲率": "Delta Curvature",
  "价格敏感度": "Price Sensitivity",
  "参考价格": "Reference Price",
  "执行价": "Strike Price",
  "无风险利率": "Risk-free Rate",
  "期限": "Maturity",
  "标的价格": "Underlying Price",
  "波动率敏感度": "Volatility Sensitivity",
  "相邻风险情景": "Adjacent Risk Scenarios",
  "障碍价": "Barrier Price",
  "风险情景": "Risk Scenarios",
  "Monte Carlo 路径": "Monte Carlo Paths",
  "产品": "Product",
  "年": "years",
  "目标": "Objective",
  "额度": "Capacity",
  "依赖": "Dependency",
  "工时": "Hours",
  "风险": "Risk",
  "未入选": "Not Selected",
  "前置交易": "Prerequisite Trade",
  "冲突": "Conflict",
  "实体": "Entity",
  "并行上限": "Concurrency Limit",
  "内部划拨": "Internal Transfer",
  "质押回购": "Repo Funding",
  "同业拆入": "Interbank Borrowing",
  "外汇掉期续作": "FX Swap Rollover",
  "外汇掉期": "FX Swap",
  "票据融资": "Bill Financing",
  "制造企业": "Manufacturing Company",
  "消费企业": "Consumer Company",
  "科技企业": "Technology Company",
  "能源企业": "Energy Company",
  "低档": "Low Tier",
  "中档": "Medium Tier",
  "高档": "High Tier",
  "信用债": "Credit Bond",
  "国债批次": "Treasury Batch",
  "政策债": "Policy-bank Bond",
  "现金": "Cash",
  "股票篮子": "Equity Basket",
  "双边一": "Bilateral One",
  "双边二": "Bilateral Two",
  "上敲出障碍期权": "Up-and-out Barrier Call",
  "亚式期权": "Asian Option",
  "欧式看涨": "European Call",
  "欧式看跌": "European Put",
  "债券": "Bonds",
  "医药": "Healthcare",
  "基础设施": "Infrastructure",
  "银行": "Banking",
  "黄金": "Gold",
  "其他状态": "Other States",
  "请求失败": "Request Failed",
  "资产": "Asset",
  "交易": "Trade",
  "时间": "Time",
  "价格冲击": "Price Shock",
  "波动率冲击": "Volatility Shock",
  "资本成本": "Capital Cost",
  "风险调整价值": "Risk-adjusted Value",
  "波动率": "Volatility",
  "预期收益": "Expected Return",
  "相关性格点": "Correlation Cells",
  "交易节点": "Trade Nodes",
  "告警 / 实体节点": "Alert / Entity Nodes",
  "分配流节点": "Allocation-flow Nodes",
  "日内动作": "Intraday Actions",
  "授信候选": "Credit Candidates",
  "压力情景": "Stress Scenarios",
  "告警": "Alerts",
  "关键实体": "Key Entities",
  "抵押品": "Collateral",
  "保证金需求": "Margin Demand",
  "制造": "Manufacturing",
  "消费": "Consumer",
  "科技": "Technology",
  "能源": "Energy",
  "日内时点": "Intraday Time",
  "资金单位": "Funding Units",
  "标的价格冲击": "Underlying-price Shock",
  "问题主体是稠密、全局或有方向的约束，使用 Digital。":
    "The problem is dominated by dense, global, or directed constraints, so Digital is used.",
  "业务冲突项由原子相互作用承担，其余约束保留为数字项。":
    "Atom interactions encode business conflicts while the remaining constraints stay digital.",
  "完整业务图可由 AHS 表达，不需要 Digital residual。":
    "AHS can express the complete business graph without a digital residual.",
  "当前场景的推荐执行模式。": "Recommended execution mode for this scenario.",
  "可运行对照实验，但不是默认方式。":
    "Available as a comparison run, but not selected by default.",
  "没有可追溯到业务冲突的 Analog interaction。":
    "No Analog interaction can be traced to a business conflict.",
  "Target 无法完整编译该模式。":
    "The target cannot compile this mode completely.",
  "Analog 业务项或 Digital residual 为空，不构成 Hybrid。":
    "An empty Analog business term set or Digital residual does not form a Hybrid program.",
};

const contentReplacements = Object.entries(contentEnglish).sort(
  ([left], [right]) => right.length - left.length,
);

export function translateContent(text: string): string {
  const exact = contentEnglish[text];
  if (exact) return exact;

  let translated = text
    .replace(/^与 (.+) 冲突$/, "Conflicts with $1")
    .replace(/^前置交易 (.+) 未入选$/, "Prerequisite trade $1 was not selected")
    .replace(/^关联 (\d+) 条告警$/, "$1 linked alerts")
    .replace(/^实体 (.+) 并行上限$/, "Entity $1 concurrency limit");
  for (const [source, target] of contentReplacements) {
    translated = translated.replaceAll(source, target);
  }
  return translated
    .replaceAll("、", ", ")
    .replaceAll("：", ": ")
    .replaceAll("。", ".");
}

function localizeScenario(scenario: ScenarioSpec, language: Language): ScenarioSpec {
  if (language === "zh") return scenario;
  const translation = scenarioEnglish[scenario.caseId];
  if (!translation) return scenario;
  return {
    ...scenario,
    shortTitle: translation.shortTitle,
    title: translation.title,
    description: translation.description,
    presets: scenario.presets.map((preset) => ({
      ...preset,
      label: translation.presets[preset.value] ?? preset.label,
    })),
    controls: scenario.controls.map((control) => ({
      ...control,
      label: translation.controls[control.key] ?? control.label,
      unit: control.unit === "年" ? " yr" : control.unit,
      options: control.options.map((option) => ({
        ...option,
        label: translation.options?.[option.value] ?? option.label,
      })),
    })),
  };
}

interface I18nValue {
  language: Language;
  setLanguage: (language: Language) => void;
  t: <K extends MessageKey>(key: K) => MessageDictionary[K];
  tx: (value: string) => string;
  scenario: (value: ScenarioSpec) => ScenarioSpec;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({
  children,
  initialLanguage,
}: {
  children: ReactNode;
  initialLanguage?: Language;
}) {
  const [language, setLanguage] = useState<Language>(() => {
    if (initialLanguage) return initialLanguage;
    if (
      typeof window === "undefined" ||
      typeof window.localStorage?.getItem !== "function"
    ) {
      return "zh";
    }
    return window.localStorage.getItem("finance-demo-language") === "en"
      ? "en"
      : "zh";
  });

  useEffect(() => {
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    document.title = language === "zh" ? zh.productTitle : en.productTitle;
    if (typeof window.localStorage?.setItem === "function") {
      window.localStorage.setItem("finance-demo-language", language);
    }
  }, [language]);

  const value = useMemo<I18nValue>(
    () => ({
      language,
      setLanguage,
      t: ((key: MessageKey) =>
        (language === "zh" ? zh[key] : en[key])) as I18nValue["t"],
      tx: (text: string) => (language === "zh" ? text : translateContent(text)),
      scenario: (item: ScenarioSpec) => localizeScenario(item, language),
    }),
    [language],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside I18nProvider");
  return value;
}
