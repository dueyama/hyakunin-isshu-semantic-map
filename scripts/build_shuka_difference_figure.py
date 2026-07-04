#!/usr/bin/env python3
"""Build the Ogura/Shuka difference PCA figure.

The script reads private embedding caches, but it only writes public-safe
labels and coordinates. Poem text and embedding vectors are not written to the
public figure.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

from analyze_embeddings import THEME_COLORS, cosine, pca_scores, primary_theme


ROOT = Path(__file__).resolve().parents[1]
PLOT_X = 92
PLOT_Y = 105
PLOT_W = 878
PLOT_H = 709
PAD_FRACTION = 0.06
OGURA_COLOR = "#9a3f2f"
SHUKA_COLOR = "#235f78"

LABELS = {
    "S053": {"text": "S053 一条院皇后宮", "dx": 18, "dy": -13, "width": 150, "color": SHUKA_COLOR},
    "S073": {"text": "S073 国信", "dx": 18, "dy": -2, "width": 126, "color": SHUKA_COLOR},
    "S076": {"text": "S076 源俊頼", "dx": -150, "dy": -31, "width": 132, "color": SHUKA_COLOR},
    "S090": {"text": "S090 長方", "dx": -132, "dy": -27, "width": 114, "color": SHUKA_COLOR},
    "H074": {"text": "H074 源俊頼", "dx": 18, "dy": -18, "width": 132, "color": OGURA_COLOR},
    "H099": {"text": "H099 後鳥羽院", "dx": -144, "dy": 10, "width": 128, "color": OGURA_COLOR},
    "H100": {"text": "H100 順徳院", "dx": -132, "dy": 30, "width": 106, "color": OGURA_COLOR},
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def int_or_none(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def load_records() -> list[dict[str, Any]]:
    ogura_rows = {int(row["id"]): row for row in read_csv(ROOT / "data/hyakunin_isshu.csv")}
    ogura_embeddings = read_json(
        ROOT / "_private/literature/embeddings/hyakunin_isshu_original_text-embedding-3-small.json"
    )["records"]
    shuka_embeddings = read_json(
        ROOT / "_private/literature/embeddings/hyakunin_shuka_mizugaki_text-embedding-3-small.json"
    )["records"]

    records: list[dict[str, Any]] = []
    for record in sorted(ogura_embeddings, key=lambda item: int(item["id"])):
        poem_id = int(record["id"])
        row = ogura_rows[poem_id]
        theme = primary_theme(row)
        records.append(
            {
                "key": f"H{poem_id:03d}",
                "kind": "ogura",
                "poet": row["poet_jp"],
                "theme": theme,
                "color": THEME_COLORS.get(theme, "#777777"),
                "embedding": record["embedding"],
            }
        )

    shuka_only = [
        record
        for record in shuka_embeddings
        if not int_or_none(record.get("hyakunin_id")) or record.get("variant_group") == "shuka_only"
    ]
    for record in sorted(shuka_only, key=lambda item: int(item["shuka_order"])):
        order = int(record["shuka_order"])
        records.append(
            {
                "key": f"S{order:03d}",
                "kind": "shuka",
                "poet": record["poet_jp"],
                "theme": "百人秀歌側のみ",
                "color": SHUKA_COLOR,
                "embedding": record["embedding"],
            }
        )

    return records


def add_pca(records: list[dict[str, Any]]) -> dict[str, float]:
    coords, explained = pca_scores([record["embedding"] for record in records])
    for record, coord in zip(records, coords):
        record["x"] = coord["x"]
        record["y"] = coord["y"]
    return explained


def make_scaler(records: list[dict[str, Any]]):
    xs = [record["x"] for record in records]
    ys = [record["y"] for record in records]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    x_range = max_x - min_x
    y_range = max_y - min_y
    min_x -= x_range * PAD_FRACTION
    max_x += x_range * PAD_FRACTION
    min_y -= y_range * PAD_FRACTION
    max_y += y_range * PAD_FRACTION

    def sx(value: float) -> float:
        return PLOT_X + (value - min_x) / (max_x - min_x) * PLOT_W

    def sy(value: float) -> float:
        return PLOT_Y + PLOT_H - (value - min_y) / (max_y - min_y) * PLOT_H

    zero_x = sx(0)
    zero_y = sy(0)
    return sx, sy, zero_x, zero_y


def nearest_ogura(records: list[dict[str, Any]], target: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    scored = []
    for record in records:
        if record["kind"] != "ogura" or record["key"] == target["key"]:
            continue
        scored.append(
            {
                "key": record["key"],
                "poet": record["poet"],
                "theme": record["theme"],
                "cosine_similarity": cosine(target["embedding"], record["embedding"]),
            }
        )
    return sorted(scored, key=lambda item: item["cosine_similarity"], reverse=True)[:limit]


def public_json(records: list[dict[str, Any]], explained: dict[str, float]) -> dict[str, Any]:
    by_key = {record["key"]: record for record in records}
    highlight_points = []
    for key in ["H074", "H099", "H100", "S053", "S073", "S076", "S090"]:
        record = by_key[key]
        highlight_points.append(
            {
                "key": key,
                "kind": record["kind"],
                "poet": record["poet"],
                "x": record["x"],
                "y": record["y"],
                "nearest_ogura": nearest_ogura(records, record),
            }
        )
    source = by_key["S076"]
    target = by_key["H074"]
    return {
        "meta": {
            "method": "PCA over Ogura 100 embeddings plus four Shuka-only/replacement embeddings",
            "model": "text-embedding-3-small",
            "input_mode": "waka_original_only",
            "record_count": len(records),
            "explained_variance_ratio": explained,
            "text_policy": "Do not publish poem text or vectors; figure labels only.",
        },
        "highlight_points": highlight_points,
        "same_poet_replacement": {
            "source": "S076",
            "target": "H074",
            "cosine_similarity": cosine(source["embedding"], target["embedding"]),
            "pca_distance": math.dist([source["x"], source["y"]], [target["x"], target["y"]]),
        },
    }


def diamond(cx: float, cy: float, radius: float) -> str:
    return (
        f"{cx:.2f},{cy - radius:.2f} "
        f"{cx + radius:.2f},{cy:.2f} "
        f"{cx:.2f},{cy + radius:.2f} "
        f"{cx - radius:.2f},{cy:.2f}"
    )


def label_anchor(px: float, py: float, x: float, y: float, width: float, height: float) -> tuple[float, float]:
    if px < x:
        anchor_x = x
    elif px > x + width:
        anchor_x = x + width
    else:
        anchor_x = px
    if py < y:
        anchor_y = y
    elif py > y + height:
        anchor_y = y + height
    else:
        anchor_y = py
    return anchor_x, anchor_y


def draw_label(lines: list[str], point: dict[str, Any], px: float, py: float) -> None:
    config = LABELS[point["key"]]
    height = 27
    width = float(config["width"])
    x = max(PLOT_X + 4, min(px + config["dx"], PLOT_X + PLOT_W - width - 4))
    y = max(PLOT_Y + 4, min(py + config["dy"], PLOT_Y + PLOT_H - height - 4))
    color = config["color"]
    anchor_x, anchor_y = label_anchor(px, py, x, y, width, height)
    lines.append(
        f'<line x1="{px:.2f}" y1="{py:.2f}" x2="{anchor_x:.2f}" y2="{anchor_y:.2f}" '
        f'stroke="{color}" stroke-width="1.7" opacity="0.68"/>'
    )
    lines.append(
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height}" rx="5" '
        f'fill="#fffdfa" stroke="{color}" stroke-width="1.25" opacity="0.96"/>'
    )
    lines.append(
        f'<text x="{x + 7:.2f}" y="{y + 18.5:.2f}" '
        'font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="13" '
        f'font-weight="700" fill="{color}">{esc(config["text"])}</text>'
    )


def build_svg(records: list[dict[str, Any]], explained: dict[str, float]) -> str:
    by_key = {record["key"]: record for record in records}
    sx, sy, zero_x, zero_y = make_scaler(records)
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="900" viewBox="0 0 1280 900">',
        '<rect width="1280" height="900" fill="#fbfaf7"/>',
        '<text x="92" y="48" font-family="Hiragino Mincho ProN, Yu Mincho, serif" font-size="30" fill="#222">小倉100首＋百人秀歌差分4首 PCA</text>',
        '<text x="92" y="78" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#555">text-embedding-3-small / 本文のみ。小倉100首に、百人秀歌側だけの4首を追加して同じ2次元に投影。</text>',
        f'<rect x="{PLOT_X}" y="{PLOT_Y}" width="{PLOT_W}" height="{PLOT_H}" fill="#fffefa" stroke="#d9d1c2"/>',
        f'<line x1="{PLOT_X}" y1="{zero_y:.2f}" x2="{PLOT_X + PLOT_W}" y2="{zero_y:.2f}" stroke="#e4ded4" stroke-width="1"/>',
        f'<line x1="{zero_x:.2f}" y1="{PLOT_Y}" x2="{zero_x:.2f}" y2="{PLOT_Y + PLOT_H}" stroke="#e4ded4" stroke-width="1"/>',
    ]

    for record in records:
        if record["kind"] != "ogura":
            continue
        lines.append(
            f'<circle cx="{sx(record["x"]):.2f}" cy="{sy(record["y"]):.2f}" r="5.4" '
            f'fill="{record["color"]}" opacity="0.28"/>'
        )

    source = by_key["S076"]
    target = by_key["H074"]
    lines.append(
        f'<line x1="{sx(source["x"]):.2f}" y1="{sy(source["y"]):.2f}" '
        f'x2="{sx(target["x"]):.2f}" y2="{sy(target["y"]):.2f}" '
        'stroke="#7a4b88" stroke-width="2.6" stroke-dasharray="7 7" opacity="0.78"/>'
    )

    marker_positions: dict[str, tuple[float, float]] = {}
    for key in ["H074", "H099", "H100"]:
        record = by_key[key]
        px, py = sx(record["x"]), sy(record["y"])
        marker_positions[key] = (px, py)
        lines.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="15" fill="#fffdfa" stroke="{OGURA_COLOR}" stroke-width="3.4"/>')
        lines.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="7" fill="{OGURA_COLOR}"/>')

    for key in ["S053", "S073", "S076", "S090"]:
        record = by_key[key]
        px, py = sx(record["x"]), sy(record["y"])
        marker_positions[key] = (px, py)
        lines.append(f'<polygon points="{diamond(px, py, 14)}" fill="#fffdfa" stroke="{SHUKA_COLOR}" stroke-width="3.4"/>')
        lines.append(f'<polygon points="{diamond(px, py, 7)}" fill="{SHUKA_COLOR}"/>')

    for key in ["S053", "S073", "S076", "S090", "H074", "H099", "H100"]:
        draw_label(lines, by_key[key], *marker_positions[key])

    explained_total = explained["pc1"] + explained["pc2"]
    lines.extend(
        [
            '<rect x="978" y="92" width="242" height="288" rx="8" fill="#fffefa" stroke="#d9d1c2"/>',
            '<text x="1000" y="126" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="16" font-weight="700" fill="#4b2447">読み方</text>',
            f'<circle cx="1000" cy="160" r="10" fill="#fffdfa" stroke="{OGURA_COLOR}" stroke-width="3"/>',
            '<text x="1020" y="165" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="13" fill="#333">小倉側だけの対応点</text>',
            f'<polygon points="{diamond(1000, 197, 10)}" fill="#fffdfa" stroke="{SHUKA_COLOR}" stroke-width="3"/>',
            '<text x="1020" y="202" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="13" fill="#333">百人秀歌側だけの4首</text>',
            '<line x1="990" y1="231" x2="1010" y2="231" stroke="#7a4b88" stroke-width="2" stroke-dasharray="6 6"/>',
            '<text x="1020" y="236" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="13" fill="#333">同歌人の別歌対応</text>',
            f'<text x="1000" y="278" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="13" fill="#555">PC1+PC2寄与率: {explained_total:.1%}</text>',
            '<text x="1000" y="304" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="13" fill="#555">点の近さは手がかり。</text>',
            '<text x="1000" y="326" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="13" fill="#555">本文・ベクトルは非公開。</text>',
            '<text x="92" y="850" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="13" fill="#666">注: これは小倉100首のみの図とは別に、小倉100首＋百人秀歌差分4首でPCAをかけ直した図。百人秀歌本文は公開せず、ラベルと位置だけを示す。</text>',
            "</svg>",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    records = load_records()
    explained = add_pca(records)
    write_json(ROOT / "_private/literature/records/shuka_difference_pca_small.json", public_json(records, explained))
    svg = build_svg(records, explained)
    output = ROOT / "docs/figures/shuka-difference-pca-small.svg"
    output.write_text(svg, encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
