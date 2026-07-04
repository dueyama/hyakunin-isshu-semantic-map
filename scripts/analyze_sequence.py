#!/usr/bin/env python3
"""Compute tag-based sequence diagnostics before embeddings are available."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def split_tags(value: str) -> set[str]:
    if not value:
        return set()
    normalized = value.replace("、", ";").replace("，", ";").replace(",", ";")
    normalized = normalized.replace("|", ";").replace("/", ";")
    return {item.strip() for item in normalized.split(";") if item.strip()}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return len(left & right) / len(left | right)


def row_tags(row: dict[str, str]) -> set[str]:
    return split_tags(row.get("theme", "")) | split_tags(row.get("season", ""))


def int_or_none(value: str) -> int | None:
    try:
        return int((value or "").strip())
    except ValueError:
        return None


def analyze(rows: list[dict[str, str]]) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: int_or_none(row.get("id", "")) or 10_000)
    pairs: list[dict[str, Any]] = []
    for left, right in zip(rows, rows[1:]):
        left_tags = row_tags(left)
        right_tags = row_tags(right)
        pairs.append(
            {
                "left_id": int_or_none(left.get("id", "")),
                "right_id": int_or_none(right.get("id", "")),
                "left_poet": left.get("poet_jp", ""),
                "right_poet": right.get("poet_jp", ""),
                "tag_jaccard": jaccard(left_tags, right_tags),
                "shared_tags": sorted(left_tags & right_tags),
                "left_only_tags": sorted(left_tags - right_tags),
                "right_only_tags": sorted(right_tags - left_tags),
            }
        )
    scores = [pair["tag_jaccard"] for pair in pairs]
    return {
        "meta": {
            "method": "theme/season tag Jaccard; pre-embedding diagnostic",
            "poem_count": len(rows),
            "pair_count": len(pairs),
        },
        "summary": {
            "mean": statistics.fmean(scores) if scores else None,
            "median": statistics.median(scores) if scores else None,
            "max": max(scores) if scores else None,
            "min": min(scores) if scores else None,
        },
        "pairs": pairs,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/hyakunin_isshu.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/adjacency_stats.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = analyze(read_csv(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {payload['meta']['pair_count']} pairs to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
