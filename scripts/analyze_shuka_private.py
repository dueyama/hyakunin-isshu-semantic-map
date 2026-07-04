#!/usr/bin/env python3
"""Private Hyakunin Shuka embedding and order analysis.

This script intentionally writes caches and detailed outputs under _private/.
It is for local research notes only until source and license questions are
settled.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from normalize_waka import normalize_text


ROOT = Path(__file__).resolve().parents[1]
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
RANDOM_SEED = 20260702


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def int_or_none(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def build_records(rows: list[dict[str, str]], model: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        order = int(row["shuka_order"])
        text = normalize_text(row.get("waka_original", ""))
        records.append(
            {
                "id": f"S{order:03d}",
                "shuka_order": order,
                "hyakunin_id": int_or_none(row.get("hyakunin_id", "")),
                "poet_jp": (row.get("poet_jp") or "").strip(),
                "source_mark": (row.get("source_mark") or "").strip(),
                "variant_group": (row.get("variant_group") or "").strip(),
                "model": model,
                "input_mode": "shuka_waka_original_only",
                "text_sha256": sha256_text(text),
                "embedding_text": text,
            }
        )
    return records


def cache_matches(existing: dict[str, Any] | None, records: list[dict[str, Any]], model: str) -> bool:
    if not existing:
        return False
    meta = existing.get("meta", {})
    if meta.get("model") != model:
        return False
    existing_records = existing.get("records", [])
    if len(existing_records) != len(records):
        return False
    for left, right in zip(existing_records, records):
        if left.get("id") != right["id"]:
            return False
        if left.get("text_sha256") != right["text_sha256"]:
            return False
        if not left.get("embedding"):
            return False
    return True


def request_embeddings(texts: list[str], model: str, api_key: str) -> list[list[float]]:
    body = json.dumps({"model": model, "input": texts}).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_EMBEDDINGS_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        print(f"OpenAI API error {error.code}: {detail}", file=sys.stderr)
        raise
    data = sorted(payload.get("data", []), key=lambda item: item["index"])
    return [item["embedding"] for item in data]


def embed_records(records: list[dict[str, Any]], model: str, cache_path: Path, batch_size: int) -> dict[str, Any]:
    existing = read_json(cache_path) if cache_path.exists() else None
    if cache_matches(existing, records, model):
        print(f"cache is current: {cache_path}")
        return existing
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not available in the environment.")

    output_records: list[dict[str, Any]] = []
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        vectors = request_embeddings([record["embedding_text"] for record in batch], model, api_key)
        for record, vector in zip(batch, vectors):
            item = dict(record)
            item.pop("embedding_text", None)
            item["embedding"] = vector
            output_records.append(item)
        print(f"embedded {len(output_records)}/{len(records)} rows")

    payload = {
        "meta": {
            "model": model,
            "input_mode": "shuka_waka_original_only",
            "created_at_unix": int(time.time()),
            "record_count": len(output_records),
            "text_policy": "private Hyakunin Shuka embedding cache; do not publish vectors",
        },
        "records": output_records,
    }
    write_json(cache_path, payload)
    print(f"wrote private embedding cache to {cache_path}")
    return payload


def dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def normalize_vector(vector: list[float]) -> list[float]:
    length = math.sqrt(dot(vector, vector))
    if length == 0:
        return vector
    return [value / length for value in vector]


def similarity_matrix(records: list[dict[str, Any]]) -> list[list[float]]:
    vectors = [normalize_vector(record["embedding"]) for record in records]
    size = len(vectors)
    sim = [[0.0] * size for _ in range(size)]
    for i in range(size):
        sim[i][i] = 1.0
        for j in range(i + 1, size):
            score = dot(vectors[i], vectors[j])
            sim[i][j] = score
            sim[j][i] = score
    return sim


def mean_for_pairs(pairs: list[tuple[int, int]], sim: list[list[float]]) -> float:
    return statistics.fmean(sim[left][right] for left, right in pairs)


def percentile(value: float, samples: list[float]) -> float:
    return sum(1 for sample in samples if sample <= value) / len(samples)


def random_order_means(size: int, pair_count: int, sim: list[list[float]], trials: int) -> list[float]:
    rng = random.Random(RANDOM_SEED)
    values: list[float] = []
    order = list(range(size))
    for _ in range(trials):
        rng.shuffle(order)
        pairs = [(order[index], order[index + 1]) for index in range(pair_count)]
        values.append(mean_for_pairs(pairs, sim))
    return values


def stats_against_random(value: float, samples: list[float]) -> dict[str, float | None]:
    random_mean = statistics.fmean(samples)
    random_sd = statistics.pstdev(samples)
    return {
        "mean": value,
        "random_mean": random_mean,
        "random_sd": random_sd,
        "z_score": (value - random_mean) / random_sd if random_sd else None,
        "percentile": percentile(value, samples),
    }


def pair_descriptor(left: dict[str, Any], right: dict[str, Any], score: float) -> dict[str, Any]:
    return {
        "left_shuka_order": left["shuka_order"],
        "right_shuka_order": right["shuka_order"],
        "left_hyakunin_id": left.get("hyakunin_id"),
        "right_hyakunin_id": right.get("hyakunin_id"),
        "left_poet": left["poet_jp"],
        "right_poet": right["poet_jp"],
        "cosine_similarity": score,
        "cosine_distance": 1 - score,
    }


def adjacent_pairs(records: list[dict[str, Any]], sim: list[list[float]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index in range(len(records) - 1):
        output.append(pair_descriptor(records[index], records[index + 1], sim[index][index + 1]))
    return output


def nearest_neighbors(records: list[dict[str, Any]], sim: list[list[float]], target_index: int, limit: int = 8) -> list[dict[str, Any]]:
    target = records[target_index]
    scored: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if index == target_index:
            continue
        scored.append(
            {
                "target_shuka_order": target["shuka_order"],
                "target_poet": target["poet_jp"],
                "neighbor_shuka_order": record["shuka_order"],
                "neighbor_hyakunin_id": record.get("hyakunin_id"),
                "neighbor_poet": record["poet_jp"],
                "cosine_similarity": sim[target_index][index],
            }
        )
    return sorted(scored, key=lambda item: item["cosine_similarity"], reverse=True)[:limit]


def analyze(records: list[dict[str, Any]], sim: list[list[float]], trials: int) -> dict[str, Any]:
    size = len(records)
    adjacent_index_pairs = [(index, index + 1) for index in range(size - 1)]
    odd_even_pairs = [(index, index + 1) for index in range(0, size - 1, 2)]
    even_odd_pairs = [(index, index + 1) for index in range(1, size - 1, 2)]
    adjacent = adjacent_pairs(records, sim)

    adjacent_random = random_order_means(size, len(adjacent_index_pairs), sim, trials)
    odd_even_random = random_order_means(size, len(odd_even_pairs), sim, trials)
    even_odd_random = random_order_means(size, len(even_odd_pairs), sim, trials)

    shuka_only_indexes = [
        index
        for index, record in enumerate(records)
        if not record.get("hyakunin_id") or record.get("variant_group") == "shuka_only"
    ]

    return {
        "meta": {
            "method": "private full Hyakunin Shuka embedding analysis",
            "random_trials": trials,
            "random_seed": RANDOM_SEED,
            "record_count": size,
            "input_mode": "shuka_waka_original_only",
            "text_policy": "public notes must not include poem text from private source",
        },
        "sequence": {
            "adjacent": {
                "pair_count": len(adjacent_index_pairs),
                **stats_against_random(mean_for_pairs(adjacent_index_pairs, sim), adjacent_random),
            },
            "odd_even_pairs": {
                "pair_count": len(odd_even_pairs),
                **stats_against_random(mean_for_pairs(odd_even_pairs, sim), odd_even_random),
            },
            "even_odd_offset_pairs": {
                "pair_count": len(even_odd_pairs),
                **stats_against_random(mean_for_pairs(even_odd_pairs, sim), even_odd_random),
            },
        },
        "top_similar_adjacent": sorted(adjacent, key=lambda item: item["cosine_similarity"], reverse=True)[:12],
        "largest_jumps": sorted(adjacent, key=lambda item: item["cosine_similarity"])[:12],
        "shuka_only_or_replacement_neighbors": [
            {
                "target": {
                    "shuka_order": records[index]["shuka_order"],
                    "hyakunin_id": records[index].get("hyakunin_id"),
                    "poet_jp": records[index]["poet_jp"],
                    "variant_group": records[index].get("variant_group"),
                },
                "nearest": nearest_neighbors(records, sim, index),
            }
            for index in shuka_only_indexes
        ],
        "terminal_adjacent_pairs": [
            pair for pair in adjacent if pair["left_shuka_order"] >= max(1, size - 8)
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--shuka",
        type=Path,
        default=ROOT / "_private/literature/records/hyakunin_shuka_mizugaki_provisional.csv",
    )
    parser.add_argument("--model", default="text-embedding-3-small")
    parser.add_argument(
        "--cache",
        type=Path,
        default=ROOT / "_private/literature/embeddings/hyakunin_shuka_mizugaki_text-embedding-3-small.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "_private/literature/records/hyakunin_shuka_full_embedding_analysis_small.json",
    )
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--random-trials", type=int, default=10_000)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = sorted(read_csv(args.shuka), key=lambda row: int(row["shuka_order"]))
    records = build_records(rows, args.model)
    if args.dry_run:
        print(f"dry run: {len(records)} rows")
        return 0
    payload = embed_records(records, args.model, args.cache, args.batch_size)
    enriched = sorted(payload["records"], key=lambda item: int(item["shuka_order"]))
    sim = similarity_matrix(enriched)
    analysis = analyze(enriched, sim, args.random_trials)
    analysis["meta"]["model"] = payload["meta"].get("model")
    analysis["meta"]["vector_dimension"] = len(enriched[0]["embedding"]) if enriched else 0
    write_json(args.output, analysis)
    print(f"wrote private analysis to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
