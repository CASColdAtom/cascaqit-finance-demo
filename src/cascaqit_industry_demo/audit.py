"""Stable audit helpers shared by local industry experiment families."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_payload(value: Any) -> str:
    """Return a stable UTF-8 JSON SHA-256 identity."""
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def local_backend_context(
    *, execution_family: str, mode: str, simulation_method: str
) -> dict[str, Any]:
    """Describe the local execution boundary without runtime identifiers."""
    return {
        "backendId": "cascaqit.local.default",
        "executionFamily": execution_family,
        "mode": mode,
        "simulationMethod": simulation_method,
        "hardwareExecution": False,
        "cloudExecution": False,
        "networkAccessed": False,
    }


def finalize_stable_audit(
    audit: dict[str, Any],
    *,
    configuration: dict[str, Any],
    outcome: dict[str, Any],
) -> None:
    """Add reproducible configuration, outcome, Backend, and report hashes."""
    backend = audit.get("backend")
    if not isinstance(backend, dict):
        raise ValueError("audit backend context is required")
    audit["backendHash"] = hash_payload(backend)
    audit["configurationHash"] = hash_payload(
        {
            "schema": str(
                audit.get(
                    "configurationSchema",
                    "biomedicine.execution-configuration.v1",
                )
            ),
            "datasetId": audit["datasetId"],
            "datasetVersion": audit["datasetVersion"],
            "manifestHash": audit["manifestHash"],
            "backendHash": audit["backendHash"],
            "configuration": configuration,
        }
    )
    audit["outcomeHash"] = hash_payload(
        {
            "schema": str(
                audit.get("outcomeSchema", "biomedicine.execution-outcome.v1")
            ),
            "configurationHash": audit["configurationHash"],
            "outcome": outcome,
        }
    )
    audit["reportHash"] = hash_payload(
        {
            "schema": str(
                audit.get("reportSchema", "biomedicine.execution-report.v1")
            ),
            "configurationHash": audit["configurationHash"],
            "outcomeHash": audit["outcomeHash"],
            "claimBoundary": audit.get("claimBoundary"),
            "optimalityClaim": audit.get("optimalityClaim", "not_claimed"),
        }
    )
