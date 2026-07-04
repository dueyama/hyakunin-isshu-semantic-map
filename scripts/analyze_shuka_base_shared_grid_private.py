#!/usr/bin/env python3
"""Private Shuka-base shared-cell 10x10 comparison.

This treats Hyakunin Shuka as the base arrangement. One Shuka-only poem is
omitted so that 100 cells are filled. The 97 common poems keep their Shuka-base
cells; the three remaining Shuka-only cells are replaced with Ogura-only poems
74, 99, and 100 in all possible assignments.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import statistics
from pathlib import Path
from typing import Any

from analyze_shared_grid_private import (
    GRID_SIZE,
    LAYOUTS,
    build_similarity_cache,
    cell_edges,
    compare_to_samples,
    dot,
    similarity,
    unit,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
RANDOM_SEED = 20260704
Cell = tuple[int, int]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pair_scores(records: list[dict[str, Any]], scores: dict[tuple[str, str], float]) -> list[float]:
    output: list[float] = []
    for left, right in itertools.combinations(records, 2):
        output.append(similarity(left["vector_id"], right["vector_id"], scores))
    return output


def edge_mean(
    edges: list[tuple[int, int]],
    occupied: list[dict[str, Any]],
    scores: dict[tuple[str, str], float],
) -> float:
    return statistics.fmean(
        similarity(occupied[left]["vector_id"], occupied[right]["vector_id"], scores)
        for left, right in edges
    )


def random_samples(pair_score_values: list[float], sample_size: int, trials: int, seed: int) -> list[float]:
    rng = random.Random(seed)
    return [statistics.fmean(rng.sample(pair_score_values, sample_size)) for _ in range(trials)]


def shuka_label(record: dict[str, Any]) -> str:
    hyakunin_id = record.get("hyakunin_id")
    hyakunin = f"H{int(hyakunin_id):03d}" if hyakunin_id else "Hnone"
    return f"S{int(record['shuka_order']):03d}/{hyakunin}/{record['poet_jp']}"


def ogura_label(record: dict[str, Any]) -> str:
    return f"H{int(record['id']):03d}/{record['poet_jp']}"


def edge_details(
    edges: list[tuple[int, int]],
    occupied: list[dict[str, Any]],
    scores: dict[tuple[str, str], float],
    limit: int = 12,
) -> dict[str, list[dict[str, Any]]]:
    rows = []
    for left, right in edges:
        left_record = occupied[left]
        right_record = occupied[right]
        rows.append(
            {
                "left": left_record["label"],
                "right": right_record["label"],
                "cosine_similarity": similarity(left_record["vector_id"], right_record["vector_id"], scores),
            }
        )
    return {
        "top": sorted(rows, key=lambda item: item["cosine_similarity"], reverse=True)[:limit],
        "bottom": sorted(rows, key=lambda item: item["cosine_similarity"])[:limit],
    }


def enrich_shuka(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for record in records:
        row = dict(record)
        row["vector_id"] = record["id"]
        row["label"] = shuka_label(record)
        enriched.append(row)
    return enriched


def enrich_ogura(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for record in records:
        row = dict(record)
        row["vector_id"] = str(record["id"])
        row["label"] = ogura_label(record)
        enriched.append(row)
    return enriched


def analyze(shuka_records: list[dict[str, Any]], ogura_records: list[dict[str, Any]], trials: int) -> dict[str, Any]:
    shuka_records = enrich_shuka(shuka_records)
    ogura_records = enrich_ogura(ogura_records)

    shuka_vectors = {record["vector_id"]: unit(record["embedding"]) for record in shuka_records}
    ogura_vectors = {record["vector_id"]: unit(record["embedding"]) for record in ogura_records}
    shuka_scores = build_similarity_cache(shuka_records, shuka_vectors)
    ogura_scores = build_similarity_cache(ogura_records, ogura_vectors)

    shuka_only = [record for record in shuka_records if not record.get("hyakunin_id")]
    common_shuka = [record for record in shuka_records if record.get("hyakunin_id")]
    common_ids = {int(record["hyakunin_id"]) for record in common_shuka}
    ogura_by_id = {int(record["id"]): record for record in ogura_records}
    ogura_only_ids = [ogura_id for ogura_id in range(1, 101) if ogura_id not in common_ids]
    ogura_only = [ogura_by_id[ogura_id] for ogura_id in ogura_only_ids]
    ogura_all_pair_scores = pair_scores(ogura_records, ogura_scores)

    shuka_rows: list[dict[str, Any]] = []
    ogura_rows: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    random_cache: dict[tuple[str, str, int], list[float]] = {}

    for layout_name, layout_fn in LAYOUTS.items():
        cells = layout_fn(GRID_SIZE)
        orthogonal_edges = cell_edges(cells, include_diagonal=False)
        eight_edges = cell_edges(cells, include_diagonal=True)

        for omitted in shuka_only:
            selected_shuka = [record for record in shuka_records if record["id"] != omitted["id"]]
            selected_shuka = sorted(selected_shuka, key=lambda record: int(record["shuka_order"]))
            shuka_occupied = selected_shuka
            if len(shuka_occupied) != GRID_SIZE * GRID_SIZE:
                raise ValueError("Shuka base grid must have 100 occupied cells")
            shuka_pair_values = pair_scores(shuka_occupied, shuka_scores)
            shuka_orth_key = (omitted["id"], "shuka_orth", len(orthogonal_edges))
            shuka_eight_key = (omitted["id"], "shuka_eight", len(eight_edges))
            if shuka_orth_key not in random_cache:
                random_cache[shuka_orth_key] = random_samples(
                    shuka_pair_values, len(orthogonal_edges), trials, RANDOM_SEED + len(random_cache)
                )
            if shuka_eight_key not in random_cache:
                random_cache[shuka_eight_key] = random_samples(
                    shuka_pair_values, len(eight_edges), trials, RANDOM_SEED + len(random_cache)
                )
            shuka_orth_mean = edge_mean(orthogonal_edges, shuka_occupied, shuka_scores)
            shuka_eight_mean = edge_mean(eight_edges, shuka_occupied, shuka_scores)
            variant_cell_indexes = [
                index
                for index, record in enumerate(shuka_occupied)
                if not record.get("hyakunin_id")
            ]
            shuka_key = f"{layout_name}__omit_{omitted['id']}__shuka_base"
            shuka_row = {
                "key": shuka_key,
                "layout": layout_name,
                "omitted": omitted["label"],
                "remaining_shuka_only_cells": [
                    {"cell_index": index, "cell": cells[index], "record": shuka_occupied[index]["label"]}
                    for index in variant_cell_indexes
                ],
                "orthogonal_neighbors": {
                    "edge_count": len(orthogonal_edges),
                    **compare_to_samples(shuka_orth_mean, random_cache[shuka_orth_key]),
                },
                "eight_neighbors": {
                    "edge_count": len(eight_edges),
                    **compare_to_samples(shuka_eight_mean, random_cache[shuka_eight_key]),
                },
            }
            shuka_rows.append(shuka_row)
            details[shuka_key] = {
                "orthogonal": edge_details(orthogonal_edges, shuka_occupied, shuka_scores),
                "eight": edge_details(eight_edges, shuka_occupied, shuka_scores),
            }

            common_cell_by_hyakunin = {
                int(record["hyakunin_id"]): index
                for index, record in enumerate(shuka_occupied)
                if record.get("hyakunin_id")
            }
            for perm_index, filler_order in enumerate(itertools.permutations(ogura_only)):
                ogura_occupied: list[dict[str, Any] | None] = [None] * (GRID_SIZE * GRID_SIZE)
                for hyakunin_id, index in common_cell_by_hyakunin.items():
                    ogura_occupied[index] = ogura_by_id[hyakunin_id]
                assignment = []
                for index, filler in zip(variant_cell_indexes, filler_order, strict=True):
                    ogura_occupied[index] = filler
                    assignment.append(
                        {
                            "cell_index": index,
                            "cell": cells[index],
                            "replaces_shuka": shuka_occupied[index]["label"],
                            "ogura_filler": filler["label"],
                        }
                    )
                if any(record is None for record in ogura_occupied):
                    raise ValueError("Ogura replacement grid contains empty cells")
                typed_ogura_occupied = [record for record in ogura_occupied if record is not None]
                ogura_orth_key = ("ogura_all", "orth", len(orthogonal_edges))
                ogura_eight_key = ("ogura_all", "eight", len(eight_edges))
                if ogura_orth_key not in random_cache:
                    random_cache[ogura_orth_key] = random_samples(
                        ogura_all_pair_scores, len(orthogonal_edges), trials, RANDOM_SEED + len(random_cache)
                    )
                if ogura_eight_key not in random_cache:
                    random_cache[ogura_eight_key] = random_samples(
                        ogura_all_pair_scores, len(eight_edges), trials, RANDOM_SEED + len(random_cache)
                    )
                ogura_orth_mean = edge_mean(orthogonal_edges, typed_ogura_occupied, ogura_scores)
                ogura_eight_mean = edge_mean(eight_edges, typed_ogura_occupied, ogura_scores)
                ogura_key = f"{layout_name}__omit_{omitted['id']}__ogura_perm_{perm_index}"
                ogura_row = {
                    "key": ogura_key,
                    "layout": layout_name,
                    "base_omitted_shuka": omitted["label"],
                    "assignment": assignment,
                    "orthogonal_neighbors": {
                        "edge_count": len(orthogonal_edges),
                        **compare_to_samples(ogura_orth_mean, random_cache[ogura_orth_key]),
                    },
                    "eight_neighbors": {
                        "edge_count": len(eight_edges),
                        **compare_to_samples(ogura_eight_mean, random_cache[ogura_eight_key]),
                    },
                }
                ogura_rows.append(ogura_row)
                details[ogura_key] = {
                    "orthogonal": edge_details(orthogonal_edges, typed_ogura_occupied, ogura_scores),
                    "eight": edge_details(eight_edges, typed_ogura_occupied, ogura_scores),
                }

    return {
        "meta": {
            "method": "Shuka-base shared-cell comparison: 97 common poems keep Shuka cells; Ogura-only poems fill remaining Shuka-only cells",
            "common_count": len(common_ids),
            "shuka_only": [record["label"] for record in shuka_only],
            "ogura_only": [record["label"] for record in ogura_only],
            "layout_names": list(LAYOUTS),
            "random_baseline": "sample same number of unordered pairs from each selected 100-poem set",
            "random_trials": trials,
            "random_seed": RANDOM_SEED,
            "text_policy": "private embeddings and private Shuka text are not published",
        },
        "top_shuka_orthogonal": sorted(
            shuka_rows,
            key=lambda item: item["orthogonal_neighbors"]["z_score"] or float("-inf"),
            reverse=True,
        )[:24],
        "top_shuka_eight": sorted(
            shuka_rows,
            key=lambda item: item["eight_neighbors"]["z_score"] or float("-inf"),
            reverse=True,
        )[:24],
        "top_ogura_orthogonal": sorted(
            ogura_rows,
            key=lambda item: item["orthogonal_neighbors"]["z_score"] or float("-inf"),
            reverse=True,
        )[:24],
        "top_ogura_eight": sorted(
            ogura_rows,
            key=lambda item: item["eight_neighbors"]["z_score"] or float("-inf"),
            reverse=True,
        )[:24],
        "shuka_all": shuka_rows,
        "ogura_all": ogura_rows,
        "details": details,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--shuka-embeddings",
        type=Path,
        default=ROOT / "_private/literature/embeddings/hyakunin_shuka_mizugaki_text-embedding-3-small.json",
    )
    parser.add_argument(
        "--ogura-embeddings",
        type=Path,
        default=ROOT / "_private/literature/embeddings/hyakunin_isshu_original_text-embedding-3-small.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "_private/literature/records/hyakunin_shuka_base_shared_cell_10x10_analysis_small.json",
    )
    parser.add_argument("--random-trials", type=int, default=10_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    shuka_payload = read_json(args.shuka_embeddings)
    ogura_payload = read_json(args.ogura_embeddings)
    shuka_records = sorted(shuka_payload["records"], key=lambda item: int(item["shuka_order"]))
    ogura_records = sorted(ogura_payload["records"], key=lambda item: int(item["id"]))
    result = analyze(shuka_records, ogura_records, args.random_trials)
    result["meta"]["shuka_model"] = shuka_payload["meta"].get("model")
    result["meta"]["shuka_input_mode"] = shuka_payload["meta"].get("input_mode")
    result["meta"]["ogura_model"] = ogura_payload["meta"].get("model")
    result["meta"]["ogura_input_mode"] = ogura_payload["meta"].get("input_mode")
    result["meta"]["vector_dimension"] = len(shuka_records[0]["embedding"]) if shuka_records else 0
    write_json(args.output, result)
    print(f"wrote private Shuka-base shared-cell analysis to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
