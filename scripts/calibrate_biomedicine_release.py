"""Run the complete fixed-seed release calibration for biomedicine presets."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cascaqit_biomedicine_demo.active_center import (
    analyze_active_center,
    run_active_center,
)
from cascaqit_biomedicine_demo.docking import (
    analyze_docking_match,
    run_docking_match,
)
from cascaqit_biomedicine_demo.electronic_structure import (
    analyze_electronic_structure,
    run_electronic_structure,
)
from cascaqit_biomedicine_demo.peptide_landscape import (
    analyze_peptide_landscape,
    run_peptide_landscape,
)

ROOT = Path(__file__).resolve().parents[1]
CASCAQIT_RELEASE = {
    "version": "1.0.7a0",
    "tag": "v1.0.7a",
    "sourceCommit": "2fa67d0c2fdb447995233ab3b65cc92897e81ec5",
    "wheelPath": "vendor/cascaqit-1.0.7a0-py3-none-any.whl",
    "wheelSha256": "c6aab02a71e0897d569c3c9f6aebf336b2886daf71be1ed1443a26640defecf6",
}
DEFAULT_OUTPUT = (
    ROOT / "docs" / "process" / "evidence" / "biomedicine_release_calibration.json"
)
SEED_PLAN = {
    "electronic_structure": {
        "h2_bond_scan": (1, 6, 7),
        "lih_active_space": (1, 6, 7),
        "h2o_minimal": (1, 6, 7),
        "lih_potential_scan": (1, 6, 7),
    },
    "docking_match": {
        "reference_pose": (1, 6, 8),
        "strict_geometry": (1, 8, 11),
        "pharmacophore_coverage": (3, 6, 8),
        "multi_pose_balanced": (0, 3, 6),
    },
    "active_center": {
        "antiferromagnetic": (1, 6, 7),
        "ligand_field": (1, 6, 7),
        "coupling_imbalance": (1, 6, 7),
        "trinuclear_frustrated": (1, 6, 7),
    },
    "peptide_landscape": {
        "hydrophobic_core": (0, 6, 7),
        "charged_competition": (1, 6, 7),
        "contact_limited": (0, 6, 7),
        "octapeptide_hydrophobic": (0, 3, 6),
    },
}


def _timed(call: Callable[[], dict[str, Any]]) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    result = call()
    return result, time.perf_counter() - started


def _audit_evidence(run: dict[str, Any]) -> dict[str, Any]:
    audit = run["audit"]
    return {
        key: audit[key]
        for key in (
            "manifestHash",
            "domainInputHash",
            "analysisHash",
            "backendHash",
            "configurationHash",
            "outcomeHash",
            "reportHash",
            "executionHash",
            "resultHash",
        )
        if key in audit
    }


def _electronic_case(preset: str, seed: int) -> dict[str, Any]:
    analysis, analysis_seconds = _timed(
        lambda: analyze_electronic_structure(preset, {})
    )
    run, run_seconds = _timed(
        lambda: run_electronic_structure(
            preset=preset,
            values={},
            shots=64,
            seed=seed,
            layers=1,
            parameter_budget=40,
            optimizer_starts=2,
        )
    )
    domain = run["domain"]
    hamiltonian_matches = run["audit"]["hamiltonianHash"] == analysis["problem"][
        "hash"
    ]
    accuracy_passed = (
        domain["absoluteErrorHartree"] <= 0.0016
        if preset == "h2_bond_scan"
        else domain["accuracyClaim"] == "error_report_only"
    )
    return {
        "analysisSeconds": analysis_seconds,
        "runSeconds": run_seconds,
        "datasetId": analysis["dataset"]["id"],
        "hamiltonianHashMatchesFixture": hamiltonian_matches,
        "absoluteErrorHartree": domain["absoluteErrorHartree"],
        "accuracyClaim": domain["accuracyClaim"],
        "passed": (
            analysis_seconds < 2
            and run_seconds < 30
            and hamiltonian_matches
            and accuracy_passed
        ),
        "audit": _audit_evidence(run),
    }


def _docking_case(preset: str, seed: int) -> dict[str, Any]:
    advanced = preset.startswith("multi_pose_")
    analysis, analysis_seconds = _timed(lambda: analyze_docking_match(preset, {}))
    run, run_seconds = _timed(
        lambda: run_docking_match(
            preset=preset,
            values={},
            mode="hybrid",
            shots=1024 if advanced else 128,
            seed=seed,
            layers=1,
            search_strategy="continuous",
            parameter_budget=24 if advanced else 12,
            optimizer_starts=1,
        )
    )
    domain = run["domain"]
    feasible = bool(domain["quantumCandidate"]["feasible"])
    return {
        "analysisSeconds": analysis_seconds,
        "runSeconds": run_seconds,
        "datasetId": analysis["dataset"]["id"],
        "quantumCandidateFeasible": feasible,
        "observedFeasibleCount": domain["observedFeasibleCount"],
        "classicCandidateSeparated": (
            domain["quantumCandidate"]["source"] == "quantum_observed"
            and domain["classicOptimum"]["source"] == "complete_enumeration"
            and domain["coCrystalReference"]["source"] == "co_crystal_reference"
        ),
        "passed": analysis_seconds < 2 and run_seconds < 30 and feasible,
        "audit": _audit_evidence(run),
    }


def _active_center_case(preset: str, seed: int) -> dict[str, Any]:
    error_limit = 0.2 if preset == "trinuclear_frustrated" else 0.02
    analysis, analysis_seconds = _timed(lambda: analyze_active_center(preset, {}))
    run, run_seconds = _timed(
        lambda: run_active_center(
            preset=preset,
            values={},
            shots=512,
            seed=seed,
            layers=1,
            parameter_budget=40,
            optimizer_starts=1,
        )
    )
    error = float(run["domain"]["absoluteErrorMeV"])
    same_hamiltonian = (
        run["audit"]["hamiltonianHash"]
        == run["audit"]["referenceHamiltonianHash"]
        == run["comparison"]["hamiltonianHash"]
        == run["comparison"]["vqeHamiltonianHash"]
    )
    return {
        "analysisSeconds": analysis_seconds,
        "runSeconds": run_seconds,
        "datasetId": analysis["dataset"]["id"],
        "absoluteErrorMeV": error,
        "absoluteErrorLimitMeV": error_limit,
        "hamiltonianIdentityVerified": same_hamiltonian,
        "passed": (
            analysis_seconds < 2
            and run_seconds < 30
            and error < error_limit
            and same_hamiltonian
        ),
        "audit": _audit_evidence(run),
    }


def _peptide_case(preset: str, seed: int) -> dict[str, Any]:
    advanced = preset.startswith("octapeptide_")
    analysis, analysis_seconds = _timed(
        lambda: analyze_peptide_landscape(preset, {})
    )
    run, run_seconds = _timed(
        lambda: run_peptide_landscape(
            preset=preset,
            values={},
            shots=128 if advanced else 512,
            seed=seed,
            layers=1,
            parameter_budget=12 if advanced else 40,
            optimizer_starts=1 if advanced else 2,
        )
    )
    domain = run["domain"]
    candidate = domain["quantumCandidate"]
    levels = sorted({float(item["energy"]) for item in domain["fullLandscape"]})
    low_energy_threshold = levels[min(1, len(levels) - 1)]
    low_energy = bool(candidate["feasible"]) and float(candidate["energy"]) <= (
        low_energy_threshold + 1e-12
    )
    return {
        "analysisSeconds": analysis_seconds,
        "runSeconds": run_seconds,
        "datasetId": analysis["dataset"]["id"],
        "quantumCandidateFeasible": candidate["feasible"],
        "candidateEnergy": candidate["energy"],
        "secondEnergyLevel": low_energy_threshold,
        "lowestOrSecondLowestObserved": low_energy,
        "observedFeasibleCount": domain["observedFeasibleCount"],
        "passed": analysis_seconds < 2 and run_seconds < 30 and low_energy,
        "audit": _audit_evidence(run),
    }


def _version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "local-source"


def _cascaqit_provenance() -> dict[str, Any]:
    wheel = ROOT / CASCAQIT_RELEASE["wheelPath"]
    if not wheel.is_file():
        raise RuntimeError(f"missing release wheel: {wheel}")
    wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if wheel_sha256 != CASCAQIT_RELEASE["wheelSha256"]:
        raise RuntimeError("CASCAQit release wheel SHA-256 does not match the pin")
    installed_version = _version("cascaqit")
    if installed_version != CASCAQIT_RELEASE["version"]:
        raise RuntimeError(
            "calibration requires CASCAQit "
            f"{CASCAQIT_RELEASE['version']}, got {installed_version}"
        )
    direct_url_text = importlib.metadata.distribution("cascaqit").read_text(
        "direct_url.json"
    )
    direct_url = json.loads(direct_url_text) if direct_url_text else None
    archive_hash = (
        direct_url.get("archive_info", {}).get("hash")
        if isinstance(direct_url, dict)
        else None
    )
    expected_archive_hash = f"sha256={CASCAQIT_RELEASE['wheelSha256']}"
    if archive_hash != expected_archive_hash:
        raise RuntimeError(
            "installed CASCAQit is not traceable to the pinned release wheel"
        )
    return {
        **CASCAQIT_RELEASE,
        "installedVersion": installed_version,
        "installedFrom": direct_url,
        "wheelHashVerified": True,
    }


def calibrate() -> dict[str, Any]:
    cascaqit_provenance = _cascaqit_provenance()
    matrix: tuple[
        tuple[str, tuple[str, ...], Callable[[str, int], dict[str, Any]]], ...
    ] = (
        (
            "electronic_structure",
            (
                "h2_bond_scan",
                "lih_active_space",
                "h2o_minimal",
                "lih_potential_scan",
            ),
            _electronic_case,
        ),
        (
            "docking_match",
            (
                "reference_pose",
                "strict_geometry",
                "pharmacophore_coverage",
                "multi_pose_balanced",
            ),
            _docking_case,
        ),
        (
            "active_center",
            (
                "antiferromagnetic",
                "ligand_field",
                "coupling_imbalance",
                "trinuclear_frustrated",
            ),
            _active_center_case,
        ),
        (
            "peptide_landscape",
            (
                "hydrophobic_core",
                "charged_competition",
                "contact_limited",
                "octapeptide_hydrophobic",
            ),
            _peptide_case,
        ),
    )
    records = []
    for scenario, presets, runner in matrix:
        for preset in presets:
            for seed in SEED_PLAN[scenario][preset]:
                print(f"calibrating {scenario}/{preset} seed={seed}", flush=True)
                evidence = runner(preset, seed)
                records.append(
                    {
                        "scenario": scenario,
                        "preset": preset,
                        "seed": seed,
                        **evidence,
                    }
                )
    passed = all(record["passed"] for record in records)
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {
        "schema": "biomedicine.release-calibration.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "product": "中科酷原行业量子实验台",
        "executionBoundary": {
            "backend": "CASCAQit LocalBackend",
            "localSimulationOnly": True,
            "hardwareExecution": False,
            "networkRequired": False,
            "quantumAdvantageClaimed": False,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cascaqit": _version("cascaqit"),
            "workbench": _version("cascaqit-industry-workbench"),
            "scriptSha256": script_hash,
        },
        "sdkProvenance": cascaqit_provenance,
        "fixedSeedPlan": {
            scenario: {preset: list(seeds) for preset, seeds in presets.items()}
            for scenario, presets in SEED_PLAN.items()
        },
        "acceptance": {
            "analysisSecondsLessThan": 2,
            "runSecondsLessThan": 30,
            "h2ErrorHartreeAtMost": 0.0016,
            "activeCenterErrorMeVLessThan": 0.02,
            "advancedActiveCenterErrorMeVLessThan": 0.2,
            "dockingRequiresObservedFeasibleCandidate": True,
            "peptideRequiresLowestOrSecondLowestCandidate": True,
        },
        "summary": {
            "scenarioCount": len(matrix),
            "presetCount": sum(len(item[1]) for item in matrix),
            "runCount": len(records),
            "passedRunCount": sum(bool(record["passed"]) for record in records),
            "passed": passed,
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = calibrate()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"calibration: {report['summary']['passedRunCount']}/"
        f"{report['summary']['runCount']} passed; evidence={output}"
    )
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
