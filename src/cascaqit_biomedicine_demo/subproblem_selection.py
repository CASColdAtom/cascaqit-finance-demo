"""Deterministic activity-window selection for advanced biomedicine problems."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def select_docking_matches(domain: dict[str, Any]) -> dict[str, Any]:
    """Select matches while preserving pose and required-feature coverage."""

    matches = list(domain["matches"])
    conflicts = list(domain["conflicts"])
    settings = domain["selection"]
    limit = int(settings["max_match_variables"])
    minimum_per_pose = int(settings["minimum_matches_per_pose"])
    required_features = tuple(str(item) for item in domain["required_feature_ids"])
    conflict_degree = {str(item["id"]): 0 for item in matches}
    for conflict in conflicts:
        conflict_degree[str(conflict["left"])] += 1
        conflict_degree[str(conflict["right"])] += 1

    def score(item: dict[str, Any]) -> float:
        return round(
            float(item["quality"])
            - float(item["distance_deviation"])
            - float(item["angle_deviation"]),
            12,
        )

    def rank(item: dict[str, Any]) -> tuple[float, int, str]:
        return (-score(item), -conflict_degree[str(item["id"])], str(item["id"]))

    selected: set[str] = set()
    for feature in required_features:
        candidates = [item for item in matches if item["pocket_feature"] == feature]
        if not candidates:
            raise ValueError(f"required pocket feature has no candidate: {feature}")
        selected.add(str(min(candidates, key=rank)["id"]))
    for pose in domain["poses"]:
        pose_id = str(pose["id"])
        candidates = sorted(
            (item for item in matches if item["pose_id"] == pose_id), key=rank
        )
        selected.update(str(item["id"]) for item in candidates[:minimum_per_pose])
    for item in sorted(matches, key=rank):
        if len(selected) >= limit:
            break
        selected.add(str(item["id"]))
    if len(selected) > limit:
        raise ValueError(
            "docking coverage requirements exceed the activity-window limit"
        )

    selected_matches = [item for item in matches if str(item["id"]) in selected]
    selected_conflicts = [
        item
        for item in conflicts
        if str(item["left"]) in selected and str(item["right"]) in selected
    ]
    excluded = [
        {
            "id": str(item["id"]),
            "reason": "activity_window_limit",
            "score": score(item),
            "poseId": str(item["pose_id"]),
            "pocketFeature": str(item["pocket_feature"]),
            "constraintCoverage": conflict_degree[str(item["id"])],
        }
        for item in matches
        if str(item["id"]) not in selected
    ]
    selected_ids = [str(item["id"]) for item in selected_matches]
    required_coverage = {
        feature: any(item["pocket_feature"] == feature for item in selected_matches)
        for feature in required_features
    }
    pose_coverage = {
        str(pose["id"]): sum(
            item["pose_id"] == pose["id"] for item in selected_matches
        )
        for pose in domain["poses"]
    }
    if not all(required_coverage.values()) or any(
        count < minimum_per_pose for count in pose_coverage.values()
    ):
        raise ValueError("docking activity window does not preserve required coverage")
    complete_identity = {
        "matches": matches,
        "poses": domain["poses"],
        "conflicts": conflicts,
        "minimumCoverage": domain["minimum_coverage"],
        "requiredFeatures": required_features,
    }
    selection_identity = {
        "ruleVersion": settings["rule_version"],
        "completeProblemHash": _stable_hash(complete_identity),
        "selectedMatchIds": selected_ids,
        "excluded": excluded,
        "requiredFeatureCoverage": required_coverage,
        "poseCoverage": pose_coverage,
    }
    return {
        **selection_identity,
        "selectionHash": _stable_hash(selection_identity),
        "completeMatchCount": len(matches),
        "selectedMatchCount": len(selected_matches),
        "coverageRate": len(selected_matches) / len(matches),
        "selectedMatches": selected_matches,
        "selectedConflicts": selected_conflicts,
    }


def _contact_distance(left: dict[str, Any], right: dict[str, Any]) -> int:
    left_contacts = {tuple(item) for item in left["contacts"]}
    right_contacts = {tuple(item) for item in right["contacts"]}
    return len(left_contacts ^ right_contacts)


def select_peptide_conformations(
    landscape: list[dict[str, Any]],
    *,
    basin_sizes: dict[str, int],
    major_basin_minimum_size: int,
    limit: int,
) -> dict[str, Any]:
    """Select an energy-window activity set with ground and basin coverage."""

    if not landscape:
        raise ValueError("peptide landscape must not be empty")
    minimum = min(float(item["energy"]) for item in landscape)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def add(item: dict[str, Any]) -> None:
        identifier = str(item["id"])
        if identifier not in selected_ids:
            selected.append(item)
            selected_ids.add(identifier)

    for item in sorted(landscape, key=lambda row: str(row["id"])):
        if float(item["energy"]) == minimum:
            add(item)
    major_basins = sorted(
        basin
        for basin, size in basin_sizes.items()
        if int(size) >= major_basin_minimum_size
    )
    for basin in major_basins:
        add(
            min(
                (item for item in landscape if item["basinId"] == basin),
                key=lambda row: (float(row["energy"]), str(row["id"])),
            )
        )
    if len(selected) > limit:
        raise ValueError("peptide basin coverage exceeds the activity-window limit")

    energy_window = 1.5
    remaining = [item for item in landscape if str(item["id"]) not in selected_ids]
    while len(selected) < limit and remaining:
        within_window = [
            item
            for item in remaining
            if float(item["energy"]) <= minimum + energy_window
        ]
        candidates = within_window or remaining

        def candidate_rank(item: dict[str, Any]) -> tuple[int, float, str]:
            diversity = min(
                (_contact_distance(item, chosen) for chosen in selected), default=0
            )
            return (-diversity, float(item["energy"]), str(item["id"]))

        chosen = min(candidates, key=candidate_rank)
        add(chosen)
        remaining = [item for item in remaining if item["id"] != chosen["id"]]

    selected_by_library_order = [
        item for item in landscape if str(item["id"]) in selected_ids
    ]
    excluded = [
        {
            "id": str(item["id"]),
            "reason": (
                "outside_energy_window"
                if float(item["energy"]) > minimum + energy_window
                else "activity_window_limit"
            ),
            "energy": float(item["energy"]),
            "basinId": str(item["basinId"]),
        }
        for item in landscape
        if str(item["id"]) not in selected_ids
    ]
    selection_identity = {
        "ruleVersion": "peptide-active-window-v1",
        "completeLandscapeHash": _stable_hash(landscape),
        "selectedConformationIds": [
            str(item["id"]) for item in selected_by_library_order
        ],
        "excluded": excluded,
        "majorBasins": major_basins,
        "energyWindow": energy_window,
    }
    selected_basins = {str(item["basinId"]) for item in selected_by_library_order}
    if not set(major_basins).issubset(selected_basins):
        raise ValueError("peptide activity window does not cover every major basin")
    return {
        **selection_identity,
        "selectionHash": _stable_hash(selection_identity),
        "completeConformationCount": len(landscape),
        "selectedConformationCount": len(selected_by_library_order),
        "coverageRate": len(selected_by_library_order) / len(landscape),
        "selectedConformations": selected_by_library_order,
    }
