"""Versioned RNA pairing fixture, QUBO, and QAOA behavior tests."""

from __future__ import annotations

from copy import deepcopy

import pytest

from cascaqit_biomedicine_demo.rna_structure import (
    _definition,
    analyze_rna_structure,
    load_rna_fixture,
    rna_values,
    run_rna_structure,
)


@pytest.mark.parametrize(
    "preset", ("hairpin_reference", "stem_competition", "limited_pseudoknot")
)
def test_rna_fixture_builds_balanced_candidate_pair_qubo(preset: str) -> None:
    fixture = load_rna_fixture(preset)
    values = rna_values(preset, {})
    definition = _definition(preset, values)
    analysis = analyze_rna_structure(preset, values)

    assert fixture.preset["sequence"] == values["sequence"]
    assert 8 <= len(definition.problem.variables) <= 9
    assert analysis["problem"]["coefficientLedger"]["balanced"] is True
    assert analysis["implementationStatus"] == "available"
    assert analysis["decision"]["recommendedMode"] == "digital"
    assert analysis["domain"]["classicExact"]["feasible"] is True
    assert analysis["domain"]["classicDynamicProgramming"]["feasible"] is True
    assert analysis["domain"]["referenceStructure"]["pairIds"]


def test_rna_fixture_rejects_undeclared_crossing_and_invalid_loop() -> None:
    analysis = analyze_rna_structure("limited_pseudoknot", {"minimum_loop": 6})

    assert all(
        item["right"] - item["left"] - 1 >= 6
        for item in analysis["domain"]["candidatePairs"]
    )
    assert analysis["domain"]["pseudoknotPolicy"] == "declared_crossings_only"


def test_rna_fixture_rejects_reference_dot_bracket_mismatch(monkeypatch) -> None:
    fixture = load_rna_fixture("hairpin_reference")
    invalid = deepcopy(fixture.preset)
    invalid["reference"]["dotBracket"] = "............"

    from cascaqit_biomedicine_demo import rna_structure

    with pytest.raises(ValueError, match="does not match reference pairs"):
        rna_structure._validate_preset("hairpin_reference", invalid)


@pytest.mark.parametrize("seed", (7, 23, 41))
def test_rna_qaoa_three_seed_calibration_never_uses_classic_fallback(seed: int) -> None:
    run = run_rna_structure(
        preset="hairpin_reference",
        values={},
        shots=256,
        seed=seed,
        layers=1,
        parameter_budget=24,
        optimizer_starts=1,
    )
    candidate = run["domain"]["quantumCandidate"]

    assert candidate["source"] in {"quantum_observed", "quantum_not_observed"}
    assert run["domain"]["classicExact"]["source"] == "classic_exact_enumeration"
    assert run["domain"]["referenceStructure"]["source"] == "dataset_reference"
    assert run["quantum"]["summary"]["shots"] == 256
    assert run["audit"]["hardwareExecution"] is False
    if not candidate["feasible"]:
        assert candidate["pairIds"] == []
        assert candidate["source"] == "quantum_not_observed"


def test_rna_counts_are_not_exposed_as_thermodynamic_probabilities() -> None:
    run = run_rna_structure(
        preset="limited_pseudoknot",
        values={},
        shots=64,
        seed=7,
        layers=1,
        parameter_budget=8,
        optimizer_starts=1,
    )

    domain_keys = {key.lower() for key in run["domain"]}
    candidate_keys = {key.lower() for key in run["domain"]["quantumCandidate"]}
    assert "thermodynamicprobability" not in domain_keys
    assert "pairprobability" not in candidate_keys
    assert any(
        "Boltzmann ensemble" in limitation
        for limitation in run["analysis"]["dataset"]["limitations"]
    )
    assert run["domain"]["interpretation"].startswith("QAOA counts 仅表示")
