"""Materials catalog and deterministic analysis contracts."""

from __future__ import annotations

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
    implementation_status: Literal["available", "preview"] = "preview"

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
                "searchStrategy": "preset",
                "parameterBudget": 2,
                "optimizerStarts": 1,
                "repeats": 1,
            },
            "executionFamily": self.execution_family,
            "resultKind": self.result_kind,
            "visualKind": self.visual_kind,
            "capabilities": list(self.capabilities),
            "implementationStatus": self.implementation_status,
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
            "joint_defect_adsorption_qubo",
            "coefficient_ledger",
            "material_qubo",
            "digital_qaoa",
            "hybrid_gate",
            "classic_enumeration",
            "offline_reference",
            "audit_hash_chain",
        ),
        "available",
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
        "available",
    ),
}


def preview_analysis(
    case_id: str,
    preset: str,
    values: dict[str, str | int | float | bool],
) -> dict[str, Any]:
    """Compatibility entry that delegates to the authoritative analyzers."""

    if case_id == "defect_adsorption":
        from cascaqit_materials_demo.defect_adsorption import (
            analyze_defect_adsorption,
        )

        return analyze_defect_adsorption(preset, values)
    if case_id == "rydberg_dynamics":
        from cascaqit_materials_demo.rydberg_dynamics import (
            analyze_rydberg_dynamics,
        )

        return analyze_rydberg_dynamics(preset, values)
    raise ValueError(f"unknown materials scenario: {case_id}")
