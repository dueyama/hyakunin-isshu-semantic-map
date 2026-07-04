#!/usr/bin/env python3
"""Normalize waka text for analysis while preserving source columns.

The normalizer is intentionally conservative. It prepares analysis columns, but
does not modernize historical kana or rewrite source text.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path


PUNCTUATION_RE = re.compile(
    r"[\s\u3000、。，．,.・:：;；!！?？"
    r"「」『』（）()\[\]［］【】〔〕〈〉《》"
    r"“”\"'`´]"
)


def normalize_text(value: str) -> str:
    """Return a compact analysis form without changing historical kana."""
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = PUNCTUATION_RE.sub("", text)
    return text.strip()


def build_embedding_text(row: dict[str, str], mode: str) -> str:
    original = normalize_text(row.get("waka_original", ""))
    kana = normalize_text(row.get("waka_kana", ""))
    theme = (row.get("theme", "") or "").strip()
    season = (row.get("season", "") or "").strip()
    notes = (row.get("notes", "") or "").strip()

    parts: list[str] = []
    if mode in {"original", "original_kana", "original_tags", "all"} and original:
        parts.append(original)
    if mode in {"kana", "original_kana", "all"} and kana:
        parts.append(kana)
    if mode in {"original_tags", "all"}:
        if theme:
            parts.append(f"theme: {theme}")
        if season:
            parts.append(f"season: {season}")
    if mode == "all" and notes:
        parts.append(f"notes: {notes}")
    return "\n".join(parts)


def normalize_row(row: dict[str, str], mode: str) -> dict[str, str]:
    output = dict(row)
    output["normalized_original"] = normalize_text(row.get("waka_original", ""))
    output["normalized_kana"] = normalize_text(row.get("waka_kana", ""))
    output["embedding_text"] = build_embedding_text(row, mode)
    return output


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/hyakunin_isshu.csv"),
        help="Input CSV path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/hyakunin_isshu.normalized.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--mode",
        choices=["original", "kana", "original_kana", "original_tags", "all"],
        default="original_tags",
        help="Embedding text composition mode.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    rows = read_csv(args.input)
    normalized = [normalize_row(row, args.mode) for row in rows]
    write_csv(args.output, normalized)
    print(f"wrote {len(normalized)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
