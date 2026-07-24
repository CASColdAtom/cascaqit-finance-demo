"""Seven-scenario Bokeh workbench backed by the unified Problem API."""

# HTML and CSS remain readable when several declarations share one physical line.
# ruff: noqa: E501

from __future__ import annotations

import html
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from bokeh.document import Document
from bokeh.layouts import column, row
from bokeh.models import (
    Button,
    ColumnDataSource,
    DataTable,
    Div,
    HoverTool,
    LinearColorMapper,
    RadioButtonGroup,
    Range1d,
    RangeSlider,
    Select,
    Slider,
    TableColumn,
    TabPanel,
    Tabs,
)
from bokeh.palettes import RdBu11
from bokeh.plotting import figure

from cascaqit_finance_demo.app.theme import (
    AMBER,
    APP_TEMPLATE,
    BLUE,
    BORDER,
    GREEN,
    GRID,
    MUTED,
    RED,
    SURFACE,
    VIOLET,
    finance_theme,
    mobile_full_width_stylesheet,
    primary_button_stylesheet,
)
from cascaqit_finance_demo.cases.constrained_selection import SelectionInput
from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS
from cascaqit_finance_demo.domain.models import (
    FraudRoutingInput,
    PortfolioInput,
    SettlementInput,
)
from cascaqit_finance_demo.quantum.problem_executor import (
    ScenarioExecutor,
    default_parameter_sets,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = PROJECT_ROOT / "artifacts" / "reports"

SCENARIO_ORDER = (
    "portfolio",
    "settlement",
    "fraud_routing",
    "collateral",
    "liquidity",
    "credit_limits",
    "derivatives",
)

SCENARIO_LABELS = {
    "portfolio": "01  投资组合",
    "settlement": "02  交易结算",
    "fraud_routing": "03  调查编排",
    "collateral": "04  抵押品分配",
    "liquidity": "05  流动性调度",
    "credit_limits": "06  授信额度",
    "derivatives": "07  衍生品定价",
}

PRESETS = {
    "portfolio": (
        ("base", "基准市场"),
        ("rates", "利率上行"),
        ("drawdown", "权益回撤"),
        ("commodity", "商品冲击"),
    ),
    "settlement": (
        ("base", "日常批次"),
        ("tight", "流动性收紧"),
        ("priority", "重点客户优先"),
    ),
    "fraud_routing": (
        ("base", "账户接管"),
        ("ring", "团伙交易"),
        ("merchant", "商户异常"),
    ),
    "collateral": (
        ("base", "日常补缴"),
        ("haircut", "市场波动"),
        ("hqla", "保留优质资产"),
    ),
    "liquidity": (
        ("base", "基准流动性"),
        ("eod", "日终压力"),
        ("fx", "跨币种短缺"),
    ),
    "credit_limits": (
        ("base", "稳健配置"),
        ("return", "收益优先"),
        ("concentration", "行业集中压降"),
    ),
    "derivatives": (
        ("european_call", "欧式看涨"),
        ("european_put", "欧式看跌"),
        ("asian_call", "亚式期权"),
        ("up_and_out_call", "上敲出障碍期权"),
    ),
}


@dataclass(frozen=True)
class CachedRun:
    """One mode result tied to the exact input and execution controls."""

    signature: tuple[str, str, str, str, str]
    case_input: Any
    result: Any


@dataclass
class Workspace:
    """Bokeh models and runtime state owned by one scenario page."""

    case_id: str
    root: Any
    controls: dict[str, Any]
    tabs: Tabs
    run_button: Button
    status: Div
    metrics: Div
    input_source: ColumnDataSource
    business_source: ColumnDataSource
    selection_source: ColumnDataSource
    matrix_source: ColumnDataSource
    objective_source: ColumnDataSource
    counts_source: ColumnDataSource
    feasibility_source: ColumnDataSource
    term_source: ColumnDataSource
    atom_source: ColumnDataSource
    waveform_sources: dict[str, ColumnDataSource]
    circuit_sources: dict[str, ColumnDataSource]
    circuit_figure: Any
    circuit_layer_figure: Any
    circuit_mode: RadioButtonGroup
    circuit_window: RangeSlider
    audit: Div
    analysis_summary: Div
    quantum_note: Div
    result_title: Div
    atom_figure: Any
    waveform_figure: Any
    circuit_cache: list[dict[str, Any]]
    analysis: Any
    result_cache: dict[str, CachedRun]
    callbacks_suspended: bool


def build_document(doc: Document) -> dict[str, Any]:
    """Build the seven-scenario finance workbench."""
    executor = ScenarioExecutor()
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="finance-problem")
    workspaces = {
        case_id: _build_workspace(case_id, executor) for case_id in SCENARIO_ORDER
    }
    active_case = Select(
        title="当前场景",
        value="portfolio",
        options=[(case_id, SCENARIO_LABELS[case_id]) for case_id in SCENARIO_ORDER],
        visible=False,
    )
    nav_buttons: dict[str, Button] = {}
    nav_items = []

    def select_case(case_id: str) -> None:
        active_case.value = case_id

    for case_id in SCENARIO_ORDER:
        button = Button(
            label=SCENARIO_LABELS[case_id],
            button_type="success" if case_id == "portfolio" else "default",
            height=38,
            sizing_mode="stretch_width",
        )
        button.on_click(lambda case_id=case_id: select_case(case_id))
        nav_buttons[case_id] = button
        analysis = executor.analyze(
            PROBLEM_SCENARIOS[case_id],
            PROBLEM_SCENARIOS[case_id].default_input(),
        )
        nav_items.append(
            column(
                button,
                Div(
                    text=(
                        f'<div class="nav-mode">推荐 {analysis.mode_decision.recommended_mode.upper()}</div>'
                    )
                ),
                spacing=2,
                sizing_mode="stretch_width",
            )
        )

    navigation = column(
        Div(text='<div class="nav-title">金融场景</div>'),
        *nav_items,
        width=190,
        min_width=190,
        spacing=8,
        css_classes=["case-navigation"],
        stylesheets=[mobile_full_width_stylesheet()],
    )
    workspace_stack = column(
        *(workspaces[case_id].root for case_id in SCENARIO_ORDER),
        sizing_mode="stretch_width",
        css_classes=["case-body"],
        styles={"min-width": "0", "flex": "1 1 auto"},
    )

    def switch_case(_attr: str, _old: str, value: str) -> None:
        for case_id, workspace in workspaces.items():
            workspace.root.visible = case_id == value
            nav_buttons[case_id].button_type = (
                "success" if case_id == value else "default"
            )

    active_case.on_change("value", switch_case)

    for case_id, workspace in workspaces.items():
        workspace.run_button.on_click(
            lambda case_id=case_id: _submit_run(
                doc,
                worker,
                executor,
                workspaces[case_id],
            )
        )

    header = Div(
        text=(
            '<div class="brand"><strong>CASCAQit Finance</strong>'
            "<span>中性原子金融量子实验台</span></div>"
            '<div class="environment"><span>本地模拟</span><span>合成数据</span>'
            "<span>无真实硬件</span></div>"
        ),
        sizing_mode="stretch_width",
        css_classes=["app-header"],
    )
    root = column(
        header,
        row(
            navigation,
            workspace_stack,
            sizing_mode="stretch_width",
            css_classes=["workspace-shell"],
            styles={"min-width": "0", "align-items": "stretch"},
        ),
        sizing_mode="stretch_width",
        css_classes=["app-root"],
    )
    doc.add_root(root)
    doc.title = "CASCAQit Finance"
    doc.theme = finance_theme()
    doc.template = APP_TEMPLATE.replace("</style>", _WORKBENCH_CSS + "</style>")
    doc.on_session_destroyed(lambda _context: worker.shutdown(wait=False))
    return {
        "active_case": active_case,
        "navigation": nav_buttons,
        "workspaces": workspaces,
        "tabs": workspaces["portfolio"].tabs,
        "run_button": workspaces["portfolio"].run_button,
        "run_sync": lambda case_id: _run_sync(
            executor,
            workspaces[case_id],
        ),
    }


def _build_workspace(case_id: str, executor: ScenarioExecutor) -> Workspace:
    scenario = PROBLEM_SCENARIOS[case_id]
    default_input = scenario.default_input()
    analysis = executor.analyze(scenario, default_input)
    controls, control_models = _scenario_controls(case_id, default_input)
    preset = Select(
        title="演示预设",
        value=PRESETS[case_id][0][0],
        options=list(PRESETS[case_id]),
        sizing_mode="stretch_width",
    )
    mode = Select(
        title="执行模式",
        value=analysis.mode_decision.recommended_mode,
        options=_mode_options(analysis),
        sizing_mode="stretch_width",
    )
    shots = Select(
        title="Shots",
        value="32",
        options=["16", "32", "64", "128"],
        sizing_mode="stretch_width",
    )
    seed = Select(
        title="Seed",
        value="23",
        options=["7", "19", "23", "41"],
        sizing_mode="stretch_width",
    )
    parameter_points = Select(
        title="参数点",
        value="2",
        options=[("1", "快速 · 1 点"), ("2", "对照 · 2 点")],
        sizing_mode="stretch_width",
    )
    run_button = Button(
        label="运行实验",
        button_type="success",
        height=42,
        sizing_mode="stretch_width",
        stylesheets=[primary_button_stylesheet()],
    )
    status = Div(
        text=_status_html("待运行", analysis.mode_decision.reason, MUTED),
        sizing_mode="stretch_width",
    )
    metrics = Div(
        text=_waiting_metrics(case_id),
        sizing_mode="stretch_width",
        css_classes=["metric-band"],
    )

    input_source = ColumnDataSource(_input_rows(case_id, default_input))
    input_table = DataTable(
        source=input_source,
        columns=[
            TableColumn(field="label", title="候选或输入"),
            TableColumn(field="group", title="分组"),
            TableColumn(field="value", title="价值 / 参数"),
            TableColumn(field="cost", title="成本 / 风险"),
            TableColumn(field="detail", title="说明"),
        ],
        height=250,
        index_position=None,
        sizing_mode="stretch_width",
    )

    business_source = ColumnDataSource(
        {"x": [], "y": [], "label": [], "color": [], "size": [], "detail": []}
    )
    business_plot = _business_figure(case_id, business_source)
    selection_source = ColumnDataSource(
        {"item": [], "status": [], "reason": [], "value": []}
    )
    selection_table = DataTable(
        source=selection_source,
        columns=[
            TableColumn(field="item", title="业务对象"),
            TableColumn(field="status", title="状态"),
            TableColumn(field="value", title="结果值"),
            TableColumn(field="reason", title="说明"),
        ],
        height=260,
        index_position=None,
        sizing_mode="stretch_width",
    )

    matrix_source = ColumnDataSource(
        {"x": [], "y": [], "value": [], "left": [], "right": []}
    )
    matrix_plot = _matrix_figure(matrix_source)
    _set_matrix_data(matrix_source, analysis.definition.problem)
    objective_source = ColumnDataSource({"index": [], "objective": [], "selected": []})
    objective_plot = _objective_figure(objective_source)

    feasibility_source = ColumnDataSource(_feasibility_data(analysis))
    feasibility_table = DataTable(
        source=feasibility_source,
        columns=[
            TableColumn(field="mode", title="模式"),
            TableColumn(field="status", title="结论"),
            TableColumn(field="physical", title="编译"),
            TableColumn(field="analog", title="Analog 项"),
            TableColumn(field="digital", title="Digital 项"),
            TableColumn(field="reason", title="原因"),
        ],
        height=155,
        index_position=None,
        sizing_mode="stretch_width",
    )
    term_source = ColumnDataSource(
        {
            "operator": [],
            "targets": [],
            "logical": [],
            "analog": [],
            "digital": [],
            "implementation": [],
        }
    )
    term_table = DataTable(
        source=term_source,
        columns=[
            TableColumn(field="operator", title="算符"),
            TableColumn(field="targets", title="变量"),
            TableColumn(field="logical", title="逻辑系数"),
            TableColumn(field="analog", title="Analog"),
            TableColumn(field="digital", title="Digital"),
            TableColumn(field="implementation", title="实现"),
        ],
        height=270,
        index_position=None,
        sizing_mode="stretch_width",
    )
    analysis_summary = Div(
        text=_analysis_html(analysis),
        sizing_mode="stretch_width",
        css_classes=["analysis-summary"],
    )

    counts_source = ColumnDataSource({"state": [], "count": [], "color": []})
    counts_plot = _counts_figure(counts_source)
    atom_source = ColumnDataSource(
        {"x": [], "y": [], "label": [], "color": [], "size": [], "role": []}
    )
    atom_plot = _atom_figure(atom_source)
    _set_atom_data(
        atom_source, analysis.problem_analysis.mapping_plan.layout.sites, set()
    )
    waveform_sources = {
        name: ColumnDataSource({"time": [], "value": [], "raw": []})
        for name in ("rabi", "detuning", "phase")
    }
    waveform_plot = _waveform_figure(waveform_sources)
    circuit_sources = {
        "wires": ColumnDataSource({"x0": [], "x1": [], "y": [], "label": []}),
        "gates": ColumnDataSource(
            {"x": [], "y": [], "label": [], "color": [], "detail": []}
        ),
        "links": ColumnDataSource({"x": [], "y0": [], "y1": []}),
        "layers": ColumnDataSource(
            {"x": [], "y": [], "width": [], "height": [], "label": [], "color": []}
        ),
    }
    circuit_plot = _circuit_figure(circuit_sources)
    layer_plot = _layer_figure(circuit_sources)
    layer_plot.visible = False
    circuit_mode = RadioButtonGroup(
        labels=["通用门", "QAOA 逻辑层"],
        active=0,
        width=230,
    )
    circuit_window = RangeSlider(
        title="线路深度窗口",
        start=0,
        end=1,
        value=(0, 1),
        step=1,
        sizing_mode="stretch_width",
    )
    quantum_note = Div(
        text=_quantum_waiting_html(analysis.mode_decision.recommended_mode),
        sizing_mode="stretch_width",
    )
    audit = Div(text=_audit_waiting_html(), sizing_mode="stretch_width")

    business_tab = TabPanel(
        title="业务结果",
        child=column(business_plot, selection_table, sizing_mode="stretch_width"),
    )
    scenario_tab = TabPanel(
        title="场景分析",
        child=column(
            Div(
                text=(
                    "<h3>当前输入</h3><p>表格展示当前预设和控制参数对应的合成数据，"
                    "运行时会重新构造 Problem。</p>"
                )
            ),
            input_table,
            sizing_mode="stretch_width",
        ),
    )
    mapping_tab = TabPanel(
        title="Problem 映射",
        child=column(
            analysis_summary,
            feasibility_table,
            row(matrix_plot, objective_plot, sizing_mode="stretch_width"),
            term_table,
            sizing_mode="stretch_width",
        ),
    )
    quantum_tab = TabPanel(
        title="量子实验",
        child=column(
            quantum_note,
            row(circuit_mode, sizing_mode="stretch_width"),
            circuit_window,
            circuit_plot,
            layer_plot,
            row(
                atom_plot,
                waveform_plot,
                sizing_mode="stretch_width",
                styles={"flex-wrap": "wrap"},
                css_classes=["quantum-pair"],
            ),
            counts_plot,
            sizing_mode="stretch_width",
        ),
    )
    audit_tab = TabPanel(title="审计证据", child=audit)
    tabs = Tabs(
        tabs=[business_tab, scenario_tab, mapping_tab, quantum_tab, audit_tab],
        sizing_mode="stretch_width",
        css_classes=["result-tabs"],
    )

    business_control_names = tuple(control_models)
    control_models.update(
        {
            "preset": preset,
            "mode": mode,
            "shots": shots,
            "seed": seed,
            "parameter_points": parameter_points,
        }
    )
    controls_column = column(
        Div(
            text=(
                f"<h2>{html.escape(scenario.title)}</h2>"
                "<p>修改业务输入后运行。模式建议会在每次运行前重新计算。</p>"
            ),
            css_classes=["panel-heading"],
        ),
        preset,
        controls,
        Div(text="<h3>量子执行</h3>"),
        mode,
        row(shots, seed, sizing_mode="stretch_width"),
        parameter_points,
        run_button,
        width=330,
        min_width=300,
        sizing_mode="stretch_height",
        css_classes=["control-panel"],
        stylesheets=[mobile_full_width_stylesheet()],
    )
    result_title = Div(text=_result_title_html(case_id, scenario.title, analysis))
    content = column(
        result_title,
        status,
        metrics,
        tabs,
        sizing_mode="stretch_width",
        css_classes=["result-panel"],
        styles={"min-width": "0", "padding": "20px"},
    )
    root = row(
        controls_column,
        content,
        sizing_mode="stretch_width",
        visible=case_id == "portfolio",
        css_classes=["case-workspace"],
        styles={"min-width": "0", "align-items": "stretch"},
    )
    workspace = Workspace(
        case_id=case_id,
        root=root,
        controls=control_models,
        tabs=tabs,
        run_button=run_button,
        status=status,
        metrics=metrics,
        input_source=input_source,
        business_source=business_source,
        selection_source=selection_source,
        matrix_source=matrix_source,
        objective_source=objective_source,
        counts_source=counts_source,
        feasibility_source=feasibility_source,
        term_source=term_source,
        atom_source=atom_source,
        waveform_sources=waveform_sources,
        circuit_sources=circuit_sources,
        circuit_figure=circuit_plot,
        circuit_layer_figure=layer_plot,
        circuit_mode=circuit_mode,
        circuit_window=circuit_window,
        audit=audit,
        analysis_summary=analysis_summary,
        quantum_note=quantum_note,
        result_title=result_title,
        atom_figure=atom_plot,
        waveform_figure=waveform_plot,
        circuit_cache=[],
        analysis=analysis,
        result_cache={},
        callbacks_suspended=False,
    )

    def on_preset(_attr: str, _old: str, _new: str) -> None:
        case_input = _build_case_input(workspace, use_control_values=False)
        workspace.callbacks_suspended = True
        try:
            _set_controls_from_input(workspace, case_input)
        finally:
            workspace.callbacks_suspended = False
        workspace.input_source.data = _input_rows(case_id, case_input)
        current = executor.analyze(scenario, case_input)
        _apply_analysis(workspace, current)
        _clear_result_views(workspace, "预设已修改，请重新运行实验。")

    preset.on_change("value", on_preset)

    def on_mode(_attr: str, _old: str, _new: str) -> None:
        _restore_mode_result(workspace)

    mode.on_change("value", on_mode)

    def input_callback(control_name: str) -> Any:
        def on_run_input(_attr: str, _old: Any, _new: Any) -> None:
            if workspace.callbacks_suspended:
                return
            try:
                current_input = _build_case_input(workspace)
                workspace.input_source.data = _input_rows(case_id, current_input)
                if control_name in business_control_names:
                    current = executor.analyze(scenario, current_input)
                    _apply_analysis(workspace, current)
            except (TypeError, ValueError):
                # A partially edited input is validated again before execution.
                pass
            _clear_result_views(
                workspace,
                "输入或运行参数已修改，请重新运行实验。",
            )

        return on_run_input

    for name, control in workspace.controls.items():
        if name not in {"preset", "mode"}:
            control.on_change("value", input_callback(name))

    def on_circuit_mode(_attr: str, _old: int, value: int) -> None:
        workspace.circuit_figure.visible = value == 0
        workspace.circuit_window.visible = value == 0
        workspace.circuit_layer_figure.visible = value == 1

    circuit_mode.on_change("active", on_circuit_mode)

    def on_window(
        _attr: str, _old: tuple[float, float], value: tuple[float, float]
    ) -> None:
        _render_circuit_window(workspace, int(value[0]), int(value[1]))

    circuit_window.on_change("value", on_window)
    return workspace


def _scenario_controls(case_id: str, case_input: Any) -> tuple[Any, dict[str, Any]]:
    controls: dict[str, Any] = {}
    if case_id == "portfolio":
        controls["risk_weight"] = Slider(
            title="风险权重",
            start=0.2,
            end=0.85,
            value=case_input.risk_weight,
            step=0.05,
        )
        controls["selected_count"] = Select(
            title="持仓数量",
            value=str(case_input.selected_count),
            options=["3", "4", "5"],
        )
        controls["sector_cap"] = Select(
            title="单行业上限",
            value=str(case_input.sector_cap),
            options=["1", "2", "3"],
        )
        controls["minimum_defensive"] = Select(
            title="防御资产下限",
            value=str(case_input.minimum_defensive),
            options=["0", "1", "2"],
        )
    elif case_id == "settlement":
        controls["notional_weight"] = Slider(
            title="金额权重",
            start=0.2,
            end=0.8,
            value=case_input.notional_weight,
            step=0.05,
        )
        controls["priority_weight"] = Slider(
            title="优先级权重",
            start=0.2,
            end=0.8,
            value=case_input.priority_weight,
            step=0.05,
        )
        controls["batch_cap"] = Select(
            title="批次上限",
            value=str(case_input.batch_cap),
            options=["5", "6", "7", "8"],
        )
        controls["penalty"] = Slider(
            title="约束罚项倍数",
            start=1.2,
            end=3.5,
            value=case_input.penalty_multiplier,
            step=0.1,
        )
    elif case_id == "fraud_routing":
        controls["risk_weight"] = Slider(
            title="风险权重",
            start=0.1,
            end=0.8,
            value=case_input.risk_weight,
            step=0.05,
        )
        controls["exposure_weight"] = Slider(
            title="金额权重",
            start=0.1,
            end=0.8,
            value=case_input.exposure_weight,
            step=0.05,
        )
        controls["urgency_weight"] = Slider(
            title="时效权重",
            start=0.1,
            end=0.8,
            value=case_input.urgency_weight,
            step=0.05,
        )
        controls["slots"] = Select(
            title="调查席位",
            value=str(case_input.investigator_slots),
            options=["3", "4", "5", "6"],
        )
        controls["entity_cap"] = Select(
            title="单实体并行上限",
            value=str(case_input.entity_parallel_cap),
            options=["1", "2"],
        )
    elif isinstance(case_input, SelectionInput):
        controls["value_weight"] = Slider(
            title="业务价值权重",
            start=0.2,
            end=0.85,
            value=case_input.value_weight,
            step=0.05,
        )
        controls["cost_weight"] = Slider(
            title="成本权重",
            start=0.15,
            end=0.8,
            value=case_input.cost_weight,
            step=0.05,
        )
        if case_input.selected_count is not None:
            controls["selected_count"] = Select(
                title="选择数量",
                value=str(case_input.selected_count),
                options=["3", "4", "5"],
            )
        if case_input.minimum_units is not None:
            controls["minimum_units"] = Slider(
                title="最低覆盖单位",
                start=8,
                end=16,
                value=case_input.minimum_units,
                step=1,
            )
        if case_input.maximum_units is not None:
            controls["maximum_units"] = Slider(
                title="资本使用上限",
                start=8,
                end=14,
                value=case_input.maximum_units,
                step=1,
            )
        if case_input.group_cap is not None:
            controls["group_cap"] = Select(
                title="单分组上限",
                value=str(case_input.group_cap),
                options=["1", "2", "3"],
            )
    else:
        controls["product"] = Select(
            title="产品", value=case_input.product, options=list(PRESETS["derivatives"])
        )
        controls["spot"] = Slider(
            title="标的价格", start=70, end=140, value=case_input.spot, step=1
        )
        controls["strike"] = Slider(
            title="执行价", start=70, end=140, value=case_input.strike, step=1
        )
        controls["volatility"] = Slider(
            title="波动率", start=0.08, end=0.6, value=case_input.volatility, step=0.01
        )
        controls["rate"] = Slider(
            title="无风险利率", start=0.0, end=0.1, value=case_input.rate, step=0.005
        )
        controls["maturity"] = Slider(
            title="期限（年）",
            start=0.25,
            end=2.0,
            value=case_input.maturity,
            step=0.25,
        )
        controls["barrier"] = Slider(
            title="障碍价", start=105, end=180, value=case_input.barrier, step=1
        )
        controls["paths"] = Select(
            title="Monte Carlo 路径",
            value=str(case_input.paths),
            options=["1024", "2048", "4096"],
        )
    return column(*controls.values(), sizing_mode="stretch_width"), controls


def _build_case_input(workspace: Workspace, *, use_control_values: bool = True) -> Any:
    case_id = workspace.case_id
    base = _preset_input(case_id, workspace.controls["preset"].value)
    if not use_control_values:
        return base
    c = workspace.controls
    if case_id == "portfolio":
        return replace(
            base,
            risk_weight=float(c["risk_weight"].value),
            selected_count=int(c["selected_count"].value),
            sector_cap=int(c["sector_cap"].value),
            minimum_defensive=int(c["minimum_defensive"].value),
        )
    if case_id == "settlement":
        return replace(
            base,
            notional_weight=float(c["notional_weight"].value),
            priority_weight=float(c["priority_weight"].value),
            batch_cap=int(c["batch_cap"].value),
            penalty_multiplier=float(c["penalty"].value),
        )
    if case_id == "fraud_routing":
        return replace(
            base,
            risk_weight=float(c["risk_weight"].value),
            exposure_weight=float(c["exposure_weight"].value),
            urgency_weight=float(c["urgency_weight"].value),
            investigator_slots=int(c["slots"].value),
            entity_parallel_cap=int(c["entity_cap"].value),
        )
    if isinstance(base, SelectionInput):
        changes = {
            "value_weight": float(c["value_weight"].value),
            "cost_weight": float(c["cost_weight"].value),
        }
        for name in ("selected_count", "minimum_units", "maximum_units", "group_cap"):
            if name in c:
                changes[name] = int(c[name].value)
        return replace(base, **changes)
    return replace(
        base,
        product=c["product"].value,
        spot=float(c["spot"].value),
        strike=float(c["strike"].value),
        volatility=float(c["volatility"].value),
        rate=float(c["rate"].value),
        maturity=float(c["maturity"].value),
        barrier=float(c["barrier"].value),
        paths=int(c["paths"].value),
    )


def _set_controls_from_input(workspace: Workspace, case_input: Any) -> None:
    c = workspace.controls
    values = {
        "risk_weight": getattr(case_input, "risk_weight", None),
        "selected_count": getattr(case_input, "selected_count", None),
        "sector_cap": getattr(case_input, "sector_cap", None),
        "minimum_defensive": getattr(case_input, "minimum_defensive", None),
        "notional_weight": getattr(case_input, "notional_weight", None),
        "priority_weight": getattr(case_input, "priority_weight", None),
        "batch_cap": getattr(case_input, "batch_cap", None),
        "penalty": getattr(case_input, "penalty_multiplier", None),
        "exposure_weight": getattr(case_input, "exposure_weight", None),
        "urgency_weight": getattr(case_input, "urgency_weight", None),
        "slots": getattr(case_input, "investigator_slots", None),
        "entity_cap": getattr(case_input, "entity_parallel_cap", None),
        "value_weight": getattr(case_input, "value_weight", None),
        "cost_weight": getattr(case_input, "cost_weight", None),
        "minimum_units": getattr(case_input, "minimum_units", None),
        "maximum_units": getattr(case_input, "maximum_units", None),
        "group_cap": getattr(case_input, "group_cap", None),
        "product": getattr(case_input, "product", None),
        "spot": getattr(case_input, "spot", None),
        "strike": getattr(case_input, "strike", None),
        "volatility": getattr(case_input, "volatility", None),
        "rate": getattr(case_input, "rate", None),
        "maturity": getattr(case_input, "maturity", None),
        "barrier": getattr(case_input, "barrier", None),
        "paths": getattr(case_input, "paths", None),
    }
    for name, value in values.items():
        if name not in c or value is None:
            continue
        c[name].value = str(value) if isinstance(c[name], Select) else value


def _preset_input(case_id: str, preset: str) -> Any:
    scenario = PROBLEM_SCENARIOS[case_id]
    base = scenario.default_input()
    if case_id == "portfolio":
        changes = {
            "rates": {"risk_weight": 0.68, "minimum_defensive": 1},
            "drawdown": {"risk_weight": 0.75, "minimum_defensive": 2},
            "commodity": {"risk_weight": 0.45, "sector_cap": 2},
        }
        return replace(base, **changes.get(preset, {}))
    if case_id == "settlement":
        changes = {
            "tight": {"batch_cap": 5, "notional_weight": 0.45},
            "priority": {"notional_weight": 0.35, "priority_weight": 0.65},
        }
        return replace(base, **changes.get(preset, {}))
    if case_id == "fraud_routing":
        changes = {
            "ring": {"risk_weight": 0.65, "investigator_slots": 5},
            "merchant": {"exposure_weight": 0.5, "entity_parallel_cap": 2},
        }
        return replace(base, **changes.get(preset, {}))
    if case_id == "collateral":
        changes = {
            "haircut": {"value_weight": 0.68, "cost_weight": 0.32},
            "hqla": {"value_weight": 0.45, "cost_weight": 0.55},
        }
        return replace(base, **changes.get(preset, {}))
    if case_id == "liquidity":
        changes = {
            "eod": {"minimum_units": 14, "cost_weight": 0.22},
            "fx": {"minimum_units": 13, "group_cap": 2},
        }
        return replace(base, **changes.get(preset, {}))
    if case_id == "credit_limits":
        changes = {
            "return": {"value_weight": 0.75, "maximum_units": 12},
            "concentration": {"group_cap": 1, "selected_count": 4},
        }
        candidate = replace(base, **changes.get(preset, {}))
        if preset == "concentration" and not scenario.exact_business_points(candidate):
            candidate = replace(candidate, selected_count=3)
        return candidate
    return replace(base, product=preset)


def _submit_run(
    doc: Document,
    worker: ThreadPoolExecutor,
    executor: ScenarioExecutor,
    workspace: Workspace,
) -> None:
    workspace.run_button.disabled = True
    try:
        case_input = _build_case_input(workspace)
        scenario = PROBLEM_SCENARIOS[workspace.case_id]
        current = executor.analyze(scenario, case_input)
        _apply_analysis(workspace, current)
        mode = workspace.controls["mode"].value
        points = int(workspace.controls["parameter_points"].value)
        signature = _run_signature(workspace, case_input, mode)
        workspace.status.text = _status_html(
            "运行中",
            f"正在以 {mode.upper()} 编译原生程序并执行本地模拟。",
            BLUE,
        )
        report_path = REPORT_DIR / f"{workspace.case_id}-{mode}.html"
        all_points = default_parameter_sets(mode)
        future = worker.submit(
            executor.run,
            scenario,
            case_input,
            mode=mode,
            parameter_sets=all_points[:points],
            shots=int(workspace.controls["shots"].value),
            seed=int(workspace.controls["seed"].value),
            report_path=report_path,
        )
        future.add_done_callback(
            lambda finished: doc.add_next_tick_callback(
                lambda: _finish_future(workspace, case_input, signature, finished)
            )
        )
    except Exception as exc:  # Bokeh callbacks must keep the session alive.
        _show_failure(workspace, exc)


def _finish_future(
    workspace: Workspace,
    case_input: Any,
    signature: tuple[str, str, str, str, str],
    future: Any,
) -> None:
    try:
        result = future.result()
        workspace.result_cache[result.mode] = CachedRun(signature, case_input, result)
        if _current_run_matches(workspace, signature, result.mode):
            _apply_result(workspace, case_input, result, signature=signature)
        else:
            workspace.run_button.disabled = False
            workspace.status.text = _status_html(
                "结果已保存",
                "运行期间输入或模式已变化；切回相同配置可恢复本次结果。",
                AMBER,
            )
    except Exception as exc:  # pragma: no cover - exercised by browser callbacks.
        _show_failure(workspace, exc)


def _run_sync(executor: ScenarioExecutor, workspace: Workspace) -> Any:
    case_input = _build_case_input(workspace)
    current = executor.analyze(PROBLEM_SCENARIOS[workspace.case_id], case_input)
    _apply_analysis(workspace, current)
    mode = workspace.controls["mode"].value
    signature = _run_signature(workspace, case_input, mode)
    result = executor.run(
        PROBLEM_SCENARIOS[workspace.case_id],
        case_input,
        mode=mode,
        parameter_sets=default_parameter_sets(mode)[
            : int(workspace.controls["parameter_points"].value)
        ],
        shots=int(workspace.controls["shots"].value),
        seed=int(workspace.controls["seed"].value),
        report_path=REPORT_DIR
        / f"{workspace.case_id}-{mode}.html",
    )
    _apply_result(workspace, case_input, result, signature=signature)
    return result


def _apply_result(
    workspace: Workspace,
    case_input: Any,
    result: Any,
    *,
    signature: tuple[str, str, str, str, str] | None = None,
    restored: bool = False,
) -> None:
    signature = signature or _run_signature(workspace, case_input, result.mode)
    workspace.result_cache[result.mode] = CachedRun(signature, case_input, result)
    _apply_analysis(workspace, result.analysis)
    workspace.run_button.disabled = False
    workspace.status.text = _status_html(
        "已恢复" if restored else "完成",
        f"{result.mode.upper()} · {result.evidence.wall_time_seconds:.3f}s · {result.evidence.shots} shots",
        BLUE if restored else GREEN,
    )
    workspace.metrics.text = _metrics_html(workspace.case_id, case_input, result)
    workspace.input_source.data = _input_rows(workspace.case_id, case_input)
    _set_business_data(workspace, case_input, result)
    _set_selection_data(
        workspace.selection_source, workspace.case_id, case_input, result
    )
    workspace.objective_source.data = {
        "index": [item.evaluation_index for item in result.execution.parameter_history],
        "objective": [
            item.objective_value for item in result.execution.parameter_history
        ],
        "selected": [
            GREEN
            if item.evaluation_index == result.execution.selected_evaluation_index
            else BLUE
            for item in result.execution.parameter_history
        ],
    }
    _set_counts_data(workspace, result.execution.result.counts)
    workspace.term_source.data = _term_data(result.execution.context.term_mapping)
    _set_quantum_data(workspace, result)
    workspace.audit.text = _audit_html(result)


def _run_signature(
    workspace: Workspace,
    case_input: Any,
    mode: str,
) -> tuple[str, str, str, str, str]:
    """Identify the exact business and execution inputs behind a result."""
    return (
        repr(case_input),
        str(mode),
        str(workspace.controls["shots"].value),
        str(workspace.controls["seed"].value),
        str(workspace.controls["parameter_points"].value),
    )


def _current_run_matches(
    workspace: Workspace,
    signature: tuple[str, str, str, str, str],
    mode: str,
) -> bool:
    if workspace.controls["mode"].value != mode:
        return False
    try:
        case_input = _build_case_input(workspace)
    except (TypeError, ValueError):
        return False
    return _run_signature(workspace, case_input, mode) == signature


def _restore_mode_result(workspace: Workspace) -> None:
    mode = workspace.controls["mode"].value
    cached = workspace.result_cache.get(mode)
    if cached is not None and _current_run_matches(
        workspace, cached.signature, cached.result.mode
    ):
        _apply_result(
            workspace,
            cached.case_input,
            cached.result,
            signature=cached.signature,
            restored=True,
        )
        return
    _clear_result_views(workspace, f"{mode.upper()} 尚未在当前输入下运行。")


def _clear_result_views(workspace: Workspace, detail: str) -> None:
    """Remove result-dependent data while retaining the current Problem analysis."""
    mode = workspace.controls["mode"].value
    workspace.status.text = _status_html("待运行", detail, MUTED)
    workspace.metrics.text = _waiting_metrics(workspace.case_id)
    workspace.business_source.data = {
        "x": [],
        "y": [],
        "label": [],
        "color": [],
        "size": [],
        "detail": [],
    }
    workspace.selection_source.data = {
        "item": [],
        "status": [],
        "reason": [],
        "value": [],
    }
    workspace.objective_source.data = {"index": [], "objective": [], "selected": []}
    workspace.counts_source.data = {"state": [], "count": [], "color": []}
    workspace.term_source.data = {
        "operator": [],
        "targets": [],
        "logical": [],
        "analog": [],
        "digital": [],
        "implementation": [],
    }
    workspace.circuit_cache = []
    for name, source in workspace.circuit_sources.items():
        source.data = {key: [] for key in source.data}
        if name == "layers":
            continue
    for source in workspace.waveform_sources.values():
        source.data = {"time": [], "value": [], "raw": []}
    _set_atom_data(
        workspace.atom_source,
        workspace.analysis.problem_analysis.mapping_plan.layout.sites,
        set(),
    )
    has_analog = mode in {"analog", "hybrid"}
    workspace.circuit_mode.visible = mode != "analog"
    workspace.circuit_window.visible = False
    workspace.circuit_figure.visible = False
    workspace.circuit_layer_figure.visible = False
    workspace.atom_figure.visible = has_analog
    workspace.waveform_figure.visible = has_analog
    workspace.quantum_note.text = _quantum_waiting_html(mode)
    workspace.audit.text = _audit_waiting_html()


def _apply_analysis(workspace: Workspace, analysis: Any) -> None:
    """Refresh all mode and mapping facts derived from the current input."""
    workspace.analysis = analysis
    options = _mode_options(analysis)
    allowed_modes = {value for value, _label in options}
    workspace.controls["mode"].options = options
    if workspace.controls["mode"].value not in allowed_modes:
        workspace.controls["mode"].value = analysis.mode_decision.recommended_mode
    workspace.feasibility_source.data = _feasibility_data(analysis)
    workspace.analysis_summary.text = _analysis_html(analysis)
    workspace.result_title.text = _result_title_html(
        workspace.case_id,
        analysis.definition.title,
        analysis,
    )
    _set_matrix_data(workspace.matrix_source, analysis.definition.problem)
    _set_atom_data(
        workspace.atom_source,
        analysis.problem_analysis.mapping_plan.layout.sites,
        set(),
    )


def _show_failure(workspace: Workspace, exc: Exception) -> None:
    workspace.run_button.disabled = False
    workspace.status.text = _status_html("失败", str(exc), RED)


def _mode_options(analysis: Any) -> list[tuple[str, str]]:
    options = []
    for row_item in analysis.mode_decision.rows:
        if row_item.status == "unsuitable":
            continue
        suffix = "推荐" if row_item.status == "recommended" else "对照"
        options.append((row_item.mode, f"{row_item.mode.upper()} · {suffix}"))
    return options


def _feasibility_data(analysis: Any) -> dict[str, list[Any]]:
    rows = analysis.mode_decision.rows
    return {
        "mode": [row.mode.upper() for row in rows],
        "status": [
            {"recommended": "推荐", "comparable": "可比较", "unsuitable": "不适用"}[
                row.status
            ]
            for row in rows
        ],
        "physical": ["可编译" if row.compiler_feasible else "不可编译" for row in rows],
        "analog": [row.analog_term_count for row in rows],
        "digital": [row.digital_term_count for row in rows],
        "reason": [
            row.reason if not row.diagnostic_codes else ", ".join(row.diagnostic_codes)
            for row in rows
        ],
    }


def _input_rows(case_id: str, case_input: Any) -> dict[str, list[Any]]:
    rows: list[tuple[str, str, str, str, str]] = []
    if isinstance(case_input, PortfolioInput):
        rows = [
            (
                asset.name,
                asset.sector,
                f"{asset.expected_return:.1%}",
                f"{asset.volatility:.1%}",
                "防御" if asset.defensive else "风险资产",
            )
            for asset in case_input.assets
        ]
    elif isinstance(case_input, SettlementInput):
        rows = [
            (
                item.trade_id,
                item.currency,
                f"{item.notional_m:.1f}m",
                f"P{item.priority}",
                f"额度 {item.cash_units} / 依赖 {','.join(item.requires) or '-'}",
            )
            for item in case_input.instructions
        ]
    elif isinstance(case_input, FraudRoutingInput):
        rows = [
            (
                item.alert_id,
                item.entity_id,
                f"风险 {item.risk_score:.0f}",
                f"{item.exposure_m:.1f}m",
                f"{item.age_hours:.0f}h / {item.estimated_hours:.1f} 工时",
            )
            for item in case_input.alerts
        ]
    elif isinstance(case_input, SelectionInput):
        rows = [
            (
                item.label,
                item.group,
                f"{item.value:.2f}",
                f"{item.cost:.2f}",
                f"{item.detail} / units {item.units}",
            )
            for item in case_input.items
        ]
    else:
        scenario = PROBLEM_SCENARIOS[case_id]
        rows = [
            (
                f"标的 {spot:+.0%}",
                f"波动率 {vol:+.0%}",
                f"S={case_input.spot * (1 + spot):.1f}",
                f"σ={max(0.01, case_input.volatility + vol):.1%}",
                "Analog 风险情景候选",
            )
            for vol in scenario.volatility_shocks
            for spot in scenario.spot_shocks
        ]
    return {
        "label": [row[0] for row in rows],
        "group": [row[1] for row in rows],
        "value": [row[2] for row in rows],
        "cost": [row[3] for row in rows],
        "detail": [row[4] for row in rows],
    }


def _set_business_data(workspace: Workspace, case_input: Any, result: Any) -> None:
    labels: list[str] = []
    x_values: list[float] = []
    y_values: list[float] = []
    details: list[str] = []
    if isinstance(case_input, PortfolioInput):
        for asset in case_input.assets:
            labels.append(asset.name)
            x_values.append(asset.volatility)
            y_values.append(asset.expected_return)
            details.append(asset.sector)
    elif isinstance(case_input, SettlementInput):
        for item in case_input.instructions:
            labels.append(item.trade_id)
            x_values.append(float(item.cash_units))
            y_values.append(item.notional_m)
            details.append(item.currency)
    elif isinstance(case_input, FraudRoutingInput):
        for item in case_input.alerts:
            labels.append(item.alert_id)
            x_values.append(item.exposure_m)
            y_values.append(item.risk_score)
            details.append(item.entity_id)
    elif isinstance(case_input, SelectionInput):
        for item in case_input.items:
            labels.append(item.item_id)
            x_values.append(item.cost)
            y_values.append(item.value)
            details.append(item.group)
    else:
        scenario = PROBLEM_SCENARIOS[workspace.case_id]
        for node in result.definition.problem.nodes:
            spot_shock, vol_shock = scenario._shocks(node)
            labels.append(node)
            x_values.append(spot_shock)
            y_values.append(vol_shock)
            details.append("风险情景")
    solution = result.displayed_solution
    selected_by_label = set(
        getattr(
            solution,
            "selected_asset_ids",
            getattr(
                solution,
                "selected_trade_ids",
                getattr(
                    solution,
                    "selected_alert_ids",
                    getattr(
                        solution,
                        "selected_item_ids",
                        getattr(solution, "selected_scenario_ids", ()),
                    ),
                ),
            ),
        )
    )
    workspace.business_source.data = {
        "x": x_values,
        "y": y_values,
        "label": labels,
        "color": [GREEN if label in selected_by_label else BLUE for label in labels],
        "size": [16 if label in selected_by_label else 10 for label in labels],
        "detail": details,
    }


def _set_selection_data(
    source: ColumnDataSource, case_id: str, case_input: Any, result: Any
) -> None:
    solution = result.displayed_solution
    if hasattr(solution, "selected_asset_ids"):
        selected = set(solution.selected_asset_ids)
        items = [(asset.asset_id, asset.name) for asset in case_input.assets]
        reasons = {}
    elif hasattr(solution, "selected_trade_ids"):
        selected = set(solution.selected_trade_ids)
        items = [(item.trade_id, item.trade_id) for item in case_input.instructions]
        reasons = solution.exclusion_reasons
    elif hasattr(solution, "selected_alert_ids"):
        selected = set(solution.selected_alert_ids)
        items = [(item.alert_id, item.alert_id) for item in case_input.alerts]
        reasons = solution.exclusion_reasons
    elif hasattr(solution, "selected_item_ids"):
        selected = set(solution.selected_item_ids)
        items = [(item.item_id, item.label) for item in case_input.items]
        reasons = solution.exclusion_reasons
    else:
        selected = set(solution.selected_scenario_ids)
        items = [(node, node) for node in result.definition.problem.nodes]
        reasons = {}
    source.data = {
        "item": [label for _, label in items],
        "status": ["入选" if item_id in selected else "未选" for item_id, _ in items],
        "reason": [
            "当前方案"
            if item_id in selected
            else reasons.get(
                item_id,
                "相邻情景已覆盖"
                if case_id == "derivatives"
                else "目标值未进入当前方案",
            )
            for item_id, _ in items
        ],
        "value": ["1" if item_id in selected else "0" for item_id, _ in items],
    }


def _set_matrix_data(source: ColumnDataSource, problem: Any) -> None:
    variables = tuple(getattr(problem, "variables", getattr(problem, "nodes", ())))
    values: dict[tuple[str, str], float] = {}
    for variable, coefficient in getattr(problem, "linear_terms", ()):
        values[(variable, variable)] = coefficient
    for left, right, coefficient in getattr(problem, "quadratic_terms", ()):
        values[(left, right)] = coefficient
        values[(right, left)] = coefficient
    for left, right in getattr(problem, "edges", ()):
        values[(left, right)] = 1.0
        values[(right, left)] = 1.0
    source.data = {
        "x": [variables.index(right) for left, right in values],
        "y": [variables.index(left) for left, right in values],
        "value": list(values.values()),
        "left": [left for left, _ in values],
        "right": [right for _, right in values],
    }


def _set_counts_data(workspace: Workspace, counts: Any) -> None:
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    top = ordered[:10]
    remainder = sum(count for _, count in ordered[10:])
    if remainder:
        top.append(("其他状态", remainder))
    workspace.counts_source.data = {
        "state": [state for state, _ in top],
        "count": [count for _, count in top],
        "color": [GREEN if index == 0 else BLUE for index in range(len(top))],
    }
    workspace.tabs.tabs[3].child.children[-1].x_range.factors = [
        state for state, _ in top
    ]


def _set_quantum_data(workspace: Workspace, result: Any) -> None:
    mode = result.mode
    native = result.execution.context.native_program.to_dict()
    circuits: list[dict[str, Any]] = []
    analog_program = None
    blocks: list[str] = []
    if mode == "digital":
        circuits = [native["circuit"]]
    elif mode == "hybrid":
        for block in native["blocks"]:
            blocks.append(block["block_type"])
            if "circuit" in block:
                circuits.append(block["circuit"])
            if block.get("block_type") == "analog":
                analog_program = block["program"]
            if block.get("block_type") == "measure":
                targets = [
                    target
                    for measurement in block.get("measurements", ())
                    for target in measurement.get("targets", ())
                ]
                circuits.append(
                    {
                        "qubits": list(result.execution.logical_order),
                        "gates": [
                            {
                                "name": "m",
                                "targets": [target],
                                "controls": [],
                                "parameters": {},
                            }
                            for target in targets
                        ],
                    }
                )
    else:
        analog_program = native

    workspace.circuit_cache = _flatten_circuits(circuits)
    depth = max(1, len(workspace.circuit_cache))
    workspace.circuit_window.end = depth
    workspace.circuit_window.value = (0, min(depth, 80))
    workspace.circuit_window.visible = (
        mode != "analog" and workspace.circuit_mode.active == 0
    )
    workspace.circuit_mode.visible = mode != "analog"
    workspace.circuit_figure.visible = (
        mode != "analog" and workspace.circuit_mode.active == 0
    )
    workspace.circuit_layer_figure.visible = (
        mode != "analog" and workspace.circuit_mode.active == 1
    )
    _render_circuit_window(workspace, 0, min(depth, 80))
    _set_layer_data(workspace, mode, blocks)

    selected = _selected_variables(result)
    sites = result.execution.context.analysis.mapping_plan.layout.sites
    _set_atom_data(workspace.atom_source, sites, selected)
    has_atoms = analog_program is not None
    workspace.atom_figure.visible = has_atoms
    workspace.waveform_figure.visible = has_atoms
    if analog_program is not None:
        _set_waveform_data(workspace.waveform_sources, analog_program)
    else:
        for source in workspace.waveform_sources.values():
            source.data = {"time": [], "value": [], "raw": []}
    workspace.quantum_note.text = _quantum_result_html(result, blocks)


def _flatten_circuits(circuits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    offset = 0
    for circuit in circuits:
        qubits = list(circuit.get("qubits", ()))
        gates = list(circuit.get("gates", ()))
        for measurement in circuit.get("measurements", ()):
            gates.extend(
                {
                    "name": "m",
                    "targets": [target],
                    "controls": [],
                    "parameters": {},
                }
                for target in measurement.get("targets", ())
            )
        for gate in gates:
            flattened.append({**gate, "qubits": qubits, "depth": offset})
            offset += 1
    return flattened


def _render_circuit_window(workspace: Workspace, start: int, end: int) -> None:
    gates = workspace.circuit_cache[max(0, start) : max(start + 1, end)]
    if not gates:
        for source in workspace.circuit_sources.values():
            if source is workspace.circuit_sources["layers"]:
                continue
            source.data = {key: [] for key in source.data}
        return
    qubits = gates[0]["qubits"]
    y_by_qubit = {qubit: len(qubits) - index for index, qubit in enumerate(qubits)}
    width = max(2, len(gates) + 1)
    workspace.circuit_sources["wires"].data = {
        "x0": [0] * len(qubits),
        "x1": [width] * len(qubits),
        "y": list(y_by_qubit.values()),
        "label": [_short_label(qubit) for qubit in qubits],
    }
    x_values = []
    y_values = []
    labels = []
    colors = []
    details = []
    link_x = []
    link_y0 = []
    link_y1 = []
    for local_index, gate in enumerate(gates, start=1):
        targets = list(gate.get("targets", ()))
        controls = list(gate.get("controls", ()))
        involved = [*controls, *targets]
        if len(involved) > 1:
            ys = [y_by_qubit[item] for item in involved]
            link_x.append(local_index)
            link_y0.append(min(ys))
            link_y1.append(max(ys))
        for target in targets or controls:
            x_values.append(local_index)
            y_values.append(y_by_qubit[target])
            name = str(gate.get("name", "U")).upper()
            labels.append(name)
            colors.append(_gate_color(name))
            details.append(str(gate.get("parameters", {})))
    workspace.circuit_sources["gates"].data = {
        "x": x_values,
        "y": y_values,
        "label": labels,
        "color": colors,
        "detail": details,
    }
    workspace.circuit_sources["links"].data = {
        "x": link_x,
        "y0": link_y0,
        "y1": link_y1,
    }
    workspace.circuit_figure.height = max(300, 150 + 28 * len(qubits))
    workspace.circuit_figure.y_range.start = 0
    workspace.circuit_figure.y_range.end = len(qubits) + 1
    workspace.circuit_figure.x_range.start = 0
    workspace.circuit_figure.x_range.end = width


def _set_layer_data(workspace: Workspace, mode: str, blocks: list[str]) -> None:
    if mode == "hybrid":
        labels = ["H", "U1", "A", "U2", "RX1", "M"]
        colors = [BLUE, VIOLET, AMBER, VIOLET, GREEN, MUTED]
    else:
        labels = ["H", "U1", "U2", "RX1", "M"]
        colors = [BLUE, VIOLET, VIOLET, GREEN, MUTED]
    workspace.circuit_sources["layers"].data = {
        "x": list(range(1, len(labels) + 1)),
        "y": [1] * len(labels),
        "width": [0.76] * len(labels),
        "height": [0.72] * len(labels),
        "label": labels,
        "color": colors,
    }
    workspace.circuit_layer_figure.title.text = (
        "Hybrid D-A-D 逻辑层" if mode == "hybrid" else "QAOA 逻辑层 U1/U2/RX1"
    )


def _set_atom_data(source: ColumnDataSource, sites: Any, selected: set[str]) -> None:
    source.data = {
        "x": [site.position[0] for site in sites],
        "y": [site.position[1] for site in sites],
        "label": [_short_label(site.logical_id) for site in sites],
        "color": [GREEN if site.logical_id in selected else BLUE for site in sites],
        "size": [20 if site.logical_id in selected else 14 for site in sites],
        "role": ["入选" if site.logical_id in selected else "未选" for site in sites],
    }


def _set_waveform_data(
    sources: dict[str, ColumnDataSource], program: dict[str, Any]
) -> None:
    terms = program.get("hamiltonian", {}).get("terms", {})
    for name, source in sources.items():
        waveform = terms.get(name)
        if name == "detuning" and isinstance(waveform, dict):
            local_terms = terms.get("local_detuning_terms", ())
            local_values = [
                float(item["waveform"]["values"][0])
                for item in local_terms
                if item.get("waveform", {}).get("values")
            ]
            if local_values and not any(waveform.get("values", ())):
                waveform = {
                    **waveform,
                    "values": [max(local_values, key=abs)],
                }
        if waveform is None:
            source.data = {"time": [], "value": [], "raw": []}
            continue
        if isinstance(waveform, (int, float)):
            duration = max(
                (
                    float(item.get("duration", 0.0))
                    for item in terms.values()
                    if isinstance(item, dict)
                ),
                default=1.0,
            )
            times = [0.0, duration]
            values = [float(waveform), float(waveform)]
        else:
            duration = float(waveform.get("duration", 1.0))
            raw_times = waveform.get("times")
            values = [float(value) for value in waveform.get("values", (0.0,))]
            if raw_times is None:
                times = [0.0, duration]
                values = [values[0], values[0]]
            else:
                times = list(raw_times)
        scale = max((abs(float(value)) for value in values), default=1.0) or 1.0
        source.data = {
            "time": times,
            "value": [float(value) / scale for value in values],
            "raw": [float(value) for value in values],
        }


def _selected_variables(result: Any) -> set[str]:
    solution = result.displayed_solution
    bitstring = solution.bitstring
    logical = tuple(
        getattr(
            result.definition.problem,
            "variables",
            getattr(result.definition.problem, "nodes", ()),
        )
    )
    return {variable for variable, bit in zip(logical, bitstring) if bit == "1"}


def _term_data(mappings: Any) -> dict[str, list[Any]]:
    rows = list(mappings)
    return {
        "operator": [item.operator.upper() for item in rows],
        "targets": [
            ", ".join(_short_label(value) for value in item.targets) for item in rows
        ],
        "logical": [f"{item.logical_coefficient:.5g}" for item in rows],
        "analog": [f"{item.analog_coefficient:.5g}" for item in rows],
        "digital": [f"{item.digital_coefficient:.5g}" for item in rows],
        "implementation": [item.implementation for item in rows],
    }


def _business_figure(case_id: str, source: ColumnDataSource) -> Any:
    labels = {
        "portfolio": ("波动率", "预期收益"),
        "settlement": ("流动性单位", "名义金额 (m)"),
        "fraud_routing": ("涉及金额 (m)", "风险分"),
        "derivatives": ("标的价格冲击", "波动率冲击"),
    }
    x_label, y_label = labels.get(case_id, ("成本", "业务价值"))
    plot = figure(
        title="业务候选与当前选择",
        height=360,
        sizing_mode="stretch_width",
        x_axis_label=x_label,
        y_axis_label=y_label,
        tools="pan,wheel_zoom,reset,save",
    )
    plot.scatter(
        x="x",
        y="y",
        source=source,
        size="size",
        color="color",
        alpha=0.85,
        line_color=SURFACE,
        line_width=1,
    )
    plot.add_tools(
        HoverTool(
            tooltips=[
                ("对象", "@label"),
                ("分组", "@detail"),
                ("x", "@x{0.000}"),
                ("y", "@y{0.000}"),
            ]
        )
    )
    _style_plot(plot)
    return plot


def _matrix_figure(source: ColumnDataSource) -> Any:
    mapper = LinearColorMapper(palette=RdBu11, low=-5.0, high=5.0)
    plot = figure(
        title="Problem 系数 / 邻接结构",
        height=340,
        sizing_mode="stretch_width",
        tools="pan,wheel_zoom,reset,save",
    )
    plot.rect(
        x="x",
        y="y",
        width=0.92,
        height=0.92,
        source=source,
        fill_color={"field": "value", "transform": mapper},
        line_color=None,
    )
    plot.add_tools(
        HoverTool(tooltips=[("变量", "@left / @right"), ("系数", "@value{0.0000}")])
    )
    _style_plot(plot)
    return plot


def _objective_figure(source: ColumnDataSource) -> Any:
    plot = figure(
        title="参数点目标值",
        height=340,
        sizing_mode="stretch_width",
        x_axis_label="参数点",
        y_axis_label="期望目标值",
        tools="reset,save",
    )
    plot.line("index", "objective", source=source, color=BLUE, line_width=2)
    plot.scatter("index", "objective", source=source, size=11, color="selected")
    _style_plot(plot)
    return plot


def _counts_figure(source: ColumnDataSource) -> Any:
    plot = figure(
        title="末端 sampling counts",
        x_range=[],
        height=330,
        sizing_mode="stretch_width",
        x_axis_label="bitstring",
        y_axis_label="counts",
        tools="xpan,xwheel_zoom,reset,save",
    )
    plot.vbar(x="state", top="count", source=source, width=0.72, color="color")
    plot.xaxis.major_label_orientation = 0.8
    plot.add_tools(HoverTool(tooltips=[("bitstring", "@state"), ("counts", "@count")]))
    _style_plot(plot)
    return plot


def _atom_figure(source: ColumnDataSource) -> Any:
    plot = figure(
        title="中性原子排列",
        height=370,
        sizing_mode="stretch_width",
        match_aspect=True,
        x_axis_label="x (μm)",
        y_axis_label="y (μm)",
        tools="pan,wheel_zoom,reset,save",
    )
    plot.scatter(
        x="x",
        y="y",
        source=source,
        size="size",
        color="color",
        alpha=0.9,
        line_color=SURFACE,
        line_width=1.5,
    )
    plot.add_tools(
        HoverTool(
            tooltips=[("site", "@label"), ("状态", "@role"), ("x", "@x"), ("y", "@y")]
        )
    )
    plot.styles = {"flex": "1 1 420px", "min-width": "320px"}
    _style_plot(plot)
    return plot


def _waveform_figure(sources: dict[str, ColumnDataSource]) -> Any:
    plot = figure(
        title="Rabi / Detuning / Phase 合并控制波形",
        height=370,
        sizing_mode="stretch_width",
        x_axis_label="时间 (μs)",
        y_axis_label="归一化控制值",
        tools="pan,wheel_zoom,reset,save",
    )
    for name, color in (("rabi", GREEN), ("detuning", BLUE), ("phase", AMBER)):
        plot.line(
            "time",
            "value",
            source=sources[name],
            color=color,
            line_width=2.5,
            legend_label=name.capitalize(),
        )
    plot.legend.location = "top_left"
    plot.styles = {"flex": "1 1 520px", "min-width": "320px"}
    _style_plot(plot)
    return plot


def _circuit_figure(sources: dict[str, ColumnDataSource]) -> Any:
    plot = figure(
        title="参数化通用门线路",
        height=300,
        sizing_mode="stretch_width",
        x_range=Range1d(0, 2),
        y_range=Range1d(0, 2),
        x_axis_label="当前深度窗口",
        tools="xpan,xwheel_zoom,reset,save",
    )
    plot.segment(
        "x0", "y", "x1", "y", source=sources["wires"], color=GRID, line_width=1.5
    )
    plot.segment(
        "x", "y0", "x", "y1", source=sources["links"], color=MUTED, line_width=1.5
    )
    plot.scatter(
        x="x", y="y", source=sources["gates"], marker="square", size=24, color="color"
    )
    plot.text(
        x="x",
        y="y",
        text="label",
        source=sources["gates"],
        text_align="center",
        text_baseline="middle",
        text_color=SURFACE,
        text_font_size="8pt",
    )
    plot.add_tools(HoverTool(tooltips=[("门", "@label"), ("参数", "@detail")]))
    _style_plot(plot)
    return plot


def _layer_figure(sources: dict[str, ColumnDataSource]) -> Any:
    plot = figure(
        title="QAOA 逻辑层 U1/U2/RX1",
        height=250,
        sizing_mode="stretch_width",
        x_range=Range1d(0, 7),
        y_range=Range1d(0, 2),
        tools="reset,save",
    )
    plot.rect(
        x="x",
        y="y",
        width="width",
        height="height",
        source=sources["layers"],
        color="color",
    )
    plot.text(
        x="x",
        y="y",
        text="label",
        source=sources["layers"],
        text_align="center",
        text_baseline="middle",
        text_color=SURFACE,
    )
    plot.axis.visible = False
    _style_plot(plot)
    return plot


def _style_plot(plot: Any) -> None:
    plot.background_fill_color = SURFACE
    plot.border_fill_color = SURFACE
    plot.outline_line_color = BORDER
    plot.grid.grid_line_color = GRID
    plot.title.text_font_size = "14px"
    plot.title.text_font_style = "normal"


def _analysis_html(analysis: Any) -> str:
    resource = analysis.problem_analysis.mapping_plan.resource_estimate
    canonical = analysis.problem_analysis.canonical_problem
    return (
        '<div class="analysis-grid">'
        f"<span><small>Problem</small><strong>{html.escape(canonical.problem_id)}</strong></span>"
        f"<span><small>类型</small><strong>{canonical.problem_type.upper()}</strong></span>"
        f"<span><small>逻辑变量</small><strong>{resource.get('logical_variables', 0)}</strong></span>"
        f"<span><small>逻辑项</small><strong>{resource.get('logical_terms', 0)}</strong></span>"
        f"<span><small>状态维度</small><strong>{resource.get('state_vector_dimension', 0):,}</strong></span>"
        f"<span><small>推荐模式</small><strong>{analysis.mode_decision.recommended_mode.upper()}</strong></span>"
        "</div>"
        f'<p class="analysis-reason">{html.escape(analysis.mode_decision.reason)}</p>'
    )


def _metrics_html(case_id: str, case_input: Any, result: Any) -> str:
    solution = result.displayed_solution
    source = result.metadata["displayed_source"]
    if hasattr(solution, "expected_return"):
        values = (
            ("预期收益", f"{solution.expected_return:.2%}"),
            ("波动率", f"{solution.volatility:.2%}"),
            ("入选资产", str(len(solution.selected_asset_ids))),
            ("业务约束", "通过" if solution.feasible else "未通过"),
        )
    elif hasattr(solution, "settled_notional_m"):
        values = (
            ("结算金额", f"{solution.settled_notional_m:.1f}m"),
            ("交易数", str(len(solution.selected_trade_ids))),
            ("业务目标", f"{solution.business_objective:.3f}"),
            ("约束", "通过" if solution.feasible else "未通过"),
        )
    elif hasattr(solution, "risk_coverage"):
        values = (
            ("风险覆盖", f"{solution.risk_coverage:.1%}"),
            ("金额覆盖", f"{solution.exposure_coverage:.1%}"),
            ("调查任务", str(len(solution.selected_alert_ids))),
            ("约束", "通过" if solution.feasible else "未通过"),
        )
    elif hasattr(solution, "total_value"):
        values = (
            ("业务价值", f"{solution.total_value:.2f}"),
            ("总成本", f"{solution.total_cost:.2f}"),
            ("资源单位", str(solution.total_units)),
            ("约束", "通过" if solution.feasible else "未通过"),
        )
    else:
        pricing = PROBLEM_SCENARIOS[case_id].price(case_input)
        values = (
            ("参考价格", f"{pricing.reference_price:.4f}"),
            ("Delta", f"{pricing.delta:.4f}"),
            ("Gamma", f"{pricing.gamma:.4f}"),
            ("Analog 情景", str(len(solution.selected_scenario_ids))),
        )
    return (
        '<div class="metrics">'
        + "".join(
            f"<span><small>{label}</small><strong>{value}</strong></span>"
            for label, value in values
        )
        + f"<span><small>展示来源</small><strong>{html.escape(source)}</strong></span></div>"
    )


def _waiting_metrics(case_id: str) -> str:
    del case_id
    return (
        '<div class="metrics">'
        + "".join(
            f"<span><small>{label}</small><strong>—</strong></span>"
            for label in ("业务结果", "候选", "约束", "耗时", "报告")
        )
        + "</div>"
    )


def _audit_html(result: Any) -> str:
    payload = {
        "case_id": result.case_id,
        "mode": result.mode,
        "problem_hash": result.execution.problem_hash,
        "analysis_hash": result.execution.analysis_hash,
        "compile_hash": result.execution.compile_hash,
        "execution_hash": result.execution.execution_hash,
        "target_id": result.execution.context.analysis.mapping_plan.target_id,
        "backend": result.evidence.backend,
        "execution_kind": result.evidence.execution_kind,
        "seed": result.evidence.seed,
        "shots": result.evidence.shots,
        "wall_time_seconds": result.evidence.wall_time_seconds,
        "hardware_execution": result.evidence.hardware_execution,
        "cloud_execution": result.evidence.cloud_execution,
        "network_accessed": result.evidence.network_accessed,
        "optimality_claim": result.execution.optimality_claim,
        "report_path": str(result.report_path) if result.report_path else None,
    }
    return (
        "<h3>运行证据</h3>"
        "<p>以下字段直接来自本次 Problem 执行和本地运行边界。</p>"
        f'<pre class="audit-json">{html.escape(json.dumps(payload, ensure_ascii=False, indent=2))}</pre>'
    )


def _audit_waiting_html() -> str:
    return "<h3>运行证据</h3><p>运行后显示 Problem、Target、Backend、hash、shots 和执行边界。</p>"


def _quantum_waiting_html(mode: str) -> str:
    return f'<div class="quantum-note"><strong>推荐 {mode.upper()}</strong><span>运行后显示实际原生程序和采样结果。</span></div>'


def _quantum_result_html(result: Any, blocks: list[str]) -> str:
    mapping = result.execution.context.term_mapping
    analog = sum(abs(item.analog_coefficient) > 1e-12 for item in mapping)
    digital = sum(abs(item.digital_coefficient) > 1e-12 for item in mapping)
    block_text = (
        " → ".join(item.upper() for item in blocks) if blocks else result.mode.upper()
    )
    boundary = (
        "counts 不参与经典参考价格。"
        if result.case_id == "derivatives"
        else "业务约束由原始输入重新检查。"
    )
    return (
        '<div class="quantum-note">'
        f"<strong>{block_text}</strong><span>Analog terms {analog} · Digital terms {digital} · "
        f"{html.escape(boundary)}</span></div>"
    )


def _status_html(title: str, detail: str, color: str) -> str:
    return f'<div class="run-status"><span style="background:{color}"></span><strong>{html.escape(title)}</strong><p>{html.escape(detail)}</p></div>'


def _scenario_description(case_id: str) -> str:
    return {
        "portfolio": "稠密协方差和全局约束使用 Digital QAOA。",
        "settlement": "交易冲突交给 Analog，相依关系和流动性约束保留为 Digital residual。",
        "fraud_routing": "共享实体冲突映射到原子相互作用，调查权重和席位约束使用数字项。",
        "collateral": "资格、唯一分配和覆盖约束使用 Digital QAOA。",
        "liquidity": "带时序和币种约束的资金动作使用 Digital QAOA。",
        "credit_limits": "资本预算和行业集中度使用 Digital QAOA；不用于授信审批。",
        "derivatives": "价格来自经典模型；Analog 只选择代表性压力情景。",
    }[case_id]


def _result_title_html(case_id: str, title: str, analysis: Any) -> str:
    mode = analysis.mode_decision.recommended_mode.upper()
    return (
        '<div class="result-title"><div>'
        f"<h1>{html.escape(title)}</h1>"
        f"<p>{_scenario_description(case_id)}</p></div>"
        f'<span class="mode-badge">推荐 {mode}</span></div>'
    )


def _short_label(value: str) -> str:
    if len(value) <= 18:
        return value
    return value[:15] + "..."


def _gate_color(name: str) -> str:
    return {"H": BLUE, "RX": GREEN, "RZ": VIOLET, "CX": AMBER, "M": MUTED}.get(
        name, BLUE
    )


_WORKBENCH_CSS = """
.app-header {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  min-height: 60px; padding: 10px 20px; flex-wrap: wrap;
}
.brand { display: flex; align-items: baseline; gap: 10px; }
.brand strong { font-size: 18px; font-weight: 650; }
.brand span, .panel-heading p, .result-title p, .analysis-reason { color: #5c6b64; }
.environment { display: flex; gap: 7px; flex-wrap: wrap; }
.environment span, .mode-badge { border: 1px solid #d7dfda; border-radius: 4px; padding: 5px 9px; background: #fff; }
.case-navigation { padding: 18px 12px; background: #e9eeeb; }
.nav-title { color: #5c6b64; font-size: 12px; font-weight: 650; margin-bottom: 4px; }
.nav-mode { color: #5c6b64; font-size: 11px; padding-left: 5px; }
.control-panel { padding: 20px 16px; background: #fff; border-right: 1px solid #d7dfda; }
.panel-heading h2, .result-title h1 { margin: 0; font-weight: 650; letter-spacing: 0; }
.panel-heading h2 { font-size: 17px; }
.panel-heading p, .result-title p { margin: 6px 0 12px; line-height: 1.5; }
.result-title { display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; flex-wrap: wrap; }
.result-title h1 { font-size: 22px; }
.mode-badge { color: #146c43; white-space: nowrap; }
.run-status { display: grid; grid-template-columns: 9px auto 1fr; align-items: center; gap: 8px; padding: 10px 0; }
.run-status > span { width: 8px; height: 8px; border-radius: 50%; }
.run-status p { margin: 0; color: #5c6b64; min-width: 0; }
.metrics { display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); border-top: 1px solid #d7dfda; border-bottom: 1px solid #d7dfda; }
.metrics span { padding: 12px 14px; border-right: 1px solid #d7dfda; }
.metrics small, .analysis-grid small { display: block; color: #5c6b64; margin-bottom: 4px; }
.metrics strong, .analysis-grid strong { display: block; font-size: 15px; overflow-wrap: anywhere; }
.analysis-grid { display: grid; grid-template-columns: repeat(6, minmax(110px, 1fr)); gap: 0; border: 1px solid #d7dfda; }
.analysis-grid span { padding: 10px 12px; border-right: 1px solid #d7dfda; }
.analysis-reason { margin: 8px 0 12px; }
.quantum-note { display: flex; justify-content: space-between; gap: 12px; padding: 10px 12px; border-left: 3px solid #146c43; background: #edf2ef; flex-wrap: wrap; }
.quantum-note span { color: #5c6b64; }
.audit-json { margin: 0; padding: 14px; border: 1px solid #d7dfda; background: #fff; white-space: pre-wrap; overflow-wrap: anywhere; max-width: 100%; }
@media (max-width: 980px) {
  .metrics { grid-template-columns: repeat(2, minmax(130px, 1fr)); }
  .analysis-grid { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
}
@media (max-width: 760px) {
  .app-header { padding: 10px 12px; }
  .brand { flex-direction: column; gap: 2px; }
  .case-navigation { min-height: auto !important; }
  .metrics { grid-template-columns: 1fr 1fr; }
  .quantum-pair > * { min-width: 100% !important; width: 100% !important; }
}
"""
