"""Pure Analog AHS dynamics for a versioned four-site effective lattice."""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cascaqit
import numpy as np
from cascaqit.analog import AHSProgram, AtomRegister, SitePattern, Waveform
from cascaqit.simulators import AnalogStateVectorKernel, SimulationState
from cascaqit.targets import MockNeutralAtomTarget
from cascaqit.validation import validate_program
from scipy.integrate import solve_ivp

from cascaqit_industry_demo.audit import (
    finalize_stable_audit,
    hash_payload,
    local_backend_context,
)

DATA_ROOT = (
    Path(__file__).resolve().parent
    / "data"
    / "rydberg_dynamics"
    / "effective_lattice_quench"
    / "1"
)
PRESETS = {"perfect_lattice", "single_vacancy", "multi_defect_impurity"}
ATOM_ORDER = ("q0", "q1", "q2", "q3")
SDK_VERSION_PREFIX = "1.0.5a"


@dataclass(frozen=True)
class RydbergDynamicsFixture:
    manifest: dict[str, Any]
    domain: dict[str, Any]
    manifest_hash: str


@dataclass(frozen=True)
class RydbergDynamicsInput:
    preset: str
    duration_us: float
    rabi_amplitude: float
    detuning_end: float
    sample_count: int


def _read_object(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"Rydberg dynamics fixture must be an object: {path.name}")
    return value, raw


def load_rydberg_dynamics_fixture() -> RydbergDynamicsFixture:
    manifest, manifest_raw = _read_object(DATA_ROOT / "manifest.json")
    domain, domain_raw = _read_object(DATA_ROOT / "domain.json")
    for key in ("dataset_id", "version", "source", "generation", "units"):
        if not manifest.get(key):
            raise ValueError(f"Rydberg dynamics manifest is missing {key}")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1:
        raise ValueError("Rydberg dynamics manifest must declare domain.json")
    artifact = artifacts[0]
    if artifact.get("path") != "domain.json":
        raise ValueError("Rydberg dynamics artifact path must be domain.json")
    if hashlib.sha256(domain_raw).hexdigest() != artifact.get("sha256"):
        raise ValueError("Rydberg dynamics domain checksum mismatch")
    declared_presets = set(manifest.get("presets", ()))
    if declared_presets != PRESETS or set(domain.get("presets", {})) != PRESETS:
        raise ValueError("Rydberg dynamics presets are inconsistent")
    for preset, model in domain["presets"].items():
        if len(model.get("activeWindow", ())) != 4:
            raise ValueError(f"{preset} must retain exactly four active sites")
        if len(model.get("rydbergPositions", ())) != 4:
            raise ValueError(f"{preset} must declare four Rydberg positions")
        if len(model.get("initialBitstring", "")) != 4:
            raise ValueError(f"{preset} must declare a four-bit initial state")
        if len(model.get("localDetuningWeights", ())) != 4:
            raise ValueError(f"{preset} must declare four local-detuning weights")
    return RydbergDynamicsFixture(
        manifest=manifest,
        domain=domain,
        manifest_hash=hashlib.sha256(manifest_raw).hexdigest(),
    )


def rydberg_dynamics_values(preset: str, overrides: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {
        "duration_us": 1.2,
        "rabi_amplitude": 2.4,
        "detuning_end": 2.0,
        "sample_count": 9,
    }
    values.update(overrides)
    case_input = _case_input(preset, values)
    return {
        "duration_us": case_input.duration_us,
        "rabi_amplitude": case_input.rabi_amplitude,
        "detuning_end": case_input.detuning_end,
        "sample_count": case_input.sample_count,
    }


def _case_input(preset: str, values: dict[str, Any]) -> RydbergDynamicsInput:
    if preset not in PRESETS:
        raise ValueError(f"unknown Rydberg dynamics preset: {preset}")
    duration = _finite_number(values.get("duration_us", 1.2), "duration_us")
    rabi = _finite_number(values.get("rabi_amplitude", 2.4), "rabi_amplitude")
    detuning = _finite_number(values.get("detuning_end", 2.0), "detuning_end")
    raw_samples = values.get("sample_count", 9)
    if (
        isinstance(raw_samples, bool)
        or not isinstance(raw_samples, (int, float))
        or not float(raw_samples).is_integer()
    ):
        raise ValueError("sample_count must be an odd integer from 5 to 21")
    sample_count = int(raw_samples)
    if not 0.2 <= duration <= 2.0:
        raise ValueError("duration_us must be between 0.2 and 2.0")
    if not 0.5 <= rabi <= 4.0:
        raise ValueError("rabi_amplitude must be between 0.5 and 4.0")
    if not -4.0 <= detuning <= 4.0:
        raise ValueError("detuning_end must be between -4.0 and 4.0")
    if not 5 <= sample_count <= 21 or sample_count % 2 == 0:
        raise ValueError("sample_count must be an odd integer from 5 to 21")
    return RydbergDynamicsInput(
        preset=preset,
        duration_us=duration,
        rabi_amplitude=rabi,
        detuning_end=detuning,
        sample_count=sample_count,
    )


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _require_sdk_contract() -> dict[str, Any]:
    version = str(getattr(cascaqit, "__version__", "unknown"))
    module_path = str(Path(cascaqit.__file__).resolve())
    if not version.startswith(SDK_VERSION_PREFIX):
        raise ValueError(
            "Rydberg dynamics requires CASCAQit >=1.0.5a0,<1.0.6; "
            f"loaded {version} from {module_path}"
        )
    return {
        "name": "CASCAQit",
        "version": version,
        "validatedRange": ">=1.0.5a0,<1.0.6",
        "validatedRelease": True,
        "modulePath": module_path,
        "capabilities": [
            "AHSProgram",
            "AtomRegister",
            "Waveform",
            "SimulationState",
            "AnalogStateVectorKernel",
            "target_validation",
        ],
    }


def _sample_times(case_input: RydbergDynamicsInput) -> list[float]:
    return [
        round(
            case_input.duration_us * index / (case_input.sample_count - 1),
            9,
        )
        for index in range(case_input.sample_count)
    ]


def _model(
    fixture: RydbergDynamicsFixture, case_input: RydbergDynamicsInput
) -> dict[str, Any]:
    return fixture.domain["presets"][case_input.preset]


def _target(model: dict[str, Any]):
    if float(model["localDetuningAmplitude"]) != 0.0:
        return MockNeutralAtomTarget.local_ahs_v0_1()
    return MockNeutralAtomTarget.v0_1()


def _rabi_value(case_input: RydbergDynamicsInput, time_us: float) -> float:
    fraction = time_us / case_input.duration_us
    peak = case_input.rabi_amplitude
    if fraction <= 0.25:
        return peak * fraction / 0.25
    if fraction <= 0.75:
        return peak
    return peak * max(0.0, (1.0 - fraction) / 0.25)


def _detuning_value(
    model: dict[str, Any], case_input: RydbergDynamicsInput, time_us: float
) -> float:
    start = float(model["detuningStart"])
    fraction = time_us / case_input.duration_us
    return start + (case_input.detuning_end - start) * fraction


def _clipped_rabi(
    case_input: RydbergDynamicsInput, duration_us: float
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    full_times = tuple(
        case_input.duration_us * fraction for fraction in (0.0, 0.25, 0.75, 1.0)
    )
    times = [value for value in full_times if value < duration_us - 1e-12]
    times.append(duration_us)
    values = [_rabi_value(case_input, value) for value in times]
    return tuple(times), tuple(values)


def _build_program(
    fixture: RydbergDynamicsFixture,
    case_input: RydbergDynamicsInput,
    duration_us: float,
) -> tuple[Any, Any]:
    if duration_us <= 0.0:
        raise ValueError("AHS program duration must be positive")
    model = _model(fixture, case_input)
    register = AtomRegister.custom(
        tuple(
            tuple(float(value) for value in pair)
            for pair in model["rydbergPositions"]
        ),
        site_ids=ATOM_ORDER,
        atom_ids=ATOM_ORDER,
    )
    rabi_times, rabi_values = _clipped_rabi(case_input, duration_us)
    program = AHSProgram(
        register,
        program_id=f"materials-{case_input.preset}-{duration_us:.9f}",
    )
    program.drive(
        rabi=Waveform.piecewise_linear(
            times=rabi_times,
            values=rabi_values,
            waveform_id="global-rabi",
        ),
        detuning=Waveform.linear(
            float(model["detuningStart"]),
            _detuning_value(model, case_input, duration_us),
            duration=duration_us,
            waveform_id="global-detuning",
        ),
        phase=0.0,
    )
    local_amplitude = float(model["localDetuningAmplitude"])
    if local_amplitude != 0.0:
        program.local_detuning(
            waveform=Waveform.constant(
                local_amplitude,
                duration=duration_us,
                waveform_id="local-impurity-detuning",
            ),
            pattern=SitePattern(
                site_ids=ATOM_ORDER,
                weights=tuple(float(value) for value in model["localDetuningWeights"]),
            ),
        )
    program.measure()
    return program.to_ir(), _target(model)


def _validation_payload(program_ir: Any, target: Any, shots: int) -> dict[str, Any]:
    diagnostics = validate_program(program_ir, target, shots=shots)
    errors = [item for item in diagnostics if item.severity == "error"]
    if errors:
        codes = ", ".join(item.code for item in errors)
        raise ValueError(f"AHS target validation failed: {codes}")
    return {
        "status": "verified",
        "diagnosticCodes": [item.code for item in diagnostics],
        "targetId": target.target_id,
        "targetSnapshotHash": target.to_snapshot(
            source="local_simulator"
        ).target_snapshot_hash,
    }


def _interactions(model: dict[str, Any], target: Any) -> list[dict[str, Any]]:
    positions = [
        tuple(float(value) for value in pair)
        for pair in model["rydbergPositions"]
    ]
    radius = float(target.metadata.get("blockade_radius", 0.0))
    output: list[dict[str, Any]] = []
    for left in range(len(positions)):
        for right in range(left + 1, len(positions)):
            distance = math.dist(positions[left], positions[right])
            if 0.0 < distance < radius:
                output.append(
                    {
                        "left": ATOM_ORDER[left],
                        "right": ATOM_ORDER[right],
                        "distance": distance,
                        "strength": (radius / distance) ** 6 * math.pi,
                        "source": "target_blockade_radius",
                    }
                )
    return output


def _material_nodes(
    fixture: RydbergDynamicsFixture, model: dict[str, Any]
) -> list[dict[str, Any]]:
    vacancies = set(model["vacancies"])
    impurities = set(model["impuritySites"])
    active = set(model["activeWindow"])
    output = []
    for item in fixture.domain["materialLattice"]["nodes"]:
        node = dict(item)
        if node["id"] in vacancies:
            node["role"] = "vacancy"
        elif node["id"] in impurities:
            node["role"] = "impurity"
        else:
            node["role"] = "lattice_site"
        node["inActiveWindow"] = node["id"] in active
        output.append(node)
    return output


def _initial_state(model: dict[str, Any]) -> SimulationState:
    bitstring = str(model["initialBitstring"])
    amplitudes = [0.0j] * (2 ** len(ATOM_ORDER))
    amplitudes[int(bitstring, 2)] = 1.0 + 0.0j
    return SimulationState.from_amplitudes(
        amplitudes,
        logical_order=ATOM_ORDER,
        state_id=f"state.materials.{bitstring}.initial",
        time_unit="us",
    )


def _analysis_payload(
    fixture: RydbergDynamicsFixture,
    case_input: RydbergDynamicsInput,
) -> dict[str, Any]:
    sdk = _require_sdk_contract()
    model = _model(fixture, case_input)
    program_ir, target = _build_program(fixture, case_input, case_input.duration_us)
    validation = _validation_payload(program_ir, target, shots=128)
    interactions = _interactions(model, target)
    sample_times = _sample_times(case_input)
    initial_state = _initial_state(model)
    program_hash = program_ir.stable_hash()
    initial_state_hash = initial_state.stable_hash()
    pulse_schedule = {
        "duration": case_input.duration_us,
        "timeUnit": "us",
        "rabi": {
            "times": [
                case_input.duration_us * fraction
                for fraction in (0.0, 0.25, 0.75, 1.0)
            ],
            "values": [0.0, case_input.rabi_amplitude, case_input.rabi_amplitude, 0.0],
            "unit": "rad/us",
        },
        "detuning": {
            "times": [0.0, case_input.duration_us],
            "values": [float(model["detuningStart"]), case_input.detuning_end],
            "unit": "rad/us",
        },
        "localDetuning": {
            "amplitude": float(model["localDetuningAmplitude"]),
            "weights": [float(value) for value in model["localDetuningWeights"]],
            "unit": "rad/us",
        },
        "phase": 0.0,
    }
    pulse_hash = hash_payload(pulse_schedule)
    layout = [
        {
            "id": atom_id,
            "sourceSite": source_site,
            "x": float(position[0]),
            "y": float(position[1]),
            "active": True,
        }
        for atom_id, source_site, position in zip(
            ATOM_ORDER, model["activeWindow"], model["rydbergPositions"]
        )
    ]
    terms = [
        {"id": "global_rabi", "kind": "drive", "source": "declared_pulse"},
        {"id": "global_detuning", "kind": "detuning", "source": "declared_pulse"},
        *[
            {
                "id": f"interaction:{item['left']}:{item['right']}",
                "kind": "rydberg_interaction",
                "source": "target_blockade_radius",
            }
            for item in interactions
        ],
    ]
    if float(model["localDetuningAmplitude"]) != 0.0:
        terms.append(
            {
                "id": "local_impurity_detuning",
                "kind": "local_detuning",
                "source": "declared_effective_impurity",
            }
        )
    definition = {
        "schema": "materials.analog-experiment-definition.v1",
        "experimentKind": "analog_ahs",
        "programHash": program_hash,
        "targetSnapshotHash": validation["targetSnapshotHash"],
        "initialStateHash": initial_state_hash,
        "pulseScheduleHash": pulse_hash,
        "sampleTimes": sample_times,
        "observableDefinitions": [
            "occupation",
            "mean_excitation",
            "magnetization_z",
            "correlation_z",
        ],
    }
    problem_hash = hash_payload(definition)
    pure_analog = {
        "status": "verified",
        "digitalGateCount": 0,
        "digitalResidualCount": 0,
        "hybridBlockCount": 0,
        "declaredHamiltonianTermCount": len(terms),
        "mappedHamiltonianTermCount": len(terms),
        "missingTermIds": [],
        "unexpectedTermIds": [],
        "interactionSource": "target_blockade_radius",
    }
    core = {
        "kind": "materials",
        "caseId": "rydberg_dynamics",
        "executionFamily": "analog_ahs",
        "implementationStatus": "available",
        "dataset": {
            "id": fixture.manifest["dataset_id"],
            "version": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "sourceKind": fixture.manifest["source"]["kind"],
            "license": fixture.manifest["license"]["name"],
            "limitations": list(fixture.manifest["limitations"]),
        },
        "problem": {
            "id": f"materials.ahs.{case_input.preset}",
            "type": "analog_experiment_definition",
            "hash": problem_hash,
            "variables": list(ATOM_ORDER),
            "terms": terms,
        },
        "resource": {
            "analogSites": 4,
            "hilbertDimension": 16,
            "sampleCount": case_input.sample_count,
            "prefixProgramCount": case_input.sample_count - 1,
            "termCount": len(terms),
            "measurementGroups": 1,
            "parameterCount": 0,
        },
        "decision": {
            "recommendedMode": "analog",
            "reason": (
                "完整有效 Hamiltonian 可由原生 AHS 驱动、失谐和 "
                "Rydberg 相互作用表达。"
            ),
            "modes": [
                {
                    "mode": "digital",
                    "algorithm": "qaoa",
                    "availableAlgorithms": ["qaoa"],
                    "status": "unsuitable",
                    "reason": "原生 AHS 时间演化不转换为数字线路。",
                },
                {
                    "mode": "hybrid",
                    "algorithm": "qaoa",
                    "availableAlgorithms": ["qaoa"],
                    "status": "unsuitable",
                    "reason": "完整模型没有 Digital residual 或 Hybrid block。",
                },
                {
                    "mode": "analog",
                    "algorithm": "qaa",
                    "availableAlgorithms": ["qaa"],
                    "status": "recommended",
                    "reason": "使用 CASCAQit AHS 程序执行有效多体量子淬火。",
                },
            ],
        },
        "analogProgram": definition,
        "sdk": sdk,
        "domain": {
            "kind": "rydberg_dynamics",
            "modelLevel": fixture.domain["modelLevel"],
            "preset": case_input.preset,
            "nodes": _material_nodes(fixture, model),
            "effectiveWindow": [
                {"atomId": atom_id, "sourceSite": source_site}
                for atom_id, source_site in zip(ATOM_ORDER, model["activeWindow"])
            ],
            "coordinateIdentities": fixture.domain["coordinateIdentities"],
            "rydbergLayout": layout,
            "rydbergLayoutHash": hash_payload(layout),
            "interactions": interactions,
            "sampleTimes": sample_times,
            "pulse": {
                "duration": case_input.duration_us,
                "rabiPeak": case_input.rabi_amplitude,
                "detuningStart": float(model["detuningStart"]),
                "detuningEnd": case_input.detuning_end,
                "rabiTimes": pulse_schedule["rabi"]["times"],
                "rabiValues": pulse_schedule["rabi"]["values"],
            },
            "pulseSchedule": pulse_schedule,
            "initialState": {
                "bitstring": model["initialBitstring"],
                "basis": "ground_rydberg_occupation",
                "atomOrder": list(ATOM_ORDER),
                "stateHash": initial_state_hash,
                "source": "declared_fixture",
            },
            "targetValidation": validation,
            "pureAnalogEvidence": pure_analog,
            "limitations": [
                "这是材料问题派生的四位点有效多体模型，不是材料全电子或全原子动力学。",
                "每个时刻从同一声明初态执行真实截断 AHS 程序，不使用插值生成量子轨迹。",
                "本地 AHS 核心限制为 4 个原子；完整材料晶格仅用于领域上下文。",
                "Rydberg 编译坐标不等于材料原子坐标。",
                "执行边界为 LOCAL SIMULATION / NO HARDWARE EXECUTION。",
            ],
        },
    }
    core["analysisHash"] = hash_payload(
        {
            "dataset": core["dataset"],
            "problem": core["problem"],
            "resource": core["resource"],
            "analogProgram": core["analogProgram"],
            "domain": core["domain"],
            "sdk": core["sdk"],
        }
    )
    return core


def analyze_rydberg_dynamics(preset: str, values: dict[str, Any]) -> dict[str, Any]:
    resolved = rydberg_dynamics_values(preset, values)
    return _analysis_payload(
        load_rydberg_dynamics_fixture(), _case_input(preset, resolved)
    )


def _expectations(probabilities: dict[str, float]) -> dict[str, Any]:
    occupation = {atom_id: 0.0 for atom_id in ATOM_ORDER}
    correlations: dict[str, float] = {}
    for bits, probability in probabilities.items():
        for index, bit in enumerate(bits):
            if bit == "1":
                occupation[ATOM_ORDER[index]] += probability
    for left in range(len(ATOM_ORDER)):
        for right in range(left + 1, len(ATOM_ORDER)):
            value = 0.0
            for bits, probability in probabilities.items():
                left_z = 1.0 if bits[left] == "1" else -1.0
                right_z = 1.0 if bits[right] == "1" else -1.0
                value += left_z * right_z * probability
            correlations[f"{ATOM_ORDER[left]},{ATOM_ORDER[right]}"] = value
    mean_excitation = sum(occupation.values()) / len(ATOM_ORDER)
    return {
        "occupation": occupation,
        "meanExcitation": mean_excitation,
        "magnetizationZ": 2.0 * mean_excitation - 1.0,
        "correlations": correlations,
    }


def _sample_counts(
    probabilities: dict[str, float], shots: int, seed: int
) -> dict[str, int]:
    states = sorted(probabilities)
    weights = [max(0.0, probabilities[state]) for state in states]
    rng = random.Random(seed)
    samples = rng.choices(states, weights=weights, k=shots)
    return dict(sorted(Counter(samples).items()))


def _time_point(
    *,
    requested_time: float,
    state: SimulationState,
    program_hash: str | None,
    counts: dict[str, int],
    diagnostic_codes: list[str],
    solver: str,
) -> dict[str, Any]:
    probabilities = state.probabilities()
    observables = _expectations(probabilities)
    payload = {
        "requestedTime": requested_time,
        "actualTime": state.logical_time,
        "timeUnit": "us",
        "programHash": program_hash,
        "stateHash": state.stable_hash(),
        "probabilityNorm": sum(probabilities.values()),
        "counts": [
            {"state": bitstring, "count": count}
            for bitstring, count in sorted(
                counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "diagnosticCodes": diagnostic_codes,
        "solver": solver,
        **observables,
    }
    payload["resultHash"] = hash_payload(payload)
    return payload


def _classical_hamiltonian(
    fixture: RydbergDynamicsFixture,
    case_input: RydbergDynamicsInput,
    time_us: float,
) -> np.ndarray:
    model = _model(fixture, case_input)
    target = _target(model)
    interactions = _interactions(model, target)
    dimension = 2 ** len(ATOM_ORDER)
    matrix = np.zeros((dimension, dimension), dtype=np.complex128)
    rabi = _rabi_value(case_input, time_us)
    detuning = _detuning_value(model, case_input, time_us)
    local_amplitude = float(model["localDetuningAmplitude"])
    local_weights = [float(value) for value in model["localDetuningWeights"]]
    pair_indices = [
        (
            ATOM_ORDER.index(item["left"]),
            ATOM_ORDER.index(item["right"]),
            item["strength"],
        )
        for item in interactions
    ]
    for basis_index in range(dimension):
        bits = format(basis_index, f"0{len(ATOM_ORDER)}b")
        diagonal = -detuning * bits.count("1")
        diagonal -= local_amplitude * sum(
            local_weights[index] for index, bit in enumerate(bits) if bit == "1"
        )
        for left, right, strength in pair_indices:
            if bits[left] == "1" and bits[right] == "1":
                diagonal += strength
        matrix[basis_index, basis_index] = diagonal
        for atom_index in range(len(ATOM_ORDER)):
            flipped = basis_index ^ (1 << (len(ATOM_ORDER) - atom_index - 1))
            matrix[flipped, basis_index] += rabi / 2.0
    return matrix


def _classic_reference(
    fixture: RydbergDynamicsFixture,
    case_input: RydbergDynamicsInput,
    initial_state: SimulationState,
    sample_times: list[float],
) -> tuple[dict[str, Any], list[np.ndarray]]:
    initial = np.asarray(initial_state.amplitudes, dtype=np.complex128)

    def derivative(time_us: float, state: np.ndarray) -> np.ndarray:
        return -1.0j * _classical_hamiltonian(fixture, case_input, time_us) @ state

    solution = solve_ivp(
        derivative,
        (0.0, case_input.duration_us),
        initial,
        method="DOP853",
        t_eval=np.asarray(sample_times),
        rtol=1e-10,
        atol=1e-12,
    )
    if not solution.success or solution.y.shape[1] != len(sample_times):
        raise ValueError(f"classic reference integration failed: {solution.message}")
    vectors = [solution.y[:, index] for index in range(solution.y.shape[1])]
    points = []
    for requested_time, vector in zip(sample_times, vectors):
        probabilities = {
            format(index, f"0{len(ATOM_ORDER)}b"): float(abs(value) ** 2)
            for index, value in enumerate(vector)
        }
        point = {
            "requestedTime": requested_time,
            "actualTime": requested_time,
            "timeUnit": "us",
            "probabilityNorm": sum(probabilities.values()),
            **_expectations(probabilities),
        }
        point["resultHash"] = hash_payload(point)
        points.append(point)
    payload = {
        "source": "independent_scipy_dop853",
        "method": "DOP853",
        "rtol": 1e-10,
        "atol": 1e-12,
        "timeSeries": points,
        "resultHash": hash_payload(points),
    }
    return payload, vectors


def _comparison_metrics(
    analog_points: list[dict[str, Any]],
    classic_points: list[dict[str, Any]],
    analog_vectors: list[np.ndarray],
    classic_vectors: list[np.ndarray],
) -> dict[str, Any]:
    occupation_errors = []
    correlation_errors = []
    for analog, classic in zip(analog_points, classic_points):
        occupation_errors.extend(
            abs(analog["occupation"][atom] - classic["occupation"][atom])
            for atom in ATOM_ORDER
        )
        correlation_errors.extend(
            abs(analog["correlations"][pair] - classic["correlations"][pair])
            for pair in analog["correlations"]
        )
    fidelity = abs(np.vdot(classic_vectors[-1], analog_vectors[-1])) ** 2
    return {
        "maxOccupationAbsoluteError": max(occupation_errors, default=0.0),
        "maxCorrelationAbsoluteError": max(correlation_errors, default=0.0),
        "terminalStateFidelity": float(fidelity),
        "maxAnalogNormError": max(
            abs(point["probabilityNorm"] - 1.0) for point in analog_points
        ),
        "maxClassicNormError": max(
            abs(point["probabilityNorm"] - 1.0) for point in classic_points
        ),
    }


def run_rydberg_dynamics(
    *,
    preset: str,
    values: dict[str, Any],
    shots: int,
    seed: int,
    time_steps: int = 320,
) -> dict[str, Any]:
    started = time.perf_counter()
    if isinstance(shots, bool) or not isinstance(shots, int) or not 1 <= shots <= 4096:
        raise ValueError("shots must be an integer from 1 to 4096")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if time_steps < 80:
        raise ValueError("time_steps must be at least 80")
    resolved = rydberg_dynamics_values(preset, values)
    case_input = _case_input(preset, resolved)
    fixture = load_rydberg_dynamics_fixture()
    analysis = _analysis_payload(fixture, case_input)
    model = _model(fixture, case_input)
    target = _target(model)
    initial_state = _initial_state(model)
    sample_times = _sample_times(case_input)
    analog_points: list[dict[str, Any]] = []
    analog_vectors: list[np.ndarray] = []
    program_hashes: list[str] = []
    for index, requested_time in enumerate(sample_times):
        if requested_time == 0.0:
            state = initial_state
            program_hash = None
            diagnostics = ["DECLARED_INITIAL_STATE"]
            solver = "declared_initial_state"
        else:
            program_ir, point_target = _build_program(
                fixture, case_input, requested_time
            )
            validation = _validation_payload(program_ir, point_target, shots)
            program_hash = program_ir.stable_hash()
            program_hashes.append(program_hash)
            steps = max(80, round(time_steps * requested_time / case_input.duration_us))
            state = AnalogStateVectorKernel(
                blockade_radius=float(target.metadata.get("blockade_radius", 0.0)),
                steps=steps,
                max_hilbert_dim=16,
            ).evolve(program_ir, initial_state)
            diagnostics = [*validation["diagnosticCodes"], "SIMULATION_COMPLETED"]
            solver = "cascaqit.AnalogStateVectorKernel.reference_rk4"
        counts = _sample_counts(state.probabilities(), shots, seed + index * 1009)
        analog_points.append(
            _time_point(
                requested_time=requested_time,
                state=state,
                program_hash=program_hash,
                counts=counts,
                diagnostic_codes=diagnostics,
                solver=solver,
            )
        )
        analog_vectors.append(np.asarray(state.amplitudes, dtype=np.complex128))
    classic_reference, classic_vectors = _classic_reference(
        fixture, case_input, initial_state, sample_times
    )
    comparison = _comparison_metrics(
        analog_points,
        classic_reference["timeSeries"],
        analog_vectors,
        classic_vectors,
    )
    execution_hash = hash_payload(
        {
            "analysisHash": analysis["analysisHash"],
            "programHashes": program_hashes,
            "initialStateHash": initial_state.stable_hash(),
            "shots": shots,
            "seed": seed,
            "timeSteps": time_steps,
        }
    )
    result_hash = hash_payload(
        {
            "timeSeries": analog_points,
            "classicReferenceHash": classic_reference["resultHash"],
            "comparison": comparison,
        }
    )
    terminal = analog_points[-1]
    payload = {
        "kind": "materials",
        "analysis": analysis,
        "domain": {
            "kind": "rydberg_dynamics_result",
            "analogStatus": "completed",
            "classicReference": classic_reference,
            "comparison": comparison,
            "interpretation": (
                "四位点材料派生有效 Rydberg Hamiltonian 的本地 AHS 时间演化；"
                "不是材料全电子动力学、输运速率、寿命或硬件结果。"
            ),
        },
        "quantum": {
            "kind": "analog_ahs",
            "experimentKind": "analog_ahs",
            "mode": "analog",
            "algorithm": "ahs_time_evolution",
            "atomOrder": list(ATOM_ORDER),
            "initialState": analysis["domain"]["initialState"],
            "pulseSchedule": analysis["domain"]["pulseSchedule"],
            "sampleTimes": sample_times,
            "timeSeries": analog_points,
            "terminalCounts": terminal["counts"],
            "pureAnalogEvidence": analysis["domain"]["pureAnalogEvidence"],
            "summary": {
                "analogSites": 4,
                "sampleCount": len(sample_times),
                "shotsPerTime": shots,
                "prefixProgramCount": len(program_hashes),
                "timeStepsAtTerminal": time_steps,
                "digitalGateCount": 0,
                "digitalResidualCount": 0,
                "hybridBlockCount": 0,
            },
        },
        "audit": {
            "domainId": "materials",
            "caseId": "rydberg_dynamics",
            "datasetId": fixture.manifest["dataset_id"],
            "datasetVersion": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "domainInputHash": hash_payload(asdict(case_input)),
            "problemHash": analysis["problem"]["hash"],
            "analysisHash": analysis["analysisHash"],
            "compileHash": analysis["analogProgram"]["programHash"],
            "executionHash": execution_hash,
            "resultHash": result_hash,
            "trajectoryHash": hash_payload(analog_points),
            "classicReferenceHash": classic_reference["resultHash"],
            "initialStateHash": initial_state.stable_hash(),
            "pulseScheduleHash": analysis["analogProgram"]["pulseScheduleHash"],
            "rydbergLayoutHash": analysis["domain"]["rydbergLayoutHash"],
            "backend": local_backend_context(
                execution_family="analog_ahs",
                mode="analog",
                simulation_method="cascaqit_exact_state_rk4_prefix",
            ),
            "seed": seed,
            "shots": shots,
            "hardwareExecution": False,
            "cloudExecution": False,
            "networkAccessed": False,
            "wallTimeSeconds": time.perf_counter() - started,
            "optimalityClaim": "not_applicable_time_evolution",
            "claimBoundary": "packaged_four_site_effective_rydberg_model",
            "configurationSchema": "materials.analog-execution-configuration.v1",
            "outcomeSchema": "materials.analog-execution-outcome.v1",
            "reportSchema": "materials.execution-report.v1",
        },
    }
    finalize_stable_audit(
        payload["audit"],
        configuration={
            "input": asdict(case_input),
            "mode": "analog",
            "algorithm": "ahs_time_evolution",
            "shotsPerTime": shots,
            "seed": seed,
            "timeStepsAtTerminal": time_steps,
        },
        outcome={
            "timeSeries": analog_points,
            "classicReferenceHash": classic_reference["resultHash"],
            "comparison": comparison,
        },
    )
    payload["audit"]["resultPresentationHash"] = hash_payload(payload["domain"])
    return payload
