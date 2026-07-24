"""Circuit-view invariants for the unified finance workbench."""

from __future__ import annotations

from bokeh.document import Document

from cascaqit_finance_demo.app import build_document


def test_circuit_height_and_depth_follow_real_program_size() -> None:
    document = Document()
    handles = build_document(document)
    workspace = handles["workspaces"]["portfolio"]
    workspace.controls["parameter_points"].value = "1"
    workspace.controls["shots"].value = "16"
    original_x_range = workspace.circuit_figure.x_range
    original_y_range = workspace.circuit_figure.y_range

    result = handles["run_sync"]("portfolio")

    qubits = len(result.execution.logical_order)
    assert workspace.circuit_figure.height == max(300, 150 + 28 * qubits)
    assert workspace.circuit_window.end == len(workspace.circuit_cache)
    assert "Uc1" not in workspace.circuit_sources["gates"].data["label"]
    assert "Uc2" not in workspace.circuit_sources["gates"].data["label"]
    assert workspace.circuit_figure.x_range is original_x_range
    assert workspace.circuit_figure.y_range is original_y_range


def test_circuit_switches_between_universal_and_qaoa_layer_views() -> None:
    document = Document()
    handles = build_document(document)
    workspace = handles["workspaces"]["portfolio"]
    workspace.controls["parameter_points"].value = "1"
    workspace.controls["shots"].value = "16"
    handles["run_sync"]("portfolio")

    assert workspace.circuit_figure.visible is True
    assert workspace.circuit_layer_figure.visible is False
    assert workspace.circuit_sources["layers"].data["label"] == [
        "H",
        "U1",
        "U2",
        "RX1",
        "M",
    ]

    workspace.circuit_mode.active = 1

    assert workspace.circuit_figure.visible is False
    assert workspace.circuit_layer_figure.visible is True
    assert "U1/U2/RX1" in workspace.circuit_layer_figure.title.text
