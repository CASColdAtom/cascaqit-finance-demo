"""QWC finite-shot measurement built on the CASCAQit 1.0.7 public API."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from cascaqit.algorithms import VQE, PauliHamiltonian
from cascaqit.digital import Circuit
from cascaqit.observables import PauliBasis
from cascaqit.simulators import LocalBackend, NoiseModel, SimulationOptions


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class PauliMeasurementConfig:
    """Uniform shot budget for each qubit-wise commuting group."""

    shots_per_group: int = 1024

    def __post_init__(self) -> None:
        if (
            not isinstance(self.shots_per_group, int)
            or isinstance(self.shots_per_group, bool)
            or self.shots_per_group < 2
        ):
            raise ValueError("shots_per_group must be an integer of at least two")


@dataclass(frozen=True)
class PauliMeasurementTerm:
    term_id: str
    coefficient: float
    observable: Any


@dataclass(frozen=True)
class PauliMeasurementGroup:
    group_index: int
    logical_order: tuple[str, ...]
    basis_by_target: MappingProxyType[str, PauliBasis]
    terms: tuple[PauliMeasurementTerm, ...]


@dataclass(frozen=True)
class PauliMeasurementPlan:
    logical_order: tuple[str, ...]
    groups: tuple[PauliMeasurementGroup, ...]
    constant: float
    shots_per_group: int
    plan_hash: str


@dataclass(frozen=True)
class ExecutionEvidence:
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


@dataclass(frozen=True)
class PauliMeasurementGroupResult:
    group: PauliMeasurementGroup
    shots: int
    counts: MappingProxyType[str, int]
    term_expectations: MappingProxyType[str, float]
    term_standard_errors: MappingProxyType[str, float]
    energy_mean: float
    energy_standard_error: float
    execution_evidence: ExecutionEvidence


@dataclass(frozen=True)
class SampledContribution:
    term_id: str
    expectation: float
    contribution: float


@dataclass(frozen=True)
class SampledObjectiveEvaluation:
    plan: PauliMeasurementPlan
    group_results: tuple[PauliMeasurementGroupResult, ...]
    contributions: tuple[SampledContribution, ...]
    energy: float
    energy_standard_error: float
    total_shots: int


def _observable_basis(
    observable: Any,
    logical_order: tuple[str, ...],
) -> dict[str, PauliBasis]:
    basis = {target: PauliBasis.I for target in logical_order}
    for factor in observable.terms:
        if factor.target not in basis:
            raise ValueError("observable target is outside the Hamiltonian order")
        if factor.basis is not PauliBasis.I:
            basis[factor.target] = factor.basis
    return basis


def _qwc_compatible(
    left: dict[str, PauliBasis],
    right: dict[str, PauliBasis],
) -> bool:
    return all(
        left[target] is PauliBasis.I
        or right[target] is PauliBasis.I
        or left[target] is right[target]
        for target in left
    )


def build_pauli_measurement_plan(
    circuit: Circuit,
    hamiltonian: PauliHamiltonian,
    *,
    config: PauliMeasurementConfig | None = None,
) -> PauliMeasurementPlan:
    """Partition a Pauli Hamiltonian into deterministic QWC groups."""

    effective = config or PauliMeasurementConfig()
    logical_order = tuple(circuit.qubits)
    if logical_order != hamiltonian.logical_order:
        raise ValueError("circuit qubits must match the Hamiltonian logical order")
    if circuit.measurements:
        raise ValueError("source circuit must not contain measurements")

    grouped_terms: list[list[PauliMeasurementTerm]] = []
    grouped_bases: list[dict[str, PauliBasis]] = []
    for term in hamiltonian.terms:
        planned = PauliMeasurementTerm(
            term_id=term.term_id,
            coefficient=float(term.coefficient),
            observable=term.observable,
        )
        term_basis = _observable_basis(term.observable, logical_order)
        destination = next(
            (
                index
                for index, group_basis in enumerate(grouped_bases)
                if _qwc_compatible(group_basis, term_basis)
            ),
            None,
        )
        if destination is None:
            grouped_terms.append([planned])
            grouped_bases.append(dict(term_basis))
            continue
        grouped_terms[destination].append(planned)
        for target, basis in term_basis.items():
            if grouped_bases[destination][target] is PauliBasis.I:
                grouped_bases[destination][target] = basis

    groups = tuple(
        PauliMeasurementGroup(
            group_index=index,
            logical_order=logical_order,
            basis_by_target=MappingProxyType(dict(basis)),
            terms=tuple(terms),
        )
        for index, (basis, terms) in enumerate(zip(grouped_bases, grouped_terms))
    )
    identity = {
        "sourceCircuitHash": circuit.structural_hash(),
        "hamiltonianHash": hamiltonian.stable_hash(),
        "shotsPerGroup": effective.shots_per_group,
        "groups": [
            {
                "index": group.group_index,
                "basis": {
                    target: basis.value
                    for target, basis in group.basis_by_target.items()
                },
                "terms": [term.term_id for term in group.terms],
            }
            for group in groups
        ],
    }
    return PauliMeasurementPlan(
        logical_order=logical_order,
        groups=groups,
        constant=float(hamiltonian.constant),
        shots_per_group=effective.shots_per_group,
        plan_hash=_stable_hash(identity),
    )


def _measurement_circuit(
    source: Circuit,
    group: PauliMeasurementGroup,
    *,
    program_id: str,
) -> Circuit:
    measured = Circuit(source.qubits, program_id=program_id).compose(source)
    for target in group.logical_order:
        basis = group.basis_by_target[target]
        if basis is PauliBasis.X:
            measured.h(target)
        elif basis is PauliBasis.Y:
            measured.sdg(target).h(target)
    measured.measure(group.logical_order, key=f"measurement.group.{group.group_index}")
    return measured


def _group_seed(root_seed: int, group_index: int) -> int:
    return int.from_bytes(
        hashlib.sha256(
            json.dumps(
                {
                    "namespace": "cascaqit-industry.qwc.v1",
                    "rootSeed": root_seed,
                    "groupIndex": group_index,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).digest()[:8],
        "big",
    )


def _group_statistics(
    group: PauliMeasurementGroup,
    counts: dict[str, int],
    *,
    shots: int,
) -> tuple[dict[str, float], dict[str, float], float, float]:
    width = len(group.logical_order)
    normalized = {str(bits).zfill(width): int(count) for bits, count in counts.items()}
    if sum(normalized.values()) != shots:
        raise ValueError("measurement counts must sum to shots")
    index_by_target = {
        target: index for index, target in enumerate(group.logical_order)
    }
    sums = {term.term_id: 0.0 for term in group.terms}
    group_sum = 0.0
    group_square_sum = 0.0
    for bitstring, count in normalized.items():
        group_value = 0.0
        for term in group.terms:
            value = 1
            for factor in term.observable.terms:
                if factor.basis is not PauliBasis.I:
                    value *= (
                        1
                        if bitstring[index_by_target[factor.target]] == "0"
                        else -1
                    )
            sums[term.term_id] += value * count
            group_value += term.coefficient * value
        group_sum += group_value * count
        group_square_sum += group_value * group_value * count
    expectations = {term_id: value / shots for term_id, value in sums.items()}
    term_errors = {
        term_id: math.sqrt(max(0.0, 1.0 - value * value) / (shots - 1))
        for term_id, value in expectations.items()
    }
    energy_mean = group_sum / shots
    centered_sum = max(0.0, group_square_sum - shots * energy_mean * energy_mean)
    energy_error = math.sqrt(centered_sum / (shots - 1) / shots)
    return expectations, term_errors, energy_mean, energy_error


def _execution_evidence(
    *,
    result: Any,
    backend_id: str,
    backend_job_id: str,
    seed: int,
    noise: NoiseModel | None,
    options: SimulationOptions | None,
) -> ExecutionEvidence:
    metadata = dict(result.to_dict().get("metadata", {}))
    return ExecutionEvidence(
        {
            "backend_id": backend_id,
            "backend_job_id": backend_job_id,
            "result_id": result.result_id,
            "result_hash": result.stable_hash(),
            "program_hash": result.program_hash,
            "requested_seed": seed,
            "noise_model": None if noise is None else noise.to_dict(),
            "requested_options": None if options is None else options.to_dict(),
            "noise_report": metadata.get(
                "noise_report",
                {
                    "truthfulness": "ideal_state_evolution",
                    "applied_channel_types": [],
                },
            ),
            "simulation_plan": metadata.get("simulation_plan"),
            "simulation_execution_config": metadata.get(
                "simulation_execution_config"
            ),
            "simulation_resource_usage": metadata.get(
                "simulation_resource_usage"
            ),
            "network_accessed": metadata.get("network_accessed", False),
        }
    )


def evaluate_sampled_vqe(
    vqe: VQE,
    parameters: dict[str, float] | MappingProxyType[str, float],
    *,
    measurement: PauliMeasurementConfig,
    seed: int,
    noise: NoiseModel | None = None,
    options: SimulationOptions | None = None,
) -> SampledObjectiveEvaluation:
    """Sample every QWC group using CASCAQit 1.0.7 backend jobs."""

    source = vqe.build_circuit()
    plan = build_pauli_measurement_plan(source, vqe.hamiltonian, config=measurement)
    bound = source.bind(dict(parameters))
    backend = LocalBackend(seed=seed)
    results: list[PauliMeasurementGroupResult] = []
    expectations_by_term: dict[str, float] = {}
    for group in plan.groups:
        group_seed = _group_seed(seed, group.group_index)
        circuit = _measurement_circuit(
            bound,
            group,
            program_id=(
                f"program.{vqe.algorithm_id}.sampled.group.{group.group_index:03d}"
            ),
        )
        job = backend.run(
            circuit,
            shots=measurement.shots_per_group,
            seed=group_seed,
            job_id=f"{vqe.algorithm_id}.sampled.group.{group.group_index:03d}",
            noise=noise,
            options=options,
        )
        result = job.result()
        status = job.status()
        counts = dict(result.counts)
        statistics = _group_statistics(group, counts, shots=result.shots)
        expectations_by_term.update(statistics[0])
        results.append(
            PauliMeasurementGroupResult(
                group=group,
                shots=result.shots,
                counts=MappingProxyType(dict(sorted(counts.items()))),
                term_expectations=MappingProxyType(statistics[0]),
                term_standard_errors=MappingProxyType(statistics[1]),
                energy_mean=statistics[2],
                energy_standard_error=statistics[3],
                execution_evidence=_execution_evidence(
                    result=result,
                    backend_id=status.backend_id,
                    backend_job_id=status.job_id,
                    seed=group_seed,
                    noise=noise,
                    options=options,
                ),
            )
        )
    group_results = tuple(results)
    contributions = tuple(
        SampledContribution(
            term_id=term.term_id,
            expectation=expectations_by_term[term.term_id],
            contribution=(
                float(term.coefficient) * expectations_by_term[term.term_id]
            ),
        )
        for term in vqe.hamiltonian.terms
    )
    return SampledObjectiveEvaluation(
        plan=plan,
        group_results=group_results,
        contributions=contributions,
        energy=(
            plan.constant + sum(item.contribution for item in contributions)
        ),
        energy_standard_error=math.sqrt(
            sum(item.energy_standard_error**2 for item in group_results)
        ),
        total_shots=sum(item.shots for item in group_results),
    )
