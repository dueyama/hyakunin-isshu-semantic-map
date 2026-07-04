#!/usr/bin/env python3
"""Compare Ogura Hyakunin Isshu order with Hyakunin Shuka order."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def int_or_none(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def compare(ogura_rows: list[dict[str, str]], shuka_rows: list[dict[str, str]]) -> dict[str, Any]:
    ogura_by_id = {
        (row.get("id") or "").strip(): row
        for row in ogura_rows
        if (row.get("id") or "").strip()
    }
    linked: list[dict[str, Any]] = []
    variants: list[dict[str, Any]] = []
    for row in shuka_rows:
        shuka_order = int_or_none(row.get("shuka_order", ""))
        hyakunin_id = (row.get("hyakunin_id") or "").strip()
        if not hyakunin_id:
            variants.append(
                {
                    "shuka_order": shuka_order,
                    "poet_jp": (row.get("poet_jp") or "").strip(),
                    "variant_group": (row.get("variant_group") or "").strip() or None,
                    "notes": (row.get("notes") or "").strip() or None,
                }
            )
            continue
        ogura_order = int_or_none(hyakunin_id)
        ogura = ogura_by_id.get(hyakunin_id, {})
        linked.append(
            {
                "hyakunin_id": ogura_order,
                "shuka_order": shuka_order,
                "order_delta": (
                    shuka_order - ogura_order
                    if shuka_order is not None and ogura_order is not None
                    else None
                ),
                "poet_jp": (row.get("poet_jp") or ogura.get("poet_jp") or "").strip(),
                "variant_group": (row.get("variant_group") or "").strip() or None,
                "notes": (row.get("notes") or "").strip() or None,
            }
        )
    linked_sorted = sorted(
        linked,
        key=lambda item: abs(item["order_delta"]) if item["order_delta"] is not None else -1,
        reverse=True,
    )
    return {
        "meta": {
            "method": "order difference shuka_order - ogura_order",
            "linked_count": len(linked),
            "variant_count": len(variants),
        },
        "largest_moves": linked_sorted[:20],
        "linked": linked,
        "variants": variants,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ogura", type=Path, default=ROOT / "data/hyakunin_isshu.csv")
    parser.add_argument("--shuka", type=Path, default=ROOT / "data/hyakunin_shuka.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/order_comparison.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = compare(read_csv(args.ogura), read_csv(args.shuka))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote order comparison to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
