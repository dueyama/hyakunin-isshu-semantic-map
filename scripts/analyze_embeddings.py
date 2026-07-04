#!/usr/bin/env python3
"""Build PCA coordinates and sequence statistics from private embeddings."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
THEME_COLORS = {
    "春": "#64a338",
    "夏": "#008c95",
    "秋": "#c27a00",
    "冬": "#3f6fb5",
    "恋": "#c44f73",
    "雑": "#666666",
    "羇旅": "#7b61b8",
    "離別": "#bd5e21",
    "哀傷": "#6a6f7d",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def split_tags(value: str) -> list[str]:
    if not value:
        return []
    normalized = value.replace("、", ";").replace("，", ";").replace(",", ";")
    normalized = normalized.replace("|", ";").replace("/", ";")
    return [item.strip() for item in normalized.split(";") if item.strip()]


def primary_theme(row: dict[str, str]) -> str:
    tags = split_tags(row.get("theme", ""))
    if not tags:
        return "未分類"
    for candidate in ["恋", "春", "夏", "秋", "冬", "羇旅", "離別", "哀傷", "雑"]:
        if candidate in tags:
            return candidate
    return tags[0]


def dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def norm(value: list[float]) -> float:
    return math.sqrt(dot(value, value))


def cosine(left: list[float], right: list[float]) -> float:
    denom = norm(left) * norm(right)
    if denom == 0:
        return 0.0
    return dot(left, right) / denom


def centered_kernel(vectors: list[list[float]]) -> list[list[float]]:
    count = len(vectors)
    dims = len(vectors[0])
    means = [0.0] * dims
    for vector in vectors:
        for index, value in enumerate(vector):
            means[index] += value
    means = [value / count for value in means]
    centered: list[list[float]] = []
    for vector in vectors:
        centered.append([value - means[index] for index, value in enumerate(vector)])
    return [[dot(centered[i], centered[j]) for j in range(count)] for i in range(count)]


def matvec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(value * vector[j] for j, value in enumerate(row)) for row in matrix]


def unit(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector))
    if length == 0:
        return [0.0 for _ in vector]
    return [value / length for value in vector]


def power_eigenvectors(
    matrix: list[list[float]],
    components: int = 2,
    iterations: int = 500,
    seed: int = 20260702,
) -> tuple[list[float], list[list[float]]]:
    rng = random.Random(seed)
    work = [row[:] for row in matrix]
    values: list[float] = []
    vectors: list[list[float]] = []
    size = len(matrix)
    for _component in range(components):
        vector = unit([rng.random() - 0.5 for _ in range(size)])
        for _ in range(iterations):
            vector = unit(matvec(work, vector))
        mv = matvec(work, vector)
        eigenvalue = dot(vector, mv)
        if eigenvalue < 0:
            eigenvalue = 0.0
        values.append(eigenvalue)
        vectors.append(vector)
        for i in range(size):
            for j in range(size):
                work[i][j] -= eigenvalue * vector[i] * vector[j]
    return values, vectors


def pca_scores(vectors: list[list[float]]) -> tuple[list[dict[str, float]], dict[str, float]]:
    kernel = centered_kernel(vectors)
    eigenvalues, eigenvectors = power_eigenvectors(kernel, components=2)
    total_variance = sum(kernel[i][i] for i in range(len(kernel)))
    coords: list[dict[str, float]] = []
    for row_index in range(len(vectors)):
        x = math.sqrt(eigenvalues[0]) * eigenvectors[0][row_index] if eigenvalues[0] else 0.0
        y = math.sqrt(eigenvalues[1]) * eigenvectors[1][row_index] if eigenvalues[1] else 0.0
        coords.append({"x": x, "y": y})
    explained = {
        "pc1": eigenvalues[0] / total_variance if total_variance else 0.0,
        "pc2": eigenvalues[1] / total_variance if total_variance else 0.0,
    }
    return coords, explained


def similarity_matrix(vectors: list[list[float]]) -> list[list[float]]:
    size = len(vectors)
    matrix = [[0.0] * size for _ in range(size)]
    for i in range(size):
        matrix[i][i] = 1.0
        for j in range(i + 1, size):
            score = cosine(vectors[i], vectors[j])
            matrix[i][j] = score
            matrix[j][i] = score
    return matrix


def mean_adjacent(order: list[int], sim: list[list[float]]) -> float:
    return statistics.fmean(sim[order[i]][order[i + 1]] for i in range(len(order) - 1))


def percentile(value: float, samples: list[float]) -> float:
    if not samples:
        return 0.0
    return sum(1 for sample in samples if sample <= value) / len(samples)


def adjacency_stats(
    rows: list[dict[str, str]],
    sim: list[list[float]],
    embeddings_meta: dict[str, Any],
    vector_dimension: int,
) -> dict[str, Any]:
    order = list(range(len(rows)))
    pairs: list[dict[str, Any]] = []
    for index in range(len(rows) - 1):
        score = sim[index][index + 1]
        pairs.append(
            {
                "left_id": int(rows[index]["id"]),
                "right_id": int(rows[index + 1]["id"]),
                "left_poet": rows[index]["poet_jp"],
                "right_poet": rows[index + 1]["poet_jp"],
                "cosine_similarity": score,
                "cosine_distance": 1 - score,
                "left_theme": split_tags(rows[index].get("theme", "")),
                "right_theme": split_tags(rows[index + 1].get("theme", "")),
            }
        )
    scores = [pair["cosine_similarity"] for pair in pairs]
    rng = random.Random(20260702)
    random_means: list[float] = []
    for _ in range(10_000):
        shuffled = order[:]
        rng.shuffle(shuffled)
        random_means.append(mean_adjacent(shuffled, sim))
    observed = statistics.fmean(scores)
    random_mean = statistics.fmean(random_means)
    random_sd = statistics.pstdev(random_means)
    return {
        "meta": {
            "method": "cosine similarity over OpenAI embeddings; random order comparison",
            "model": embeddings_meta.get("model"),
            "input_mode": embeddings_meta.get("input_mode"),
            "vector_dimension": vector_dimension,
            "random_trials": 10_000,
            "random_seed": 20260702,
            "pair_count": len(pairs),
        },
        "summary": {
            "mean": observed,
            "median": statistics.median(scores),
            "random_mean": random_mean,
            "random_sd": random_sd,
            "z_score": (observed - random_mean) / random_sd if random_sd else None,
            "percentile": percentile(observed, random_means),
        },
        "top_similar_adjacent": sorted(pairs, key=lambda item: item["cosine_similarity"], reverse=True)[:10],
        "largest_jumps": sorted(pairs, key=lambda item: item["cosine_similarity"])[:10],
        "pairs": pairs,
    }


def pair_rankings(
    rows: list[dict[str, str]],
    sim: list[list[float]],
    embeddings_meta: dict[str, Any],
    vector_dimension: int,
) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            pairs.append(
                {
                    "left_id": int(rows[i]["id"]),
                    "right_id": int(rows[j]["id"]),
                    "left_poet": rows[i]["poet_jp"],
                    "right_poet": rows[j]["poet_jp"],
                    "left_theme": split_tags(rows[i].get("theme", "")),
                    "right_theme": split_tags(rows[j].get("theme", "")),
                    "cosine_similarity": sim[i][j],
                    "mirror_pair": int(rows[i]["id"]) + int(rows[j]["id"]) == 101,
                    "adjacent_pair": abs(int(rows[i]["id"]) - int(rows[j]["id"])) == 1,
                }
            )
    return {
        "meta": {
            "method": "all-pair cosine similarity over embeddings",
            "model": embeddings_meta.get("model"),
            "input_mode": embeddings_meta.get("input_mode"),
            "vector_dimension": vector_dimension,
            "pair_count": len(pairs),
        },
        "top_pairs": sorted(pairs, key=lambda item: item["cosine_similarity"], reverse=True)[:50],
        "bottom_pairs": sorted(pairs, key=lambda item: item["cosine_similarity"])[:50],
        "mirror_pairs": [pair for pair in pairs if pair["mirror_pair"]],
    }


def pca_payload(
    rows: list[dict[str, str]],
    embeddings_meta: dict[str, Any],
    coords: list[dict[str, float]],
    explained: dict[str, float],
    vector_dimension: int,
) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    for row, coord in zip(rows, coords):
        theme = primary_theme(row)
        points.append(
            {
                "id": int(row["id"]),
                "poet_jp": row["poet_jp"],
                "x": coord["x"],
                "y": coord["y"],
                "primary_theme": theme,
                "color": THEME_COLORS.get(theme, "#777777"),
                "theme": split_tags(row.get("theme", "")),
                "season": split_tags(row.get("season", "")),
                "source_anthology": row.get("source_anthology", ""),
                "source_book": row.get("source_book", ""),
                "source_number": row.get("source_number", ""),
            }
        )
    return {
        "meta": {
            "method": "PCA via centered Gram matrix, pure Python power iteration",
            "model": embeddings_meta.get("model"),
            "input_mode": embeddings_meta.get("input_mode"),
            "vector_dimension": vector_dimension,
            "explained_variance_ratio": explained,
            "text_policy": "public points omit poem text",
        },
        "points": points,
    }


def svg_map(points: list[dict[str, Any]], output: Path) -> None:
    width = 1200
    height = 900
    margin = 80
    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    def scale_x(value: float) -> float:
        return margin + (value - min_x) / (max_x - min_x or 1) * (width - 2 * margin)

    def scale_y(value: float) -> float:
        return height - margin - (value - min_y) / (max_y - min_y or 1) * (height - 2 * margin)

    lines: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" viewBox="0 0 1200 900">',
        '<rect width="1200" height="900" fill="#fbfaf7"/>',
        '<text x="80" y="50" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="28" fill="#222">小倉百人一首 意味空間 PCA</text>',
        '<text x="80" y="80" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#555">本文 + 読みによる OpenAI embedding。線は小倉順。</text>',
    ]
    ordered = sorted(points, key=lambda item: item["id"])
    for left, right in zip(ordered, ordered[1:]):
        lines.append(
            f'<line x1="{scale_x(left["x"]):.2f}" y1="{scale_y(left["y"]):.2f}" '
            f'x2="{scale_x(right["x"]):.2f}" y2="{scale_y(right["y"]):.2f}" '
            'stroke="#d2ccc0" stroke-width="1.2" opacity="0.65"/>'
        )
    for point in ordered:
        x = scale_x(point["x"])
        y = scale_y(point["y"])
        label = point["id"]
        color = point["color"]
        lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="7" fill="{color}" opacity="0.88"/>')
        lines.append(
            f'<text x="{x + 9:.2f}" y="{y + 4:.2f}" '
            'font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="11" fill="#222">'
            f"{label}</text>"
        )
    legend_x = 880
    legend_y = 120
    for index, (theme, color) in enumerate(THEME_COLORS.items()):
        y = legend_y + index * 24
        lines.append(f'<circle cx="{legend_x}" cy="{y}" r="6" fill="{color}"/>')
        lines.append(
            f'<text x="{legend_x + 14}" y="{y + 5}" '
            'font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="14" fill="#333">'
            f"{theme}</text>"
        )
    lines.append("</svg>")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def svg_distribution(points: list[dict[str, Any]], output: Path) -> None:
    width = 1200
    height = 900
    margin = 90
    plot_right = 930
    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    def scale_x(value: float) -> float:
        return margin + (value - min_x) / (max_x - min_x or 1) * (plot_right - margin)

    def scale_y(value: float) -> float:
        return height - margin - (value - min_y) / (max_y - min_y or 1) * (height - 2 * margin)

    by_theme: dict[str, list[dict[str, Any]]] = {}
    for point in points:
        by_theme.setdefault(point["primary_theme"], []).append(point)

    lines: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" viewBox="0 0 1200 900">',
        '<rect width="1200" height="900" fill="#fbfaf7"/>',
        '<text x="80" y="50" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="28" fill="#222">小倉百人一首 意味空間 PCA 分布</text>',
        '<text x="80" y="80" font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="15" fill="#555">線なし。点の色は主題、薄い大きな点は主題別centroid。</text>',
    ]
    zero_x = scale_x(0.0)
    zero_y = scale_y(0.0)
    lines.append(f'<line x1="{margin}" y1="{zero_y:.2f}" x2="{plot_right}" y2="{zero_y:.2f}" stroke="#e5dfd5" stroke-width="1"/>')
    lines.append(f'<line x1="{zero_x:.2f}" y1="{margin}" x2="{zero_x:.2f}" y2="{height - margin}" stroke="#e5dfd5" stroke-width="1"/>')

    for theme, group in by_theme.items():
        centroid_x = sum(point["x"] for point in group) / len(group)
        centroid_y = sum(point["y"] for point in group) / len(group)
        color = THEME_COLORS.get(theme, "#777777")
        lines.append(
            f'<circle cx="{scale_x(centroid_x):.2f}" cy="{scale_y(centroid_y):.2f}" '
            f'r="{12 + min(len(group), 40) * 0.22:.2f}" fill="{color}" opacity="0.16"/>'
        )

    for point in sorted(points, key=lambda item: item["id"]):
        x = scale_x(point["x"])
        y = scale_y(point["y"])
        label = point["id"]
        color = point["color"]
        lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="7.5" fill="{color}" opacity="0.9"/>')
        lines.append(
            f'<text x="{x + 9:.2f}" y="{y + 4:.2f}" '
            'font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="11" fill="#222">'
            f"{label}</text>"
        )

    legend_x = 980
    legend_y = 120
    for index, (theme, color) in enumerate(THEME_COLORS.items()):
        y = legend_y + index * 24
        count = len(by_theme.get(theme, []))
        lines.append(f'<circle cx="{legend_x}" cy="{y}" r="6" fill="{color}"/>')
        lines.append(
            f'<text x="{legend_x + 14}" y="{y + 5}" '
            'font-family="Hiragino Sans, Yu Gothic, sans-serif" font-size="14" fill="#333">'
            f"{theme} ({count})</text>"
        )
    lines.append("</svg>")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--embeddings",
        type=Path,
        default=ROOT / "data/embeddings/hyakunin_isshu_original_kana_text-embedding-3-large.json",
    )
    parser.add_argument("--poems", type=Path, default=ROOT / "data/hyakunin_isshu.csv")
    parser.add_argument("--pca-output", type=Path, default=ROOT / "public/data/embeddings_pca.json")
    parser.add_argument("--adjacency-output", type=Path, default=ROOT / "public/data/adjacency_stats.json")
    parser.add_argument("--pairs-output", type=Path, default=ROOT / "public/data/pair_rankings.json")
    parser.add_argument("--svg-output", type=Path, default=ROOT / "docs/figures/semantic-pca-map.svg")
    parser.add_argument(
        "--distribution-svg-output",
        type=Path,
        default=ROOT / "docs/figures/semantic-pca-distribution.svg",
    )
    parser.add_argument("--viewer-data-output", type=Path, default=ROOT / "docs/viewer/viewer_data.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = sorted(read_csv(args.poems), key=lambda row: int(row["id"]))
    embedding_payload = read_json(args.embeddings)
    embedding_records = sorted(embedding_payload["records"], key=lambda row: int(row["id"]))
    vectors = [record["embedding"] for record in embedding_records]
    vector_dimension = len(vectors[0]) if vectors else 0
    coords, explained = pca_scores(vectors)
    sim = similarity_matrix(vectors)
    pca = pca_payload(rows, embedding_payload["meta"], coords, explained, vector_dimension)
    write_json(args.pca_output, pca)
    adjacency = adjacency_stats(rows, sim, embedding_payload["meta"], vector_dimension)
    pairs = pair_rankings(rows, sim, embedding_payload["meta"], vector_dimension)
    write_json(args.adjacency_output, adjacency)
    write_json(args.pairs_output, pairs)
    write_json(
        args.viewer_data_output,
        {
            "pca": pca,
            "adjacency_summary": adjacency["summary"],
            "top_similar_adjacent": adjacency["top_similar_adjacent"],
            "largest_jumps": adjacency["largest_jumps"],
        },
    )
    svg_map(pca["points"], args.svg_output)
    svg_distribution(pca["points"], args.distribution_svg_output)
    print(f"wrote {args.pca_output}")
    print(f"wrote {args.adjacency_output}")
    print(f"wrote {args.pairs_output}")
    print(f"wrote {args.viewer_data_output}")
    print(f"wrote {args.svg_output}")
    print(f"wrote {args.distribution_svg_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
