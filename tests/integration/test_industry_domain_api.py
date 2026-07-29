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


def test_preview_scenario_rejects_execution_before_backend_work() -> None:
    analysis = client.post(
        "/api/domains/biomedicine/scenarios/docking_match/analyze",
        json={},
    )
    run = client.post(
        "/api/domains/biomedicine/scenarios/docking_match/run",
        json={},
    )
    assert analysis.status_code == 200
    assert analysis.json()["analysis"]["implementationStatus"] == "preview"
    assert run.status_code == 422
    assert run.json()["detail"]["code"] == "BIOMEDICINE_EXECUTOR_NOT_IMPLEMENTED"


def test_legacy_finance_catalog_remains_seven_scenarios() -> None:
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    assert len(response.json()["scenarios"]) == 7
