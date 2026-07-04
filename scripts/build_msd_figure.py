"""Build a PCA-based mean squared displacement figure for Ogura order."""

from __future__ import annotations

import html
import json
import random
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POINTS_PATH = ROOT / "public/data/embeddings_pca_small.json"
OUTPUT_PATH = ROOT / "docs/figures/ogura-msd-pca-small.svg"

WIDTH = 1600
HEIGHT = 900
PLOT_X = 112
PLOT_Y = 150
PLOT_W = 1320
PLOT_H = 560
MAX_LAG = 40
RANDOM_TRIALS = 10000
RANDOM_SEED = 20260703


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def load_points() -> list[dict[str, object]]:
    raw = json.loads(POINTS_PATH.read_text(encoding="utf-8"))
    return sorted(raw["points"], key=lambda item: int(item["id"]))


def coords_for(points: list[dict[str, object]]) -> list[tuple[float, float]]:
    return [(float(point["x"]), float(point["y"])) for point in points]


def squared_distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return (left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2


def msd(coords: list[tuple[float, float]], order: list[int], lag: int) -> float:
    return statistics.fmean(
        squared_distance(coords[order[index]], coords[order[index + lag]])
        for index in range(len(order) - lag)
    )


def compute_rows(coords: list[tuple[float, float]]) -> list[dict[str, float]]:
    sequence_order = list(range(len(coords)))
    ogura = {lag: msd(coords, sequence_order, lag) for lag in range(1, MAX_LAG + 1)}
    rng = random.Random(RANDOM_SEED)
    order = list(range(len(coords)))
    samples: dict[int, list[float]] = {lag: [] for lag in range(1, MAX_LAG + 1)}
    for _ in range(RANDOM_TRIALS):
        rng.shuffle(order)
        for lag in range(1, MAX_LAG + 1):
            samples[lag].append(msd(coords, order, lag))

    rows = []
    for lag in range(1, MAX_LAG + 1):
        values = sorted(samples[lag])
        mean = statistics.fmean(values)
        rows.append(
            {
                "lag": lag,
                "ogura": ogura[lag],
                "random_mean": mean,
                "random_p05": values[int(0.05 * len(values))],
                "random_p95": values[int(0.95 * len(values))],
                "percentile": sum(value <= ogura[lag] for value in values) / len(values),
                "ratio": ogura[lag] / mean if mean else 0.0,
            }
        )
    return rows


def line_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    first, *rest = points
    chunks = [f"M {first[0]:.2f} {first[1]:.2f}"]
    chunks.extend(f"L {x:.2f} {y:.2f}" for x, y in rest)
    return " ".join(chunks)


def area_path(upper: list[tuple[float, float]], lower: list[tuple[float, float]]) -> str:
    if not upper or not lower:
        return ""
    first, *rest = upper
    chunks = [f"M {first[0]:.2f} {first[1]:.2f}"]
    chunks.extend(f"L {x:.2f} {y:.2f}" for x, y in rest)
    chunks.extend(f"L {x:.2f} {y:.2f}" for x, y in reversed(lower))
    chunks.append("Z")
    return " ".join(chunks)


def build_svg() -> str:
    points = load_points()
    coords = coords_for(points)
    rows = compute_rows(coords)
    max_y = max(row["random_p95"] for row in rows) * 1.08

    def sx(lag: float) -> float:
        return PLOT_X + (lag - 1) / (MAX_LAG - 1) * PLOT_W

    def sy(value: float) -> float:
        return PLOT_Y + PLOT_H - value / max_y * PLOT_H

    random_upper = [(sx(row["lag"]), sy(row["random_p95"])) for row in rows]
    random_lower = [(sx(row["lag"]), sy(row["random_p05"])) for row in rows]
    random_mean = [(sx(row["lag"]), sy(row["random_mean"])) for row in rows]
    ogura_line = [(sx(row["lag"]), sy(row["ogura"])) for row in rows]

    key_rows = {row["lag"]: row for row in rows if row["lag"] in {1, 2, 5, 10, 20, 40}}
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#fbfaf7"/>',
        '<text x="90" y="62" font-family="Hiragino Mincho ProN, Yu Mincho, serif" font-size="42" fill="#222">小倉順のMSDを見る</text>',
        '<text x="90" y="100" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="19" fill="#555">PCA二次元図上で、k首先まで進むと平均してどれくらい離れるか。</text>',
        f'<rect x="{PLOT_X}" y="{PLOT_Y}" width="{PLOT_W}" height="{PLOT_H}" fill="#fffdfa" stroke="#d7d0c2"/>',
    ]

    for index in range(5):
        value = max_y * index / 4
        y = sy(value)
        lines.append(f'<line x1="{PLOT_X}" y1="{y:.2f}" x2="{PLOT_X + PLOT_W}" y2="{y:.2f}" stroke="#eee7dc" stroke-width="1"/>')
        lines.append(f'<text x="{PLOT_X - 14}" y="{y + 5:.2f}" text-anchor="end" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="14" fill="#74706a">{value:.2f}</text>')

    for lag in [1, 5, 10, 20, 30, 40]:
        x = sx(lag)
        lines.append(f'<line x1="{x:.2f}" y1="{PLOT_Y}" x2="{x:.2f}" y2="{PLOT_Y + PLOT_H}" stroke="#f0ebe3" stroke-width="1"/>')
        lines.append(f'<text x="{x:.2f}" y="{PLOT_Y + PLOT_H + 32}" text-anchor="middle" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#74706a">{lag}</text>')

    lines.append(f'<path d="{area_path(random_upper, random_lower)}" fill="#b8c7d9" opacity="0.34"/>')
    lines.append(f'<path d="{line_path(random_mean)}" fill="none" stroke="#6e8197" stroke-width="3" stroke-dasharray="8 8" opacity="0.9"/>')
    lines.append(f'<path d="{line_path(ogura_line)}" fill="none" stroke="#9a3f2f" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>')

    for lag, row in key_rows.items():
        x = sx(lag)
        y = sy(row["ogura"])
        lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="#9a3f2f" stroke="#fffdfa" stroke-width="2"/>')
        if lag in {2, 20, 40}:
            dy = -16 if lag != 40 else -12
            lines.append(
                f'<text x="{x + 10:.2f}" y="{y + dy:.2f}" font-family="Hiragino Sans, Yu Gothic, sans-serif" '
                f'font-size="14" fill="#4b4039">k={lag}: {row["ogura"]:.3f} / pct {row["percentile"]:.3f}</text>'
            )

    lines.extend(
        [
            '<text x="90" y="764" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="17" fill="#555">横軸: 何首先を見るか（lag）。縦軸: PCA二次元図上の平均二乗変位（MSD）。</text>',
            '<rect x="90" y="794" width="28" height="12" fill="#b8c7d9" opacity="0.34"/><text x="128" y="806" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#555">ランダム順の5-95%帯</text>',
            '<line x1="338" y1="800" x2="392" y2="800" stroke="#6e8197" stroke-width="3" stroke-dasharray="8 8"/><text x="402" y="806" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#555">ランダム順平均</text>',
            '<line x1="586" y1="800" x2="640" y2="800" stroke="#9a3f2f" stroke-width="4"/><text x="650" y="806" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#555">小倉順</text>',
            f'<text x="90" y="842" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#74706a">k=1: 小倉{key_rows[1]["ogura"]:.3f} / ランダム{key_rows[1]["random_mean"]:.3f} / percentile {key_rows[1]["percentile"]:.3f}。k=2: 小倉{key_rows[2]["ogura"]:.3f} / ランダム{key_rows[2]["random_mean"]:.3f} / percentile {key_rows[2]["percentile"]:.3f}。</text>',
            '<text x="90" y="866" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#74706a">短いlagでは近く、長いlagではランダム平均との差が薄れる。これはPCA図上の補助診断であり、高次元の意味距離そのものではない。</text>',
            f'<text x="{PLOT_X + PLOT_W - 84}" y="{PLOT_Y + PLOT_H + 62}" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="16" fill="#74706a">lag</text>',
            f'<text x="{PLOT_X - 2}" y="{PLOT_Y - 16}" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="16" fill="#74706a">MSD</text>',
            "</svg>",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_svg(), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
