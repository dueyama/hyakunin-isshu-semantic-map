#!/usr/bin/env python3
"""Private exploratory 10x10 layout analysis for Hyakunin Shuka.

This script tests simple reproducible 10x10 placement models. It does not claim
to reconstruct any specific manuscript or Setoguchi's full argument.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
RANDOM_SEED = 20260702
GRID_SIZE = 10


Cell = tuple[int, int]
LayoutFn = Callable[[int], list[Cell]]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def unit(vector: list[float]) -> list[float]:
    length = math.sqrt(dot(vector, vector))
    if length == 0:
        return vector
    return [value / length for value in vector]


def similarity_matrix(records: list[dict[str, Any]]) -> list[list[float]]:
    vectors = [unit(record["embedding"]) for record in records]
    size = len(vectors)
    sim = [[0.0] * size for _ in range(size)]
    for i in range(size):
        sim[i][i] = 1.0
        for j in range(i + 1, size):
            score = dot(vectors[i], vectors[j])
            sim[i][j] = score
            sim[j][i] = score
    return sim


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
        diagonal = [
            (row, total - row)
            for row in range(size)
            if 0 <= total - row < size
        ]
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


LAYOUTS: dict[str, LayoutFn] = {
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
            neighbor = (row + row_delta, col + col_delta)
            other = index_by_cell.get(neighbor)
            if other is not None:
                edges.append((index, other))
    return edges


def edge_mean(edges: list[tuple[int, int]], indexes: list[int], sim: list[list[float]]) -> float:
    return statistics.fmean(sim[indexes[left]][indexes[right]] for left, right in edges)


def all_pair_scores(indexes: list[int], sim: list[list[float]]) -> list[float]:
    scores: list[float] = []
    for offset, left in enumerate(indexes):
        for right in indexes[offset + 1 :]:
            scores.append(sim[left][right])
    return scores


def random_samples(scores: list[float], sample_size: int, trials: int) -> list[float]:
    rng = random.Random(RANDOM_SEED + sample_size + len(scores))
    values: list[float] = []
    for _ in range(trials):
        values.append(statistics.fmean(rng.sample(scores, sample_size)))
    return values


def percentile(value: float, samples: list[float]) -> float:
    return sum(1 for sample in samples if sample <= value) / len(samples)


def compare_to_random(value: float, samples: list[float]) -> dict[str, float | None]:
    random_mean = statistics.fmean(samples)
    random_sd = statistics.pstdev(samples)
    return {
        "mean": value,
        "random_mean": random_mean,
        "random_sd": random_sd,
        "z_score": (value - random_mean) / random_sd if random_sd else None,
        "percentile": percentile(value, samples),
    }


def omitted_label(record: dict[str, Any]) -> str:
    hyakunin = record.get("hyakunin_id")
    if hyakunin is None:
        hyakunin_part = "none"
    else:
        hyakunin_part = str(hyakunin)
    return f"S{int(record['shuka_order']):03d}/H{hyakunin_part}/{record['poet_jp']}"


def score_configuration(
    records: list[dict[str, Any]],
    sim: list[list[float]],
    layout_name: str,
    omitted_index: int,
    trials: int,
) -> dict[str, Any]:
    kept = [index for index in range(len(records)) if index != omitted_index]
    cells = LAYOUTS[layout_name](GRID_SIZE)
    orthogonal_edges = cell_edges(cells, include_diagonal=False)
    eight_edges = cell_edges(cells, include_diagonal=True)
    pair_scores = all_pair_scores(kept, sim)
    orthogonal_random = random_samples(pair_scores, len(orthogonal_edges), trials)
    eight_random = random_samples(pair_scores, len(eight_edges), trials)
    return {
        "layout": layout_name,
        "omitted_index": omitted_index,
        "omitted": {
            "shuka_order": records[omitted_index]["shuka_order"],
            "hyakunin_id": records[omitted_index].get("hyakunin_id"),
            "poet_jp": records[omitted_index]["poet_jp"],
            "label": omitted_label(records[omitted_index]),
        },
        "orthogonal_neighbors": {
            "edge_count": len(orthogonal_edges),
            **compare_to_random(edge_mean(orthogonal_edges, kept, sim), orthogonal_random),
        },
        "eight_neighbors": {
            "edge_count": len(eight_edges),
            **compare_to_random(edge_mean(eight_edges, kept, sim), eight_random),
        },
    }


def analyze(records: list[dict[str, Any]], trials: int) -> dict[str, Any]:
    sim = similarity_matrix(records)
    configurations: list[dict[str, Any]] = []
    for layout_name in LAYOUTS:
        for omitted_index in range(len(records)):
            configurations.append(score_configuration(records, sim, layout_name, omitted_index, trials))

    def sort_key_orthogonal(item: dict[str, Any]) -> float:
        return item["orthogonal_neighbors"]["z_score"] or float("-inf")

    def sort_key_eight(item: dict[str, Any]) -> float:
        return item["eight_neighbors"]["z_score"] or float("-inf")

    fixed_omissions = {0, 52, 72, 75, 89, 100}
    fixed_results = [
        item
        for item in configurations
        if item["omitted_index"] in fixed_omissions
    ]

    return {
        "meta": {
            "method": "exploratory 10x10 placement analysis using private Hyakunin Shuka embeddings",
            "grid_size": GRID_SIZE,
            "layout_names": list(LAYOUTS),
            "random_baseline": "sample same number of unordered poem pairs from the same 100 kept poems",
            "random_trials": trials,
            "random_seed": RANDOM_SEED,
            "record_count": len(records),
            "text_policy": "do not publish private source text or vectors",
            "caveat": "best over all omissions is hypothesis-generating and selection-biased",
        },
        "top_orthogonal": sorted(configurations, key=sort_key_orthogonal, reverse=True)[:20],
        "top_eight_neighbor": sorted(configurations, key=sort_key_eight, reverse=True)[:20],
        "fixed_omission_checks": sorted(
            fixed_results,
            key=lambda item: (item["omitted"]["shuka_order"], item["layout"]),
        ),
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
        default=ROOT / "_private/literature/records/hyakunin_shuka_10x10_layout_analysis_small.json",
    )
    parser.add_argument("--random-trials", type=int, default=1_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = read_json(args.embeddings)
    records = sorted(payload["records"], key=lambda item: int(item["shuka_order"]))
    result = analyze(records, args.random_trials)
    result["meta"]["model"] = payload["meta"].get("model")
    result["meta"]["input_mode"] = payload["meta"].get("input_mode")
    result["meta"]["vector_dimension"] = len(records[0]["embedding"]) if records else 0
    write_json(args.output, result)
    print(f"wrote private layout analysis to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
