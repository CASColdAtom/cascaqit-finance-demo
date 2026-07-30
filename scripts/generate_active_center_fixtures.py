"""Generate deterministic effective-spin fixtures for active-center demos."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "cascaqit_biomedicine_demo"
    / "data"
    / "active_center"
)

MODELS: tuple[dict[str, Any], ...] = (
    {
        "directory": "bimetal_spin",
        "dataset_id": "active-center.bimetal-spin.effective-model",
        "model_name": "桥联双金属中心各向异性 Heisenberg 模型",
        "model_level": "双金属中心二自旋低能有效模型",
        "sites": ("spin.m1", "spin.m2"),
        "positions": ((26.0, 54.0), (74.0, 54.0)),
        "presets": {
            "antiferromagnetic": {
                "label": "反铁磁耦合",
                "exchange_coupling_mev": 1.2,
                "local_field_mev": 0.15,
                "description": "各向同性正交换耦合与弱交错局域场。",
                "exchange_paths": (
                    ("exchange", "spin.m1", "spin.m2", 1.0, 1.0),
                ),
                "field_multipliers": (1.0, -1.0),
            },
            "ligand_field": {
                "label": "配体场扰动",
                "exchange_coupling_mev": 1.2,
                "local_field_mev": 0.4,
                "description": "不对称局域场模拟两个有效位点受到的不同扰动。",
                "exchange_paths": (
                    ("exchange", "spin.m1", "spin.m2", 1.0, 1.0),
                ),
                "field_multipliers": (1.0, -0.25),
            },
            "coupling_imbalance": {
                "label": "耦合不平衡",
                "exchange_coupling_mev": 1.2,
                "local_field_mev": 0.15,
                "description": "XX/YY 与 ZZ 各向异性表示有效交换通道不平衡。",
                "exchange_paths": (
                    ("exchange", "spin.m1", "spin.m2", 0.75, 1.25),
                ),
                "field_multipliers": (1.0, -0.6),
            },
        },
    },
    {
        "directory": "trinuclear_spin",
        "dataset_id": "active-center.trinuclear-spin.effective-model",
        "model_name": "三中心受挫各向异性 Heisenberg 模型",
        "model_level": "三金属语境下的三自旋低能有效模型",
        "sites": ("spin.m1", "spin.m2", "spin.m3"),
        "positions": ((25.0, 68.0), (75.0, 68.0), (50.0, 25.0)),
        "presets": {
            "trinuclear_frustrated": {
                "label": "三中心受挫网络",
                "exchange_coupling_mev": 1.1,
                "local_field_mev": 0.12,
                "description": "三条反铁磁交换路径组成三角网络并加入弱不均匀局域场。",
                "exchange_paths": (
                    ("exchange.m1-m2", "spin.m1", "spin.m2", 1.0, 1.05),
                    ("exchange.m2-m3", "spin.m2", "spin.m3", 0.9, 1.0),
                    ("exchange.m3-m1", "spin.m3", "spin.m1", 1.1, 0.95),
                ),
                "field_multipliers": (1.0, -0.5, 0.25),
            }
        },
    },
    {
        "directory": "tetranuclear_spin",
        "dataset_id": "active-center.tetranuclear-spin.effective-model",
        "model_name": "四中心环形各向异性 Heisenberg 模型",
        "model_level": "四金属语境下的四自旋低能有效模型",
        "sites": ("spin.m1", "spin.m2", "spin.m3", "spin.m4"),
        "positions": (
            (25.0, 28.0),
            (75.0, 28.0),
            (75.0, 72.0),
            (25.0, 72.0),
        ),
        "presets": {
            "tetranuclear_ligand_field": {
                "label": "四中心配体场网络",
                "exchange_coupling_mev": 0.9,
                "local_field_mev": 0.18,
                "description": "四条不等价交换路径和交错局域场组成环形有效模型。",
                "exchange_paths": (
                    ("exchange.m1-m2", "spin.m1", "spin.m2", 1.0, 1.0),
                    ("exchange.m2-m3", "spin.m2", "spin.m3", 0.8, 1.15),
                    ("exchange.m3-m4", "spin.m3", "spin.m4", 1.1, 0.9),
                    ("exchange.m4-m1", "spin.m4", "spin.m1", 0.95, 1.05),
                ),
                "field_multipliers": (1.0, -1.0, 0.5, -0.5),
            }
        },
    },
)


def _stable_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _resolved_terms(
    sites: tuple[str, ...], definition: dict[str, Any]
) -> list[dict[str, Any]]:
    exchange = float(definition["exchange_coupling_mev"])
    field = float(definition["local_field_mev"])
    terms: list[dict[str, Any]] = []
    for path_id, left, right, jxy_multiplier, jz_multiplier in definition[
        "exchange_paths"
    ]:
        for axis, multiplier in (
            ("X", jxy_multiplier),
            ("Y", jxy_multiplier),
            ("Z", jz_multiplier),
        ):
            terms.append(
                {
                    "term_id": f"{path_id}.{axis.lower() * 2}",
                    "operator": f"{axis}({left}) {axis}({right})",
                    "coefficient": exchange * float(multiplier) / 4,
                    "factors": [[left, axis], [right, axis]],
                }
            )
    for site, multiplier in zip(sites, definition["field_multipliers"]):
        terms.append(
            {
                "term_id": f"field.{site.split('.')[-1]}",
                "operator": f"Z({site})",
                "coefficient": field * float(multiplier) / 2,
                "factors": [[site, "Z"]],
            }
        )
    return terms


def _spectrum(sites: tuple[str, ...], terms: list[dict[str, Any]]) -> list[float]:
    pauli = {
        "I": np.eye(2, dtype=complex),
        "X": np.array([[0, 1], [1, 0]], dtype=complex),
        "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
        "Z": np.array([[1, 0], [0, -1]], dtype=complex),
    }
    matrix = np.zeros((2 ** len(sites), 2 ** len(sites)), dtype=complex)
    for term in terms:
        factors = {site: axis for site, axis in term["factors"]}
        operator = np.array([[1.0 + 0.0j]])
        for site in sites:
            operator = np.kron(operator, pauli[factors.get(site, "I")])
        matrix += float(term["coefficient"]) * operator
    return [float(value) for value in np.linalg.eigvalsh(matrix)]


def _fixture(model: dict[str, Any], script_hash: str) -> tuple[bytes, bytes, bytes]:
    sites = tuple(model["sites"])
    domain = {
        "modelLevel": model["model_level"],
        "modelName": model["model_name"],
        "effectiveSpinSites": len(sites),
        "declaredSector": "total_magnetization_z",
        "nodes": [
            {
                "id": site,
                "label": site.split(".")[-1].upper(),
                "group": "有效自旋",
                "x": position[0],
                "y": position[1],
                "role": "effective_spin_site",
            }
            for site, position in zip(sites, model["positions"])
        ],
        "edges": [
            {
                "source": left,
                "target": right,
                "kind": "effective_exchange",
                "pathId": path_id,
                "score": float(jz_multiplier),
            }
            for definition in model["presets"].values()
            for path_id, left, right, _jxy_multiplier, jz_multiplier in definition[
                "exchange_paths"
            ]
        ],
    }
    unique_edges = {item["pathId"]: item for item in domain["edges"]}
    domain["edges"] = list(unique_edges.values())
    pauli_presets = {}
    references = {}
    for preset, definition in model["presets"].items():
        exchange_paths = [
            {
                "id": path_id,
                "left": left,
                "right": right,
                "jxy_multiplier": jxy_multiplier,
                "jz_multiplier": jz_multiplier,
            }
            for path_id, left, right, jxy_multiplier, jz_multiplier in definition[
                "exchange_paths"
            ]
        ]
        pauli_presets[preset] = {
            key: value
            for key, value in definition.items()
            if key not in {"exchange_paths", "field_multipliers"}
        } | {
            "exchange_paths": exchange_paths,
            "fields": [
                {"site": site, "multiplier": multiplier}
                for site, multiplier in zip(sites, definition["field_multipliers"])
            ],
        }
        spectrum = _spectrum(sites, _resolved_terms(sites, definition))
        references[preset] = {
            "exchange_coupling_mev": definition["exchange_coupling_mev"],
            "local_field_mev": definition["local_field_mev"],
            "exact_ground_energy_mev": spectrum[0],
            "exact_first_gap_mev": spectrum[1] - spectrum[0],
        }
    pauli_payload = {
        "hamiltonian_id_prefix": model["dataset_id"],
        "logical_order": list(sites),
        "constant_mev": 0.0,
        "coefficient_definition": (
            "H = sum_paths (Jxy/4)(XX+YY) + (Jz/4)ZZ + "
            "sum_sites (h/2)Z"
        ),
        "presets": pauli_presets,
    }
    domain_raw = _stable_json(domain)
    pauli_raw = _stable_json(pauli_payload)
    manifest = {
        "dataset_id": model["dataset_id"],
        "version": "1",
        "source": {
            "kind": "project_generated_effective_model",
            "uri": None,
            "raw_file_sha256": None,
            "license": "project_generated",
            "license_checked_at": "2026-07-30",
        },
        "generation": {
            "tool": "cascaqit-biomedicine effective-spin fixture generator",
            "tool_version": "active-center-fixture-v2",
            "script": "scripts/generate_active_center_fixtures.py",
            "script_sha256": script_hash,
            "parameters": {
                "model": model["model_name"],
                "site_count": len(sites),
                "units": "meV",
            },
        },
        "units": {
            "energy": "meV",
            "exchange_coupling": "meV",
            "local_field": "meV",
            "spin_observable": "dimensionless Pauli expectation",
        },
        "coordinate_system": {
            "domain": "effective spin graph without spatial coordinates",
            "hardware": "not_applicable; effective spins are not atom positions",
        },
        "logical_order": list(sites),
        "artifacts": [
            {"path": "domain.json", "sha256": _hash(domain_raw)},
            {"path": "pauli.json", "sha256": _hash(pauli_raw)},
        ],
        "reference": {
            "method": "exact diagonalization of the resolved Pauli Hamiltonian",
            "software": "numpy.linalg.eigvalsh",
            "software_version": np.__version__,
            "standard_presets": references,
        },
        "allowed_claims": [
            "Compare CASCAQit VQE with exact diagonalization of the same model.",
            "Explain exchange paths, local fields, and spin correlations.",
        ],
        "limitations": [
            "Project-generated low-energy effective model, not ab initio chemistry.",
            "Effective spin sites are not orbitals or neutral-atom positions.",
            "Exact excitation gaps are classical references, not VQD results.",
            "No catalytic, kinetic, redox, or enzyme-activity prediction.",
            "Local simulation only; no hardware execution or quantum advantage claim.",
        ],
    }
    return domain_raw, pauli_raw, _stable_json(manifest)


def main() -> None:
    script_hash = _hash(Path(__file__).read_bytes())
    for model in MODELS:
        domain_raw, pauli_raw, manifest_raw = _fixture(model, script_hash)
        destination = ROOT / model["directory"] / "1"
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "domain.json").write_bytes(domain_raw)
        (destination / "pauli.json").write_bytes(pauli_raw)
        (destination / "manifest.json").write_bytes(manifest_raw)
        print(f"generated {model['dataset_id']}: {destination}")


if __name__ == "__main__":
    main()
