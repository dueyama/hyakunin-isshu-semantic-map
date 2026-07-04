#!/usr/bin/env python3
"""Build chapter 3 overlap evidence for Shuka diagonal vs Ogura spiral."""

from __future__ import annotations

import csv
import json
from html import escape
from pathlib import Path
from typing import Any

from analyze_shuka_layout_private import GRID_SIZE, LAYOUTS, cell_edges


ROOT = Path(__file__).resolve().parents[1]
RECORD_DIR = ROOT / "_private" / "literature" / "records"
FIG_DIR = ROOT / "docs" / "figures"
OUT_JSON = RECORD_DIR / "hyakunin_layout_overlap_chapter3_small.json"
OUT_SVG = FIG_DIR / "chapter3-diagonal-spiral-overlap.svg"

SHUKA_CSV = RECORD_DIR / "hyakunin_shuka_mizugaki_provisional.csv"
OGURA_CSV = ROOT / "data" / "hyakunin_isshu.csv"
OGURA_LAYOUT_JSON = RECORD_DIR / "hyakunin_isshu_10x10_layout_analysis_small.json"

COLORS = {
    "paper": "#fbfaf7",
    "panel": "#fffdf8",
    "grid": "#ded6c9",
    "ink": "#202124",
    "muted": "#6f6a62",
    "plum": "#4b2447",
    "cinnabar": "#9a3f2f",
    "moss": "#526b55",
    "indigo": "#263c61",
    "blue": "#496f86",
    "gold": "#a77d35",
    "wash": "#f4f1ea",
}


def read_shuka() -> list[dict[str, Any]]:
    with SHUKA_CSV.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["shuka_order_i"] = int(row["shuka_order"])
        raw_id = (row.get("hyakunin_id") or "").strip()
        row["hyakunin_id_i"] = int(raw_id) if raw_id else None
    return sorted(rows, key=lambda item: item["shuka_order_i"])


def read_ogura() -> list[dict[str, Any]]:
    with OGURA_CSV.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["id_i"] = int(row["id"])
    return sorted(rows, key=lambda item: item["id_i"])


def edge_set(
    records: list[dict[str, Any]],
    id_key: str,
    layout_name: str,
    include_diagonal: bool,
    common_ids: set[int],
) -> set[tuple[int, int]]:
    cells = LAYOUTS[layout_name](GRID_SIZE)
    output: set[tuple[int, int]] = set()
    for left, right in cell_edges(cells, include_diagonal=include_diagonal):
        left_id = records[left][id_key]
        right_id = records[right][id_key]
        if left_id in common_ids and right_id in common_ids:
            output.add(tuple(sorted((left_id, right_id))))
    return output


def compare_edges(left: set[tuple[int, int]], right: set[tuple[int, int]], pair_space: int) -> dict[str, float | int]:
    intersection = left & right
    union = left | right
    expected = len(left) * len(right) / pair_space
    return {
        "intersection": len(intersection),
        "left_edges": len(left),
        "right_edges": len(right),
        "union": len(union),
        "overlap_left": len(intersection) / len(left) if left else 0,
        "jaccard": len(intersection) / len(union) if union else 0,
        "expected_random": expected,
        "ratio_to_random_pair_sets": len(intersection) / expected if expected else 0,
    }


def layout_label(layout_name: str) -> str:
    return {
        "row_major": "通常行型",
        "row_serpentine": "行つづら折り",
        "column_major": "通常列型",
        "column_serpentine": "列つづら折り",
        "diagonal_nw_se_serpentine": "斜めつづら折り",
        "diagonal_ne_sw_serpentine": "逆斜めつづら折り",
        "spiral_clockwise": "螺旋置き",
    }[layout_name]


def pair_label(pair: tuple[int, int], ogura_by_id: dict[int, dict[str, Any]]) -> str:
    left, right = pair
    return f"H{left:03d}-{right:03d} {ogura_by_id[left]['poet_jp']} / {ogura_by_id[right]['poet_jp']}"


def build_payload() -> dict[str, Any]:
    shuka = read_shuka()
    ogura = read_ogura()
    common_ids = {
        row["hyakunin_id_i"]
        for row in shuka
        if row["hyakunin_id_i"] is not None
    } & {row["id_i"] for row in ogura}
    pair_space = len(common_ids) * (len(common_ids) - 1) // 2

    ogura_by_id = {row["id_i"]: row for row in ogura}
    shuka_s076_omitted = [row for row in shuka if row["shuka_order_i"] != 76]
    shuka_diagonal_orth = edge_set(
        shuka_s076_omitted,
        "hyakunin_id_i",
        "diagonal_nw_se_serpentine",
        False,
        common_ids,
    )
    shuka_diagonal_eight = edge_set(
        shuka_s076_omitted,
        "hyakunin_id_i",
        "diagonal_nw_se_serpentine",
        True,
        common_ids,
    )
    ogura_spiral_orth = edge_set(ogura, "id_i", "spiral_clockwise", False, common_ids)
    ogura_spiral_eight = edge_set(ogura, "id_i", "spiral_clockwise", True, common_ids)

    orth_overlap = shuka_diagonal_orth & ogura_spiral_orth
    eight_overlap = shuka_diagonal_eight & ogura_spiral_eight

    matrix_orth = []
    matrix_eight = []
    for layout_name in LAYOUTS:
        ogura_orth = edge_set(ogura, "id_i", layout_name, False, common_ids)
        ogura_eight = edge_set(ogura, "id_i", layout_name, True, common_ids)
        matrix_orth.append(
            {
                "ogura_layout": layout_name,
                "ogura_layout_label": layout_label(layout_name),
                **compare_edges(shuka_diagonal_orth, ogura_orth, pair_space),
            }
        )
        matrix_eight.append(
            {
                "ogura_layout": layout_name,
                "ogura_layout_label": layout_label(layout_name),
                **compare_edges(shuka_diagonal_eight, ogura_eight, pair_space),
            }
        )

    omitted_scan_orth = []
    omitted_scan_eight = []
    for omitted in shuka:
        kept = [row for row in shuka if row is not omitted]
        omitted_scan_orth.append(
            {
                "omitted": f"S{omitted['shuka_order_i']:03d}/H{omitted['hyakunin_id_i']}/{omitted['poet_jp']}",
                **compare_edges(
                    edge_set(kept, "hyakunin_id_i", "diagonal_nw_se_serpentine", False, common_ids),
                    ogura_spiral_orth,
                    pair_space,
                ),
            }
        )
        omitted_scan_eight.append(
            {
                "omitted": f"S{omitted['shuka_order_i']:03d}/H{omitted['hyakunin_id_i']}/{omitted['poet_jp']}",
                **compare_edges(
                    edge_set(kept, "hyakunin_id_i", "diagonal_nw_se_serpentine", True, common_ids),
                    ogura_spiral_eight,
                    pair_space,
                ),
            }
        )

    ogura_layout = json.loads(OGURA_LAYOUT_JSON.read_text(encoding="utf-8"))
    spiral_pairs = ogura_layout["layout_pair_details"]["spiral_clockwise"]["orthogonal"]

    return {
        "meta": {
            "model": "text-embedding-3-small",
            "common_count": len(common_ids),
            "pair_space": pair_space,
            "shuka_condition": "S076 omitted, diagonal_nw_se_serpentine",
            "ogura_condition": "spiral_clockwise",
            "note": "Edge overlap only; vectors and complete private text are not published.",
        },
        "main": {
            "orthogonal": {
                **compare_edges(shuka_diagonal_orth, ogura_spiral_orth, pair_space),
                "consecutive_pairs": sum(1 for left, right in orth_overlap if right - left == 1),
                "overlap_pairs": [
                    {"left_id": left, "right_id": right, "label": pair_label((left, right), ogura_by_id)}
                    for left, right in sorted(orth_overlap)
                ],
            },
            "eight": {
                **compare_edges(shuka_diagonal_eight, ogura_spiral_eight, pair_space),
                "consecutive_pairs": sum(1 for left, right in eight_overlap if right - left == 1),
                "overlap_pairs": [
                    {"left_id": left, "right_id": right, "label": pair_label((left, right), ogura_by_id)}
                    for left, right in sorted(eight_overlap)
                ],
            },
        },
        "ogura_layout_matrix": {
            "orthogonal": sorted(matrix_orth, key=lambda item: item["intersection"], reverse=True),
            "eight": sorted(matrix_eight, key=lambda item: item["intersection"], reverse=True),
        },
        "shuka_omission_scan_against_ogura_spiral": {
            "orthogonal": sorted(omitted_scan_orth, key=lambda item: item["intersection"], reverse=True)[:12],
            "eight": sorted(omitted_scan_eight, key=lambda item: item["intersection"], reverse=True)[:12],
        },
        "ogura_spiral_orthogonal_pairs": {
            "top": spiral_pairs["top"][:12],
            "bottom": spiral_pairs["bottom"][:12],
        },
    }


def tag(name: str, content: str = "", **attrs: object) -> str:
    clean = {key.replace("_", "-"): value for key, value in attrs.items() if value is not None}
    attr = " ".join(f'{key}="{escape(str(value), quote=True)}"' for key, value in clean.items())
    if attr:
        attr = " " + attr
    if content:
        return f"<{name}{attr}>{content}</{name}>"
    return f"<{name}{attr}/>"


def text(x: float, y: float, value: str, size: int = 18, fill: str | None = None, weight: int | str | None = None, anchor: str | None = None, family: str = "sans") -> str:
    family_value = "Hiragino Mincho ProN, Yu Mincho, serif" if family == "serif" else "Hiragino Sans, Yu Gothic, sans-serif"
    return tag(
        "text",
        escape(value),
        x=x,
        y=y,
        fill=fill or COLORS["ink"],
        font_family=family_value,
        font_size=size,
        font_weight=weight,
        text_anchor=anchor,
        letter_spacing=0,
    )


def rect(x: float, y: float, width: float, height: float, fill: str, stroke: str | None = None, rx: float = 8, opacity: float | None = None, stroke_width: float | None = None) -> str:
    return tag("rect", x=x, y=y, width=width, height=height, fill=fill, stroke=stroke, rx=rx, opacity=opacity, stroke_width=stroke_width)


def line(x1: float, y1: float, x2: float, y2: float, stroke: str, width: float = 1, opacity: float | None = None, dasharray: str | None = None) -> str:
    return tag("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=stroke, stroke_width=width, opacity=opacity, stroke_dasharray=dasharray)


def svg_doc(body: str, width: int = 1280, height: int = 840) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
<defs>
  <filter id="shadow" x="-12%" y="-12%" width="124%" height="124%">
    <feDropShadow dx="0" dy="16" stdDeviation="16" flood-color="#202124" flood-opacity="0.11"/>
  </filter>
</defs>
<rect width="{width}" height="{height}" fill="{COLORS["paper"]}"/>
<rect x="34" y="34" width="{width - 68}" height="{height - 68}" rx="18" fill="{COLORS["panel"]}" stroke="{COLORS["grid"]}" filter="url(#shadow)"/>
{body}
</svg>
'''


def bar_row(x: float, y: float, label: str, count: int, max_count: int, color: str, note: str = "") -> str:
    width = 470
    fill_width = width * count / max_count
    return "\n".join(
        [
            text(x, y + 20, label, 17, COLORS["ink"], 700),
            rect(x + 170, y, width, 28, "#eee8dc", None, rx=14),
            rect(x + 170, y, fill_width, 28, color, None, rx=14),
            text(x + 170 + fill_width - 10, y + 20, str(count), 15, "#fffdf8", 700, anchor="end"),
            text(x + 660, y + 20, note, 15, COLORS["muted"]),
        ]
    )


def build_svg(payload: dict[str, Any]) -> str:
    orth = payload["main"]["orthogonal"]
    eight = payload["main"]["eight"]
    orth_rows = payload["ogura_layout_matrix"]["orthogonal"]
    eight_rows = payload["ogura_layout_matrix"]["eight"]
    max_orth = max(row["intersection"] for row in orth_rows)
    max_eight = max(row["intersection"] for row in eight_rows)

    parts = [
        text(78, 88, "百人秀歌の斜め × 小倉の螺旋", 34, COLORS["plum"], 700, family="serif"),
        text(78, 122, "S076を外した百人秀歌の斜めつづら折りと、小倉の螺旋置きが同じ隣ペアをどれだけ拾うか。", 17, COLORS["muted"]),
    ]

    cards = [
        ("22組", "上下左右で重なるペア", COLORS["cinnabar"]),
        ("13.0%", "百人秀歌斜め側から見た重なり率", COLORS["indigo"]),
        ("21/22", "重なった上下左右ペアの多くは連番", COLORS["moss"]),
    ]
    for index, (big, small, color) in enumerate(cards):
        x = 78 + index * 370
        parts.append(rect(x, 158, 330, 114, COLORS["wash"], color, rx=16, stroke_width=1.4))
        parts.append(text(x + 28, 212, big, 34, color, 800, family="serif"))
        parts.append(text(x + 28, 246, small, 16, COLORS["ink"]))

    parts.extend(
        [
            text(78, 322, "百人秀歌斜めと、小倉側の各置き方の重なり", 24, COLORS["ink"], 700, family="serif"),
            text(78, 350, "数値は上下左右近傍。螺旋置きは偶然より重なるが、候補中で特別に高いわけではない。", 16, COLORS["muted"]),
        ]
    )
    y = 382
    for row in orth_rows:
        color = COLORS["cinnabar"] if row["ogura_layout"] == "spiral_clockwise" else COLORS["blue"]
        note = "小倉螺旋" if row["ogura_layout"] == "spiral_clockwise" else ""
        parts.append(bar_row(90, y, row["ogura_layout_label"], int(row["intersection"]), max_orth, color, note))
        y += 46

    parts.extend(
        [
            line(88, 712, 1160, 712, COLORS["grid"], 1.2),
            text(90, 744, f"8近傍では、螺旋置きの重なりは {eight['intersection']}組 / {eight['left_edges']}組。最大は {eight_rows[0]['ogura_layout_label']} の {eight_rows[0]['intersection']}組。", 17, COLORS["ink"]),
            text(90, 772, f"全{payload['meta']['common_count']}首から任意のペアを選ぶだけなら、上下左右の期待重なりは約{orth['expected_random']:.1f}組。観測値はその約{orth['ratio_to_random_pair_sets']:.1f}倍。", 15, COLORS["muted"]),
        ]
    )
    return svg_doc("\n".join(parts))


def main() -> None:
    payload = build_payload()
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_SVG.write_text(build_svg(payload), encoding="utf-8")
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_SVG}")


if __name__ == "__main__":
    main()
