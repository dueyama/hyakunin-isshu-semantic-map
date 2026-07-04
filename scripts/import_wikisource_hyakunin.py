#!/usr/bin/env python3
"""Import Ogura Hyakunin Isshu rows from a saved Wikisource raw wikitext file."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIKISOURCE_URL = (
    "https://ja.wikisource.org/wiki/"
    "%E5%B0%8F%E5%80%89%E7%99%BE%E4%BA%BA%E4%B8%80%E9%A6%96"
)
WIKISOURCE_OLDID = "240235"

ANTHOLOGIES = [
    "新古今集",
    "後拾遺集",
    "新勅撰集",
    "続後撰集",
    "後撰集",
    "拾遺集",
    "古今集",
    "金葉集",
    "詞花集",
    "千載集",
]

KANJI_DIGITS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def strip_wiki_markup(value: str) -> str:
    text = value
    text = text.replace("<br />", "\n").replace("<br/>", "\n")
    text = text.replace("'''", "")
    text = re.sub(r"\[\[[^|\]]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    return text.strip()


def cell_payload(line: str) -> str:
    stripped = line.lstrip("|!")
    if "|" not in stripped:
        return stripped.strip()
    return stripped.split("|", 1)[1].strip()


def kanji_number(value: str) -> int:
    if value == "百":
        return 100
    if "十" not in value:
        return KANJI_DIGITS[value]
    left, _, right = value.partition("十")
    tens = KANJI_DIGITS[left] if left else 1
    ones = KANJI_DIGITS[right] if right else 0
    return tens * 10 + ones


def split_poem_cell(value: str) -> tuple[str, str, str, str]:
    text = strip_wiki_markup(value)
    if "（" not in text:
        original = text
        kana = ""
    else:
        original, rest = text.split("（", 1)
        kana = rest.rsplit("）", 1)[0]
    original_lines = [line.strip() for line in original.splitlines() if line.strip()]
    kana_lines = [line.strip() for line in kana.splitlines() if line.strip()]
    kami = original_lines[0] if original_lines else ""
    shimo = original_lines[1] if len(original_lines) > 1 else ""
    waka_original = " ".join(original_lines)
    waka_kana = " ".join(kana_lines)
    return waka_original, waka_kana, kami, shimo


def split_author_cell(value: str) -> tuple[str, str]:
    text = strip_wiki_markup(value)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    poet = lines[0] if lines else ""
    kana = ""
    if len(lines) > 1:
        kana = lines[1].strip("（）")
    return poet, kana


def split_source_cell(value: str) -> tuple[str, str, str]:
    text = strip_wiki_markup(value).replace(" ", "")
    match = re.match(r"(.+?)(\d+)$", text)
    if match:
        prefix = match.group(1)
        number = match.group(2)
    else:
        prefix = text
        number = ""
    anthology = ""
    book = prefix
    for candidate in ANTHOLOGIES:
        if prefix.startswith(candidate):
            anthology = candidate
            book = prefix[len(candidate) :]
            break
    return anthology, book, number


def infer_tags(source_book: str) -> tuple[str, str]:
    themes: list[str] = []
    seasons: list[str] = []
    for season in ["春", "夏", "秋", "冬"]:
        if season in source_book and season not in seasons:
            seasons.append(season)
            themes.append(season)
    mappings = [
        ("恋", "恋"),
        ("雑", "雑"),
        ("羇旅", "羇旅"),
        ("離別", "離別"),
        ("哀傷", "哀傷"),
        ("神祇", "神祇"),
        ("釈教", "釈教"),
    ]
    for marker, tag in mappings:
        if marker in source_book and tag not in themes:
            themes.append(tag)
    return ";".join(themes), ";".join(seasons)


def parse_rows(raw_text: str) -> list[dict[str, str]]:
    lines = raw_text.splitlines()
    rows: list[dict[str, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not (line.startswith("!style=") and "<span id=" in line):
            index += 1
            continue
        number_text = strip_wiki_markup(cell_payload(line))
        poem_cell = cell_payload(lines[index + 1])
        author_cell = cell_payload(lines[index + 2])
        source_cell = cell_payload(lines[index + 3])
        waka_original, waka_kana, kami, shimo = split_poem_cell(poem_cell)
        poet_jp, poet_kana = split_author_cell(author_cell)
        anthology, source_book, source_number = split_source_cell(source_cell)
        theme, season = infer_tags(source_book)
        rows.append(
            {
                "id": str(kanji_number(number_text)),
                "poet_jp": poet_jp,
                "poet_kana": poet_kana,
                "waka_original": waka_original,
                "waka_kana": waka_kana,
                "kami_no_ku": kami,
                "shimo_no_ku": shimo,
                "source_anthology": anthology,
                "source_book": source_book,
                "source_number": source_number,
                "theme": theme,
                "season": season,
                "notes": (
                    "Initial candidate imported from Japanese Wikisource "
                    f"oldid {WIKISOURCE_OLDID}; CC BY-SA 3.0; verify against "
                    "scholarly editions and source anthologies."
                ),
            }
        )
        index += 1
    return sorted(rows, key=lambda row: int(row["id"]))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
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
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True, help="Saved Wikisource raw wikitext.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/hyakunin_isshu.csv",
        help="Output CSV path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    rows = parse_rows(args.raw.read_text(encoding="utf-8"))
    if len(rows) != 100:
        print(f"ERROR expected 100 rows, found {len(rows)}", file=sys.stderr)
        return 1
    write_csv(args.output, rows)
    print(f"wrote {len(rows)} rows to {args.output}")
    print(f"source: {WIKISOURCE_URL} oldid {WIKISOURCE_OLDID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
