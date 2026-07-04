"""Build a highlighted PCA figure for adjacent near/far poem pairs."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
POINTS_PATH = ROOT / "public/data/embeddings_pca_small.json"
OUTPUT_PATH = ROOT / "docs/figures/neighbor-pairs-pca-small.svg"
OUTPUT_NEAR_PATH = ROOT / "docs/figures/neighbor-pairs-near-pca-small.svg"
OUTPUT_FAR_PATH = ROOT / "docs/figures/neighbor-pairs-far-pca-small.svg"

NEAR_PAIRS = [(1, 2), (6, 7), (52, 53), (67, 68), (70, 71), (85, 86)]
FAR_PAIRS = [(9, 10), (10, 11), (41, 42), (68, 69), (93, 94), (98, 99)]

NEAR_IDS = {item for pair in NEAR_PAIRS for item in pair}
FAR_IDS = {item for pair in FAR_PAIRS for item in pair}

LABEL_OFFSETS: dict[str, dict[int, tuple[int, int]]] = {
    "near": {
        1: (10, -20),
        2: (16, 24),
        6: (14, -30),
        7: (-72, 16),
        52: (12, -18),
        53: (-92, 22),
        67: (12, 20),
        68: (10, -22),
        70: (-82, -16),
        71: (16, 40),
        85: (-80, -16),
        86: (12, 20),
    },
    "far": {
        9: (-68, 22),
        10: (16, -18),
        11: (12, -18),
        41: (12, 18),
        42: (-88, -16),
        68: (12, -22),
        69: (-86, 18),
        93: (12, -18),
        94: (-86, 20),
        98: (-82, -16),
        99: (12, 20),
    },
}

PAIR_SIMILARITIES = {
    (1, 2): 0.576,
    (6, 7): 0.531,
    (52, 53): 0.603,
    (67, 68): 0.532,
    (70, 71): 0.598,
    (85, 86): 0.520,
    (9, 10): 0.324,
    (10, 11): 0.286,
    (41, 42): 0.324,
    (68, 69): 0.319,
    (93, 94): 0.293,
    (98, 99): 0.308,
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def load_points() -> dict[int, dict[str, object]]:
    raw = json.loads(POINTS_PATH.read_text(encoding="utf-8"))
    return {int(point["id"]): point for point in raw["points"]}


def bounds(points: Iterable[dict[str, object]]) -> tuple[float, float, float, float]:
    xs = [float(point["x"]) for point in points]
    ys = [float(point["y"]) for point in points]
    pad_x = (max(xs) - min(xs)) * 0.06
    pad_y = (max(ys) - min(ys)) * 0.06
    return min(xs) - pad_x, max(xs) + pad_x, min(ys) - pad_y, max(ys) + pad_y


def make_scaler(
    x0: int,
    y0: int,
    width: int,
    height: int,
    data_bounds: tuple[float, float, float, float],
):
    min_x, max_x, min_y, max_y = data_bounds
    data_width = max_x - min_x or 1
    data_height = max_y - min_y or 1
    scale = min(width / data_width, height / data_height)
    plot_width = data_width * scale
    plot_height = data_height * scale
    plot_x0 = x0 + (width - plot_width) / 2
    plot_y0 = y0 + (height - plot_height) / 2

    def sx(value: float) -> float:
        return plot_x0 + (value - min_x) * scale

    def sy(value: float) -> float:
        return plot_y0 + plot_height - (value - min_y) * scale

    return sx, sy, plot_x0, plot_y0, plot_width, plot_height


def label_text(point: dict[str, object]) -> str:
    return f"H{int(point['id']):03d} {point['poet_jp']}"


def draw_panel(
    lines: list[str],
    *,
    title: str,
    subtitle: str,
    x0: int,
    y0: int,
    width: int,
    height: int,
    points: dict[int, dict[str, object]],
    data_bounds: tuple[float, float, float, float],
    pairs: list[tuple[int, int]],
    focus_ids: set[int],
    mode: str,
    accent: str,
) -> None:
    sx, sy, plot_x0, plot_y0, plot_width, plot_height = make_scaler(x0, y0, width, height, data_bounds)
    min_x, max_x, min_y, max_y = data_bounds
    zero_x = sx(0)
    zero_y = sy(0)

    lines.append(f'<text x="{x0}" y="{y0 - 68}" font-family="Hiragino Mincho ProN, Yu Mincho, serif" font-size="34" fill="#4b2447">{esc(title)}</text>')
    lines.append(f'<text x="{x0}" y="{y0 - 34}" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="18" fill="#5d5a55">{esc(subtitle)}</text>')
    lines.append(f'<rect x="{x0}" y="{y0}" width="{width}" height="{height}" fill="#fffdfa" stroke="#d7d0c2"/>')
    lines.append(f'<rect x="{plot_x0:.2f}" y="{plot_y0:.2f}" width="{plot_width:.2f}" height="{plot_height:.2f}" fill="#fffdfa" stroke="#ebe5db"/>')
    if min_x <= 0 <= max_x:
        lines.append(f'<line x1="{zero_x:.2f}" y1="{plot_y0:.2f}" x2="{zero_x:.2f}" y2="{plot_y0 + plot_height:.2f}" stroke="#ebe5db" stroke-width="1"/>')
    if min_y <= 0 <= max_y:
        lines.append(f'<line x1="{plot_x0:.2f}" y1="{zero_y:.2f}" x2="{plot_x0 + plot_width:.2f}" y2="{zero_y:.2f}" stroke="#ebe5db" stroke-width="1"/>')

    for point in points.values():
        px = sx(float(point["x"]))
        py = sy(float(point["y"]))
        fill = point.get("color", "#777777")
        lines.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="5.4" fill="{esc(fill)}" opacity="0.24"/>')

    for left_id, right_id in pairs:
        left = points[left_id]
        right = points[right_id]
        x1 = sx(float(left["x"]))
        y1 = sy(float(left["y"]))
        x2 = sx(float(right["x"]))
        y2 = sy(float(right["y"]))
        lines.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{accent}" stroke-width="4.2" opacity="0.78" stroke-linecap="round"/>'
        )

        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        sim = PAIR_SIMILARITIES[(left_id, right_id)]
        lines.append(
            f'<text x="{mx + 7:.2f}" y="{my - 7:.2f}" font-family="Hiragino Sans, Yu Gothic, sans-serif" '
            f'font-size="15" fill="{accent}" font-weight="700">{sim:.3f}</text>'
        )

    for point_id in sorted(focus_ids):
        point = points[point_id]
        px = sx(float(point["x"]))
        py = sy(float(point["y"]))
        fill = point.get("color", "#777777")
        lines.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="15" fill="#fffdfa" stroke="{accent}" stroke-width="4"/>')
        lines.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="8" fill="{esc(fill)}" opacity="0.96"/>')
        dx, dy = LABEL_OFFSETS[mode].get(point_id, (10, -12))
        lx = px + dx
        ly = py + dy
        label = label_text(point)
        label_width = 9.0 * len(label) + 22
        label_height = 30
        box_x = lx - 10
        box_y = ly - 21
        if dx < 0:
            box_x = lx - label_width + 8
            lx = box_x + 8
        box_x = max(plot_x0 + 3, min(box_x, plot_x0 + plot_width - label_width - 3))
        box_y = max(plot_y0 + 3, min(box_y, plot_y0 + plot_height - label_height - 3))
        lx = box_x + 8
        ly = box_y + 21
        lines.append(
            f'<rect x="{box_x:.2f}" y="{box_y:.2f}" width="{label_width:.2f}" height="{label_height}" '
            'rx="6" fill="#fffdfa" stroke="#d7d0c2" opacity="0.95"/>'
        )
        lines.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" font-family="Hiragino Sans, Yu Gothic, sans-serif" '
            f'font-size="15" fill="#202124" font-weight="700">{esc(label)}</text>'
        )

    lines.append(f'<text x="{plot_x0 + plot_width - 62:.2f}" y="{plot_y0 + plot_height + 34:.2f}" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="16" fill="#74706a">PC1</text>')
    lines.append(f'<text x="{plot_x0 - 2:.2f}" y="{plot_y0 - 10:.2f}" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="16" fill="#74706a">PC2</text>')


def build_svg() -> str:
    points = load_points()
    data_bounds = bounds(points.values())
    min_x, max_x, min_y, max_y = data_bounds
    data_aspect = (max_x - min_x) / (max_y - min_y or 1)
    panel_width = 665
    panel_height = round(panel_width / data_aspect)
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">',
        '<rect width="1600" height="900" fill="#fbfaf7"/>',
        '<text x="70" y="60" font-family="Hiragino Mincho ProN, Yu Mincho, serif" font-size="34" fill="#222">近い隣、遠い隣は地図のどこにいるか</text>',
        '<text x="70" y="94" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="17" fill="#555">text-embedding-3-small / PCA。PC1/PC2は同一スケール。背景は小倉百人一首100首。</text>',
    ]
    draw_panel(
        lines,
        title="近く出る候補",
        subtitle="本文の声や場面が近づくペア",
        x0=70,
        y0=210,
        width=panel_width,
        height=panel_height,
        points=points,
        data_bounds=data_bounds,
        pairs=NEAR_PAIRS,
        focus_ids=NEAR_IDS,
        mode="near",
        accent="#1f6f88",
    )
    draw_panel(
        lines,
        title="大きく跳ぶ候補",
        subtitle="歌順の前後で場面が切り替わるペア",
        x0=865,
        y0=210,
        width=panel_width,
        height=panel_height,
        points=points,
        data_bounds=data_bounds,
        pairs=FAR_PAIRS,
        focus_ids=FAR_IDS,
        mode="far",
        accent="#a43a2f",
    )
    lines.append('<circle cx="74" cy="835" r="6" fill="#999" opacity="0.35"/>')
    lines.append('<text x="92" y="842" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#666">薄い点は全100首。線の横の数値はsmall条件のcosine similarity。</text>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def build_single_svg(
    *,
    title: str,
    panel_title: str,
    subtitle: str,
    pairs: list[tuple[int, int]],
    focus_ids: set[int],
    mode: str,
    accent: str,
) -> str:
    points = load_points()
    data_bounds = bounds(points.values())
    min_x, max_x, min_y, max_y = data_bounds
    data_aspect = (max_x - min_x) / (max_y - min_y or 1)
    panel_width = 1420
    panel_height = round(panel_width / data_aspect)
    svg_height = 250 + panel_height + 130
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{svg_height}" viewBox="0 0 1600 {svg_height}">',
        f'<rect width="1600" height="{svg_height}" fill="#fbfaf7"/>',
        f'<text x="90" y="70" font-family="Hiragino Mincho ProN, Yu Mincho, serif" font-size="42" fill="#222">{esc(title)}</text>',
        '<text x="90" y="112" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="19" fill="#555">text-embedding-3-small / PCA。PC1/PC2は同一スケールで描いている。</text>',
    ]
    draw_panel(
        lines,
        title=panel_title,
        subtitle=subtitle,
        x0=90,
        y0=230,
        width=panel_width,
        height=panel_height,
        points=points,
        data_bounds=data_bounds,
        pairs=pairs,
        focus_ids=focus_ids,
        mode=mode,
        accent=accent,
    )
    footer_y = 250 + panel_height + 72
    lines.append(f'<circle cx="94" cy="{footer_y}" r="6" fill="#999" opacity="0.35"/>')
    lines.append(f'<text x="112" y="{footer_y + 7}" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="17" fill="#666">薄い点は全100首。線の横の数値はsmall条件のcosine similarity。</text>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_svg(), encoding="utf-8")
    OUTPUT_NEAR_PATH.write_text(
        build_single_svg(
            title="近い隣は地図のどこにいるか",
            panel_title="近く出る候補",
            subtitle="本文の声や場面が近づくペア",
            pairs=NEAR_PAIRS,
            focus_ids=NEAR_IDS,
            mode="near",
            accent="#1f6f88",
        ),
        encoding="utf-8",
    )
    OUTPUT_FAR_PATH.write_text(
        build_single_svg(
            title="遠い隣は地図のどこにいるか",
            panel_title="大きく跳ぶ候補",
            subtitle="歌順の前後で場面が切り替わるペア",
            pairs=FAR_PAIRS,
            focus_ids=FAR_IDS,
            mode="far",
            accent="#a43a2f",
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT_PATH}")
    print(f"wrote {OUTPUT_NEAR_PATH}")
    print(f"wrote {OUTPUT_FAR_PATH}")


if __name__ == "__main__":
    main()
