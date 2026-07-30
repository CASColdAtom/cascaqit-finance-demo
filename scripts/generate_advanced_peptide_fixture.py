"""Generate a deterministic eight-residue self-avoiding conformation library."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Callable

ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "cascaqit_biomedicine_demo"
    / "data"
    / "peptide_landscape"
    / "eight_residue_2d"
    / "1"
)
RESIDUE_COUNT = 8
BASIN_DISTANCE_THRESHOLD = 2
MAJOR_BASIN_MINIMUM_SIZE = 4


def _stable_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _transforms() -> tuple[Callable[[int, int], tuple[int, int]], ...]:
    return (
        lambda x, y: (x, y),
        lambda x, y: (x, -y),
        lambda x, y: (-x, y),
        lambda x, y: (-x, -y),
        lambda x, y: (y, x),
        lambda x, y: (y, -x),
        lambda x, y: (-y, x),
        lambda x, y: (-y, -x),
    )


def _canonical(coordinates: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    variants = []
    for transform in _transforms():
        transformed = [transform(x, y) for x, y in coordinates]
        origin_x, origin_y = transformed[0]
        variants.append(
            tuple((x - origin_x, y - origin_y) for x, y in transformed)
        )
    return min(variants)


def _contacts(coordinates: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    return tuple(
        (left + 1, right + 1)
        for left, right in combinations(range(len(coordinates)), 2)
        if right != left + 1
        and sum(
            abs(coordinates[left][axis] - coordinates[right][axis])
            for axis in (0, 1)
        )
        == 1
    )


def _walks() -> list[tuple[tuple[int, int], ...]]:
    unique: set[tuple[tuple[int, int], ...]] = set()

    def extend(coordinates: tuple[tuple[int, int], ...]) -> None:
        if len(coordinates) == RESIDUE_COUNT:
            unique.add(_canonical(coordinates))
            return
        x, y = coordinates[-1]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            point = (x + dx, y + dy)
            if point not in coordinates:
                extend((*coordinates, point))

    extend(((0, 0),))
    return sorted(
        unique,
        key=lambda coordinates: (
            -len(_contacts(coordinates)),
            max(x for x, _y in coordinates)
            - min(x for x, _y in coordinates)
            + max(y for _x, y in coordinates)
            - min(y for _x, y in coordinates),
            coordinates,
        ),
    )


def _select_library(
    walks: list[tuple[tuple[int, int], ...]],
) -> list[tuple[tuple[int, int], ...]]:
    selected: list[tuple[tuple[int, int], ...]] = []
    contact_counts = sorted({len(_contacts(item)) for item in walks}, reverse=True)
    for count in contact_counts:
        group = [item for item in walks if len(_contacts(item)) == count]
        target = min(len(group), 12 if count >= 2 else 8)
        indices = sorted(
            {
                round(index * (len(group) - 1) / max(1, target - 1))
                for index in range(target)
            }
        )
        selected.extend(group[index] for index in indices)
    for item in walks:
        if len(selected) >= 48:
            break
        if item not in selected:
            selected.append(item)
    return selected[:48]


def _basin_labels(
    walks: list[tuple[tuple[int, int], ...]],
) -> tuple[list[str], dict[str, int]]:
    representatives: list[set[tuple[int, int]]] = []
    labels: list[str] = []
    for coordinates in walks:
        contact_set = set(_contacts(coordinates))
        basin_index = next(
            (
                index
                for index, representative in enumerate(representatives)
                if len(contact_set ^ representative) <= BASIN_DISTANCE_THRESHOLD
            ),
            len(representatives),
        )
        if basin_index == len(representatives):
            representatives.append(contact_set)
        labels.append(f"basin.{basin_index:02d}")
    return labels, dict(Counter(labels))


def _pair_score(left: str, right: str) -> float:
    pair = {left, right}
    if left in "+-" and right in "+-":
        return -1.2 if left != right else 0.8
    if "H" in pair and ("+" in pair or "-" in pair):
        return -0.2
    if left == right == "H":
        return -1.0
    if pair == {"H", "P"}:
        return -0.1
    if left == right == "P":
        return 0.05
    return 0.0


def _energy(sequence: str, contacts: tuple[tuple[int, int], ...]) -> float:
    return round(
        sum(
            _pair_score(sequence[left - 1], sequence[right - 1])
            for left, right in contacts
        ),
        10,
    )


def main() -> None:
    script_hash = _hash(Path(__file__).read_bytes())
    walks = _select_library(_walks())
    labels, basin_sizes = _basin_labels(walks)
    conformations = [
        {
            "id": f"a{index:02d}",
            "coordinates": [list(point) for point in coordinates],
            "contacts": [list(pair) for pair in _contacts(coordinates)],
            "basinId": labels[index],
        }
        for index, coordinates in enumerate(walks)
    ]
    domain = {
        "modelLevel": "八残基二维格点粗粒化构象库",
        "lattice": "square_2d",
        "residueCount": RESIDUE_COUNT,
        "symmetryNormalization": "translation_rotation_reflection",
        "basinRule": {
            "version": "contact-hamming-greedy-v1",
            "distanceThreshold": BASIN_DISTANCE_THRESHOLD,
            "majorBasinMinimumSize": MAJOR_BASIN_MINIMUM_SIZE,
            "basinSizes": basin_sizes,
        },
        "selection": {
            "rule_version": "peptide-active-window-v1",
            "max_conformations": 12,
        },
        "conformations": conformations,
    }
    domain_raw = _stable_json(domain)
    presets = {
        "octapeptide_hydrophobic": "HPPHHPHH",
        "octapeptide_charge_shift": "+-PH-+HP",
        "octapeptide_mutation": "HPHPPHH+",
    }
    references = {}
    for preset, sequence in presets.items():
        energies = {
            item["id"]: _energy(
                sequence, tuple(tuple(pair) for pair in item["contacts"])
            )
            for item in conformations
        }
        ground = min(energies.values())
        references[preset] = {
            "sequence": sequence,
            "ground_energy": ground,
            "ground_conformation_ids": sorted(
                identifier
                for identifier, energy in energies.items()
                if energy == ground
            ),
        }
    manifest = {
        "dataset_id": "peptide.eight-residue.square-lattice",
        "version": "1",
        "source": {
            "kind": "project_generated_enumeration",
            "uri": None,
            "raw_file_sha256": None,
            "license": "project_generated",
            "license_checked_at": "2026-07-30",
        },
        "generation": {
            "tool": "deterministic self-avoiding walk enumeration",
            "tool_version": "peptide-fixture-v2",
            "script": "scripts/generate_advanced_peptide_fixture.py",
            "script_sha256": script_hash,
            "parameters": {
                "length": RESIDUE_COUNT,
                "lattice": "square_2d",
                "symmetry": "D4 plus translation",
                "library_size": len(conformations),
                "basin_distance_threshold": BASIN_DISTANCE_THRESHOLD,
            },
        },
        "units": {
            "energy": "dimensionless coarse-grained score",
            "coordinates": "lattice unit",
        },
        "coordinate_system": {
            "domain": "two-dimensional integer square lattice",
            "normalization": "translation and D4 symmetry canonicalization",
        },
        "variable_order": [f"conf.{item['id']}" for item in conformations],
        "artifacts": [{"path": "domain.json", "sha256": _hash(domain_raw)}],
        "reference": {
            "method": (
                "complete enumeration of the packaged finite conformation landscape"
            ),
            "software": "CPython deterministic enumeration",
            "software_version": "3.9.6",
            "standard_presets": references,
        },
        "allowed_claims": [
            "Demonstrate a 48-conformation coarse-grained landscape and "
            "basin-aware active window.",
            "Compare Digital QAOA samples with the complete finite "
            "classical landscape.",
        ],
        "limitations": [
            "This is an eight-residue two-dimensional coarse-grained library.",
            "The quantum activity window contains 12 of 48 conformations.",
            "No folding kinetics, solvent, three-dimensional structure, or "
            "biological function is modeled.",
            "Local simulation only; no hardware execution or quantum advantage claim.",
        ],
    }
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "domain.json").write_bytes(domain_raw)
    (ROOT / "manifest.json").write_bytes(_stable_json(manifest))
    print(f"generated {manifest['dataset_id']}: {ROOT}")


if __name__ == "__main__":
    main()
