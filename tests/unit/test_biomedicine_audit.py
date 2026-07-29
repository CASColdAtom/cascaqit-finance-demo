"""Cross-scenario reproducibility contracts for biomedicine audit hashes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from cascaqit_biomedicine_demo.active_center import run_active_center
from cascaqit_biomedicine_demo.docking import run_docking_match
from cascaqit_biomedicine_demo.electronic_structure import (
    run_electronic_structure,
)
from cascaqit_biomedicine_demo.peptide_landscape import run_peptide_landscape

RunFactory = Callable[[], dict[str, Any]]


def _electronic_run() -> dict[str, Any]:
    return run_electronic_structure(
        preset="h2_bond_scan",
        values={},
        shots=16,
        seed=23,
        layers=1,
        parameter_budget=6,
        optimizer_starts=1,
    )


def _docking_run() -> dict[str, Any]:
    return run_docking_match(
        preset="reference_pose",
        values={},
        mode="hybrid",
        shots=16,
        seed=23,
        layers=1,
        search_strategy="preset",
        parameter_budget=2,
        optimizer_starts=1,
    )


def _active_center_run() -> dict[str, Any]:
    return run_active_center(
        preset="antiferromagnetic",
        values={},
        shots=16,
        seed=23,
        layers=1,
        parameter_budget=6,
        optimizer_starts=1,
    )


def _peptide_run() -> dict[str, Any]:
    return run_peptide_landscape(
        preset="hydrophobic_core",
        values={},
        shots=16,
        seed=23,
        layers=1,
        parameter_budget=4,
        optimizer_starts=1,
    )


@pytest.mark.parametrize(
    "run_factory",
    (_electronic_run, _docking_run, _active_center_run, _peptide_run),
    ids=("electronic", "docking", "active-center", "peptide"),
)
def test_same_configuration_and_seed_have_stable_audit_hashes(
    run_factory: RunFactory,
) -> None:
    first = run_factory()["audit"]
    second = run_factory()["audit"]

    assert first["configurationHash"] == second["configurationHash"]
    assert first["outcomeHash"] == second["outcomeHash"]
    assert first["reportHash"] == second["reportHash"]
    assert first["backendHash"] == second["backendHash"]
    assert first["hardwareExecution"] is False
    assert first["cloudExecution"] is False
    assert first["networkAccessed"] is False
