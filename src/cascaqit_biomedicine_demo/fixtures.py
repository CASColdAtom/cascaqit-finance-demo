"""Validated loading of packaged biomedicine experiment fixtures."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATA_ROOT = Path(__file__).resolve().parent / "data"

ELECTRONIC_DATASET_PATHS = {
    "h2_sto3g_0500": "h2_sto3g_0500",
    "h2_sto3g_0735": "h2_sto3g",
    "h2_sto3g_1500": "h2_sto3g_1500",
    "lih_sto3g_1600": "lih_sto3g_1600",
    "h2o_sto3g_equilibrium": "h2o_sto3g_equilibrium",
}

H2_BOND_SCAN_DATASETS = (
    "h2_sto3g_0500",
    "h2_sto3g_0735",
    "h2_sto3g_1500",
)


@dataclass(frozen=True)
class LoadedFixture:
    root: Path
    manifest: dict[str, Any]
    domain: dict[str, Any]
    pauli: dict[str, Any]
    manifest_hash: str


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"fixture JSON must contain an object: {path.name}")
    return value, raw


def load_fixture(scenario: str, dataset: str, version: str) -> LoadedFixture:
    root = DATA_ROOT / scenario / dataset / version
    manifest, manifest_raw = _read_json(root / "manifest.json")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("fixture manifest must declare artifacts")
    loaded: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("fixture artifact declarations must be objects")
        name = str(artifact.get("path", ""))
        if name not in {"domain.json", "pauli.json"}:
            raise ValueError(f"unsupported fixture artifact: {name}")
        payload, raw = _read_json(root / name)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != artifact.get("sha256"):
            raise ValueError(f"fixture checksum mismatch: {name}")
        loaded[name] = payload
    if set(loaded) != {"domain.json", "pauli.json"}:
        raise ValueError("electronic structure fixture is incomplete")
    logical_order = manifest.get("logical_order")
    if (
        not isinstance(logical_order, list)
        or not logical_order
        or len(set(logical_order)) != len(logical_order)
    ):
        raise ValueError("fixture logical_order must contain unique identifiers")
    if loaded["pauli.json"].get("logical_order") != logical_order:
        raise ValueError("fixture manifest and Pauli logical_order mismatch")
    generation_parameters = manifest.get("generation", {}).get("parameters", {})
    if generation_parameters.get("final_qubit_count") != len(logical_order):
        raise ValueError("fixture final_qubit_count and logical_order mismatch")
    if generation_parameters.get("tapered_qubit_count") != 2:
        raise ValueError("fixture must declare the two-qubit symmetry tapering")
    term_ids: set[str] = set()
    for term in loaded["pauli.json"].get("terms", ()):
        term_id = term.get("term_id")
        if not isinstance(term_id, str) or not term_id or term_id in term_ids:
            raise ValueError("fixture Pauli term identifiers must be unique")
        term_ids.add(term_id)
        coefficient = term.get("coefficient")
        if (
            not isinstance(coefficient, (int, float))
            or isinstance(coefficient, bool)
            or not math.isfinite(float(coefficient))
        ):
            raise ValueError("fixture Pauli coefficients must be finite")
        factors = term.get("factors")
        if not isinstance(factors, list) or not factors:
            raise ValueError("fixture Pauli terms must declare factors")
        if any(
            not isinstance(factor, list)
            or len(factor) != 2
            or factor[0] not in logical_order
            or factor[1] not in {"X", "Y", "Z"}
            for factor in factors
        ):
            raise ValueError("fixture Pauli factors are invalid")
    reference = manifest.get("reference", {})
    for key in ("exact_ground_energy_hartree", "hartree_fock_energy_hartree"):
        value = reference.get(key)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise ValueError(f"fixture reference {key} must be finite")
    return LoadedFixture(
        root=root,
        manifest=manifest,
        domain=loaded["domain.json"],
        pauli=loaded["pauli.json"],
        manifest_hash=hashlib.sha256(manifest_raw).hexdigest(),
    )


def load_electronic_fixture(dataset_key: str) -> LoadedFixture:
    try:
        dataset = ELECTRONIC_DATASET_PATHS[dataset_key]
    except KeyError as exc:
        raise ValueError(
            f"unknown electronic structure dataset: {dataset_key}"
        ) from exc
    fixture = load_fixture("electronic_structure", dataset, "1")
    if fixture.domain.get("datasetKey") != dataset_key:
        raise ValueError("electronic fixture dataset key mismatch")
    source = fixture.manifest.get("source", {})
    generation = fixture.manifest.get("generation", {})
    for digest in (source.get("input_sha256"), generation.get("script_sha256")):
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("electronic fixture provenance hash is invalid")
    return fixture


def load_h2_fixture() -> LoadedFixture:
    """Load the equilibrium H2 fixture retained for API compatibility."""
    return load_electronic_fixture("h2_sto3g_0735")
