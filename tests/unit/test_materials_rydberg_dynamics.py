from __future__ import annotations

import pytest

from cascaqit_materials_demo import rydberg_dynamics as module
from cascaqit_materials_demo.rydberg_dynamics import (
    analyze_rydberg_dynamics,
    load_rydberg_dynamics_fixture,
    run_rydberg_dynamics,
    rydberg_dynamics_values,
)


def test_fixture_preserves_three_coordinate_identities_and_four_site_windows() -> None:
    fixture = load_rydberg_dynamics_fixture()

    assert fixture.manifest["dataset_id"] == (
        "materials.effective-lattice.rydberg-quench.teaching-v1"
    )
    assert set(fixture.domain["coordinateIdentities"]) == {
        "material",
        "effective",
        "rydberg",
    }
    for model in fixture.domain["presets"].values():
        assert len(model["activeWindow"]) == 4
        assert len(model["rydbergPositions"]) == 4
        assert len(model["initialBitstring"]) == 4


@pytest.mark.parametrize(
    "preset",
    ["perfect_lattice", "single_vacancy", "multi_defect_impurity"],
)
def test_analysis_proves_complete_pure_analog_mapping(preset: str) -> None:
    analysis = analyze_rydberg_dynamics(preset, {"sample_count": 5})

    evidence = analysis["domain"]["pureAnalogEvidence"]
    assert analysis["implementationStatus"] == "available"
    assert analysis["executionFamily"] == "analog_ahs"
    assert analysis["problem"]["type"] == "analog_experiment_definition"
    assert analysis["resource"]["analogSites"] == 4
    assert analysis["resource"]["hilbertDimension"] == 16
    assert analysis["domain"]["targetValidation"]["status"] == "verified"
    assert evidence["status"] == "verified"
    assert evidence["digitalGateCount"] == 0
    assert evidence["digitalResidualCount"] == 0
    assert evidence["hybridBlockCount"] == 0
    assert evidence["declaredHamiltonianTermCount"] == (
        evidence["mappedHamiltonianTermCount"]
    )
    assert evidence["missingTermIds"] == []
    assert evidence["unexpectedTermIds"] == []


@pytest.mark.parametrize(
    "preset",
    ["perfect_lattice", "single_vacancy", "multi_defect_impurity"],
)
def test_run_returns_real_prefix_evolution_and_independent_reference(
    preset: str,
) -> None:
    run = run_rydberg_dynamics(
        preset=preset,
        values={"sample_count": 5},
        shots=32,
        seed=23,
        time_steps=120,
    )

    points = run["quantum"]["timeSeries"]
    reference = run["domain"]["classicReference"]
    comparison = run["domain"]["comparison"]
    assert run["quantum"]["kind"] == "analog_ahs"
    assert run["quantum"]["mode"] == "analog"
    assert run["quantum"]["algorithm"] == "ahs_time_evolution"
    assert len(points) == 5
    assert points[0]["solver"] == "declared_initial_state"
    assert points[0]["programHash"] is None
    assert all(point["programHash"] for point in points[1:])
    assert all(point["actualTime"] == point["requestedTime"] for point in points)
    assert all(abs(point["probabilityNorm"] - 1.0) < 1e-12 for point in points)
    assert reference["source"] == "independent_scipy_dop853"
    assert "timeSeries" not in run["domain"]
    assert comparison["maxOccupationAbsoluteError"] < 1e-3
    assert comparison["maxCorrelationAbsoluteError"] < 1e-3
    assert comparison["terminalStateFidelity"] > 0.999
    assert run["audit"]["hardwareExecution"] is False
    assert run["audit"]["cloudExecution"] is False
    assert run["audit"]["networkAccessed"] is False


def test_counts_and_stable_hashes_are_reproducible() -> None:
    kwargs = {
        "preset": "single_vacancy",
        "values": {"sample_count": 5},
        "shots": 32,
        "seed": 41,
        "time_steps": 120,
    }

    first = run_rydberg_dynamics(**kwargs)
    second = run_rydberg_dynamics(**kwargs)

    assert first["quantum"]["terminalCounts"] == second["quantum"][
        "terminalCounts"
    ]
    assert first["audit"]["trajectoryHash"] == second["audit"]["trajectoryHash"]
    assert first["audit"]["reportHash"] == second["audit"]["reportHash"]


def test_controls_change_program_and_analysis_identity() -> None:
    baseline = analyze_rydberg_dynamics("perfect_lattice", {})
    changed = analyze_rydberg_dynamics(
        "perfect_lattice",
        {"duration_us": 1.4, "rabi_amplitude": 3.0, "detuning_end": 1.0},
    )

    assert baseline["analysisHash"] != changed["analysisHash"]
    assert baseline["problem"]["hash"] != changed["problem"]["hash"]
    assert baseline["analogProgram"]["pulseScheduleHash"] != changed[
        "analogProgram"
    ]["pulseScheduleHash"]


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"sample_count": 6}, "odd integer"),
        ({"duration_us": 2.1}, "duration_us"),
        ({"rabi_amplitude": 0.4}, "rabi_amplitude"),
        ({"detuning_end": 4.25}, "detuning_end"),
    ],
)
def test_input_validation_rejects_unsupported_controls(
    values: dict[str, float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        rydberg_dynamics_values("perfect_lattice", values)


def test_sdk_version_source_is_a_hard_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module.cascaqit, "__version__", "1.0.0a1")

    with pytest.raises(ValueError, match="requires CASCAQit"):
        analyze_rydberg_dynamics("perfect_lattice", {})
