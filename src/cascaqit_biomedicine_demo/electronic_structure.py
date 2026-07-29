"""H2 active-space analysis and CASCAQit VQE execution."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from cascaqit.algorithms import VQE, HamiltonianTerm, OptimizerConfig, PauliHamiltonian
from cascaqit.algorithms.measurement import (
    PauliMeasurementConfig,
    build_pauli_measurement_plan,
)
from cascaqit.observables import PauliProduct

from cascaqit_biomedicine_demo.catalog import BIOMEDICINE_SCENARIO_SPECS
from cascaqit_biomedicine_demo.fixtures import LoadedFixture, load_h2_fixture


def _hash_payload(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _hamiltonian(fixture: LoadedFixture) -> PauliHamiltonian:
    pauli = fixture.pauli
    logical_order = tuple(str(item) for item in pauli["logical_order"])
    terms = []
    for item in pauli["terms"]:
        factors = tuple((str(target), str(basis)) for target, basis in item["factors"])
        terms.append(
            HamiltonianTerm(
                str(item["term_id"]),
                float(item["coefficient"]),
                PauliProduct(factors, name=str(item["operator"])),
            )
        )
    return PauliHamiltonian(
        hamiltonian_id=str(pauli["hamiltonian_id"]),
        terms=tuple(terms),
        constant=float(pauli["constant"]),
        logical_order=logical_order,
        metadata={
            "dataset_id": fixture.manifest["dataset_id"],
            "manifest_hash": fixture.manifest_hash,
        },
    )


def analyze_electronic_structure() -> dict[str, Any]:
    fixture = load_h2_fixture()
    hamiltonian = _hamiltonian(fixture)
    vqe = VQE(hamiltonian, layers=1)
    plan = build_pauli_measurement_plan(
        vqe.build_circuit(),
        hamiltonian,
        config=PauliMeasurementConfig(shots_per_group=64),
    )
    reference = fixture.manifest["reference"]
    analysis = {
        "kind": "biomedicine",
        "caseId": "electronic_structure",
        "executionFamily": "pauli_vqe",
        "implementationStatus": "available",
        "dataset": {
            "id": fixture.manifest["dataset_id"],
            "version": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "sourceKind": fixture.manifest["source"]["kind"],
            "license": fixture.manifest["source"]["license"],
            "limitations": fixture.manifest["limitations"],
        },
        "problem": {
            "id": hamiltonian.hamiltonian_id,
            "type": "pauli_hamiltonian",
            "hash": hamiltonian.stable_hash(),
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
            "reason": "非对角 Pauli 项需要通用数字线路和分组测量。",
            "modes": [
                {
                    "mode": "digital",
                    "algorithm": "vqe",
                    "availableAlgorithms": ["vqe"],
                    "status": "recommended",
                    "reason": "CASCAQit 已支持 PauliHamiltonian、VQE 与 QWC 分组测量。",
                },
                {
                    "mode": "hybrid",
                    "algorithm": "qaoa",
                    "availableAlgorithms": ["qaoa"],
                    "status": "unsuitable",
                    "reason": (
                        "该电子 Hamiltonian 不是 QUBO，也没有可审计的 Analog core。"
                    ),
                },
                {
                    "mode": "analog",
                    "algorithm": "qaa",
                    "availableAlgorithms": ["qaa"],
                    "status": "unsuitable",
                    "reason": "XX 非对角项不能由当前纯 Analog 目标完整表达。",
                },
            ],
        },
        "domain": {
            "kind": "electronic_structure",
            **fixture.domain,
            "reference": reference,
            "limitations": fixture.manifest["limitations"],
        },
    }
    analysis["analysisHash"] = _hash_payload(analysis)
    return analysis


def run_electronic_structure(
    *, shots: int, seed: int, layers: int, parameter_budget: int, optimizer_starts: int
) -> dict[str, Any]:
    if layers != 1:
        raise ValueError("H2 首个已校准预设只支持一层 VQE Ansatz。")
    fixture = load_h2_fixture()
    hamiltonian = _hamiltonian(fixture)
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
    sampled = vqe.evaluate_sampled(
        best.parameter_bind.values,
        measurement=PauliMeasurementConfig(shots_per_group=shots),
        seed=seed,
    )
    wall_time = time.perf_counter() - started
    reference = float(fixture.manifest["reference"]["exact_ground_energy_hartree"])
    exact_energy = float(best.energy)
    sampled_energy = float(sampled.energy)
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
    analysis = analyze_electronic_structure()
    result_dict = result.to_dict()
    payload = {
        "kind": "biomedicine",
        "analysis": analysis,
        "domain": {
            "kind": "ground_state_energy",
            "exactOptimizedEnergy": exact_energy,
            "sampledConfirmationEnergy": sampled_energy,
            "sampledStandardError": float(sampled.energy_standard_error),
            "referenceEnergy": reference,
            "absoluteErrorHartree": abs(exact_energy - reference),
            "chemicalAccuracyThresholdHartree": 0.0016,
            "withinChemicalAccuracy": abs(exact_energy - reference) <= 0.0016,
            "estimatorNote": (
                "优化目标来自理想态矢量；最终能量确认来自 QWC 有限 shots 测量。"
            ),
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
            },
            "circuit": {
                "qubits": list(circuit["qubits"]),
                "gates": circuit_gates,
                "depth": len(circuit_gates),
            },
            "counts": dict(result.final_result.counts) if result.final_result else {},
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
                    }
                    for item in sampled.group_results
                ],
            },
            "termination": result_dict["termination"],
            "ansatz": result_dict["ansatz"],
        },
        "comparison": {
            "referenceMethod": fixture.manifest["reference"]["method"],
            "hartreeFockEnergy": fixture.manifest["reference"][
                "hartree_fock_energy_hartree"
            ],
            "exactGroundEnergy": reference,
            "vqeExactEnergy": exact_energy,
            "vqeSampledEnergy": sampled_energy,
        },
        "audit": {
            "domainId": "biomedicine",
            "caseId": "electronic_structure",
            "datasetId": fixture.manifest["dataset_id"],
            "datasetVersion": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "hamiltonianHash": hamiltonian.stable_hash(),
            "analysisHash": analysis["analysisHash"],
            "ansatzHash": result.ansatz.stable_hash(),
            "measurementPlanHash": sampled.plan.plan_hash,
            "executionHash": result.stable_hash(),
            "seed": seed,
            "shotsPerGroup": shots,
            "hardwareExecution": False,
            "cloudExecution": False,
            "networkAccessed": False,
            "wallTimeSeconds": wall_time,
        },
    }
    payload["audit"]["resultHash"] = _hash_payload(payload)
    return payload


def scenario_payload() -> dict[str, Any]:
    return BIOMEDICINE_SCENARIO_SPECS["electronic_structure"].to_dict()
