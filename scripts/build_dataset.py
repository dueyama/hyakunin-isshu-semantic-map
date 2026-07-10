#!/usr/bin/env python3
"""Create and validate the initial CSV data skeletons."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCHEMAS: dict[str, list[str]] = {
    "data/hyakunin_isshu.csv": [
        "id",
        "poet_jp",
        "poet_kana",
        "waka_original",
        "waka_kana",
        "kami_no_ku",
        "shimo_no_ku",
        "source_anthology",
        "source_book",
        "source_number",
        "theme",
        "season",
        "notes",
    ],
    "data/hyakunin_shuka.csv": [
        "shuka_order",
        "hyakunin_id",
        "poet_jp",
        "waka_original",
        "waka_kana",
        "notes",
        "variant_group",
    ],
    "data/metadata_poets.csv": [
        "hyakunin_id",
        "poet_jp",
        "period",
        "approx_year",
        "birth_year",
        "death_year",
        "status",
        "gender",
        "lineage",
        "notes",
    ],
}


def ensure_csv(path: Path, fieldnames: list[str]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def validate_file(path: Path, required: list[str]) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"missing file: {path}"]
    fieldnames, rows = read_rows(path)
    missing = [name for name in required if name not in fieldnames]
    if missing:
        errors.append(f"{path}: missing columns: {', '.join(missing)}")
    if path.name == "hyakunin_isshu.csv" and rows:
        ids: list[int] = []
        for index, row in enumerate(rows, start=2):
            raw_id = (row.get("id") or "").strip()
            if not raw_id:
                errors.append(f"{path}:{index}: missing id")
                continue
            try:
                ids.append(int(raw_id))
            except ValueError:
                errors.append(f"{path}:{index}: non-integer id {raw_id!r}")
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            errors.append(f"{path}: duplicate ids: {duplicates}")
        outside = [item for item in ids if item < 1 or item > 100]
        if outside:
            errors.append(f"{path}: ids outside 1..100: {outside}")
    return errors


def report() -> int:
    exit_code = 0
    for relative, columns in SCHEMAS.items():
        path = ROOT / relative
        errors = validate_file(path, columns)
        if errors:
            exit_code = 1
            for error in errors:
                print(f"ERROR {error}", file=sys.stderr)
            continue
        _fieldnames, rows = read_rows(path)
        if not rows:
            print(f"SCHEMA-ONLY {relative}: 0 data rows (public placeholder)")
        else:
            print(f"OK {relative}: {len(rows)} data rows")
    return exit_code


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", action="store_true", help="Create missing CSV files.")
    parser.add_argument("--check", action="store_true", help="Validate CSV files.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.init:
        for relative, columns in SCHEMAS.items():
            ensure_csv(ROOT / relative, columns)
    return report()


if __name__ == "__main__":
    raise SystemExit(main())
