"""Biomedicine scenario catalog and analysis-only preview contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from cascaqit_biomedicine_demo.advanced_experiments import (
    catalog_experiment_metadata,
)

DomainStatus = Literal["available", "preview"]


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
class BiomedicineScenarioSpec:
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
    execution_family: Literal["pauli_vqe", "problem"]
    result_kind: str
    visual_kind: str
    capabilities: tuple[str, ...]
    implementation_status: DomainStatus
    recommended_execution: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "domainId": "biomedicine",
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
            "recommendedExecution": dict(self.recommended_execution),
            "executionFamily": self.execution_family,
            "resultKind": self.result_kind,
            "visualKind": self.visual_kind,
            "capabilities": list(self.capabilities),
            "implementationStatus": self.implementation_status,
            **catalog_experiment_metadata(self.case_id),
        }


def _select(key: str, label: str, options: tuple[tuple[str, str], ...]) -> ControlSpec:
    return ControlSpec(key=key, label=label, kind="select", options=options)


def _range(
    key: str,
    label: str,
    minimum: float,
    maximum: float,
    step: float,
    unit: str = "",
) -> ControlSpec:
    return ControlSpec(key, label, "range", minimum, maximum, step, unit=unit)


_VQE_PROFILE = {
    "shots": 64,
    "seed": 23,
    "algorithm": "vqe",
    "layerPolicy": "fixed",
    "layers": 1,
    "maxLayers": 1,
    "minImprovement": 0,
    "searchStrategy": "continuous",
    "parameterBudget": 40,
    "optimizerStarts": 2,
    "repeats": 1,
}

_QAOA_PROFILE = {
    "shots": 64,
    "seed": 23,
    "algorithm": "qaoa",
    "layerPolicy": "fixed",
    "layers": 1,
    "maxLayers": 2,
    "minImprovement": 0,
    "searchStrategy": "continuous",
    "parameterBudget": 12,
    "optimizerStarts": 1,
    "repeats": 1,
}


BIOMEDICINE_SCENARIO_SPECS: dict[str, BiomedicineScenarioSpec] = {
    "electronic_structure": BiomedicineScenarioSpec(
        "electronic_structure",
        "电子结构",
        "小分子活性空间基态能量估计",
        "PAULI HAMILTONIAN / DIGITAL VQE",
        (
            "从可审计的 H2、LiH 或 H2O 活性空间 Hamiltonian 出发，"
            "执行 VQE 并比较精确基态能量。"
        ),
        "atom",
        "emerald",
        (
            ("h2_bond_scan", "H2 键长扫描"),
            ("lih_active_space", "LiH 活性空间"),
            ("lih_potential_scan", "LiH 五点势能扫描 · 高级"),
            ("h2o_minimal", "H2O 最小活性空间"),
        ),
        (
            _select(
                "dataset",
                "分子与几何",
                (
                    ("h2_sto3g_0500", "H2 / 0.500 Å"),
                    ("h2_sto3g_0735", "H2 / 0.735 Å"),
                    ("h2_sto3g_1500", "H2 / 1.500 Å"),
                    ("lih_sto3g_1600", "LiH / 1.600 Å / 2e-3o"),
                    (
                        "h2o_sto3g_equilibrium",
                        "H2O / 0.958 Å / 104.45° / 2e-3o",
                    ),
                    ("lih_sto3g_1200", "LiH / 1.200 Å / 2e-3o"),
                    ("lih_sto3g_1400", "LiH / 1.400 Å / 2e-3o"),
                    ("lih_sto3g_1800", "LiH / 1.800 Å / 2e-3o"),
                    ("lih_sto3g_2200", "LiH / 2.200 Å / 2e-3o"),
                ),
            ),
            _select(
                "noise_model",
                "测量模型",
                (("ideal", "理想 QWC"), ("readout_demo", "读出噪声对照")),
            ),
        ),
        {"dataset": "h2_sto3g_0735", "noise_model": "ideal"},
        "digital",
        "pauli_vqe",
        "ground_state_energy",
        "electronic-structure",
        ("analysis", "vqe", "qwc_measurement", "exact_reference", "audit"),
        "available",
        {**_VQE_PROFILE, "maxLayers": 2, "estimatedSeconds": 1.2},
    ),
    "docking_match": BiomedicineScenarioSpec(
        "docking_match",
        "构象匹配",
        "靶点口袋与配体候选构象匹配",
        "POCKET CONFLICT GRAPH / HYBRID QAOA",
        "把离散候选相互作用映射为匹配奖励、占位冲突和覆盖约束。",
        "scan-search",
        "cyan",
        (
            ("reference_pose", "共晶参考"),
            ("strict_geometry", "几何严格"),
            ("pharmacophore_coverage", "药效团覆盖"),
            ("multi_pose_balanced", "三构象综合匹配 · 高级"),
            ("multi_pose_geometry", "三构象几何约束 · 高级"),
            ("multi_pose_coverage", "三构象特征覆盖 · 高级"),
        ),
        (
            _range("match_weight", "匹配权重", 0.2, 1.0, 0.05),
            _range("collision_penalty", "碰撞罚项", 1.0, 4.0, 0.1),
            _range("coverage_weight", "关键特征覆盖", 0.2, 1.5, 0.05),
        ),
        {
            "match_weight": 0.65,
            "collision_penalty": 2.4,
            "coverage_weight": 0.6,
        },
        "hybrid",
        "problem",
        "candidate_pose_match",
        "docking-match",
        (
            "analysis",
            "hybrid_qaoa",
            "digital_qaoa",
            "classic_enumeration",
            "co_crystal_reference",
            "audit",
        ),
        "available",
        {**_QAOA_PROFILE, "shots": 128, "seed": 1, "estimatedSeconds": 2.7},
    ),
    "active_center": BiomedicineScenarioSpec(
        "active_center",
        "金属活性中心",
        "金属酶活性中心有效 Hamiltonian",
        "EFFECTIVE SPIN MODEL / DIGITAL VQE",
        "展示二至四中心有效交换耦合、局域场与可观测量边界。",
        "orbit",
        "amber",
        (
            ("antiferromagnetic", "反铁磁耦合"),
            ("ligand_field", "配体场扰动"),
            ("coupling_imbalance", "耦合不平衡"),
            ("trinuclear_frustrated", "三中心受挫网络"),
            ("tetranuclear_ligand_field", "四中心配体场网络"),
        ),
        (
            _range("exchange_coupling", "交换耦合 J", 0.2, 2.0, 0.1, " meV"),
            _range("local_field", "局域场 h", 0.02, 1.0, 0.05, " meV"),
        ),
        {"exchange_coupling": 1.2, "local_field": 0.15},
        "digital",
        "pauli_vqe",
        "spin_correlation",
        "active-center",
        (
            "analysis",
            "digital_vqe",
            "qwc_observables",
            "exact_diagonalization",
            "audit",
        ),
        "available",
        {
            **_VQE_PROFILE,
            "maxLayers": 2,
            "shots": 512,
            "seed": 7,
            "parameterBudget": 40,
            "optimizerStarts": 1,
            "estimatedSeconds": 0.4,
        },
    ),
    "peptide_landscape": BiomedicineScenarioSpec(
        "peptide_landscape",
        "小肽能景",
        "小肽离散构象与折叠能景采样",
        "DISCRETE CONFORMATION / DIGITAL QAOA",
        "在有限二维自回避构象库中展示粗粒化接触能与低能候选。",
        "route",
        "emerald",
        (
            ("hydrophobic_core", "疏水核心"),
            ("charged_competition", "带电竞争"),
            ("contact_limited", "接触受限"),
            ("octapeptide_hydrophobic", "八残基疏水核心 · 高级"),
            ("octapeptide_charge_shift", "八残基电荷位移 · 高级"),
            ("octapeptide_mutation", "八残基突变对照 · 高级"),
        ),
        (
            _select(
                "sequence",
                "短肽序列",
                (
                    ("HPPHHP", "HPPHHP"),
                    ("+-P-+H", "+-P-+H"),
                    ("HPHPPH", "HPHPPH"),
                    ("HPPHHPHH", "HPPHHPHH"),
                    ("+-PH-+HP", "+-PH-+HP"),
                    ("HPHPPHH+", "HPHPPHH+"),
                ),
            ),
            _range("contact_weight", "接触能权重", 0.5, 2.0, 0.1),
        ),
        {"sequence": "HPPHHP", "contact_weight": 1.0},
        "digital",
        "problem",
        "conformation_landscape",
        "peptide-landscape",
        ("analysis", "digital_qaoa", "classic_landscape", "audit"),
        "available",
        {
            **_QAOA_PROFILE,
            "shots": 512,
            "seed": 7,
            "parameterBudget": 40,
            "optimizerStarts": 2,
            "estimatedSeconds": 2.2,
        },
    ),
    "rna_structure": BiomedicineScenarioSpec(
        "rna_structure",
        "RNA 折叠路径",
        "RNA 二级结构集合与折叠路径",
        "BASE-PAIR CONSTRAINTS / DIGITAL QAOA",
        "在有来源的候选碱基配对与能量参数中搜索低能可行二级结构集合。",
        "git-branch",
        "cyan",
        (
            ("hairpin_reference", "短发卡结构"),
            ("stem_competition", "竞争茎结构"),
            ("limited_pseudoknot", "有限假结研究预设"),
        ),
        (_range("minimum_loop", "最小环长", 3, 6, 1, " nt"),),
        {"minimum_loop": 3},
        "digital",
        "problem",
        "rna_structure_ensemble",
        "rna-structure",
        (
            "analysis",
            "candidate_pairs",
            "pairing_qubo",
            "digital_qaoa",
            "classic_enumeration",
            "classic_dynamic_programming",
            "dataset_reference",
            "audit",
        ),
        "available",
        {
            **_QAOA_PROFILE,
            "shots": 256,
            "seed": 7,
            "parameterBudget": 24,
            "estimatedSeconds": 1.2,
        },
    ),
    "protein_dynamics": BiomedicineScenarioSpec(
        "protein_dynamics",
        "蛋白转变路径",
        "蛋白构象转变路径与动力学网络",
        "CONFORMATION NETWORK / DIGITAL QAOA",
        "在版本化亚稳构象网络中搜索连通、低代价的离散转变路径。",
        "network",
        "emerald",
        (
            ("open_to_closed", "开放态 → 闭合态"),
            ("barrier_shift", "能垒扰动"),
            ("alternate_basin", "竞争构象盆地"),
        ),
        (
            _range("maximum_steps", "最大路径步数", 3, 4, 1),
            _range("barrier_weight", "能垒权重", 0.5, 2.0, 0.1),
        ),
        {"maximum_steps": 3, "barrier_weight": 1.0},
        "digital",
        "problem",
        "conformation_transition_path",
        "protein-dynamics",
        (
            "state_network",
            "path_qubo",
            "digital_qaoa",
            "classic_shortest_path",
            "audit",
        ),
        "available",
        {
            **_QAOA_PROFILE,
            "shots": 256,
            "seed": 7,
            "parameterBudget": 4,
            "estimatedSeconds": 2.4,
        },
    ),
}


_PREVIEW_MODELS: dict[str, dict[str, Any]] = {
    "protein_dynamics": {
        "kind": "protein_dynamics",
        "modelLevel": "离散亚稳构象状态网络",
        "nodes": [
            {
                "id": "state.open",
                "label": "Open",
                "group": "start",
                "x": 12,
                "y": 55,
                "role": "state",
            },
            {
                "id": "state.i1",
                "label": "I1",
                "group": "intermediate",
                "x": 36,
                "y": 30,
                "role": "state",
            },
            {
                "id": "state.i2",
                "label": "I2",
                "group": "intermediate",
                "x": 36,
                "y": 76,
                "role": "state",
            },
            {
                "id": "state.i3",
                "label": "I3",
                "group": "intermediate",
                "x": 64,
                "y": 52,
                "role": "state",
            },
            {
                "id": "state.closed",
                "label": "Closed",
                "group": "target",
                "x": 88,
                "y": 52,
                "role": "state",
            },
        ],
        "edges": [
            {
                "source": "state.open",
                "target": "state.i1",
                "kind": "transition",
                "score": 1.2,
            },
            {
                "source": "state.open",
                "target": "state.i2",
                "kind": "transition",
                "score": 1.6,
            },
            {
                "source": "state.i1",
                "target": "state.i3",
                "kind": "transition",
                "score": 0.9,
            },
            {
                "source": "state.i2",
                "target": "state.i3",
                "kind": "transition",
                "score": 0.7,
            },
            {
                "source": "state.i3",
                "target": "state.closed",
                "kind": "transition",
                "score": 1.0,
            },
        ],
        "limitations": ["不是全原子分子动力学", "路径代价不自动转换为真实时间"],
    },
    "docking_match": {
        "kind": "docking_match",
        "modelLevel": "离散候选相互作用匹配",
        "nodes": [
            {
                "id": "lig.N1",
                "label": "N1",
                "group": "配体",
                "x": 18,
                "y": 48,
                "role": "donor",
            },
            {
                "id": "lig.O2",
                "label": "O2",
                "group": "配体",
                "x": 34,
                "y": 68,
                "role": "acceptor",
            },
            {
                "id": "pocket.Asp25",
                "label": "Asp25",
                "group": "口袋",
                "x": 72,
                "y": 34,
                "role": "acceptor",
            },
            {
                "id": "pocket.Ile50",
                "label": "Ile50",
                "group": "口袋",
                "x": 76,
                "y": 70,
                "role": "hydrophobic",
            },
        ],
        "edges": [
            {
                "source": "lig.N1",
                "target": "pocket.Asp25",
                "kind": "hydrogen_bond",
                "score": -1.4,
            },
            {
                "source": "lig.O2",
                "target": "pocket.Ile50",
                "kind": "candidate_match",
                "score": -0.7,
            },
        ],
        "limitations": ["不是连续空间分子对接", "不输出结合自由能或药效结论"],
    },
    "active_center": {
        "kind": "active_center",
        "modelLevel": "双金属低能有效自旋模型",
        "nodes": [
            {
                "id": "metal.1",
                "label": "M1",
                "group": "金属",
                "x": 30,
                "y": 50,
                "role": "spin_site",
            },
            {
                "id": "bridge.O",
                "label": "O",
                "group": "桥联配体",
                "x": 50,
                "y": 50,
                "role": "ligand",
            },
            {
                "id": "metal.2",
                "label": "M2",
                "group": "金属",
                "x": 70,
                "y": 50,
                "role": "spin_site",
            },
            {
                "id": "lig.His",
                "label": "His",
                "group": "配位环境",
                "x": 50,
                "y": 20,
                "role": "ligand",
            },
        ],
        "edges": [
            {
                "source": "metal.1",
                "target": "bridge.O",
                "kind": "coordination",
                "score": 1.0,
            },
            {
                "source": "bridge.O",
                "target": "metal.2",
                "kind": "coordination",
                "score": 1.0,
            },
            {
                "source": "metal.1",
                "target": "metal.2",
                "kind": "exchange",
                "score": 1.2,
            },
        ],
        "limitations": ["不是完整电子结构模型", "不预测催化势垒或酶活性"],
    },
    "peptide_landscape": {
        "kind": "peptide_landscape",
        "modelLevel": "二维格点粗粒化构象",
        "sequence": "HPPHHP",
        "nodes": [
            {
                "id": f"res.{index + 1}",
                "label": residue,
                "group": residue,
                "x": x,
                "y": y,
                "role": "residue",
            }
            for index, (residue, x, y) in enumerate(
                (
                    ("H", 18, 55),
                    ("P", 32, 55),
                    ("P", 46, 55),
                    ("H", 46, 40),
                    ("H", 32, 40),
                    ("P", 18, 40),
                )
            )
        ],
        "edges": [
            {
                "source": f"res.{index}",
                "target": f"res.{index + 1}",
                "kind": "chain",
                "score": 0.0,
            }
            for index in range(1, 6)
        ]
        + [{"source": "res.1", "target": "res.5", "kind": "contact", "score": -1.0}],
        "limitations": ["只覆盖有限离散构象库", "不模拟真实蛋白质折叠动力学"],
    },
}


def preview_analysis(case_id: str) -> dict[str, Any]:
    """Return a truthful design preview for scenarios without an executor yet."""
    spec = BIOMEDICINE_SCENARIO_SPECS[case_id]
    visual = _PREVIEW_MODELS[case_id]
    identity = hashlib.sha256(
        json.dumps(visual, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if spec.recommended_mode == "hybrid":
        modes = (
            (
                "digital",
                "qaoa",
                "comparable",
                "Digital QAOA 对照链将在对接执行阶段接入。",
            ),
            ("hybrid", "qaoa", "recommended", "冲突图适合 Hybrid；几何门禁尚未完成。"),
            ("analog", "qaa", "unsuitable", "完整目标和覆盖约束不能由纯 Analog 表达。"),
        )
    else:
        algorithm = "vqe" if spec.execution_family == "pauli_vqe" else "qaoa"
        modes = (
            ("digital", algorithm, "recommended", "领域模型设计为 Digital 执行链。"),
            ("hybrid", "qaoa", "unsuitable", "当前模型没有已验证的 Analog core。"),
            (
                "analog",
                "qaa",
                "unsuitable",
                "当前 Hamiltonian 不能完整映射到纯 Analog。",
            ),
        )
    return {
        "kind": "biomedicine",
        "caseId": case_id,
        "executionFamily": spec.execution_family,
        "implementationStatus": "preview",
        "dataset": {
            "id": f"preview.{case_id}",
            "version": "design-1",
            "manifestHash": identity,
            "sourceKind": "synthetic_design_preview",
            "license": "project_generated",
            "limitations": list(visual["limitations"]),
        },
        "problem": {
            "id": f"preview.{case_id}",
            "type": "design_preview",
            "hash": identity,
            "variables": [node["id"] for node in visual["nodes"]],
            "terms": [],
        },
        "resource": {
            "logicalQubits": len(visual["nodes"]),
            "termCount": 0,
            "measurementGroups": 0,
            "parameterCount": 0,
        },
        "decision": {
            "recommendedMode": spec.recommended_mode,
            "reason": "领域结构已定义，量子执行器尚未接入。",
            "modes": [
                {
                    "mode": mode,
                    "algorithm": algorithm,
                    "availableAlgorithms": [algorithm],
                    "status": status,
                    "reason": reason,
                }
                for mode, algorithm, status, reason in modes
            ],
        },
        "domain": visual,
    }
