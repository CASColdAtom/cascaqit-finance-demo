"""Audited active-space molecular analysis and CASCAQit VQE execution."""

from __future__ import annotations

import time
from typing import Any

from cascaqit.algorithms import VQE, OptimizerConfig, PauliHamiltonian
from cascaqit.algorithms.ansatz import transfer_vqe_parameters
from cascaqit.algorithms.measurement import (
    PauliMeasurementConfig,
    SampledObjectiveEvaluationIR,
    build_pauli_measurement_plan,
)
from cascaqit.simulators import NoiseChannel, NoiseModel, SimulationOptions

from cascaqit_biomedicine_demo.audit import (
    finalize_stable_audit,
    local_backend_context,
)
from cascaqit_biomedicine_demo.catalog import BIOMEDICINE_SCENARIO_SPECS
from cascaqit_biomedicine_demo.fixtures import (
    ELECTRONIC_DATASET_PATHS,
    H2_BOND_SCAN_DATASETS,
    LoadedFixture,
    load_electronic_fixture,
)
from cascaqit_biomedicine_demo.pauli_vqe import (
    build_pauli_hamiltonian,
    exact_diagonalization,
    hash_payload,
)

_PRESETS = {
    "h2_bond_scan": {
        "dataset": "h2_sto3g_0735",
        "noise_model": "ideal",
    },
    "lih_active_space": {
        "dataset": "lih_sto3g_1600",
        "noise_model": "ideal",
    },
    "h2o_minimal": {
        "dataset": "h2o_sto3g_equilibrium",
        "noise_model": "ideal",
    },
}


def electronic_values(preset: str, overrides: dict[str, Any]) -> dict[str, str]:
    try:
        values = dict(_PRESETS[preset])
    except KeyError as exc:
        raise ValueError(f"unknown electronic structure preset: {preset}") from exc
    values.update(overrides)
    dataset = str(values["dataset"])
    if dataset not in ELECTRONIC_DATASET_PATHS:
        raise ValueError(f"unknown electronic structure dataset: {dataset}")
    noise_model = str(values["noise_model"])
    if noise_model not in {"ideal", "readout_demo"}:
        raise ValueError("noise_model must be ideal or readout_demo")
    return {"dataset": dataset, "noise_model": noise_model}


def _hamiltonian(fixture: LoadedFixture) -> PauliHamiltonian:
    payload = {
        **fixture.pauli,
        "metadata": {
            "dataset_id": fixture.manifest["dataset_id"],
            "manifest_hash": fixture.manifest_hash,
        },
    }
    return build_pauli_hamiltonian(payload)


def _validated_reference(
    fixture: LoadedFixture, hamiltonian: PauliHamiltonian
) -> float:
    packaged = float(fixture.manifest["reference"]["exact_ground_energy_hartree"])
    diagonalized = float(exact_diagonalization(hamiltonian)["energy"])
    if abs(packaged - diagonalized) > 1e-10:
        raise ValueError("electronic fixture reference and Pauli Hamiltonian mismatch")
    return packaged


def _bond_scan_reference(selected_dataset: str) -> list[dict[str, Any]]:
    points = []
    for dataset in H2_BOND_SCAN_DATASETS:
        fixture = load_electronic_fixture(dataset)
        points.append(
            {
                "dataset": dataset,
                "bondLengthAngstrom": fixture.domain["bonds"][0][
                    "lengthAngstrom"
                ],
                "exactGroundEnergy": fixture.manifest["reference"][
                    "exact_ground_energy_hartree"
                ],
                "hartreeFockEnergy": fixture.manifest["reference"][
                    "hartree_fock_energy_hartree"
                ],
                "selected": dataset == selected_dataset,
            }
        )
    return points


def analyze_electronic_structure(
    preset: str = "h2_bond_scan", values: dict[str, Any] | None = None
) -> dict[str, Any]:
    resolved = electronic_values(preset, {} if values is None else values)
    fixture = load_electronic_fixture(resolved["dataset"])
    hamiltonian = _hamiltonian(fixture)
    reference = _validated_reference(fixture, hamiltonian)
    vqe = VQE(hamiltonian, layers=1)
    plan = build_pauli_measurement_plan(
        vqe.build_circuit(),
        hamiltonian,
        config=PauliMeasurementConfig(shots_per_group=64),
    )
    source = fixture.manifest["source"]
    generation = fixture.manifest["generation"]
    domain = {
        "kind": "electronic_structure",
        **fixture.domain,
        "preset": preset,
        "noiseModel": resolved["noise_model"],
        "reference": fixture.manifest["reference"],
        "bondScanReference": (
            _bond_scan_reference(resolved["dataset"])
            if fixture.domain["molecule"] == "H2"
            else []
        ),
        "limitations": fixture.manifest["limitations"],
    }
    input_hash = hash_payload(
        {
            "preset": preset,
            "values": resolved,
            "manifestHash": fixture.manifest_hash,
        }
    )
    analysis = {
        "kind": "biomedicine",
        "caseId": "electronic_structure",
        "executionFamily": "pauli_vqe",
        "implementationStatus": "available",
        "dataset": {
            "id": fixture.manifest["dataset_id"],
            "version": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "sourceKind": source["kind"],
            "sourceInputHash": source["input_sha256"],
            "generationScriptHash": generation["script_sha256"],
            "license": source["license"],
            "licenseCheckedAt": source["license_checked_at"],
            "allowedClaims": fixture.manifest["allowed_claims"],
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
                    "reason": (
                        "CASCAQit 已支持 PauliHamiltonian、VQE、QWC 分组测量"
                        "和可选读出噪声对照。"
                    ),
                },
                {
                    "mode": "hybrid",
                    "algorithm": "qaoa",
                    "availableAlgorithms": ["qaoa"],
                    "status": "unsuitable",
                    "reason": (
                        "电子 Hamiltonian 不是 QUBO，也没有可审计的 Analog core。"
                    ),
                },
                {
                    "mode": "analog",
                    "algorithm": "qaa",
                    "availableAlgorithms": ["qaa"],
                    "status": "unsuitable",
                    "reason": "非对角 Pauli 项不能由当前纯 Analog 目标完整表达。",
                },
            ],
        },
        "domain": domain,
        "domainInputHash": input_hash,
        "exactReferenceEnergy": reference,
    }
    analysis["analysisHash"] = hash_payload(analysis)
    return analysis


def _initial_parameters(
    fixture: LoadedFixture, hamiltonian: PauliHamiltonian, layers: int
) -> dict[str, float]:
    values = {
        str(key): float(value)
        for key, value in fixture.manifest["recommended_initial_parameters"][
            "values"
        ].items()
    }
    if layers == 1:
        return values
    previous = VQE(hamiltonian, layers=1)
    current = VQE(hamiltonian, layers=2)
    return transfer_vqe_parameters(
        previous.ansatz_spec(), current.ansatz_spec(), values
    )


def _measurement_groups(
    sampled: SampledObjectiveEvaluationIR,
) -> list[dict[str, Any]]:
    return [
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
    ]


def _readout_noise() -> tuple[NoiseModel, SimulationOptions]:
    noise = NoiseModel(
        "noise.biomedicine.electronic.readout-demo.v1",
        (NoiseChannel.readout(0.03, p10=0.04),),
        metadata={
            "purpose": "simulator sensitivity demonstration",
            "hardware_forecast": False,
        },
    )
    return noise, SimulationOptions(method="density_matrix", workers=1)


def run_electronic_structure(
    *,
    shots: int,
    seed: int,
    layers: int,
    parameter_budget: int,
    optimizer_starts: int,
    preset: str = "h2_bond_scan",
    values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if layers not in {1, 2}:
        raise ValueError("电子结构已校准 Ansatz 只支持一层或两层 VQE。")
    resolved = electronic_values(preset, {} if values is None else values)
    fixture = load_electronic_fixture(resolved["dataset"])
    hamiltonian = _hamiltonian(fixture)
    reference = _validated_reference(fixture, hamiltonian)
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
        initial_parameters=_initial_parameters(fixture, hamiltonian, layers),
        final_shots=shots,
    )
    best = result.evaluations[result.best_evaluation_index]
    measurement = PauliMeasurementConfig(shots_per_group=shots)
    sampled = vqe.evaluate_sampled(
        best.parameter_bind.values,
        measurement=measurement,
        seed=seed,
    )
    noisy_sampled: SampledObjectiveEvaluationIR | None = None
    noise: NoiseModel | None = None
    noise_options: SimulationOptions | None = None
    if resolved["noise_model"] == "readout_demo":
        noise, noise_options = _readout_noise()
        noisy_sampled = vqe.evaluate_sampled(
            best.parameter_bind.values,
            measurement=measurement,
            seed=seed,
            noise=noise,
            options=noise_options,
        )
    wall_time = time.perf_counter() - started
    exact_energy = float(best.energy)
    sampled_energy = float(sampled.energy)
    error = abs(exact_energy - reference)
    accuracy_applicable = resolved["dataset"] == "h2_sto3g_0735"
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
    analysis = analyze_electronic_structure(preset, resolved)
    result_dict = result.to_dict()
    backend_context = local_backend_context(
        execution_family="pauli_vqe",
        mode="digital",
        simulation_method=(
            "state_vector"
            if noise_options is None
            else "state_vector + density_matrix_readout"
        ),
    )
    payload = {
        "kind": "biomedicine",
        "analysis": analysis,
        "domain": {
            "kind": "ground_state_energy",
            "molecule": fixture.domain["molecule"],
            "datasetKey": resolved["dataset"],
            "exactOptimizedEnergy": exact_energy,
            "sampledConfirmationEnergy": sampled_energy,
            "sampledStandardError": float(sampled.energy_standard_error),
            "noisySampledConfirmationEnergy": (
                None if noisy_sampled is None else float(noisy_sampled.energy)
            ),
            "noisySampledStandardError": (
                None
                if noisy_sampled is None
                else float(noisy_sampled.energy_standard_error)
            ),
            "referenceEnergy": reference,
            "absoluteErrorHartree": error,
            "relativeError": error / max(abs(reference), 1e-12),
            "chemicalAccuracyThresholdHartree": (
                0.0016 if accuracy_applicable else None
            ),
            "withinChemicalAccuracy": (
                error <= 0.0016 if accuracy_applicable else None
            ),
            "accuracyClaim": (
                "h2_equilibrium_benchmark"
                if accuracy_applicable
                else "error_report_only"
            ),
            "estimatorNote": (
                "优化目标来自理想态矢量；理想和可选带噪结果来自同一参数点的"
                "QWC 有限 shots 测量。"
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
                "noiseModel": resolved["noise_model"],
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
                    "selected": index == result.best_evaluation_index,
                }
                for index, item in enumerate(result.evaluations)
            ],
            "measurement": {
                "planHash": sampled.plan.plan_hash,
                "groups": _measurement_groups(sampled),
                "noisyGroups": (
                    [] if noisy_sampled is None else _measurement_groups(noisy_sampled)
                ),
                "noiseModelHash": None if noise is None else noise.stable_hash(),
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
            "vqeNoisySampledEnergy": (
                None if noisy_sampled is None else float(noisy_sampled.energy)
            ),
        },
        "audit": {
            "domainId": "biomedicine",
            "caseId": "electronic_structure",
            "datasetId": fixture.manifest["dataset_id"],
            "datasetVersion": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "sourceInputHash": fixture.manifest["source"]["input_sha256"],
            "domainInputHash": analysis["domainInputHash"],
            "hamiltonianHash": hamiltonian.stable_hash(),
            "analysisHash": analysis["analysisHash"],
            "ansatzHash": result.ansatz.stable_hash(),
            "compileHash": result.ansatz.stable_hash(),
            "measurementPlanHash": sampled.plan.plan_hash,
            "backend": backend_context,
            "noiseModelHash": None if noise is None else noise.stable_hash(),
            "executionHash": result.stable_hash(),
            "seed": seed,
            "shotsPerGroup": shots,
            "warmStartSource": "fixture.recommended_initial_parameters",
            "hardwareExecution": False,
            "cloudExecution": False,
            "networkAccessed": False,
            "wallTimeSeconds": wall_time,
            "optimalityClaim": "not_claimed",
            "claimBoundary": "fixed_active_space_teaching_fixture",
        },
    }
    finalize_stable_audit(
        payload["audit"],
        configuration={
            "preset": preset,
            "values": resolved,
            "hamiltonianHash": hamiltonian.stable_hash(),
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
            "noiseModelHash": None if noise is None else noise.stable_hash(),
        },
        outcome={
            "domain": payload["domain"],
            "finalCounts": payload["quantum"]["counts"],
            "idealGroupCounts": [
                item["counts"] for item in payload["quantum"]["measurement"]["groups"]
            ],
            "noisyGroupCounts": [
                item["counts"]
                for item in payload["quantum"]["measurement"]["noisyGroups"]
            ],
            "parameterHistory": payload["quantum"]["parameterHistory"],
        },
    )
    payload["audit"]["resultHash"] = hash_payload(payload)
    return payload


def scenario_payload() -> dict[str, Any]:
    return BIOMEDICINE_SCENARIO_SPECS["electronic_structure"].to_dict()
