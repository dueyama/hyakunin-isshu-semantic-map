"""Build a PCA figure that connects Ogura poems in sequence order."""

from __future__ import annotations

import html
import json
import math
import random
import statistics
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
POINTS_PATH = ROOT / "public/data/embeddings_pca_small.json"
OUTPUT_PATH = ROOT / "docs/figures/ogura-sequence-path-pca-small.svg"


WIDTH = 1600
HEIGHT = 1152
PLOT_X = 110
PLOT_Y = 150
PLOT_W = 1320
PLOT_H = 820

MILESTONE_OFFSETS = {
    1: (18, -18),
    25: (18, 26),
    50: (-86, -18),
    75: (18, -18),
    100: (-98, 28),
}
RANDOM_SEED = 20260703
RANDOM_TRIALS = 10000


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def load_points() -> list[dict[str, object]]:
    raw = json.loads(POINTS_PATH.read_text(encoding="utf-8"))
    return sorted(raw["points"], key=lambda item: int(item["id"]))


def bounds(points: Iterable[dict[str, object]]) -> tuple[float, float, float, float]:
    xs = [float(point["x"]) for point in points]
    ys = [float(point["y"]) for point in points]
    pad_x = (max(xs) - min(xs)) * 0.08
    pad_y = (max(ys) - min(ys)) * 0.08
    return min(xs) - pad_x, max(xs) + pad_x, min(ys) - pad_y, max(ys) + pad_y


def make_scaler(data_bounds: tuple[float, float, float, float]):
    min_x, max_x, min_y, max_y = data_bounds
    data_w = max_x - min_x or 1.0
    data_h = max_y - min_y or 1.0
    scale = min(PLOT_W / data_w, PLOT_H / data_h)
    actual_w = data_w * scale
    actual_h = data_h * scale
    plot_x0 = PLOT_X + (PLOT_W - actual_w) / 2
    plot_y0 = PLOT_Y + (PLOT_H - actual_h) / 2

    def sx(value: float) -> float:
        return plot_x0 + (value - min_x) * scale

    def sy(value: float) -> float:
        return plot_y0 + actual_h - (value - min_y) * scale

    return sx, sy, plot_x0, plot_y0, actual_w, actual_h


def lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def segment_color(index: int, total: int) -> str:
    # Indigo to cinnabar, with a moss-green midpoint so the path reads as a route.
    t = index / max(total - 1, 1)
    stops = [
        (0.0, (38, 60, 97)),
        (0.52, (82, 107, 85)),
        (1.0, (154, 63, 47)),
    ]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            local = (t - t0) / (t1 - t0)
            return f"rgb({lerp(c0[0], c1[0], local)}, {lerp(c0[1], c1[1], local)}, {lerp(c0[2], c1[2], local)})"
    r, g, b = stops[-1][1]
    return f"rgb({r}, {g}, {b})"


def label_box(lines: list[str], text: str, x: float, y: float, dx: int, dy: int) -> None:
    label_w = 8.6 * len(text) + 22
    label_h = 32
    bx = x + dx
    by = y + dy - label_h
    if dx < 0:
        bx = x + dx - label_w
    bx = max(PLOT_X + 6, min(bx, PLOT_X + PLOT_W - label_w - 6))
    by = max(PLOT_Y + 6, min(by, PLOT_Y + PLOT_H - label_h - 6))
    lines.append(
        f'<rect x="{bx:.2f}" y="{by:.2f}" width="{label_w:.2f}" height="{label_h}" '
        'rx="6" fill="#fffdfa" stroke="#d7d0c2" opacity="0.96"/>'
    )
    lines.append(
        f'<text x="{bx + 10:.2f}" y="{by + 22:.2f}" '
        'font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" '
        f'font-weight="700" fill="#202124">{esc(text)}</text>'
    )


def path_length(points: list[dict[str, object]]) -> float:
    return sum(
        math.dist((float(left["x"]), float(left["y"])), (float(right["x"]), float(right["y"])))
        for left, right in zip(points, points[1:])
    )


def angle_delta(start: float, end: float) -> float:
    delta = end - start
    while delta <= -math.pi:
        delta += 2 * math.pi
    while delta > math.pi:
        delta -= 2 * math.pi
    return delta


def coords_for(points: list[dict[str, object]]) -> list[tuple[float, float]]:
    return [(float(point["x"]), float(point["y"])) for point in points]


def path_length_for_order(coords: list[tuple[float, float]], order: list[int]) -> float:
    return sum(math.dist(coords[order[index]], coords[order[index + 1]]) for index in range(len(order) - 1))


def center_sweep_rotations(coords: list[tuple[float, float]], order: list[int]) -> float:
    center_x = statistics.fmean(x for x, _ in coords)
    center_y = statistics.fmean(y for _, y in coords)
    angles = [math.atan2(coords[index][1] - center_y, coords[index][0] - center_x) for index in order]
    return sum(abs(angle_delta(start, end)) for start, end in zip(angles, angles[1:])) / (2 * math.pi)


def heading_turn_rotations(coords: list[tuple[float, float]], order: list[int]) -> float:
    headings = [
        math.atan2(coords[right][1] - coords[left][1], coords[right][0] - coords[left][0])
        for left, right in zip(order, order[1:])
    ]
    return sum(abs(angle_delta(start, end)) for start, end in zip(headings, headings[1:])) / (2 * math.pi)


def random_stats(coords: list[tuple[float, float]], value: float, sampler) -> dict[str, float]:
    order = list(range(len(coords)))
    rng = random.Random(RANDOM_SEED)
    samples: list[float] = []
    for _ in range(RANDOM_TRIALS):
        rng.shuffle(order)
        samples.append(sampler(order))
    return {
        "mean": statistics.fmean(samples),
        "sd": statistics.pstdev(samples),
        "percentile": sum(sample <= value for sample in samples) / len(samples),
    }


def build_svg() -> str:
    points = load_points()
    meta = json.loads(POINTS_PATH.read_text(encoding="utf-8"))["meta"]
    explained = meta["explained_variance_ratio"]["pc1"] + meta["explained_variance_ratio"]["pc2"]
    data_bounds = bounds(points)
    sx, sy, plot_x0, plot_y0, plot_w, plot_h = make_scaler(data_bounds)
    min_x, max_x, min_y, max_y = data_bounds
    zero_x = sx(0.0)
    zero_y = sy(0.0)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#fbfaf7"/>',
        '<text x="90" y="62" font-family="Hiragino Mincho ProN, Yu Mincho, serif" font-size="42" fill="#222">小倉順を線でつないだPCA地図</text>',
        '<text x="90" y="100" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="19" fill="#555">text-embedding-3-small / PCA。1番から100番へ、歌順に沿って点を結ぶ。</text>',
        f'<rect x="{PLOT_X}" y="{PLOT_Y}" width="{PLOT_W}" height="{PLOT_H}" fill="#fffdfa" stroke="#d7d0c2"/>',
        f'<rect x="{plot_x0:.2f}" y="{plot_y0:.2f}" width="{plot_w:.2f}" height="{plot_h:.2f}" fill="#fffdfa" stroke="#ebe5db"/>',
    ]

    if min_x <= 0 <= max_x:
        lines.append(f'<line x1="{zero_x:.2f}" y1="{plot_y0:.2f}" x2="{zero_x:.2f}" y2="{plot_y0 + plot_h:.2f}" stroke="#ebe5db" stroke-width="1"/>')
    if min_y <= 0 <= max_y:
        lines.append(f'<line x1="{plot_x0:.2f}" y1="{zero_y:.2f}" x2="{plot_x0 + plot_w:.2f}" y2="{zero_y:.2f}" stroke="#ebe5db" stroke-width="1"/>')

    # Background points first.
    for point in points:
        x = sx(float(point["x"]))
        y = sy(float(point["y"]))
        fill = point.get("color", "#777777")
        lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6.4" fill="{esc(fill)}" opacity="0.32"/>')

    total_segments = len(points) - 1
    for index, (left, right) in enumerate(zip(points, points[1:]), start=1):
        x1 = sx(float(left["x"]))
        y1 = sy(float(left["y"]))
        x2 = sx(float(right["x"]))
        y2 = sy(float(right["y"]))
        color = segment_color(index - 1, total_segments)
        lines.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{color}" stroke-width="2.2" opacity="0.56" stroke-linecap="round"/>'
        )

    # Draw milestones and labels on top of the route.
    milestones = {1, 25, 50, 75, 100}
    for point in points:
        point_id = int(point["id"])
        x = sx(float(point["x"]))
        y = sy(float(point["y"]))
        fill = point.get("color", "#777777")
        radius = 13 if point_id in milestones else 5.5
        stroke = "#202124" if point_id in milestones else "#fffdfa"
        stroke_w = 2.2 if point_id in milestones else 1.0
        opacity = "0.96" if point_id in milestones else "0.62"
        lines.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{esc(fill)}" '
            f'stroke="{stroke}" stroke-width="{stroke_w}" opacity="{opacity}"/>'
        )
        if point_id in milestones:
            label_box(lines, f"H{point_id:03d} {point['poet_jp']}", x, y, *MILESTONE_OFFSETS[point_id])

    # A compact color legend for sequence direction.
    legend_x = 1040
    legend_y = 1030
    legend_w = 260
    steps = 52
    for step in range(steps):
        color = segment_color(step, steps - 1)
        x = legend_x + step * (legend_w / steps)
        lines.append(
            f'<rect x="{x:.2f}" y="{legend_y}" width="{legend_w / steps + 0.6:.2f}" height="12" fill="{color}" opacity="0.86"/>'
        )
    lines.append('<text x="90" y="1032" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="17" fill="#555">薄い点は全100首。線は小倉順の1→100。色は序盤から終盤への進行を示す。</text>')
    lines.append(f'<text x="{legend_x - 44}" y="{legend_y + 12}" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="14" fill="#555">H001</text>')
    lines.append(f'<text x="{legend_x + legend_w + 10}" y="{legend_y + 12}" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="14" fill="#555">H100</text>')
    lines.append(f'<text x="90" y="1064" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#74706a">PC1+PC2寄与率 {explained:.3f}。この線は2次元射影上の見え方であり、高次元の近さそのものではない。</text>')
    coords = coords_for(points)
    sequence_order = list(range(len(coords)))
    route_length = path_length_for_order(coords, sequence_order)
    route_stats = random_stats(coords, route_length, lambda order: path_length_for_order(coords, order))
    sweep = center_sweep_rotations(coords, sequence_order)
    sweep_stats = random_stats(coords, sweep, lambda order: center_sweep_rotations(coords, order))
    turn = heading_turn_rotations(coords, sequence_order)
    turn_stats = random_stats(coords, turn, lambda order: heading_turn_rotations(coords, order))
    lines.append(f'<text x="90" y="1088" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#74706a">経路長 {route_length:.3f}（ランダム平均 {route_stats["mean"]:.3f}, percentile {route_stats["percentile"]:.3f}）。中心回り累積 {sweep:.1f}周分（percentile {sweep_stats["percentile"]:.3f}）。</text>')
    lines.append(f'<text x="90" y="1112" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#74706a">進行方向の総回転 {turn:.1f}周分（ランダム平均 {turn_stats["mean"]:.1f}, percentile {turn_stats["percentile"]:.3f}）。小刻みに曲がる度合いを見る補助値。</text>')
    lines.append(f'<text x="{plot_x0 + plot_w - 62:.2f}" y="{plot_y0 + plot_h + 34:.2f}" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="16" fill="#74706a">PC1</text>')
    lines.append(f'<text x="{plot_x0 - 2:.2f}" y="{plot_y0 - 10:.2f}" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="16" fill="#74706a">PC2</text>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_svg(), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
