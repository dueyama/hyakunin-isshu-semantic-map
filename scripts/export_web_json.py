#!/usr/bin/env python3
"""Export a conservative public JSON snapshot for the web app.

By default, poem text is omitted until source and license review is complete.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def split_tags(value: str) -> list[str]:
    if not value:
        return []
    normalized = value.replace("、", ";").replace("，", ";").replace(",", ";")
    normalized = normalized.replace("|", ";").replace("/", ";")
    return [item.strip() for item in normalized.split(";") if item.strip()]


def int_or_none(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def poet_metadata(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {
        (row.get("hyakunin_id") or "").strip(): row
        for row in rows
        if (row.get("hyakunin_id") or "").strip()
    }


def shuka_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        hyakunin_id = (row.get("hyakunin_id") or "").strip()
        if not hyakunin_id:
            continue
        lookup[hyakunin_id] = {
            "shuka_order": int_or_none(row.get("shuka_order", "")),
            "variant_group": (row.get("variant_group") or "").strip() or None,
            "notes": (row.get("notes") or "").strip() or None,
        }
    return lookup


def poem_record(
    row: dict[str, str],
    metadata: dict[str, str] | None,
    shuka: dict[str, Any] | None,
    include_text: bool,
) -> dict[str, Any]:
    poem_id = (row.get("id") or "").strip()
    record: dict[str, Any] = {
        "id": int_or_none(poem_id),
        "poet_jp": (row.get("poet_jp") or "").strip(),
        "poet_kana": (row.get("poet_kana") or "").strip(),
        "source": {
            "anthology": (row.get("source_anthology") or "").strip() or None,
            "book": (row.get("source_book") or "").strip() or None,
            "number": (row.get("source_number") or "").strip() or None,
        },
        "theme": split_tags(row.get("theme", "")),
        "season": split_tags(row.get("season", "")),
        "notes": (row.get("notes") or "").strip() or None,
        "shuka": shuka,
    }
    if metadata:
        record["poet_metadata"] = {
            "period": (metadata.get("period") or "").strip() or None,
            "approx_year": (metadata.get("approx_year") or "").strip() or None,
            "birth_year": (metadata.get("birth_year") or "").strip() or None,
            "death_year": (metadata.get("death_year") or "").strip() or None,
            "status": (metadata.get("status") or "").strip() or None,
            "gender": (metadata.get("gender") or "").strip() or None,
            "lineage": (metadata.get("lineage") or "").strip() or None,
        }
    if include_text:
        record["text"] = {
            "waka_original": (row.get("waka_original") or "").strip(),
            "waka_kana": (row.get("waka_kana") or "").strip(),
            "kami_no_ku": (row.get("kami_no_ku") or "").strip(),
            "shimo_no_ku": (row.get("shimo_no_ku") or "").strip(),
        }
    else:
        record["text_status"] = "omitted_pending_source_license_review"
    return record


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poems", type=Path, default=ROOT / "data/hyakunin_isshu.csv")
    parser.add_argument("--poets", type=Path, default=ROOT / "data/metadata_poets.csv")
    parser.add_argument("--shuka", type=Path, default=ROOT / "data/hyakunin_shuka.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/poems.json")
    text_group = parser.add_mutually_exclusive_group()
    text_group.add_argument("--include-text", action="store_true")
    text_group.add_argument("--omit-text", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    include_text = bool(args.include_text and not args.omit_text)
    poem_rows = read_csv(args.poems)
    metadata = poet_metadata(read_csv(args.poets))
    shuka = shuka_lookup(read_csv(args.shuka))
    poems = [
        poem_record(
            row,
            metadata.get((row.get("id") or "").strip()),
            shuka.get((row.get("id") or "").strip()),
            include_text,
        )
        for row in poem_rows
    ]
    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "include_text": include_text,
            "row_count": len(poems),
            "source_policy": "Poem text is omitted by default until source license review is complete.",
        },
        "poems": poems,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(poems)} poems to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
