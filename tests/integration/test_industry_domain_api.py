"""Unified industry-domain API integration tests."""

from __future__ import annotations

import asyncio
import json
import shutil
import threading
import time
from importlib import import_module

import httpx
import pytest
from fastapi.testclient import TestClient

from cascaqit_biomedicine_demo import fixtures
from cascaqit_biomedicine_demo.local_jobs import LocalJobManager
from cascaqit_finance_demo.api.app import app

app_module = import_module("cascaqit_finance_demo.api.app")
client = TestClient(app)


def test_default_data_dir_uses_platform_user_storage(tmp_path) -> None:
    resolver = app_module._default_user_data_dir
    suffix = ("CASColdAtom", "IndustryQuantumWorkbench")
    assert resolver(platform_name="darwin", environ={}, home=tmp_path) == (
        tmp_path / "Library" / "Application Support" / suffix[0] / suffix[1]
    )
    assert resolver(
        platform_name="win32",
        environ={"LOCALAPPDATA": str(tmp_path / "Local")},
        home=tmp_path,
    ) == (tmp_path / "Local" / suffix[0] / suffix[1])
    assert resolver(
        platform_name="linux",
        environ={"XDG_DATA_HOME": str(tmp_path / "xdg")},
        home=tmp_path,
    ) == (tmp_path / "xdg" / suffix[0] / suffix[1])
    assert resolver(
        platform_name="win32", environ={"LOCALAPPDATA": ""}, home=tmp_path
    ) == (tmp_path / "AppData" / "Local" / suffix[0] / suffix[1])
    assert resolver(
        platform_name="linux", environ={"XDG_DATA_HOME": ""}, home=tmp_path
    ) == (tmp_path / ".local" / "share" / suffix[0] / suffix[1])


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
    assert all(
        item["experimentLevels"] == ["standard", "advanced"]
        for item in biomedicine.json()["scenarios"]
    )
    statuses = {
        item["caseId"]: [
            profile["status"] for profile in item["complexityProfiles"]
        ]
        for item in biomedicine.json()["scenarios"]
    }
    assert statuses["electronic_structure"] == [
        "available",
        "available",
        "planned",
    ]
    assert statuses["docking_match"] == ["available", "available", "planned"]
    assert statuses["peptide_landscape"] == [
        "available",
        "available",
        "planned",
    ]


def test_biomedicine_capabilities_are_explicit_and_version_gated() -> None:
    response = client.get("/api/domains/biomedicine/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sdk"]["validatedRelease"] is True
    statuses = {item["id"]: item["status"] for item in payload["capabilities"]}
    assert statuses["pauli_vqe"] == "available"
    assert statuses["hybrid_dad"] == "available"
    assert statuses["experiment_planning"] == "available"
    assert statuses["batch_execution"] == "available"
    assert statuses["quantum_excited_states"] == "unavailable"


def test_electronic_structure_analysis_exposes_pauli_fixture_evidence() -> None:
    response = client.post(
        "/api/domains/biomedicine/scenarios/electronic_structure/analyze",
        json={"preset": "h2_bond_scan", "values": {}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"]["implementationStatus"] == "available"
    assert payload["analysis"]["problem"]["type"] == "pauli_hamiltonian"
    assert payload["analysis"]["domain"]["molecule"] == "H2"
    assert payload["dataset"] == payload["analysis"]["dataset"]
    assert payload["analysis"]["resource"]["measurementGroups"] == 2
    assert len(payload["scenario"]["presets"]) == 4
    assert len(payload["analysis"]["domain"]["bondScanReference"]) == 3
    assert payload["experimentPlan"]["executionPolicy"] == "sync"
    assert payload["experimentPlan"]["runCount"] == 1
    assert payload["experimentPlan"]["profile"]["profileId"] == "standard"


@pytest.mark.parametrize(
    ("case_id", "preset"),
    [
        ("electronic_structure", "h2_bond_scan"),
        ("docking_match", "reference_pose"),
        ("active_center", "antiferromagnetic"),
        ("peptide_landscape", "hydrophobic_core"),
    ],
)
def test_each_standard_scenario_has_one_executable_plan(
    case_id: str, preset: str
) -> None:
    response = client.post(
        f"/api/domains/biomedicine/scenarios/{case_id}/analyze",
        json={"preset": preset, "values": {}},
    )

    assert response.status_code == 200
    plan = response.json()["experimentPlan"]
    assert plan["caseId"] == case_id
    assert plan["runCount"] == 1
    assert plan["executionPolicy"] == "sync"
    assert plan["diagnostics"] == []
    assert plan["profile"]["status"] == "available"


def test_advanced_analysis_returns_truthful_rejected_plan_until_release() -> None:
    response = client.post(
        "/api/domains/biomedicine/scenarios/active_center/analyze",
        json={
            "preset": "trinuclear_frustrated",
            "values": {},
            "experimentLevel": "advanced",
            "complexityProfile": "advanced_live",
            "seeds": [7, 23, 41],
            "sweep": {
                "parameter": "exchange_coupling",
                "values": [0.8, 1.2, 1.6],
            },
        },
    )

    assert response.status_code == 200
    plan = response.json()["experimentPlan"]
    assert plan["runCount"] == 9
    assert plan["executionPolicy"] == "job"
    assert [point["values"]["exchange_coupling"] for point in plan["points"]] == [
        0.8,
        1.2,
        1.6,
    ]
    assert plan["diagnostics"] == []


def test_advanced_lih_scan_builds_five_point_audited_plan() -> None:
    datasets = [
        "lih_sto3g_1200",
        "lih_sto3g_1400",
        "lih_sto3g_1600",
        "lih_sto3g_1800",
        "lih_sto3g_2200",
    ]
    response = client.post(
        "/api/domains/biomedicine/scenarios/electronic_structure/analyze",
        json={
            "preset": "lih_potential_scan",
            "experimentLevel": "advanced",
            "complexityProfile": "advanced_live",
            "values": {},
            "sweep": {"parameter": "dataset", "values": datasets},
        },
    )

    assert response.status_code == 200
    plan = response.json()["experimentPlan"]
    assert plan["runCount"] == 5
    assert plan["profile"]["status"] == "available"
    assert [point["values"]["dataset"] for point in plan["points"]] == datasets
    assert {point["resource"]["logicalQubits"] for point in plan["points"]} == {4}
    assert plan["executionPolicy"] == "job"
    assert plan["diagnostics"] == []


@pytest.mark.parametrize(
    ("case_id", "preset", "configurations"),
    [
        (
            "docking_match",
            "multi_pose_balanced",
            [
                {"mode": "digital", "algorithm": "qaoa"},
                {"mode": "hybrid", "algorithm": "qaoa"},
            ],
        ),
        (
            "peptide_landscape",
            "octapeptide_hydrophobic",
            [
                {"mode": "digital", "algorithm": "qaoa", "layers": 1},
                {"mode": "digital", "algorithm": "qaoa", "layers": 1},
            ],
        ),
    ],
)
def test_advanced_optimization_plans_use_persistent_jobs(
    case_id: str,
    preset: str,
    configurations: list[dict[str, object]],
) -> None:
    response = client.post(
        f"/api/domains/biomedicine/scenarios/{case_id}/analyze",
        json={
            "preset": preset,
            "experimentLevel": "advanced",
            "complexityProfile": "advanced_live",
            "configurations": configurations,
            "seeds": [7, 23],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    plan = payload["experimentPlan"]
    problem = payload["analysis"]["problem"]
    assert plan["profile"]["status"] == "available"
    assert plan["runCount"] == 4
    assert plan["executionPolicy"] == "job"
    assert plan["diagnostics"] == []
    assert plan["completeDomainProblemHash"] != plan["quantumSubproblemHash"]
    assert problem["completeDomainProblemHash"] != problem["quantumSubproblemHash"]


def test_job_api_revalidates_plan_and_persists_progress(tmp_path, monkeypatch) -> None:
    manager = LocalJobManager(tmp_path / "jobs")
    monkeypatch.setattr(app_module, "JOB_MANAGER", manager)
    monkeypatch.setattr(
        app_module,
        "_execute_biomedicine_job_unit",
        lambda _case_id, _preset, unit: {
            "audit": {"reportHash": f"report-{unit.run_id}"}
        },
    )
    body = {
        "preset": "trinuclear_frustrated",
        "experimentLevel": "advanced",
        "complexityProfile": "advanced_live",
        "seeds": [7, 23],
    }
    analysis = client.post(
        "/api/domains/biomedicine/scenarios/active_center/analyze", json=body
    )
    plan_id = analysis.json()["experimentPlan"]["planId"]

    stale = client.post(
        "/api/domains/biomedicine/scenarios/active_center/jobs",
        json={**body, "planId": "0" * 64},
    )
    created = client.post(
        "/api/domains/biomedicine/scenarios/active_center/jobs",
        json={**body, "planId": plan_id},
    )

    assert stale.status_code == 422
    assert stale.json()["detail"]["code"] == "EXPERIMENT_PLAN_STALE"
    assert created.status_code == 202
    job_id = created.json()["job"]["jobId"]
    for _ in range(100):
        current = client.get(f"/api/jobs/{job_id}")
        if current.json()["job"]["status"] == "succeeded":
            break
        time.sleep(0.01)
    job = current.json()["job"]
    assert job["status"] == "succeeded"
    assert job["progress"]["completed"] == 2
    assert (tmp_path / "jobs" / job_id / "job.json").exists()
    manager.shutdown()


def test_planning_controls_require_advanced_level_and_declared_parameter() -> None:
    standard = client.post(
        "/api/domains/biomedicine/scenarios/active_center/analyze",
        json={"preset": "antiferromagnetic", "seeds": [7, 23]},
    )
    unknown_sweep = client.post(
        "/api/domains/biomedicine/scenarios/active_center/analyze",
        json={
            "preset": "antiferromagnetic",
            "experimentLevel": "advanced",
            "sweep": {"parameter": "unknown", "values": [1.0]},
        },
    )
    mismatched_profile = client.post(
        "/api/domains/biomedicine/scenarios/active_center/analyze",
        json={
            "preset": "antiferromagnetic",
            "experimentLevel": "advanced",
            "complexityProfile": "standard",
        },
    )

    assert standard.status_code == 422
    assert standard.json()["detail"]["code"] == "ADVANCED_EXPERIMENT_LEVEL_REQUIRED"
    assert unknown_sweep.status_code == 422
    assert unknown_sweep.json()["detail"]["code"] == "SWEEP_PARAMETER_UNSUPPORTED"
    assert mismatched_profile.status_code == 422
    assert mismatched_profile.json()["detail"] == {
        "code": "BIOMEDICINE_PLAN_INVALID",
        "message": "advanced experiment level requires an advanced profile",
        "stage": "planning",
    }


def test_h2o_api_returns_separate_evidence_and_persists_report(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(app_module, "REPORT_DIR", tmp_path / "reports")
    response = client.post(
        "/api/domains/biomedicine/scenarios/electronic_structure/run",
        json={
            "preset": "h2o_minimal",
            "values": {"noise_model": "readout_demo"},
            "mode": "digital",
            "algorithm": "vqe",
            "shots": 32,
            "seed": 7,
            "layers": 1,
            "parameter_budget": 40,
            "optimizer_starts": 2,
        },
    )
    assert response.status_code == 200
    run = response.json()["run"]
    payload = response.json()
    assert payload["dataset"] == run["analysis"]["dataset"]
    assert payload["analysis"] == run["analysis"]
    assert run["domain"]["molecule"] == "H2O"
    assert run["domain"]["withinChemicalAccuracy"] is None
    assert run["quantum"]["measurement"]["groups"]
    assert run["quantum"]["measurement"]["noisyGroups"]
    assert run["audit"]["noiseModelHash"]
    report_path = tmp_path / "reports" / (
        f"electronic_structure-{run['audit']['reportHash'][:16]}.json"
    )
    assert run["audit"]["reportPath"] == str(report_path.resolve())
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema"] == "biomedicine.execution-report.v1"
    assert report["reportHash"] == run["audit"]["reportHash"]
    assert report["run"]["audit"] == run["audit"]
    assert run["audit"]["timings"]["preflightSeconds"] >= 0.0
    assert run["audit"]["timings"]["reportSeconds"] >= 0.0
    assert (
        run["audit"]["timings"]["totalSeconds"]
        >= run["audit"]["timings"]["executionSeconds"]
    )


def test_electronic_structure_rejects_unsupported_mode_with_422() -> None:
    response = client.post(
        "/api/domains/biomedicine/scenarios/electronic_structure/run",
        json={"preset": "h2_bond_scan", "mode": "analog"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "PAULI_MODE_UNSUPPORTED"
    assert detail["stage"] == "preflight"
    assert "Digital VQE" in detail["message"]


def test_biomedicine_request_validation_uses_one_structured_422_contract() -> None:
    cases = (
        ({"preset": "unknown"}, "BIOMEDICINE_PRESET_UNKNOWN"),
        ({"preset": "h2_bond_scan", "shots": 0}, "BIOMEDICINE_REQUEST_INVALID"),
    )
    for payload, expected_code in cases:
        response = client.post(
            "/api/domains/biomedicine/scenarios/electronic_structure/run",
            json=payload,
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == expected_code
        assert detail["stage"] == "preflight"
        assert isinstance(detail["message"], str) and detail["message"]


def test_long_biomedicine_run_does_not_block_health_check(
    tmp_path, monkeypatch
) -> None:
    started = threading.Event()
    release = threading.Event()
    original_run = app_module.run_electronic_structure
    monkeypatch.setattr(app_module, "REPORT_DIR", tmp_path / "reports")

    def delayed_run(**kwargs):
        started.set()
        if not release.wait(timeout=5):
            raise TimeoutError("test did not release the delayed run")
        return original_run(**kwargs)

    monkeypatch.setattr(app_module, "run_electronic_structure", delayed_run)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as async_client:
            run_task = asyncio.create_task(
                async_client.post(
                    "/api/domains/biomedicine/scenarios/electronic_structure/run",
                    json={
                        "preset": "h2_bond_scan",
                        "mode": "digital",
                        "algorithm": "vqe",
                        "shots": 16,
                        "seed": 23,
                        "layers": 1,
                        "parameter_budget": 6,
                        "optimizer_starts": 1,
                    },
                )
            )
            try:
                assert await asyncio.wait_for(
                    asyncio.to_thread(started.wait), timeout=2
                )
                health = await asyncio.wait_for(
                    async_client.get("/api/health"), timeout=2
                )
                assert health.status_code == 200
                assert health.json()["status"] == "ok"
                frontend = await asyncio.wait_for(
                    async_client.get("/index.html"), timeout=2
                )
                assert frontend.status_code == 200
                assert "root" in frontend.text
            finally:
                release.set()
            response = await asyncio.wait_for(run_task, timeout=15)
            assert response.status_code == 200

    asyncio.run(exercise())


def test_corrupted_electronic_fixture_returns_422_without_local_path(
    tmp_path, monkeypatch
) -> None:
    copied_data = tmp_path / "data"
    shutil.copytree(fixtures.DATA_ROOT, copied_data)
    pauli = (
        copied_data
        / "electronic_structure"
        / "h2_sto3g"
        / "1"
        / "pauli.json"
    )
    pauli.write_text(pauli.read_text(encoding="utf-8") + " ", encoding="utf-8")
    monkeypatch.setattr(fixtures, "DATA_ROOT", copied_data)

    response = client.post(
        "/api/domains/biomedicine/scenarios/electronic_structure/analyze",
        json={"preset": "h2_bond_scan", "values": {}},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail == {
        "code": "BIOMEDICINE_ANALYSIS_INVALID",
        "message": "fixture checksum mismatch: pauli.json",
        "stage": "analysis",
    }
    assert str(tmp_path) not in detail["message"]


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


def test_unknown_biomedicine_failure_returns_opaque_error_id(monkeypatch) -> None:
    def fail_run(**_kwargs):
        raise RuntimeError("private path: /tmp/secret-fixture.json")

    monkeypatch.setattr(app_module, "run_electronic_structure", fail_run)
    safe_client = TestClient(app, raise_server_exceptions=False)
    response = safe_client.post(
        "/api/domains/biomedicine/scenarios/electronic_structure/run",
        json={"preset": "h2_bond_scan", "mode": "digital", "algorithm": "vqe"},
    )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["code"] == "INTERNAL_EXECUTION_ERROR"
    assert detail["stage"] == "internal"
    assert len(detail["error_id"]) == 32
    assert "/tmp/secret-fixture.json" not in detail["message"]
