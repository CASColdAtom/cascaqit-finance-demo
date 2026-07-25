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
    assert sum(len(item["presets"]) for item in scenarios) == 21
    preset_values = {
        option["value"] for item in scenarios for option in item["presets"]
    }
    assert "eod" not in preset_values
    assert "concentration" not in preset_values
    assert {item["recommendedMode"] for item in scenarios} == {
        "digital",
        "hybrid",
        "analog",
    }
    profiles = {item["caseId"]: item["recommendedExecution"] for item in scenarios}
    assert profiles["liquidity"] == {
        "shots": 128,
        "seed": 23,
        "layers": 1,
        "searchStrategy": "preset",
        "parameterBudget": 2,
    }
    assert profiles["credit_limits"] == {
        "shots": 128,
        "seed": 23,
        "layers": 2,
        "searchStrategy": "preset",
        "parameterBudget": 2,
    }


@pytest.mark.parametrize(
    ("case_id", "expected_layers"),
    [("liquidity", 1), ("credit_limits", 2)],
)
def test_run_uses_scenario_execution_profile_when_fields_are_omitted(
    case_id: str,
    expected_layers: int,
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
    assert captured["shots"] == 128
    assert captured["seed"] == 23
    assert captured["layers"] == expected_layers
    assert captured["search_strategy"] == "preset"
    assert captured["parameter_budget"] == 2


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


@pytest.mark.parametrize(
    "payload",
    [
        {
            "mode": "hybrid",
            "layers": 2,
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
