"""Bokeh document and synchronous workflow smoke tests."""

from __future__ import annotations

import json

from bokeh.core.validation import check_integrity
from bokeh.document import Document
from bokeh.embed.standalone import html_page_for_render_items
from bokeh.embed.util import RenderItem

from cascaqit_finance_demo.app import build_document


def test_app_builds_seven_scenarios_and_five_result_tabs() -> None:
    document = Document()
    handles = build_document(document)

    serialized = json.dumps(document.to_json(), ensure_ascii=False)
    assert document.title == "中科酷原行业量子实验台 · 金融领域"
    assert len(document.roots) == 1
    assert list(handles["workspaces"]) == [
        "portfolio",
        "settlement",
        "fraud_routing",
        "collateral",
        "liquidity",
        "credit_limits",
        "derivatives",
    ]
    assert [panel.title for panel in handles["tabs"].tabs] == [
        "业务结果",
        "场景分析",
        "Problem 映射",
        "量子实验",
        "审计证据",
    ]
    assert "合成数据" in serialized
    assert "counts 不参与经典参考价格" not in serialized
    assert "运行实验" in serialized


def test_navigation_switches_complete_workspaces() -> None:
    document = Document()
    handles = build_document(document)

    handles["active_case"].value = "derivatives"

    assert handles["workspaces"]["derivatives"].root.visible is True
    assert handles["workspaces"]["portfolio"].root.visible is False
    assert handles["navigation"]["derivatives"].button_type == "success"
    assert handles["workspaces"]["derivatives"].controls["mode"].value == "analog"


def test_custom_template_renders_as_server_page() -> None:
    document = Document()
    build_document(document)

    rendered = html_page_for_render_items(
        bundle=("", ""),
        docs_json={},
        render_items=[RenderItem(docid="finance-document")],
        title=document.title,
        template=document.template,
    )

    assert "中科酷原行业量子实验台" in rendered
    assert "金融领域" in rendered
    assert "overflow-x: clip" in rendered
    assert "analysis-grid" in rendered


def test_bokeh_models_have_valid_layout_and_quantum_plot_structure() -> None:
    document = Document()
    handles = build_document(document)

    issues = check_integrity(document.roots)

    assert issues.error == []
    assert issues.warning == []
    for workspace in handles["workspaces"].values():
        assert workspace.atom_figure.match_aspect is True
        assert len(workspace.waveform_figure.renderers) == 3
        assert set(workspace.waveform_sources) == {"rabi", "detuning", "phase"}


def test_digital_run_populates_circuit_counts_mapping_and_audit() -> None:
    document = Document()
    handles = build_document(document)
    workspace = handles["workspaces"]["portfolio"]
    workspace.controls["parameter_points"].value = "1"
    workspace.controls["shots"].value = "16"

    result = handles["run_sync"]("portfolio")

    assert result.mode == "digital"
    assert sum(workspace.counts_source.data["count"]) == 16
    gate_names = {str(gate["name"]).upper() for gate in workspace.circuit_cache}
    assert {"H", "RZ", "RX", "M"} <= gate_names
    assert workspace.term_source.data["operator"]
    assert "hardware_execution" in workspace.audit.text
    assert workspace.atom_figure.visible is False


def test_hybrid_and_analog_runs_populate_atom_and_waveform_views() -> None:
    document = Document()
    handles = build_document(document)
    for case_id, expected_mode in (("settlement", "hybrid"), ("derivatives", "analog")):
        workspace = handles["workspaces"][case_id]
        workspace.controls["parameter_points"].value = "1"
        workspace.controls["shots"].value = "16"

        result = handles["run_sync"](case_id)

        assert result.mode == expected_mode
        assert workspace.atom_source.data["x"]
        assert workspace.waveform_sources["rabi"].data["time"]
        assert workspace.waveform_sources["detuning"].data["time"]
        assert workspace.atom_figure.visible is True
        assert workspace.waveform_figure.visible is True
        assert sum(workspace.counts_source.data["count"]) == 16
    assert (
        "counts 不参与经典参考价格"
        in handles["workspaces"]["derivatives"].quantum_note.text
    )


def test_mode_switch_keeps_each_execution_result_isolated() -> None:
    document = Document()
    handles = build_document(document)
    workspace = handles["workspaces"]["derivatives"]
    workspace.controls["parameter_points"].value = "1"
    workspace.controls["shots"].value = "16"

    analog = handles["run_sync"]("derivatives")
    analog_counts = dict(workspace.counts_source.data)

    workspace.controls["mode"].value = "digital"
    assert workspace.counts_source.data["count"] == []
    assert "DIGITAL 尚未" in workspace.status.text

    digital = handles["run_sync"]("derivatives")
    assert digital.mode == "digital"
    assert digital.execution.problem_hash == analog.execution.problem_hash
    assert digital.execution.logical_order == analog.execution.logical_order
    assert "&quot;mode&quot;: &quot;digital&quot;" in workspace.audit.text

    workspace.controls["mode"].value = "analog"
    assert workspace.counts_source.data == analog_counts
    assert "&quot;mode&quot;: &quot;analog&quot;" in workspace.audit.text
    assert "已恢复" in workspace.status.text
    assert set(workspace.result_cache) == {analog.mode, digital.mode}


def test_changed_input_clears_result_dependent_views() -> None:
    document = Document()
    handles = build_document(document)
    workspace = handles["workspaces"]["portfolio"]
    workspace.controls["parameter_points"].value = "1"
    workspace.controls["shots"].value = "16"
    handles["run_sync"]("portfolio")

    assert workspace.counts_source.data["count"]
    workspace.controls["risk_weight"].value = 0.75

    assert workspace.counts_source.data["count"] == []
    assert workspace.business_source.data["label"] == []
    assert workspace.term_source.data["operator"] == []
    assert "已修改" in workspace.status.text


def test_run_reanalyzes_input_and_falls_back_from_hybrid_to_digital() -> None:
    document = Document()
    handles = build_document(document)
    workspace = handles["workspaces"]["fraud_routing"]
    workspace.controls["parameter_points"].value = "1"
    workspace.controls["shots"].value = "16"
    workspace.controls["entity_cap"].value = "2"

    assert workspace.controls["mode"].value == "digital"
    assert "推荐 DIGITAL" in workspace.result_title.text
    result = handles["run_sync"]("fraud_routing")

    assert result.mode == "digital"
    assert workspace.controls["mode"].value == "digital"
    assert [value for value, _label in workspace.controls["mode"].options] == [
        "digital"
    ]
    assert workspace.atom_figure.visible is False
