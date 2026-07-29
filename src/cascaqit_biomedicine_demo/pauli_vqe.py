"""Domain-neutral helpers for packaged Pauli Hamiltonian VQE experiments."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
from cascaqit.algorithms import HamiltonianTerm, PauliHamiltonian
from cascaqit.observables import PauliProduct


def hash_payload(value: Any) -> str:
    """Return the stable JSON hash used by the demo audit chain."""
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_pauli_hamiltonian(payload: dict[str, Any]) -> PauliHamiltonian:
    """Build a CASCAQit Hamiltonian from a validated fixture-style payload."""
    terms = []
    for item in payload["terms"]:
        factors = tuple((str(target), str(basis)) for target, basis in item["factors"])
        terms.append(
            HamiltonianTerm(
                str(item["term_id"]),
                float(item["coefficient"]),
                PauliProduct(factors, name=str(item["operator"])),
            )
        )
    return PauliHamiltonian(
        hamiltonian_id=str(payload["hamiltonian_id"]),
        terms=tuple(terms),
        constant=float(payload.get("constant", 0.0)),
        logical_order=tuple(str(item) for item in payload["logical_order"]),
        metadata=dict(payload.get("metadata", {})),
    )


_PAULI = {
    "I": np.eye(2, dtype=complex),
    "X": np.array([[0, 1], [1, 0]], dtype=complex),
    "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
    "Z": np.array([[1, 0], [0, -1]], dtype=complex),
}


def pauli_matrix(
    logical_order: tuple[str, ...], factors: tuple[tuple[str, str], ...]
) -> np.ndarray:
    """Construct a dense matrix for a small auditable Pauli product."""
    basis = dict(factors)
    matrix = np.array([[1.0 + 0.0j]])
    for target in logical_order:
        matrix = np.kron(matrix, _PAULI[basis.get(target, "I")])
    return matrix


def exact_diagonalization(hamiltonian: PauliHamiltonian) -> dict[str, Any]:
    """Diagonalize a small packaged Hamiltonian and retain its ground vector."""
    size = 2 ** len(hamiltonian.logical_order)
    matrix = np.eye(size, dtype=complex) * hamiltonian.constant
    term_matrices: dict[str, np.ndarray] = {}
    for term in hamiltonian.terms:
        factors = tuple(
            (factor.target, factor.basis.value) for factor in term.observable.terms
        )
        operator = pauli_matrix(hamiltonian.logical_order, factors)
        term_matrices[term.term_id] = operator
        matrix += term.coefficient * operator
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    ground = eigenvectors[:, 0]
    expectations = {
        term_id: float(np.real(np.vdot(ground, operator @ ground)))
        for term_id, operator in term_matrices.items()
    }
    return {
        "energy": float(eigenvalues[0]),
        "spectrum": [float(value) for value in eigenvalues],
        "expectations": expectations,
        "probabilities": [float(abs(value) ** 2) for value in ground],
    }


def sector_occupancy_from_probabilities(
    probabilities: list[float], qubits: int
) -> dict[str, float]:
    """Aggregate computational probabilities by total Pauli-Z magnetization."""
    sectors: dict[str, float] = {}
    for index, probability in enumerate(probabilities):
        state = format(index, f"0{qubits}b")
        magnetization = sum(0.5 if bit == "0" else -0.5 for bit in state)
        key = f"Mz={magnetization:+g}"
        sectors[key] = sectors.get(key, 0.0) + float(probability)
    return dict(sorted(sectors.items(), reverse=True))


def sector_occupancy_from_counts(counts: dict[str, int]) -> dict[str, float]:
    """Aggregate backend counts by the declared total-magnetization sector."""
    total = sum(counts.values())
    if total <= 0:
        return {}
    probabilities = [0.0] * (2 ** len(next(iter(counts))))
    for state, count in counts.items():
        probabilities[int(state, 2)] = count / total
    return sector_occupancy_from_probabilities(probabilities, len(next(iter(counts))))
