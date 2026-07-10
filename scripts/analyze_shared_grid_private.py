#!/usr/bin/env python3
"""Private shared-cell 10x10 analysis for Ogura/Shuka common poems.

Common Shuka poems are fixed to the cell occupied by the same Ogura id.
The three Ogura-only cells are filled with three of four Shuka-only poems;
one Shuka-only poem is omitted. This keeps 100 occupied cells.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
from pathlib import Path
from typing import Any

from layout_permutation import random_layout_permutations, random_layout_samples


ROOT = Path(__file__).resolve().parents[1]
GRID_SIZE = 10
RANDOM_SEED = 20260710

Cell = tuple[int, int]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def unit(vector: list[float]) -> list[float]:
    length = math.sqrt(dot(vector, vector))
    if not length:
        return vector
    return [value / length for value in vector]


def row_major(size: int) -> list[Cell]:
    return [(index // size, index % size) for index in range(size * size)]


def row_serpentine(size: int) -> list[Cell]:
    cells: list[Cell] = []
    for row in range(size):
        cols = range(size) if row % 2 == 0 else range(size - 1, -1, -1)
        for col in cols:
            cells.append((row, col))
    return cells


def column_major(size: int) -> list[Cell]:
    return [(index % size, index // size) for index in range(size * size)]


def column_serpentine(size: int) -> list[Cell]:
    cells: list[Cell] = []
    for col in range(size):
        rows = range(size) if col % 2 == 0 else range(size - 1, -1, -1)
        for row in rows:
            cells.append((row, col))
    return cells


def diagonal_nw_se_serpentine(size: int) -> list[Cell]:
    cells: list[Cell] = []
    for total in range(2 * size - 1):
        diagonal = [(row, total - row) for row in range(size) if 0 <= total - row < size]
        if total % 2:
            diagonal.reverse()
        cells.extend(diagonal)
    return cells


def diagonal_ne_sw_serpentine(size: int) -> list[Cell]:
    return [(row, size - 1 - col) for row, col in diagonal_nw_se_serpentine(size)]


def spiral_clockwise(size: int) -> list[Cell]:
    cells: list[Cell] = []
    top, left = 0, 0
    bottom, right = size - 1, size - 1
    while top <= bottom and left <= right:
        for col in range(left, right + 1):
            cells.append((top, col))
        top += 1
        for row in range(top, bottom + 1):
            cells.append((row, right))
        right -= 1
        if top <= bottom:
            for col in range(right, left - 1, -1):
                cells.append((bottom, col))
            bottom -= 1
        if left <= right:
            for row in range(bottom, top - 1, -1):
                cells.append((row, left))
            left += 1
    return cells


LAYOUTS = {
    "row_major": row_major,
    "row_serpentine": row_serpentine,
    "column_major": column_major,
    "column_serpentine": column_serpentine,
    "diagonal_nw_se_serpentine": diagonal_nw_se_serpentine,
    "diagonal_ne_sw_serpentine": diagonal_ne_sw_serpentine,
    "spiral_clockwise": spiral_clockwise,
}


def cell_edges(cells: list[Cell], include_diagonal: bool) -> list[tuple[int, int]]:
    index_by_cell = {cell: index for index, cell in enumerate(cells)}
    offsets = [(1, 0), (0, 1)]
    if include_diagonal:
        offsets.extend([(1, 1), (1, -1)])
    edges: list[tuple[int, int]] = []
    for index, (row, col) in enumerate(cells):
        for row_delta, col_delta in offsets:
            other = index_by_cell.get((row + row_delta, col + col_delta))
            if other is not None:
                edges.append((index, other))
    return edges


def compare_to_samples(value: float, samples: list[float]) -> dict[str, float | None]:
    random_mean = statistics.fmean(samples)
    random_sd = statistics.pstdev(samples)
    return {
        "mean": value,
        "random_mean": random_mean,
        "random_sd": random_sd,
        "z_score": (value - random_mean) / random_sd if random_sd else None,
        "percentile": sum(1 for sample in samples if sample <= value) / len(samples),
    }


def build_similarity_cache(records: list[dict[str, Any]], vectors: dict[str, list[float]]) -> dict[tuple[str, str], float]:
    scores: dict[tuple[str, str], float] = {}
    for left, right in itertools.combinations(records, 2):
        key = tuple(sorted((left["id"], right["id"])))
        scores[key] = dot(vectors[left["id"]], vectors[right["id"]])
    return scores


def similarity(left_id: str, right_id: str, scores: dict[tuple[str, str], float]) -> float:
    if left_id == right_id:
        return 1.0
    return scores[tuple(sorted((left_id, right_id)))]


def similarity_matrix_for_records(
    records: list[dict[str, Any]],
    score_lookup: dict[tuple[str, str], float],
) -> list[list[float]]:
    return [
        [similarity(left["id"], right["id"], score_lookup) for right in records]
        for left in records
    ]


def edge_mean(
    edges: list[tuple[int, int]],
    occupied: list[dict[str, Any]],
    scores: dict[tuple[str, str], float],
) -> float:
    return statistics.fmean(similarity(occupied[left]["id"], occupied[right]["id"], scores) for left, right in edges)


def assignment_label(record: dict[str, Any]) -> str:
    hyakunin_id = record.get("hyakunin_id")
    hyakunin = f"H{int(hyakunin_id):03d}" if hyakunin_id else "Hnone"
    return f"{record['id']}/{hyakunin}/{record['poet_jp']}"


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
                "left": assignment_label(left_record),
                "right": assignment_label(right_record),
                "cosine_similarity": similarity(left_record["id"], right_record["id"], scores),
            }
        )
    return {
        "top": sorted(rows, key=lambda item: item["cosine_similarity"], reverse=True)[:limit],
        "bottom": sorted(rows, key=lambda item: item["cosine_similarity"])[:limit],
    }


def analyze(records: list[dict[str, Any]], trials: int) -> dict[str, Any]:
    vectors = {record["id"]: unit(record["embedding"]) for record in records}
    similarity_cache = build_similarity_cache(records, vectors)
    common_by_hyakunin = {
        int(record["hyakunin_id"]): record
        for record in records
        if record.get("hyakunin_id")
    }
    missing_ogura_ids = [hyakunin_id for hyakunin_id in range(1, 101) if hyakunin_id not in common_by_hyakunin]
    shuka_only = [record for record in records if not record.get("hyakunin_id")]
    rows: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    random_cache: dict[tuple[str, int], list[float]] = {}
    canonical_cells = row_major(GRID_SIZE)
    canonical_orthogonal = cell_edges(canonical_cells, include_diagonal=False)
    canonical_eight = cell_edges(canonical_cells, include_diagonal=True)
    permutations = random_layout_permutations(GRID_SIZE * GRID_SIZE, trials, RANDOM_SEED)

    for layout_name, layout_fn in LAYOUTS.items():
        cells_by_ogura_order = {ogura_id: cell for ogura_id, cell in enumerate(layout_fn(GRID_SIZE), start=1)}
        empty_cells = [cells_by_ogura_order[ogura_id] for ogura_id in missing_ogura_ids]
        canonical_cells = layout_fn(GRID_SIZE)
        canonical_index = {cell: index for index, cell in enumerate(canonical_cells)}
        orthogonal_edges = cell_edges(canonical_cells, include_diagonal=False)
        eight_edges = cell_edges(canonical_cells, include_diagonal=True)

        for omitted in shuka_only:
            fillers = [record for record in shuka_only if record["id"] != omitted["id"]]
            for perm_index, filler_order in enumerate(itertools.permutations(fillers)):
                occupied_by_cell: dict[Cell, dict[str, Any]] = {}
                for ogura_id, record in common_by_hyakunin.items():
                    occupied_by_cell[cells_by_ogura_order[ogura_id]] = record
                assignment = []
                for ogura_id, cell, filler in zip(missing_ogura_ids, empty_cells, filler_order, strict=True):
                    occupied_by_cell[cell] = filler
                    assignment.append(
                        {
                            "ogura_empty_id": ogura_id,
                            "cell": cell,
                            "filler": assignment_label(filler),
                        }
                    )
                occupied = [occupied_by_cell[cell] for cell in canonical_cells]
                if len(occupied) != GRID_SIZE * GRID_SIZE:
                    raise ValueError("shared grid assignment did not fill all cells")
                orth_mean = edge_mean(orthogonal_edges, occupied, similarity_cache)
                eight_mean = edge_mean(eight_edges, occupied, similarity_cache)
                orth_random_key = (omitted["id"], len(orthogonal_edges))
                eight_random_key = (omitted["id"], len(eight_edges))
                if orth_random_key not in random_cache:
                    selected_sim = similarity_matrix_for_records(occupied, similarity_cache)
                    random_cache[orth_random_key] = random_layout_samples(
                        selected_sim, canonical_orthogonal, permutations
                    )
                if eight_random_key not in random_cache:
                    selected_sim = similarity_matrix_for_records(occupied, similarity_cache)
                    random_cache[eight_random_key] = random_layout_samples(
                        selected_sim, canonical_eight, permutations
                    )
                row = {
                    "layout": layout_name,
                    "omitted": assignment_label(omitted),
                    "assignment": assignment,
                    "orthogonal_neighbors": {
                        "edge_count": len(orthogonal_edges),
                        **compare_to_samples(orth_mean, random_cache[orth_random_key]),
                    },
                    "eight_neighbors": {
                        "edge_count": len(eight_edges),
                        **compare_to_samples(eight_mean, random_cache[eight_random_key]),
                    },
                }
                key = f"{layout_name}__omit_{omitted['id']}__perm_{perm_index}"
                row["key"] = key
                details[key] = {
                    "orthogonal": edge_details(orthogonal_edges, occupied, similarity_cache),
                    "eight": edge_details(eight_edges, occupied, similarity_cache),
                }
                rows.append(row)

    return {
        "meta": {
            "method": "shared 10x10 cell constraint: common Shuka poems fixed to Ogura cell positions",
            "common_count": len(common_by_hyakunin),
            "shuka_only_count": len(shuka_only),
            "missing_ogura_ids": missing_ogura_ids,
            "shuka_only": [assignment_label(record) for record in shuka_only],
            "layout_names": list(LAYOUTS),
            "random_baseline": "randomly permute each selected 100-poem set across a fixed 10x10 grid",
            "random_trials": trials,
            "random_seed": RANDOM_SEED,
            "text_policy": "private embeddings and private Shuka text are not published",
        },
        "top_orthogonal": sorted(
            rows,
            key=lambda item: item["orthogonal_neighbors"]["z_score"] or float("-inf"),
            reverse=True,
        )[:24],
        "top_eight": sorted(
            rows,
            key=lambda item: item["eight_neighbors"]["z_score"] or float("-inf"),
            reverse=True,
        )[:24],
        "all": rows,
        "details": details,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--embeddings",
        type=Path,
        default=ROOT / "_private/literature/embeddings/hyakunin_shuka_mizugaki_text-embedding-3-small.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "_private/literature/records/hyakunin_shared_cell_10x10_analysis_small.json",
    )
    parser.add_argument("--random-trials", type=int, default=10_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = read_json(args.embeddings)
    records = sorted(payload["records"], key=lambda item: int(item["shuka_order"]))
    result = analyze(records, args.random_trials)
    result["meta"]["model"] = payload["meta"].get("model")
    result["meta"]["input_mode"] = payload["meta"].get("input_mode")
    result["meta"]["record_count"] = len(records)
    result["meta"]["vector_dimension"] = len(records[0]["embedding"]) if records else 0
    write_json(args.output, result)
    print(f"wrote private shared-cell analysis to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
