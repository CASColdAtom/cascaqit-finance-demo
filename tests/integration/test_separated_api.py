"""独立金融 Demo 前端依赖的 FastAPI 契约测试。"""

from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

import pytest
from cascaqit.exceptions import CapabilityError
from fastapi.testclient import TestClient

from cascaqit_finance_demo.api.app import app
from cascaqit_finance_demo.quantum.problem_executor import ScenarioExecutor

app_module = import_module("cascaqit_finance_demo.api.app")
client = TestClient(app)


@pytest.mark.parametrize("path", ["/", "/index.html"])
def test_frontend_entry_is_not_cached_across_demo_upgrades(path: str) -> None:
    """验证入口页面不会让浏览器长期持有上一版前端 chunk。"""

    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"


def test_health_and_scenario_catalog_expose_offline_boundaries() -> None:
    """验证健康接口明确披露离线模拟边界，目录完整返回七个场景。"""
    health = client.get("/api/health")
    catalog = client.get("/api/scenarios")

    assert health.status_code == 200
    assert health.json()["execution"] == "local_simulation"
    assert health.json()["hardware"] is False
    assert catalog.status_code == 200
    scenarios = catalog.json()["scenarios"]
    assert len(scenarios) == 7
    assert sum(len(item["presets"]) for item in scenarios) == 19
    preset_values = {
        option["value"] for item in scenarios for option in item["presets"]
    }
    assert "eod" not in preset_values
    assert "concentration" not in preset_values
    assert "tight" not in preset_values
    assert "fx" not in preset_values
    assert {item["recommendedMode"] for item in scenarios} == {
        "digital",
        "hybrid",
        "analog",
    }
    profiles = {item["caseId"]: item["recommendedExecution"] for item in scenarios}
    assert profiles["portfolio"] == {
        "shots": 32,
        "seed": 23,
        "algorithm": "recommended",
        "layerPolicy": "fixed",
        "layers": 1,
        "maxLayers": 3,
        "minImprovement": 0.0,
        "searchStrategy": "continuous",
        "parameterBudget": 12,
        "optimizerStarts": 2,
        "repeats": 1,
    }
    assert profiles["liquidity"] == {
        "shots": 128,
        "seed": 23,
        "algorithm": "recommended",
        "layerPolicy": "fixed",
        "layers": 1,
        "maxLayers": 3,
        "minImprovement": 0.0,
        "searchStrategy": "preset",
        "parameterBudget": 2,
        "optimizerStarts": 1,
        "repeats": 1,
    }
    assert profiles["collateral"] == {
        "shots": 64,
        "seed": 23,
        "algorithm": "recommended",
        "layerPolicy": "fixed",
        "layers": 1,
        "maxLayers": 3,
        "minImprovement": 0.0,
        "searchStrategy": "continuous",
        "parameterBudget": 12,
        "optimizerStarts": 1,
        "repeats": 1,
    }
    assert profiles["credit_limits"] == {
        "shots": 128,
        "seed": 23,
        "algorithm": "recommended",
        "layerPolicy": "fixed",
        "layers": 2,
        "maxLayers": 3,
        "minImprovement": 0.0,
        "searchStrategy": "preset",
        "parameterBudget": 2,
        "optimizerStarts": 1,
        "repeats": 1,
    }


@pytest.mark.parametrize(
    (
        "case_id",
        "expected_shots",
        "expected_layers",
        "expected_search",
        "expected_budget",
    ),
    [
        ("collateral", 64, 1, "continuous", 12),
        ("liquidity", 128, 1, "preset", 2),
        ("credit_limits", 128, 2, "preset", 2),
    ],
)
def test_run_uses_scenario_execution_profile_when_fields_are_omitted(
    case_id: str,
    expected_shots: int,
    expected_layers: int,
    expected_search: str,
    expected_budget: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证脚本调用省略执行字段时与 Web UI 使用同一套推荐值。"""
    captured: dict[str, object] = {}

    def record_run(
        self: ScenarioExecutor,
        scenario: object,
        case_input: object,
        **kwargs: object,
    ) -> object:
        captured.update(kwargs)
        return SimpleNamespace(analysis=self.analyze(scenario, case_input))

    monkeypatch.setattr(app_module.ScenarioExecutor, "run", record_run)
    monkeypatch.setattr(
        app_module,
        "execution_payload",
        lambda case_id, case_input, result: {"recorded": True},
    )

    response = client.post(f"/api/scenarios/{case_id}/run", json={})

    assert response.status_code == 200
    assert response.json()["run"] == {"recorded": True}
    assert captured["shots"] == expected_shots
    assert captured["seed"] == 23
    assert captured["layers"] == expected_layers
    assert captured["search_strategy"] == expected_search
    assert captured["parameter_budget"] == expected_budget


@pytest.mark.parametrize(
    ("case_id", "expected_budget", "expected_max_layers"),
    [
        ("portfolio", 14, 1),
        ("collateral", 12, 1),
        ("liquidity", 18, 1),
        ("credit_limits", 16, 1),
    ],
)
def test_explicit_vqe_uses_an_algorithm_specific_execution_profile(
    case_id: str,
    expected_budget: int,
    expected_max_layers: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """只指定 VQE 时必须派生可执行的连续优化配置，不能继承 QAOA 默认值。"""
    captured: dict[str, object] = {}

    def record_run(
        self: ScenarioExecutor,
        scenario: object,
        case_input: object,
        **kwargs: object,
    ) -> object:
        captured.update(kwargs)
        return SimpleNamespace(analysis=self.analyze(scenario, case_input))

    monkeypatch.setattr(app_module.ScenarioExecutor, "run", record_run)
    monkeypatch.setattr(
        app_module,
        "execution_payload",
        lambda case_id, case_input, result: {"recorded": True},
    )

    response = client.post(
        f"/api/scenarios/{case_id}/run",
        json={"algorithm": "vqe"},
    )

    assert response.status_code == 200
    assert captured["algorithm"] == "vqe"
    assert captured["layers"] == 1
    assert captured["max_layers"] == expected_max_layers
    assert captured["search_strategy"] == "continuous"
    assert captured["parameter_budget"] == expected_budget
    assert captured["optimizer_starts"] == 1
    assert captured["shots"] == 64


def test_analysis_recommends_digital_after_fraud_conflicts_disappear() -> None:
    """验证共享实体冲突消失后不再为了展示效果强行推荐 Hybrid。"""
    response = client.post(
        "/api/scenarios/fraud_routing/analyze",
        json={"preset": "base", "values": {"entity_cap": 2}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis"]["decision"]["recommendedMode"] == "digital"
    assert payload["scenario"]["values"]["entity_cap"] == 2


def test_analysis_exposes_balanced_business_to_canonical_coefficient_ledger() -> None:
    """验证分析接口公开业务规则到 Canonical 项的逐系数账本。"""
    response = client.post(
        "/api/scenarios/settlement/analyze",
        json={"preset": "base", "values": {}},
    )

    assert response.status_code == 200
    ledger = response.json()["analysis"]["problem"]["coefficientLedger"]
    assert ledger["applicability"] == "qubo"
    assert ledger["balanced"] is True
    assert ledger["hamiltonianBalanced"] is True
    assert ledger["contributionCount"] == len(ledger["rows"])
    conflict = next(
        row
        for row in ledger["rows"]
        if row["sourceRule"] == "settlement_pairwise_conflict"
    )
    assert conflict["canonicalTermId"].startswith("quadratic.")
    assert {item["operator"] for item in conflict["hamiltonianTerms"]} == {"z", "zz"}
    for item in conflict["hamiltonianTerms"]:
        expected_effect = (
            conflict["contributionCoefficient"] / 4.0
            if item["operator"] == "zz"
            else -conflict["contributionCoefficient"] / 4.0
        )
        assert item["contributionEffect"] == pytest.approx(expected_effect)
    assert all(
        item["implementation"] == "pending_mode_allocation"
        for item in conflict["hamiltonianTerms"]
    )

    graph_ledger = client.post(
        "/api/scenarios/derivatives/analyze",
        json={"preset": "european_call", "values": {}},
    ).json()["analysis"]["problem"]["coefficientLedger"]
    assert graph_ledger == {
        "applicability": "not_applicable_graph",
        "balanced": True,
        "hamiltonianBalanced": True,
        "contributionCount": 0,
        "canonicalTermCount": 0,
        "rows": [],
    }


def test_analysis_exposes_business_native_visual_contract_for_every_scenario() -> None:
    """验证七个场景在执行前都提供符合各自业务语义的可视化模型。"""
    expected = {
        "portfolio": "portfolio-correlation",
        "settlement": "settlement-network",
        "fraud_routing": "fraud-entity-network",
        "collateral": "collateral-flow",
        "liquidity": "liquidity-timeline",
        "credit_limits": "credit-capital-map",
        "derivatives": "derivatives-pnl-surface",
    }
    for case_id, kind in expected.items():
        response = client.post(
            f"/api/scenarios/{case_id}/analyze",
            json={"values": {}},
        )

        assert response.status_code == 200
        visual = response.json()["analysis"]["scenarioVisual"]
        assert visual["kind"] == kind
        assert visual["title"]
        assert visual["subtitle"]
        assert any(
            (
                visual["nodes"],
                visual["points"],
                visual["matrix"]["cells"],
            )
        )

    derivative_visual = client.post(
        "/api/scenarios/derivatives/analyze",
        json={"preset": "european_call", "values": {}},
    ).json()["analysis"]["scenarioVisual"]
    assert len(derivative_visual["matrix"]["cells"]) == 9
    assert any(cell["value"] != 0.0 for cell in derivative_visual["matrix"]["cells"])


def test_digital_execution_returns_business_circuit_counts_and_audit() -> None:
    """验证 Digital 执行返回业务解、真实线路、采样计数和审计链。"""
    response = client.post(
        "/api/scenarios/portfolio/run",
        json={
            "preset": "base",
            "mode": "recommended",
            "shots": 16,
            "seed": 17,
            "search_strategy": "preset",
            "parameter_budget": 1,
        },
    )

    assert response.status_code == 200
    run = response.json()["run"]
    assert run["quantum"]["mode"] == "digital"
    assert run["quantum"]["circuit"]["gates"]
    assert sum(item["count"] for item in run["quantum"]["counts"]) == 16
    assert run["business"]["metrics"]
    assert run["business"]["chart"]["title"] == "可行组合与当前候选"
    assert run["business"]["chart"]["xLabel"] == "波动率"
    assert run["audit"]["hardwareExecution"] is False


def test_hybrid_and_analog_expose_atoms_waveforms_and_real_term_mapping() -> None:
    """验证 Hybrid/Analog 返回原子、真实控制波形及可追溯项映射。"""
    cases = (("settlement", "hybrid"), ("derivatives", "analog"))
    for case_id, mode in cases:
        response = client.post(
            f"/api/scenarios/{case_id}/run",
            json={
                "preset": "base" if case_id == "settlement" else "european_call",
                "mode": "recommended",
                "shots": 8,
                "seed": 19,
                "parameter_budget": 1,
            },
        )

        assert response.status_code == 200
        quantum = response.json()["run"]["quantum"]
        assert quantum["mode"] == mode
        assert quantum["atoms"]
        assert quantum["waveforms"]["rabi"]
        assert quantum["waveforms"]["detuning"]
        assert quantum["waveforms"]["phase"]
        assert all(
            len(quantum["waveforms"][name]) >= 2
            for name in ("rabi", "detuning", "phase")
        )
        assert quantum["termMapping"]
        assert sum(item["count"] for item in quantum["counts"]) == 8
        if case_id == "settlement":
            ledger = response.json()["run"]["analysis"]["problem"][
                "coefficientLedger"
            ]
            conflict = next(
                row
                for row in ledger["rows"]
                if row["sourceRule"] == "settlement_pairwise_conflict"
            )
            assert conflict["conserved"] is True
            assert all(
                item["implementation"] != "pending_mode_allocation"
                for item in conflict["hamiltonianTerms"]
            )
            assert any(
                abs(item["analog"] or 0.0) > 0.0
                for item in conflict["hamiltonianTerms"]
            )


def test_run_maps_capability_error_to_stable_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证规划器的已知能力错误不会退化为缺少上下文的裸 500。"""

    def reject_run(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise CapabilityError(
            "资源预算不足。",
            code="SIMULATION_RESOURCE_BUDGET_EXCEEDED",
            stage="simulation",
        )

    monkeypatch.setattr(app_module.ScenarioExecutor, "run", reject_run)
    response = client.post(
        "/api/scenarios/settlement/run",
        json={"shots": 1, "parameter_budget": 1},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "SIMULATION_RESOURCE_BUDGET_EXCEEDED"
    assert detail["stage"] == "simulation"
    assert detail["error_id"]


def test_run_maps_unknown_error_to_traceable_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证未知执行错误隐藏内部堆栈，同时向现场提供可检索错误编号。"""

    def fail_run(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("sensitive implementation detail")

    monkeypatch.setattr(app_module.ScenarioExecutor, "run", fail_run)
    response = client.post(
        "/api/scenarios/settlement/run",
        json={"shots": 1, "parameter_budget": 1},
    )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["code"] == "internal_execution_error"
    assert len(detail["error_id"]) == 32
    assert "sensitive" not in detail["message"]


def test_digital_multilayer_search_returns_real_parameters() -> None:
    """验证 API 把多层参数搜索真实传入编译器并返回完整参数历史。"""
    response = client.post(
        "/api/scenarios/portfolio/run",
        json={
            "preset": "base",
            "mode": "digital",
            "shots": 8,
            "seed": 17,
            "layers": 3,
            "search_strategy": "seeded_sample",
            "parameter_budget": 2,
        },
    )

    assert response.status_code == 200
    quantum = response.json()["run"]["quantum"]
    assert quantum["layerCount"] == 3
    assert quantum["searchStrategy"] == "seeded_sample"
    assert quantum["evaluationCount"] == 2
    assert quantum["selectedEvaluationIndex"] in {0, 1}
    assert len(quantum["layers"]) == 11
    assert all(
        set(item["parameters"])
        == {
            "gamma_0",
            "gamma_1",
            "gamma_2",
            "beta_0",
            "beta_1",
            "beta_2",
        }
        for item in quantum["parameterHistory"]
    )
    assert sum(item["count"] for item in quantum["counts"]) == 8


def test_continuous_multistart_run_exposes_optimizer_evidence() -> None:
    """验证连续多起点优化进入真实执行，并返回预算和终止证据。"""
    response = client.post(
        "/api/scenarios/portfolio/run",
        json={
            "preset": "base",
            "mode": "digital",
            "shots": 4,
            "seed": 17,
            "layers": 1,
            "search_strategy": "continuous",
            "parameter_budget": 4,
            "optimizer_starts": 2,
        },
    )

    assert response.status_code == 200
    quantum = response.json()["run"]["quantum"]
    assert quantum["searchStrategy"] == "continuous"
    assert 2 <= quantum["evaluationCount"] <= 8
    assert quantum["optimizer"]["method"] == "COBYLA"
    assert quantum["optimizer"]["starts"] == 2
    assert quantum["optimizer"]["perStartEvaluationBudget"] == 4
    assert quantum["optimizer"]["selectedStartIndex"] in {0, 1}
    assert quantum["optimizer"]["startInitializations"] == ["explicit", "random"]


@pytest.mark.parametrize(
    ("case_id", "budget", "parameter_count", "entanglement"),
    [
        ("collateral", 12, 8, "linear"),
        ("portfolio", 14, 12, "circular"),
    ],
)
def test_vqe_api_stays_internal_until_each_scenario_calibration_passes(
    case_id: str,
    budget: int,
    parameter_count: int,
    entanglement: str,
) -> None:
    """页面只发布已校准算法，但显式 VQE 请求仍进入真实执行链路。"""
    analysis = client.post(
        f"/api/scenarios/{case_id}/analyze",
        json={"preset": "base", "values": {}},
    ).json()["analysis"]
    digital = next(
        row for row in analysis["decision"]["modes"] if row["mode"] == "digital"
    )
    assert digital["algorithm"] == "qaoa"
    assert digital["availableAlgorithms"] == ["qaoa"]

    response = client.post(
        f"/api/scenarios/{case_id}/run",
        json={
            "preset": "base",
            "mode": "digital",
            "algorithm": "vqe",
            "shots": 2,
            "seed": 7,
        },
    )

    assert response.status_code == 200
    quantum = response.json()["run"]["quantum"]
    assert quantum["algorithm"] == "vqe"
    assert quantum["ansatz"]["kind"] == "hardware_efficient"
    assert quantum["ansatz"]["definition"] == {
        "definition_kind": "hardware_efficient",
        "entanglement": entanglement,
        "rotation_axes": ["ry"],
        "schema_version": "cascaqit.algorithms.vqe_ansatz.v1",
    }
    assert quantum["ansatz"]["parameterCount"] == parameter_count
    assert quantum["optimizer"]["perStartEvaluationBudget"] == budget
    assert quantum["layers"] == ["|0>", "RY", "CX", "M"]


def test_adaptive_qaoa_api_exposes_layer_selection_evidence() -> None:
    """自动选层响应必须保留逐层目标值、改善、早停和总评估成本。"""
    response = client.post(
        "/api/scenarios/collateral/run",
        json={
            "preset": "base",
            "mode": "digital",
            "algorithm": "qaoa",
            "layer_policy": "adaptive",
            "max_layers": 2,
            "shots": 2,
            "seed": 11,
            "search_strategy": "continuous",
            "parameter_budget": 6,
            "optimizer_starts": 1,
        },
    )

    assert response.status_code == 200
    quantum = response.json()["run"]["quantum"]
    evidence = quantum["layerEvidence"]
    assert evidence["policy"] == "adaptive"
    assert evidence["executedLayers"] in ([1], [1, 2])
    assert evidence["selectedLayers"] == quantum["layerCount"]
    assert evidence["totalEvaluationCount"] == sum(
        step["evaluationCount"] for step in evidence["steps"]
    )
    assert sum(step["selected"] for step in evidence["steps"]) == 1


@pytest.mark.parametrize(
    ("case_id", "preset", "mode", "search_strategy", "expected_budget"),
    [
        ("settlement", "base", "hybrid", "continuous", 4),
        ("portfolio", "base", "digital", "preset", 2),
    ],
)
def test_search_strategy_override_derives_a_valid_default_budget(
    case_id: str,
    preset: str,
    mode: str,
    search_strategy: str,
    expected_budget: int,
) -> None:
    """只覆盖搜索方式时，应派生合法预算而不是继承不兼容的推荐值。"""
    response = client.post(
        f"/api/scenarios/{case_id}/run",
        json={
            "preset": preset,
            "mode": mode,
            "shots": 1,
            "seed": 17,
            "search_strategy": search_strategy,
        },
    )

    assert response.status_code == 200
    quantum = response.json()["run"]["quantum"]
    assert quantum["searchStrategy"] == search_strategy
    if search_strategy == "continuous":
        assert quantum["optimizer"]["perStartEvaluationBudget"] == expected_budget
    else:
        assert quantum["evaluationCount"] == expected_budget


def test_repeated_run_statistics_use_quantum_candidates_only() -> None:
    """重复验收统计量子候选可行率，不用经典基线填充失败运行。"""
    response = client.post(
        "/api/scenarios/portfolio/run",
        json={
            "preset": "base",
            "mode": "digital",
            "shots": 4,
            "seed": 17,
            "layers": 1,
            "search_strategy": "preset",
            "parameter_budget": 1,
            "repeats": 3,
        },
    )

    assert response.status_code == 200
    statistics = response.json()["run"]["statistics"]
    assert statistics["repeatCount"] == 3
    assert len(statistics["runs"]) == 3
    assert [item["seed"] for item in statistics["runs"]] == [17, 18, 19]
    assert statistics["feasibleCount"] == sum(
        item["quantumCandidateFeasible"] for item in statistics["runs"]
    )
    assert statistics["feasibleRate"] == pytest.approx(
        statistics["feasibleCount"] / 3
    )
    assert statistics["successSource"] == "quantum_business_candidate"
    assert statistics["objective"]["confidenceLevel"] == 0.95
    assert statistics["totalEvaluationCount"] == sum(
        item["evaluationCount"] for item in statistics["runs"]
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "mode": "hybrid",
            "layers": 3,
            "search_strategy": "preset",
            "parameter_budget": 2,
        },
        {
            "mode": "digital",
            "layers": 2,
            "search_strategy": "grid",
            "parameter_budget": 4,
        },
        {
            "mode": "digital",
            "layers": 1,
            "search_strategy": "preset",
            "parameter_budget": 3,
        },
    ],
)
def test_run_rejects_unsupported_search_combinations(
    payload: dict[str, object],
) -> None:
    """验证不支持的层数和搜索策略组合不会被静默降级。"""
    response = client.post(
        "/api/scenarios/settlement/run",
        json={"preset": "base", "shots": 1, "seed": 17, **payload},
    )

    assert response.status_code == 422
