"""Validated loading of packaged biomedicine experiment fixtures."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATA_ROOT = Path(__file__).resolve().parent / "data"


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
    return LoadedFixture(
        root=root,
        manifest=manifest,
        domain=loaded["domain.json"],
        pauli=loaded["pauli.json"],
        manifest_hash=hashlib.sha256(manifest_raw).hexdigest(),
    )


def load_h2_fixture() -> LoadedFixture:
    return load_fixture("electronic_structure", "h2_sto3g", "1")
