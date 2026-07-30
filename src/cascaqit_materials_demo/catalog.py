"""Materials catalog and analysis-only preview contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ControlSpec:
    key: str
    label: str
    kind: Literal["range", "select"]
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    options: tuple[tuple[str, str], ...] = ()
    unit: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
            "options": [
                {"value": value, "label": label} for value, label in self.options
            ],
            "unit": self.unit,
        }


@dataclass(frozen=True)
class MaterialsScenarioSpec:
    case_id: str
    short_title: str
    title: str
    eyebrow: str
    description: str
    icon: str
    accent: Literal["cyan", "emerald", "amber"]
    presets: tuple[tuple[str, str], ...]
    controls: tuple[ControlSpec, ...]
    values: dict[str, str | int | float | bool]
    recommended_mode: Literal["digital", "hybrid", "analog"]
    execution_family: Literal["problem", "analog_ahs"]
    result_kind: str
    visual_kind: str
    capabilities: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "domainId": "materials",
            "caseId": self.case_id,
            "shortTitle": self.short_title,
            "title": self.title,
            "eyebrow": self.eyebrow,
            "description": self.description,
            "icon": self.icon,
            "accent": self.accent,
            "presets": [
                {"value": value, "label": label} for value, label in self.presets
            ],
            "controls": [control.to_dict() for control in self.controls],
            "values": dict(self.values),
            "recommendedMode": self.recommended_mode,
            "recommendedExecution": {
                "shots": 128,
                "seed": 23,
                "algorithm": "qaa" if self.execution_family == "analog_ahs" else "qaoa",
                "layerPolicy": "fixed",
                "layers": 1,
                "maxLayers": 1 if self.execution_family == "analog_ahs" else 2,
                "minImprovement": 0,
                "searchStrategy": "preset"
                if self.execution_family == "analog_ahs"
                else "continuous",
                "parameterBudget": 2 if self.execution_family == "analog_ahs" else 12,
                "optimizerStarts": 1,
                "repeats": 1,
            },
            "executionFamily": self.execution_family,
            "resultKind": self.result_kind,
            "visualKind": self.visual_kind,
            "capabilities": list(self.capabilities),
            "implementationStatus": "preview",
            "experimentLevels": ["standard"],
        }


def _range(
    key: str,
    label: str,
    minimum: float,
    maximum: float,
    step: float,
    unit: str = "",
) -> ControlSpec:
    return ControlSpec(key, label, "range", minimum, maximum, step, unit=unit)


MATERIALS_SCENARIO_SPECS: dict[str, MaterialsScenarioSpec] = {
    "defect_adsorption": MaterialsScenarioSpec(
        "defect_adsorption",
        "缺陷与吸附",
        "催化表面缺陷与吸附协同构型优化",
        "PERIODIC LATTICE / DIGITAL + HYBRID",
        "在版本化周期表面和离线能量模型中联合选择缺陷、吸附位点与覆盖度。",
        "grid-3x3",
        "amber",
        (
            ("ceria_vacancy_co", "CeO2(111) 氧空位 / CO"),
            ("tio2_vacancy_water", "TiO2(110) 氧空位 / H2O"),
            ("mos2_vacancy_hydrogen", "MoS2 硫空位 / H"),
        ),
        (
            _range("defect_count", "缺陷数量", 1, 3, 1),
            _range("coverage", "吸附覆盖度", 0.25, 1.0, 0.25, " ML"),
            _range("interaction_weight", "近邻相互作用权重", 0.2, 2.0, 0.1),
        ),
        {"defect_count": 1, "coverage": 0.5, "interaction_weight": 1.0},
        "hybrid",
        "problem",
        "material_configuration",
        "material-defect-adsorption",
        (
            "periodic_lattice",
            "symmetry_canonicalization",
            "material_qubo",
            "digital_qaoa",
            "hybrid_gate",
            "classic_enumeration",
        ),
    ),
    "rydberg_dynamics": MaterialsScenarioSpec(
        "rydberg_dynamics",
        "Rydberg 动力学",
        "材料缺陷晶格中的 Rydberg 动力学与量子淬火",
        "NATIVE AHS / PURE ANALOG",
        "演化材料有效晶格对应的原生 Rydberg Hamiltonian，观察缺陷诱导传播与局域化。",
        "activity",
        "emerald",
        (
            ("perfect_lattice", "理想晶格基准"),
            ("single_vacancy", "单空位传播"),
            ("multi_defect_impurity", "多缺陷 / 局域杂质"),
        ),
        (
            _range("duration_us", "演化时长", 0.2, 2.0, 0.1, " μs"),
            _range("rabi_amplitude", "Rabi 峰值", 0.5, 4.0, 0.1, " rad/μs"),
            _range("detuning_end", "终态失谐", -4.0, 4.0, 0.25, " rad/μs"),
            _range("sample_count", "采样时刻", 5, 21, 2),
        ),
        {
            "duration_us": 1.2,
            "rabi_amplitude": 2.4,
            "detuning_end": 2.0,
            "sample_count": 9,
        },
        "analog",
        "analog_ahs",
        "rydberg_time_series",
        "material-rydberg-dynamics",
        (
            "ahs_program",
            "rydberg_layout",
            "pulse_schedule",
            "time_resolved_observables",
            "pure_analog_evidence",
            "exact_evolution_reference",
        ),
    ),
}


def _lattice_nodes(vacancies: set[int]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for row in range(3):
        for column in range(4):
            index = row * 4 + column
            nodes.append(
                {
                    "id": f"site.{index}",
                    "label": f"S{index + 1}",
                    "x": 14 + column * 24,
                    "y": 22 + row * 28,
                    "role": "vacancy" if index in vacancies else "lattice_site",
                }
            )
    return nodes


def preview_analysis(
    case_id: str,
    preset: str,
    values: dict[str, str | int | float | bool],
) -> dict[str, Any]:
    """Build a deterministic, non-executable materials preview."""

    spec = MATERIALS_SCENARIO_SPECS[case_id]
    if case_id == "rydberg_dynamics":
        vacancies = {
            "perfect_lattice": set(),
            "single_vacancy": {5},
            "multi_defect_impurity": {2, 9},
        }[preset]
        nodes = _lattice_nodes(vacancies)
        rydberg_layout = [
            {
                "id": node["id"].replace("site", "atom"),
                "sourceSite": node["id"],
                "x": 10.0 + (index % 4) * 5.6,
                "y": 10.0 + (index // 4) * 5.6,
                "active": node["role"] != "vacancy",
            }
            for index, node in enumerate(nodes)
        ]
        duration = float(values["duration_us"])
        sample_count = int(values["sample_count"])
        sample_times = [
            round(duration * index / (sample_count - 1), 6)
            for index in range(sample_count)
        ]
        domain = {
            "kind": "rydberg_dynamics",
            "modelLevel": "材料有效多体晶格 / 原生 AHS",
            "nodes": nodes,
            "rydbergLayout": rydberg_layout,
            "sampleTimes": sample_times,
            "pulse": {
                "duration": duration,
                "rabiPeak": float(values["rabi_amplitude"]),
                "detuningStart": -2.0,
                "detuningEnd": float(values["detuning_end"]),
            },
            "pureAnalogEvidence": {
                "digitalGateCount": 0,
                "digitalResidualCount": 0,
                "hybridBlockCount": 0,
                "status": "planned",
            },
            "limitations": [
                "当前页面是确定性分析预览，不执行 AHS 时间演化",
                "材料晶格坐标与 Rydberg 编译坐标分别展示",
                "时分辨 SDK 契约通过前不生成动力学曲线",
            ],
        }
        problem_type = "analog_experiment_definition"
        mode_reason = "完整模型目标为纯 Analog；时分辨 SDK 契约尚未通过。"
    else:
        nodes = _lattice_nodes({5})
        domain = {
            "kind": "defect_adsorption",
            "modelLevel": "周期表面缺陷-吸附离散模型",
            "nodes": nodes,
            "adsorbates": [
                {"id": "ads.1", "site": "site.1", "label": "CO", "orientation": "top"},
                {
                    "id": "ads.2",
                    "site": "site.6",
                    "label": "CO",
                    "orientation": "bridge",
                },
                {"id": "ads.3", "site": "site.10", "label": "CO", "orientation": "top"},
            ],
            "constraints": ["周期边界", "占位互斥", "化学计量", "覆盖度", "近邻排斥"],
            "limitations": [
                "离线能量模型尚未固化为发布 fixture",
                "不在运行时执行 DFT",
                "不从构型目标值推导催化活性",
            ],
        }
        problem_type = "material_qubo_preview"
        mode_reason = "Digital/Hybrid 共用逻辑 QUBO；材料与 Rydberg 坐标门禁待实现。"
    identity_payload = {
        "caseId": case_id,
        "preset": preset,
        "values": values,
        "domain": domain,
    }
    identity = hashlib.sha256(
        json.dumps(identity_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if case_id == "rydberg_dynamics":
        mode_statuses = {
            "digital": ("unsuitable", "原生 AHS 时间演化不转换为数字线路。"),
            "hybrid": ("unsuitable", "纯 Analog 实验不包含 Hybrid block。"),
            "analog": ("recommended", mode_reason),
        }
    else:
        mode_statuses = {
            "digital": ("comparable", "逻辑 QUBO 可作为 Digital 对照执行。"),
            "hybrid": ("recommended", mode_reason),
            "analog": (
                "unsuitable",
                "构型目标尚无可验证的原生 AHS 映射，不能作为纯 Analog 执行。",
            ),
        }
    modes = [
        {
            "mode": mode,
            "algorithm": "qaa" if mode == "analog" else "qaoa",
            "availableAlgorithms": ["qaa" if mode == "analog" else "qaoa"],
            "status": status,
            "reason": reason,
        }
        for mode, (status, reason) in mode_statuses.items()
    ]
    resource_size_key = (
        "analogSites" if spec.execution_family == "analog_ahs" else "logicalQubits"
    )
    return {
        "kind": "materials",
        "caseId": case_id,
        "executionFamily": spec.execution_family,
        "implementationStatus": "preview",
        "analysisHash": identity,
        "dataset": {
            "id": f"materials.preview.{case_id}.{preset}",
            "version": "design-1",
            "manifestHash": identity,
            "sourceKind": "project_generated_design_preview",
            "license": "project_generated",
            "limitations": domain["limitations"],
        },
        "problem": {
            "id": f"materials.preview.{case_id}",
            "type": problem_type,
            "hash": identity,
            "variables": [node["id"] for node in nodes],
            "terms": [],
        },
        "resource": {
            resource_size_key: len(
                [node for node in nodes if node["role"] != "vacancy"]
            ),
            "termCount": 0,
            "measurementGroups": 0,
            "parameterCount": 0,
        },
        "decision": {
            "recommendedMode": spec.recommended_mode,
            "reason": mode_reason,
            "modes": modes,
        },
        "domain": domain,
    }
