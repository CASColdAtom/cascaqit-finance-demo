"""Effective multi-center spin analysis and CASCAQit VQE execution."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cascaqit.algorithms import VQE, OptimizerConfig

from cascaqit_biomedicine_demo.catalog import BIOMEDICINE_SCENARIO_SPECS
from cascaqit_biomedicine_demo.fixtures import validate_manifest_contract
from cascaqit_biomedicine_demo.pauli_vqe import (
    build_pauli_hamiltonian,
    exact_diagonalization,
    hash_payload,
    sector_occupancy_from_counts,
    sector_occupancy_from_probabilities,
)
from cascaqit_biomedicine_demo.qwc_measurement import (
    PauliMeasurementConfig,
    build_pauli_measurement_plan,
    evaluate_sampled_vqe,
)
from cascaqit_industry_demo.audit import (
    finalize_stable_audit,
    local_backend_context,
)

DATA_ROOT = Path(__file__).resolve().parent / "data" / "active_center"
_PRESET_DIRECTORIES = {
    "antiferromagnetic": "bimetal_spin",
    "ligand_field": "bimetal_spin",
    "coupling_imbalance": "bimetal_spin",
    "trinuclear_frustrated": "trinuclear_spin",
    "tetranuclear_ligand_field": "tetranuclear_spin",
}


@dataclass(frozen=True)
class ActiveCenterFixture:
    manifest: dict[str, Any]
    domain: dict[str, Any]
    pauli: dict[str, Any]
    manifest_hash: str


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"active-center fixture must contain an object: {path.name}")
    return value, raw


def load_active_center_fixture(preset: str | None = None) -> ActiveCenterFixture:
    """Load and checksum the packaged effective-model fixture for a preset."""
    selected_preset = preset or "antiferromagnetic"
    try:
        directory = _PRESET_DIRECTORIES[selected_preset]
    except KeyError as exc:
        raise ValueError(f"unknown active-center preset: {selected_preset}") from exc
    fixture_root = DATA_ROOT / directory / "1"
    manifest, manifest_raw = _read_json(fixture_root / "manifest.json")
    validate_manifest_contract(manifest)
    artifacts: dict[str, dict[str, Any]] = {
        str(item["path"]): item for item in manifest["artifacts"]
    }
    loaded: dict[str, dict[str, Any]] = {}
    for name in ("domain.json", "pauli.json"):
        payload, raw = _read_json(fixture_root / name)
        expected = str(artifacts[name]["sha256"])
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"active-center fixture checksum mismatch: {name}")
        loaded[name] = payload
    if manifest["logical_order"] != loaded["pauli.json"]["logical_order"]:
        raise ValueError("active-center fixture logical order is inconsistent")
    if selected_preset not in loaded["pauli.json"]["presets"]:
        raise ValueError(
            f"active-center fixture does not define preset: {selected_preset}"
        )
    return ActiveCenterFixture(
        manifest=manifest,
        domain=loaded["domain.json"],
        pauli=loaded["pauli.json"],
        manifest_hash=hashlib.sha256(manifest_raw).hexdigest(),
    )


def active_center_values(preset: str, overrides: dict[str, Any]) -> dict[str, float]:
    fixture = load_active_center_fixture(preset)
    try:
        definition = fixture.pauli["presets"][preset]
    except KeyError as exc:
        raise ValueError(f"unknown active-center preset: {preset}") from exc
    values = {
        "exchange_coupling": float(definition["exchange_coupling_mev"]),
        "local_field": float(definition["local_field_mev"]),
    }
    values.update({key: float(value) for key, value in overrides.items()})
    if not 0.2 <= values["exchange_coupling"] <= 2.0:
        raise ValueError("exchange_coupling must be between 0.2 and 2.0 meV")
    if not 0.02 <= values["local_field"] <= 1.0:
        raise ValueError("local_field must be between 0.02 and 1.0 meV")
    return values


def _resolved_pauli(
    fixture: ActiveCenterFixture, preset: str, values: dict[str, float]
) -> dict[str, Any]:
    definition = fixture.pauli["presets"][preset]
    exchange = values["exchange_coupling"]
    field = values["local_field"]
    logical_order = fixture.pauli["logical_order"]
    terms: list[dict[str, Any]] = []
    for path in definition["exchange_paths"]:
        for axis, multiplier in (
            ("X", path["jxy_multiplier"]),
            ("Y", path["jxy_multiplier"]),
            ("Z", path["jz_multiplier"]),
        ):
            left = str(path["left"])
            right = str(path["right"])
            terms.append(
                {
                    "term_id": f"{path['id']}.{axis.lower() * 2}",
                    "operator": f"{axis}({left}) {axis}({right})",
                    "coefficient": exchange * float(multiplier) / 4,
                    "factors": [[left, axis], [right, axis]],
                }
            )
    for item in definition["fields"]:
        site = str(item["site"])
        terms.append(
            {
                "term_id": f"field.{site.split('.')[-1]}",
                "operator": f"Z({site})",
                "coefficient": field * float(item["multiplier"]) / 2,
                "factors": [[site, "Z"]],
            }
        )
    payload = {
        "hamiltonian_id": f"{fixture.pauli['hamiltonian_id_prefix']}.{preset}",
        "logical_order": logical_order,
        "constant": float(fixture.pauli["constant_mev"]),
        "terms": terms,
        "metadata": {
            "dataset_id": fixture.manifest["dataset_id"],
            "manifest_hash": fixture.manifest_hash,
            "preset": preset,
            "units": "meV",
            "coefficient_definition": fixture.pauli["coefficient_definition"],
        },
    }
    return payload


def _template_hash(fixture: ActiveCenterFixture, preset: str) -> str:
    definition = fixture.pauli["presets"][preset]
    return hash_payload(
        {
            "datasetId": fixture.manifest["dataset_id"],
            "logicalOrder": fixture.pauli["logical_order"],
            "constantMeV": fixture.pauli["constant_mev"],
            "coefficientDefinition": fixture.pauli["coefficient_definition"],
            "exchangePaths": definition["exchange_paths"],
            "fields": definition["fields"],
        }
    )


def _analysis(preset: str, values: dict[str, float]) -> dict[str, Any]:
    fixture = load_active_center_fixture(preset)
    pauli = _resolved_pauli(fixture, preset, values)
    hamiltonian = build_pauli_hamiltonian(pauli)
    vqe = VQE(hamiltonian, layers=1)
    plan = build_pauli_measurement_plan(
        vqe.build_circuit(),
        hamiltonian,
        config=PauliMeasurementConfig(shots_per_group=256),
    )
    exact = exact_diagonalization(hamiltonian)
    exact_first_gap = exact["spectrum"][1] - exact["spectrum"][0]
    template_hash = _template_hash(fixture, preset)
    definition = fixture.pauli["presets"][preset]
    analysis = {
        "kind": "biomedicine",
        "caseId": "active_center",
        "executionFamily": "pauli_vqe",
        "implementationStatus": "available",
        "dataset": {
            "id": fixture.manifest["dataset_id"],
            "version": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "sourceKind": fixture.manifest["source"]["kind"],
            "license": fixture.manifest["source"]["license"],
            "licenseCheckedAt": fixture.manifest["source"]["license_checked_at"],
            "allowedClaims": fixture.manifest["allowed_claims"],
            "limitations": fixture.manifest["limitations"],
        },
        "problem": {
            "id": hamiltonian.hamiltonian_id,
            "type": "pauli_hamiltonian",
            "hash": hamiltonian.stable_hash(),
            "templateHash": template_hash,
            "variables": list(hamiltonian.logical_order),
            "constant": hamiltonian.constant,
            "terms": [
                {
                    "id": term.term_id,
                    "operator": term.observable.name,
                    "targets": list(term.observable.targets),
                    "coefficient": term.coefficient,
                }
                for term in hamiltonian.terms
            ],
            "measurementPlanHash": plan.plan_hash,
            "measurementGroups": [
                {
                    "index": group.group_index,
                    "basis": dict(group.basis_by_target),
                    "termIds": [term.term_id for term in group.terms],
                }
                for group in plan.groups
            ],
        },
        "resource": {
            "logicalQubits": len(hamiltonian.logical_order),
            "termCount": len(hamiltonian.terms),
            "measurementGroups": len(plan.groups),
            "parameterCount": len(vqe.parameter_names),
        },
        "decision": {
            "recommendedMode": "digital",
            "reason": (
                "XX/YY 非对角交换项与局域场由 Digital VQE "
                "和 QWC 分组测量完整表达。"
            ),
            "modes": [
                {
                    "mode": "digital",
                    "algorithm": "vqe",
                    "availableAlgorithms": ["vqe"],
                    "status": "recommended",
                    "reason": "同一 Pauli Hamiltonian 支持 VQE、QWC 观测量和精确对照。",
                },
                {
                    "mode": "hybrid",
                    "algorithm": "qaoa",
                    "availableAlgorithms": ["qaoa"],
                    "status": "unsuitable",
                    "reason": (
                        "有效自旋 Hamiltonian 不是 QUBO，"
                        "未声明可审计的 Analog core。"
                    ),
                },
                {
                    "mode": "analog",
                    "algorithm": "qaa",
                    "availableAlgorithms": ["qaa"],
                    "status": "unsuitable",
                    "reason": "当前 Analog 目标不能完整表达 XX/YY 交换项。",
                },
            ],
        },
        "domain": {
            "kind": "active_center",
            **fixture.domain,
            "preset": preset,
            "presetLabel": definition["label"],
            "presetDescription": definition["description"],
            "parameters": {**values, "units": "meV"},
            "exactGroundEnergyMeV": exact["energy"],
            "exactFirstGapMeV": exact_first_gap,
            "exactFirstGapSource": "classical_exact_diagonalization",
            "templateHamiltonianHash": template_hash,
            "instanceHamiltonianHash": hamiltonian.stable_hash(),
            "limitations": fixture.manifest["limitations"],
        },
    }
    analysis["analysisHash"] = hash_payload(analysis)
    return analysis


def analyze_active_center(preset: str, values: dict[str, Any]) -> dict[str, Any]:
    resolved = active_center_values(preset, values)
    return _analysis(preset, resolved)


def run_active_center(
    *,
    preset: str,
    values: dict[str, Any],
    shots: int,
    seed: int,
    layers: int,
    parameter_budget: int,
    optimizer_starts: int,
) -> dict[str, Any]:
    if layers not in {1, 2}:
        raise ValueError("金属活性中心模型只支持一层或两层 VQE Ansatz。")
    resolved = active_center_values(preset, values)
    fixture = load_active_center_fixture(preset)
    hamiltonian = build_pauli_hamiltonian(_resolved_pauli(fixture, preset, resolved))
    vqe = VQE(hamiltonian, layers=layers)
    started = time.perf_counter()
    result = vqe.run(
        optimizer=OptimizerConfig(
            method="COBYLA",
            max_iterations=parameter_budget,
            max_evaluations=parameter_budget,
            starts=optimizer_starts,
            seed=seed,
        ),
        final_shots=shots,
    )
    best = result.evaluations[result.best_evaluation_index]
    sampled = evaluate_sampled_vqe(
        vqe,
        best.parameter_bind.values,
        measurement=PauliMeasurementConfig(shots_per_group=shots),
        seed=seed,
    )
    exact = exact_diagonalization(hamiltonian)
    exact_first_gap = exact["spectrum"][1] - exact["spectrum"][0]
    counts = dict(result.final_result.counts) if result.final_result else {}
    sampled_expectations = {
        item.term_id: float(item.expectation) for item in sampled.contributions
    }
    standard_errors: dict[str, float] = {}
    for group in sampled.group_results:
        standard_errors.update(
            {key: float(value) for key, value in group.term_standard_errors.items()}
        )
    analysis = _analysis(preset, resolved)
    hamiltonian_hash = hamiltonian.stable_hash()
    result_dict = result.to_dict()
    bound_circuit = vqe.build_circuit().bind(best.parameter_bind.values)
    circuit = bound_circuit.to_program().to_dict()["circuit"]
    circuit_gates = [
        {
            "depth": index,
            "name": str(gate["name"]).upper(),
            "targets": list(gate.get("targets", ())),
            "controls": list(gate.get("controls", ())),
            "parameters": gate.get("parameters", {}),
        }
        for index, gate in enumerate(circuit["gates"])
    ]
    payload = {
        "kind": "biomedicine",
        "analysis": analysis,
        "domain": {
            "kind": "active_center_result",
            "vqeExactEnergyMeV": float(best.energy),
            "sampledEnergyMeV": float(sampled.energy),
            "sampledStandardErrorMeV": float(sampled.energy_standard_error),
            "exactGroundEnergyMeV": exact["energy"],
            "absoluteErrorMeV": abs(float(best.energy) - exact["energy"]),
            "exactFirstGapMeV": exact_first_gap,
            "exactFirstGapSource": "classical_exact_diagonalization",
            "magnetization": [
                {
                    "siteId": str(item["site"]),
                    "expectation": sampled_expectations[
                        f"field.{str(item['site']).split('.')[-1]}"
                    ],
                    "standardError": standard_errors[
                        f"field.{str(item['site']).split('.')[-1]}"
                    ],
                }
                for item in fixture.pauli["presets"][preset]["fields"]
            ],
            "correlations": [
                {
                    "pathId": str(path["id"]),
                    "leftSiteId": str(path["left"]),
                    "rightSiteId": str(path["right"]),
                    "operator": f"{axis}{axis}",
                    "expectation": sampled_expectations[
                        f"{path['id']}.{axis.lower() * 2}"
                    ],
                    "standardError": standard_errors[
                        f"{path['id']}.{axis.lower() * 2}"
                    ],
                }
                for path in fixture.pauli["presets"][preset]["exchange_paths"]
                for axis in ("X", "Y", "Z")
            ],
            "sectorOccupancy": sector_occupancy_from_counts(counts),
            "declaredSector": fixture.domain["declaredSector"],
            "interpretation": "结果仅描述固化低能有效自旋模型的无量纲 Pauli 期望值。",
        },
        "quantum": {
            "kind": "pauli_vqe",
            "mode": "digital",
            "algorithm": "vqe",
            "summary": {
                "qubits": len(hamiltonian.logical_order),
                "pauliTerms": len(hamiltonian.terms),
                "measurementGroups": len(sampled.plan.groups),
                "shotsPerGroup": shots,
                "totalMeasurementShots": sampled.total_shots,
                "evaluations": len(result.evaluations),
                "noiseModel": "ideal",
            },
            "circuit": {
                "qubits": list(circuit["qubits"]),
                "gates": circuit_gates,
                "depth": len(circuit_gates),
            },
            "counts": counts,
            "parameterHistory": [
                {
                    "index": index,
                    "objective": float(item.energy),
                    "parameters": dict(item.parameter_bind.values),
                }
                for index, item in enumerate(result.evaluations)
            ],
            "measurement": {
                "planHash": sampled.plan.plan_hash,
                "groups": [
                    {
                        "index": item.group.group_index,
                        "basis": dict(item.group.basis_by_target),
                        "shots": item.shots,
                        "counts": dict(item.counts),
                        "termExpectations": dict(item.term_expectations),
                        "termStandardErrors": dict(item.term_standard_errors),
                        "executionEvidence": item.execution_evidence.to_dict(),
                    }
                    for item in sampled.group_results
                ],
                "noisyGroups": [],
                "noiseModelHash": None,
            },
            "termination": result_dict["termination"],
            "ansatz": result_dict["ansatz"],
        },
        "comparison": {
            "referenceMethod": fixture.manifest["reference"]["method"],
            "hamiltonianHash": hamiltonian_hash,
            "exactSpectrumMeV": exact["spectrum"],
            "exactFirstGapMeV": exact_first_gap,
            "exactFirstGapSource": "classical_exact_diagonalization",
            "exactExpectations": exact["expectations"],
            "exactSectorOccupancy": sector_occupancy_from_probabilities(
                exact["probabilities"], len(hamiltonian.logical_order)
            ),
            "vqeHamiltonianHash": hamiltonian_hash,
        },
        "audit": {
            "domainId": "biomedicine",
            "caseId": "active_center",
            "datasetId": fixture.manifest["dataset_id"],
            "datasetVersion": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "domainInputHash": hash_payload(
                {
                    "preset": preset,
                    "values": resolved,
                    "manifestHash": fixture.manifest_hash,
                }
            ),
            "hamiltonianHash": hamiltonian_hash,
            "templateHamiltonianHash": _template_hash(fixture, preset),
            "referenceHamiltonianHash": hamiltonian_hash,
            "analysisHash": analysis["analysisHash"],
            "ansatzHash": result.ansatz.stable_hash(),
            "compileHash": result.ansatz.stable_hash(),
            "measurementPlanHash": sampled.plan.plan_hash,
            "backend": local_backend_context(
                execution_family="pauli_vqe",
                mode="digital",
                simulation_method="state_vector",
            ),
            "executionHash": result.stable_hash(),
            "seed": seed,
            "shotsPerGroup": shots,
            "hardwareExecution": False,
            "cloudExecution": False,
            "networkAccessed": False,
            "wallTimeSeconds": time.perf_counter() - started,
            "optimalityClaim": "not_claimed",
            "claimBoundary": "effective_spin_model_only",
        },
    }
    finalize_stable_audit(
        payload["audit"],
        configuration={
            "preset": preset,
            "values": resolved,
            "hamiltonianHash": hamiltonian_hash,
            "ansatzHash": result.ansatz.stable_hash(),
            "measurementPlanHash": sampled.plan.plan_hash,
            "layers": layers,
            "shotsPerGroup": shots,
            "seed": seed,
            "optimizer": {
                "method": "COBYLA",
                "parameterBudget": parameter_budget,
                "starts": optimizer_starts,
            },
        },
        outcome={
            "domain": payload["domain"],
            "finalCounts": payload["quantum"]["counts"],
            "groupCounts": [
                item["counts"] for item in payload["quantum"]["measurement"]["groups"]
            ],
            "parameterHistory": payload["quantum"]["parameterHistory"],
        },
    )
    payload["audit"]["resultHash"] = hash_payload(payload)
    return payload


def scenario_payload() -> dict[str, Any]:
    return BIOMEDICINE_SCENARIO_SPECS["active_center"].to_dict()
