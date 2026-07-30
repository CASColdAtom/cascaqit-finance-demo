"""Generate the deterministic 1HSG-derived advanced docking-match fixture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STANDARD_ROOT = (
    ROOT
    / "src"
    / "cascaqit_biomedicine_demo"
    / "data"
    / "docking_match"
    / "1hsg_indinavir"
    / "1"
)
DESTINATION = (
    ROOT
    / "src"
    / "cascaqit_biomedicine_demo"
    / "data"
    / "docking_match"
    / "1hsg_indinavir_advanced"
    / "1"
)


def _stable_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _domain() -> dict[str, Any]:
    standard = json.loads((STANDARD_ROOT / "domain.json").read_text(encoding="utf-8"))
    pose_specs = (
        ("crystal", "共晶派生构象", 0.12, True, 0.08),
        ("rotated", "旋转候选构象", 0.34, False, -0.02),
        ("flipped", "翻转候选构象", 0.47, False, -0.07),
    )
    ligand_features = (
        "MK1.O2",
        "MK1.aromatic_A",
        "MK1.N2",
        "MK1.N4",
        "MK1.aromatic_B",
        "MK1.OH1",
        "MK1.hydrophobe_C",
        "MK1.amine_D",
    )
    pocket_features = (
        "Asp25:A.carboxylate",
        "Ile50:A.hydrophobic",
        "Asp25:B.carboxylate",
        "Ile50:B.hydrophobic",
        "Gly27:A.backbone",
        "Gly27:B.backbone",
        "Val82:A.hydrophobic",
        "Val82:B.hydrophobic",
    )
    required_features = pocket_features[:3]
    poses = [
        {
            "id": f"pose.{pose_id}",
            "label": label,
            "strain": strain,
            "reference": reference,
        }
        for pose_id, label, strain, reference, _adjustment in pose_specs
    ]
    matches = []
    for pose_index, (pose_id, _label, _strain, _reference, adjustment) in enumerate(
        pose_specs
    ):
        for index, ligand_feature in enumerate(ligand_features):
            pocket_feature = pocket_features[
                (index + pose_index) % len(pocket_features)
            ]
            quality = min(0.99, 0.91 - 0.035 * index + adjustment)
            distance = 0.06 + 0.035 * ((index + pose_index) % 5)
            angle = 0.0 if "hydrophobic" in pocket_feature else 0.04 + 0.025 * index
            matches.append(
                {
                    "id": f"match.{pose_id[0]}{index}",
                    "pose_id": f"pose.{pose_id}",
                    "ligand_feature": ligand_feature,
                    "pocket_feature": pocket_feature,
                    "interaction": (
                        "hydrophobic"
                        if "hydrophobic" in pocket_feature
                        else "hydrogen_bond"
                    ),
                    "quality": round(quality, 6),
                    "distance_deviation": round(distance, 6),
                    "angle_deviation": round(angle, 6),
                    "critical": pocket_feature in required_features,
                    "reference": pose_id == "crystal" and index in {0, 2},
                }
            )
    conflicts = []
    for pose_id, _label, _strain, _reference, _adjustment in pose_specs:
        prefix = pose_id[0]
        for pair_index, (left, right) in enumerate(((0, 1), (2, 3), (4, 5), (6, 7))):
            conflicts.append(
                {
                    "left": f"match.{prefix}{left}",
                    "right": f"match.{prefix}{right}",
                    "rule": (
                        "spatial_collision"
                        if pair_index % 2
                        else "pocket_occupancy_exclusive"
                    ),
                    "evidence": (
                        f"{pose_id} candidate volumes {left}/{right} overlap in the "
                        "fixed discretized feature model"
                    ),
                }
            )
    ligand_nodes = [
        {
            "id": feature,
            "label": feature.split(".")[-1],
            "group": "Indinavir",
            "role": "ligand_feature",
            "x": 15 + (index % 2) * 15,
            "y": 15 + (index // 2) * 22,
        }
        for index, feature in enumerate(ligand_features)
    ]
    pocket_nodes = [
        {
            "id": feature,
            "label": feature.split(".")[0],
            "group": "Pocket",
            "role": "pocket_feature",
            "x": 70 + (index % 2) * 15,
            "y": 15 + (index // 2) * 22,
        }
        for index, feature in enumerate(pocket_features)
    ]
    return {
        "structure": standard["structure"],
        "poses": poses,
        "matches": matches,
        "conflicts": conflicts,
        "minimum_coverage": 2,
        "required_feature_ids": list(required_features),
        "selection": {
            "rule_version": "docking-active-subproblem-v1",
            "max_match_variables": 9,
            "minimum_matches_per_pose": 2,
        },
        "reference": {
            "pose_id": "pose.crystal",
            "match_ids": ["match.c0", "match.c2"],
            "interpretation": (
                "共晶结构派生的离散相互作用参考，不是结合自由能或药效标签"
            ),
        },
        "visual": {"nodes": [*ligand_nodes, *pocket_nodes]},
        "limitations": [
            "离线派生的多构象离散候选图，不执行连续空间对接或分子动力学",
            "活动子问题由固定规则选择，不代表全部 24 个候选同时进入量子执行",
            "评分是无量纲演示目标，不是结合自由能、Kd、Ki、IC50 或药效结论",
        ],
    }


def main() -> None:
    script_hash = _hash(Path(__file__).read_bytes())
    standard_manifest = json.loads(
        (STANDARD_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    domain = _domain()
    reference = {
        "reference_kind": "co_crystal_derived_discrete_interactions",
        "reference_pose_id": "pose.crystal",
        "reference_match_ids": ["match.c0", "match.c2"],
        "classic_method": "bounded enumeration of the selected binary subproblem",
        "prohibited_interpretations": [
            "binding free energy",
            "affinity or potency",
            "continuous-space docking",
        ],
    }
    domain_raw = _stable_json(domain)
    reference_raw = _stable_json(reference)
    match_order = [item["id"] for item in domain["matches"]]
    pose_order = [
        f"select.{item['id'].split('.', 1)[1]}" for item in domain["poses"]
    ]
    manifest = {
        "dataset_id": "docking.1hsg.indinavir.advanced-discrete-match",
        "version": "1",
        "source": standard_manifest["source"],
        "generation": {
            "tool": "cascaqit-biomedicine advanced docking fixture generator",
            "tool_version": "docking-fixture-v2",
            "script": "scripts/generate_advanced_docking_fixture.py",
            "script_sha256": script_hash,
            "parameters": {
                "model": "multi-pose discrete ligand-pocket feature matching",
                "poses": len(domain["poses"]),
                "candidate_matches": len(domain["matches"]),
                "active_match_limit": domain["selection"]["max_match_variables"],
                "minimum_coverage": domain["minimum_coverage"],
            },
        },
        "units": standard_manifest["units"],
        "coordinate_system": standard_manifest["coordinate_system"],
        "variable_order": [*match_order, *pose_order, "slack.coverage"],
        "artifacts": [
            {"path": "domain.json", "sha256": _hash(domain_raw)},
            {"path": "reference.json", "sha256": _hash(reference_raw)},
        ],
        "reference": {
            "method": "bounded enumeration of each selected binary subproblem",
            "software": "CPython standard-library enumeration",
            "software_version": "3.9.6",
            "standard_presets": {
                preset: {
                    "reference_pose_id": "pose.crystal",
                    "reference_match_ids": ["match.c0", "match.c2"],
                }
                for preset in (
                    "multi_pose_balanced",
                    "multi_pose_geometry",
                    "multi_pose_coverage",
                )
            },
        },
        "allowed_claims": [
            "Demonstrate deterministic reduction of a 24-candidate matching graph.",
            "Compare Digital and Hybrid QAOA on the same selected QUBO identity.",
        ],
        "limitations": [
            "Only fixed features derived from 1HSG are represented.",
            "The quantum activity window contains 9 of 24 candidate matches.",
            "Local simulation only; no hardware execution or quantum advantage claim.",
        ],
    }
    DESTINATION.mkdir(parents=True, exist_ok=True)
    (DESTINATION / "domain.json").write_bytes(domain_raw)
    (DESTINATION / "reference.json").write_bytes(reference_raw)
    (DESTINATION / "manifest.json").write_bytes(_stable_json(manifest))
    print(f"generated {manifest['dataset_id']}: {DESTINATION}")


if __name__ == "__main__":
    main()
