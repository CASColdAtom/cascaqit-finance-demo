"""Unified industry-domain API integration tests."""

from fastapi.testclient import TestClient

from cascaqit_finance_demo.api.app import app

client = TestClient(app)


def test_domain_catalog_keeps_finance_and_biomedicine_separate() -> None:
    domains = client.get("/api/domains")
    finance = client.get("/api/domains/finance/scenarios")
    biomedicine = client.get("/api/domains/biomedicine/scenarios")

    assert domains.status_code == 200
    assert [item["id"] for item in domains.json()["domains"]] == [
        "finance",
        "biomedicine",
    ]
    assert len(finance.json()["scenarios"]) == 7
    assert len(biomedicine.json()["scenarios"]) == 4
    assert {item["domainId"] for item in finance.json()["scenarios"]} == {"finance"}
    assert {item["domainId"] for item in biomedicine.json()["scenarios"]} == {
        "biomedicine"
    }


def test_electronic_structure_analysis_exposes_pauli_fixture_evidence() -> None:
    response = client.post(
        "/api/domains/biomedicine/scenarios/electronic_structure/analyze",
        json={"preset": "h2_equilibrium", "values": {}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"]["implementationStatus"] == "available"
    assert payload["analysis"]["problem"]["type"] == "pauli_hamiltonian"
    assert payload["analysis"]["domain"]["molecule"] == "H2"
    assert payload["analysis"]["resource"]["measurementGroups"] == 2


def test_docking_analysis_exposes_hybrid_gate_and_offline_source() -> None:
    analysis = client.post(
        "/api/domains/biomedicine/scenarios/docking_match/analyze",
        json={},
    )
    assert analysis.status_code == 200
    payload = analysis.json()["analysis"]
    assert payload["implementationStatus"] == "available"
    assert payload["problem"]["type"] == "qubo"
    assert payload["decision"]["recommendedMode"] == "hybrid"
    hybrid = next(
        item for item in payload["decision"]["modes"] if item["mode"] == "hybrid"
    )
    assert hybrid["geometryStatus"] == "verified"
    assert hybrid["analogTermCount"] > 0
    assert hybrid["digitalTermCount"] > 0
    assert payload["dataset"]["license"] == "CC0-1.0"


def test_peptide_landscape_run_keeps_quantum_and_classic_landscape_separate() -> None:
    run = client.post(
        "/api/domains/biomedicine/scenarios/peptide_landscape/run",
        json={
            "preset": "hydrophobic_core",
            "mode": "digital",
            "algorithm": "qaoa",
            "shots": 256,
            "seed": 7,
            "layers": 1,
            "parameter_budget": 24,
            "optimizer_starts": 1,
        },
    )
    assert run.status_code == 200
    domain = run.json()["run"]["domain"]
    assert domain["quantumCandidate"]["feasible"] is True
    assert len(domain["fullLandscape"]) == 10
    assert domain["classicGroundConformations"]


def test_active_center_analysis_and_run_expose_one_hamiltonian_chain() -> None:
    analysis_response = client.post(
        "/api/domains/biomedicine/scenarios/active_center/analyze",
        json={"preset": "coupling_imbalance", "values": {}},
    )
    assert analysis_response.status_code == 200
    assert analysis_response.json()["analysis"]["implementationStatus"] == "available"

    response = client.post(
        "/api/domains/biomedicine/scenarios/active_center/run",
        json={
            "preset": "antiferromagnetic",
            "mode": "digital",
            "algorithm": "vqe",
            "shots": 256,
            "seed": 7,
            "layers": 1,
            "parameter_budget": 40,
            "optimizer_starts": 1,
        },
    )
    assert response.status_code == 200
    run = response.json()["run"]
    assert run["audit"]["hamiltonianHash"] == run["comparison"]["hamiltonianHash"]
    assert len(run["domain"]["correlations"]) == 3


def test_docking_run_keeps_quantum_classic_and_reference_results_separate() -> None:
    response = client.post(
        "/api/domains/biomedicine/scenarios/docking_match/run",
        json={
            "preset": "reference_pose",
            "mode": "hybrid",
            "algorithm": "qaoa",
            "shots": 128,
            "seed": 7,
            "layers": 1,
            "search_strategy": "continuous",
            "parameter_budget": 12,
            "optimizer_starts": 1,
        },
    )
    assert response.status_code == 200
    run = response.json()["run"]
    assert run["domain"]["quantumCandidate"]["feasible"] is True
    assert run["domain"]["quantumCandidate"]["source"] == "quantum_observed"
    assert run["domain"]["classicOptimum"]["source"] == "complete_enumeration"
    assert run["domain"]["coCrystalReference"]["source"] == "co_crystal_reference"
    assert run["quantum"]["blocks"] == [
        "digital",
        "analog",
        "digital",
        "measure",
    ]
    assert run["audit"]["domainId"] == "biomedicine"


def test_legacy_finance_catalog_remains_seven_scenarios() -> None:
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    assert len(response.json()["scenarios"]) == 7
