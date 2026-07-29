"""Stable audit helpers shared by biomedicine experiment families."""

from __future__ import annotations

from typing import Any

from cascaqit_biomedicine_demo.pauli_vqe import hash_payload


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
            "schema": "biomedicine.execution-configuration.v1",
            "datasetId": audit["datasetId"],
            "datasetVersion": audit["datasetVersion"],
            "manifestHash": audit["manifestHash"],
            "backendHash": audit["backendHash"],
            "configuration": configuration,
        }
    )
    audit["outcomeHash"] = hash_payload(
        {
            "schema": "biomedicine.execution-outcome.v1",
            "configurationHash": audit["configurationHash"],
            "outcome": outcome,
        }
    )
    audit["reportHash"] = hash_payload(
        {
            "schema": "biomedicine.execution-report.v1",
            "configurationHash": audit["configurationHash"],
            "outcomeHash": audit["outcomeHash"],
            "claimBoundary": audit.get("claimBoundary"),
            "optimalityClaim": audit.get("optimalityClaim", "not_claimed"),
        }
    )
