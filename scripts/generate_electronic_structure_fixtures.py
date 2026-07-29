"""Generate audited small-molecule Pauli fixtures for the biomedicine demo.

This script is a release-time tool. PySCF and OpenFermion are intentionally not
runtime dependencies of the packaged workbench.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from openfermion import (
    MolecularData,
    QubitOperator,
    get_fermion_operator,
    get_sparse_operator,
    symmetry_conserving_bravyi_kitaev,
)
from openfermionpyscf import run_pyscf

PYSCF_VERSION = "2.10.0"
OPENFERMION_VERSION = "1.7.1"
OPENFERMION_PYSCF_VERSION = "0.5"


@dataclass(frozen=True)
class FixtureSpec:
    key: str
    directory: str
    dataset_id: str
    molecule: str
    geometry_label: str
    geometry: tuple[tuple[str, tuple[float, float, float]], ...]
    bonds: tuple[tuple[int, int, int], ...]
    occupied_indices: tuple[int, ...]
    active_indices: tuple[int, ...]
    active_electrons: int


FIXTURES = (
    FixtureSpec(
        key="h2_sto3g_0500",
        directory="h2_sto3g_0500",
        dataset_id="electronic.h2.sto3g.0500",
        molecule="H2",
        geometry_label="compressed bond reference",
        geometry=(("H", (0.0, 0.0, 0.0)), ("H", (0.0, 0.0, 0.5))),
        bonds=((0, 1, 1),),
        occupied_indices=(),
        active_indices=(0, 1),
        active_electrons=2,
    ),
    FixtureSpec(
        key="h2_sto3g_0735",
        directory="h2_sto3g",
        dataset_id="electronic.h2.sto3g.0735",
        molecule="H2",
        geometry_label="equilibrium bond reference",
        geometry=(("H", (0.0, 0.0, 0.0)), ("H", (0.0, 0.0, 0.735))),
        bonds=((0, 1, 1),),
        occupied_indices=(),
        active_indices=(0, 1),
        active_electrons=2,
    ),
    FixtureSpec(
        key="h2_sto3g_1500",
        directory="h2_sto3g_1500",
        dataset_id="electronic.h2.sto3g.1500",
        molecule="H2",
        geometry_label="stretched bond reference",
        geometry=(("H", (0.0, 0.0, 0.0)), ("H", (0.0, 0.0, 1.5))),
        bonds=((0, 1, 1),),
        occupied_indices=(),
        active_indices=(0, 1),
        active_electrons=2,
    ),
    FixtureSpec(
        key="lih_sto3g_1600",
        directory="lih_sto3g_1600",
        dataset_id="electronic.lih.sto3g.1600.active-2e-3o",
        molecule="LiH",
        geometry_label="1.600 angstrom active-space reference",
        geometry=(("Li", (0.0, 0.0, 0.0)), ("H", (0.0, 0.0, 1.6))),
        bonds=((0, 1, 1),),
        occupied_indices=(0,),
        active_indices=(1, 2, 3),
        active_electrons=2,
    ),
    FixtureSpec(
        key="h2o_sto3g_equilibrium",
        directory="h2o_sto3g_equilibrium",
        dataset_id="electronic.h2o.sto3g.equilibrium.active-2e-3o",
        molecule="H2O",
        geometry_label="0.9584 angstrom / 104.45 degree reference",
        geometry=(
            ("O", (0.0, 0.0, 0.0)),
            ("H", (0.7575, 0.0, 0.5871)),
            ("H", (-0.7575, 0.0, 0.5871)),
        ),
        bonds=((0, 1, 1), (0, 2, 1)),
        occupied_indices=(0, 1, 2, 3),
        active_indices=(4, 5, 6),
        active_electrons=2,
    ),
)


def _stable_json(value: Any, *, compact: bool = False) -> bytes:
    options: dict[str, Any] = {
        "ensure_ascii": False,
        "sort_keys": True,
    }
    if compact:
        options["separators"] = (",", ":")
    else:
        options["indent"] = 2
    return (json.dumps(value, **options) + "\n").encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _number(value: complex | float) -> float:
    resolved = complex(value)
    if abs(resolved.imag) > 1e-10:
        raise ValueError(f"Pauli coefficient is not real: {value}")
    return float(f"{resolved.real:.15g}")


def _input_payload(spec: FixtureSpec) -> dict[str, Any]:
    return {
        "molecule": spec.molecule,
        "geometry_angstrom": [
            {"element": element, "coordinates": list(point)}
            for element, point in spec.geometry
        ],
        "charge": 0,
        "multiplicity": 1,
        "basis": "STO-3G",
        "occupied_indices": list(spec.occupied_indices),
        "active_indices": list(spec.active_indices),
        "active_electrons": spec.active_electrons,
        "mapping": "symmetry_conserving_bravyi_kitaev",
        "spin_orbital_count": 2 * len(spec.active_indices),
        "tapered_qubit_count": 2,
        "final_qubit_count": 2 * len(spec.active_indices) - 2,
    }


def _visual_coordinates(spec: FixtureSpec) -> list[tuple[float, float]]:
    if spec.molecule in {"H2", "LiH"}:
        return [(25.0, 50.0), (75.0, 50.0)]
    return [(50.0, 35.0), (24.0, 72.0), (76.0, 72.0)]


def _domain(spec: FixtureSpec, reference_bitstring: str) -> dict[str, Any]:
    visual = _visual_coordinates(spec)
    atoms = [
        {
            "id": f"{element}{index + 1}",
            "element": element,
            "x": visual[index][0],
            "y": visual[index][1],
            "z": 0.0,
            "coordinatesAngstrom": list(point),
        }
        for index, (element, point) in enumerate(spec.geometry)
    ]
    return {
        "datasetKey": spec.key,
        "molecule": spec.molecule,
        "geometryLabel": spec.geometry_label,
        "charge": 0,
        "multiplicity": 1,
        "basis": "STO-3G",
        "activeSpace": (
            f"{spec.active_electrons} electrons / {len(spec.active_indices)} orbitals"
        ),
        "mapping": "symmetry-conserving Bravyi-Kitaev with two-qubit tapering",
        "referenceHartreeFockBitstring": reference_bitstring,
        "atoms": atoms,
        "bonds": [
            {
                "source": atoms[left]["id"],
                "target": atoms[right]["id"],
                "order": order,
                "lengthAngstrom": _number(
                    math.dist(spec.geometry[left][1], spec.geometry[right][1])
                ),
            }
            for left, right, order in spec.bonds
        ],
    }


def _pauli_payload(
    spec: FixtureSpec, qubit_operator: QubitOperator, qubits: int
) -> tuple[dict[str, Any], QubitOperator]:
    logical_order = [f"q{index}" for index in range(qubits)]
    rounded = QubitOperator()
    terms = []
    constant = 0.0
    for factors, coefficient in sorted(qubit_operator.terms.items()):
        value = _number(coefficient)
        if abs(value) < 1e-12:
            continue
        rounded += QubitOperator(factors, value)
        if not factors:
            constant = value
            continue
        term_suffix = ".".join(f"{basis.lower()}{index}" for index, basis in factors)
        terms.append(
            {
                "term_id": f"pauli.{term_suffix}",
                "operator": " ".join(
                    f"{basis}(q{index})" for index, basis in factors
                ),
                "coefficient": value,
                "factors": [[f"q{index}", basis] for index, basis in factors],
            }
        )
    return (
        {
            "hamiltonian_id": spec.dataset_id,
            "constant": constant,
            "logical_order": logical_order,
            "terms": terms,
        },
        rounded,
    )


def _warm_start(qubits: int) -> dict[str, float]:
    # The inverse of the linear CX ladder maps |11..1> to |10..0> before
    # entanglement, so this parameter point prepares the tapered HF bitstring.
    values: dict[str, float] = {}
    for index in range(qubits):
        values[f"ry_0_{index}"] = math.pi if index == 0 else 0.0
        values[f"rz_0_{index}"] = 0.0
    return values


def _build_fixture(spec: FixtureSpec, script_hash: str) -> tuple[bytes, bytes, bytes]:
    with tempfile.TemporaryDirectory(prefix="cascaqit-electronic-fixture-") as tmp:
        molecule = MolecularData(
            list(spec.geometry),
            "sto-3g",
            1,
            0,
            description=spec.key,
            filename=str(Path(tmp) / spec.key),
        )
        molecule = run_pyscf(molecule, run_scf=1, run_fci=1)
    molecular_hamiltonian = molecule.get_molecular_hamiltonian(
        occupied_indices=list(spec.occupied_indices),
        active_indices=list(spec.active_indices),
    )
    spin_orbitals = 2 * len(spec.active_indices)
    qubit_operator = symmetry_conserving_bravyi_kitaev(
        get_fermion_operator(molecular_hamiltonian),
        active_orbitals=spin_orbitals,
        active_fermions=spec.active_electrons,
    )
    qubits = spin_orbitals - 2
    pauli, rounded_operator = _pauli_payload(spec, qubit_operator, qubits)
    matrix = get_sparse_operator(rounded_operator, n_qubits=qubits).toarray()
    eigenvalues = np.linalg.eigvalsh(matrix)
    diagonal = np.real(np.diag(matrix))
    hf_index = int(np.argmin(np.abs(diagonal - float(molecule.hf_energy))))
    hf_energy = float(diagonal[hf_index])
    if abs(hf_energy - float(molecule.hf_energy)) > 1e-9:
        raise ValueError(f"unable to identify tapered Hartree-Fock state: {spec.key}")
    reference_bitstring = format(hf_index, f"0{qubits}b")
    domain = _domain(spec, reference_bitstring)
    domain_raw = _stable_json(domain)
    pauli_raw = _stable_json(pauli)
    input_raw = _stable_json(_input_payload(spec), compact=True)
    manifest = {
        "dataset_id": spec.dataset_id,
        "version": "1",
        "source": {
            "kind": "project_generated_ab_initio_fixture",
            "uri": None,
            "license": "project_generated",
            "license_checked_at": "2026-07-30",
            "input_sha256": _sha256(input_raw),
        },
        "generation": {
            "tool": "PySCF + OpenFermion-PySCF + OpenFermion",
            "tool_versions": {
                "pyscf": PYSCF_VERSION,
                "openfermion": OPENFERMION_VERSION,
                "openfermionpyscf": OPENFERMION_PYSCF_VERSION,
            },
            "script": "scripts/generate_electronic_structure_fixtures.py",
            "script_sha256": script_hash,
            "parameters": _input_payload(spec),
        },
        "units": {"geometry": "angstrom", "energy": "hartree"},
        "coordinate_system": "Cartesian molecular geometry; 2D display projection",
        "logical_order": pauli["logical_order"],
        "artifacts": [
            {"path": "domain.json", "sha256": _sha256(domain_raw)},
            {"path": "pauli.json", "sha256": _sha256(pauli_raw)},
        ],
        "reference": {
            "method": "exact diagonalization of the packaged tapered Pauli Hamiltonian",
            "exact_ground_energy_hartree": _number(eigenvalues[0]),
            "hartree_fock_energy_hartree": _number(hf_energy),
            "full_space_fci_energy_hartree": _number(molecule.fci_energy),
            "hartree_fock_bitstring": reference_bitstring,
        },
        "recommended_initial_parameters": {
            "ansatz": "hardware_efficient_ry_rz_linear",
            "layers": 1,
            "values": _warm_start(qubits),
            "purpose": "Prepare the tapered Hartree-Fock state before optimization.",
        },
        "limitations": [
            (
                "Fixed STO-3G active-space teaching fixture; not an arbitrary "
                "molecule workflow."
            ),
            (
                "Frozen-orbital and active-space truncation omit correlation "
                "outside the declared space."
            ),
            (
                "Readout-noise mode is a simulator sensitivity demonstration, "
                "not a hardware forecast."
            ),
            "Local simulation only; no hardware execution or quantum advantage claim.",
        ],
        "allowed_claims": [
            (
                "Compare CASCAQit VQE with the exact energy of the same packaged "
                "Hamiltonian."
            ),
            (
                "Explain active-space, Pauli mapping, QWC measurement, and "
                "finite-shot uncertainty."
            ),
        ],
    }
    return domain_raw, pauli_raw, _stable_json(manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "src"
            / "cascaqit_biomedicine_demo"
            / "data"
            / "electronic_structure"
        ),
    )
    parser.add_argument("--only", choices=[item.key for item in FIXTURES])
    args = parser.parse_args()
    script_hash = _sha256(Path(__file__).read_bytes())
    selected = [item for item in FIXTURES if args.only in {None, item.key}]
    for spec in selected:
        domain_raw, pauli_raw, manifest_raw = _build_fixture(spec, script_hash)
        destination = args.output_root / spec.directory / "1"
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "domain.json").write_bytes(domain_raw)
        (destination / "pauli.json").write_bytes(pauli_raw)
        (destination / "manifest.json").write_bytes(manifest_raw)
        print(f"generated {spec.key}: {destination}")


if __name__ == "__main__":
    main()
