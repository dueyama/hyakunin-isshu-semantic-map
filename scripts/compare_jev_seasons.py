#!/usr/bin/env python3
"""Compare cached Jev judgments to existing embeddings, without making API calls.

Requires numpy; --figures also requires matplotlib. Detailed results stay private.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path

import numpy as np

from jev_seasons import ROOT, RUN, MODEL, LABELS, SEASONS, QUESTIONS, digest, encoded, load_poems, load_result
from normalize_waka import build_embedding_text

SPACES = [
    ("ogura_small", "ogura", "original_kana", "data/embeddings/hyakunin_isshu_original_kana_text-embedding-3-small.json"),
    ("ogura_large", "ogura", "original_kana", "data/embeddings/hyakunin_isshu_original_kana_text-embedding-3-large.json"),
    ("ogura_original", "ogura", "original", "_private/literature/embeddings/hyakunin_isshu_original_text-embedding-3-small.json"),
    ("shuka_small", "shuka", "original", "_private/literature/embeddings/hyakunin_shuka_mizugaki_text-embedding-3-small.json"),
]
SEED = 20260920


def align_embeddings(poems, cache, mode):
    """Align by identity, never row position; mismatched texts are explicitly excluded."""
    records = cache["records"]
    by_order = {int(str(r["id"]).lstrip("HS")): r for r in records}
    if len(by_order) != len(records) or set(by_order) != {p["order"] for p in poems}:
        raise ValueError("Embedding IDs do not cover the corpus exactly")
    aligned = [by_order[p["order"]] for p in poems]
    matrix = np.asarray([r["embedding"] for r in aligned], dtype=float)
    if matrix.ndim != 2 or not np.isfinite(matrix).all() or (np.linalg.norm(matrix, axis=1) == 0).any():
        raise ValueError("Invalid embedding vectors")
    valid = np.array([r["text_sha256"] == digest(build_embedding_text(p["source_row"], mode))
                      for p, r in zip(poems, aligned)])
    return matrix, valid


def neighbor_statistics(vectors, labels, trials=10000, seed=SEED):
    """Five-neighbor homophily, preserving category counts in node-label permutations.

    Pairwise edges are dependent; shuffle poems' labels, never sample edges as IID.
    """
    vectors = np.asarray(vectors, dtype=float)
    labels = np.asarray(labels)
    n = len(labels)
    if n < 6 or len(set(labels)) < 2:
        return {"n": n, "available": False}
    normalized = vectors / np.linalg.norm(vectors, axis=1)[:, None]
    similarity = normalized @ normalized.T
    ranking = similarity.copy()
    np.fill_diagonal(ranking, -np.inf)
    neighbors = np.argsort(-ranking, axis=1, kind="stable")[:, :5]
    observed = float((labels[neighbors] == labels[:, None]).mean())
    counts = Counter(labels.tolist())
    expected = sum(c * (c - 1) for c in counts.values()) / (n * (n - 1))
    rng = np.random.default_rng(seed)
    null = np.empty(trials)
    for start in range(0, trials, 250):
        batch = np.array([rng.permutation(labels) for _ in range(min(250, trials - start))])
        null[start:start + len(batch)] = (batch[:, neighbors] == batch[:, :, None]).mean(axis=(1, 2))
    left, right = np.triu_indices(n, 1)
    same = labels[left] == labels[right]
    within = float(similarity[left[same], right[same]].mean()) if same.any() else None
    between = float(similarity[left[~same], right[~same]].mean()) if (~same).any() else None
    return {"n": n, "available": True, "k": 5, "counts": dict(counts),
            "same_label_neighbor_rate": observed, "random_expectation": expected,
            "null_mean": float(null.mean()), "null_95_percent_interval": np.quantile(null, [.025, .975]).tolist(),
            "permutation_p_one_sided": float((1 + (null >= observed - 1e-12).sum()) / (trials + 1)),
            "same_label_cosine": within, "different_label_cosine": between,
            "cosine_gap": within - between if within is not None and between is not None else None,
            "trials": trials, "seed": seed}


def build_report(trials=10000):
    poems = load_poems()
    entries = {p["id"]: load_result(p) for p in poems}
    judgments = {key: entry["response"]["answers"] for key, entry in entries.items()}
    report = {"meta": {"jev_model": MODEL, "questions_sha256": digest(encoded(QUESTIONS)),
                       "seed": SEED, "trials": trials, "prompt_language": "English", "text_language": "Japanese",
                       "input_tokens": sum(e["response"]["usage"]["input_tokens"] for e in entries.values()),
                       "output_tokens": sum(e["response"]["usage"]["output_tokens"] for e in entries.values()),
                       "first_request_at": min(e["created_at"] for e in entries.values()),
                       "last_request_at": max(e["created_at"] for e in entries.values()),
                       "median_request_seconds": float(np.median([e["elapsed_seconds"] for e in entries.values() if e["elapsed_seconds"] is not None])),
                       "validated_responses": len(entries),
                       "validation_recoveries": [key for key, e in entries.items() if e.get("validation_recovery")],
                       "usage_scope": "Retained, validated responses only; excludes the first failed S053 response, whose usage was not retained.",
                       "note": "Exploratory model comparison, not validated classical-literature accuracy."},
              "corpora": {}, "spaces": {}, "shared": {}}
    for corpus in ["ogura", "shuka"]:
        selected = [p for p in poems if p["corpus"] == corpus]
        counts = Counter(judgments[p["id"]]["season"]["choice"] for p in selected)
        report["corpora"][corpus] = {"n": len(selected), "season_counts": dict(counts),
            "low_confidence_count_below_0_6": sum(judgments[p["id"]]["season"]["confidence"] < .6 for p in selected),
            "median_confidence": float(np.median([judgments[p["id"]]["season"]["confidence"] for p in selected])),
            "love_at_least_0_5": sum(judgments[p["id"]]["love"]["noul"] >= .5 for p in selected),
            "nature_at_least_0_5": sum(judgments[p["id"]]["nature"]["noul"] >= .5 for p in selected)}
    ogura = [p for p in poems if p["corpus"] == "ogura"]
    tagged = [p for p in ogura if p["source_row"]["season"] in LABELS.values()]
    differences = [p["id"] for p in tagged if LABELS[judgments[p["id"]]["season"]["choice"]] != p["source_row"]["season"]]
    love_tagged = [p for p in ogura if "恋" in p["source_row"]["theme"]]
    report["reference_comparison"] = {
        "tagged_n": len(tagged), "agree_n": len(tagged) - len(differences), "difference_ids": differences,
        "blank_n": len(ogura) - len(tagged),
        "blank_with_four_season_choice_ids": [p["id"] for p in ogura if not p["source_row"]["season"] and judgments[p["id"]]["season"]["choice"] in SEASONS],
        "legacy_love_n": len(love_tagged),
        "legacy_love_and_jev_love_n": sum(judgments[p["id"]]["love"]["noul"] >= .5 for p in love_tagged),
        "legacy_season_and_jev_nature_n": sum(judgments[p["id"]]["nature"]["noul"] >= .5 for p in tagged),
        "note": "Initial source-derived tags are provisional references; blanks are missing labels, not negative labels."}
    common = [p for p in poems if p["corpus"] == "shuka" and p["hyakunin_id"]]
    shared_differences = []
    for p in common:
        h = f"H{p['hyakunin_id']:03d}"
        a, b = judgments[h]["season"], judgments[p["id"]]["season"]
        if a["choice"] != b["choice"]:
            shared_differences.append({"ogura_id": h, "shuka_id": p["id"], "ogura": a, "shuka": b})
    report["shared"] = {"n": len(common), "agree_n": len(common) - len(shared_differences),
                         "differences": shared_differences,
                         "note": "Shared poems are not independent replications. Wording and kana-input conditions also differ."}
    for name, corpus, mode, filename in SPACES:
        selected = [p for p in poems if p["corpus"] == corpus]
        cache = json.loads((ROOT / filename).read_text())
        vectors, valid = align_embeddings(selected, cache, mode)
        labels = np.array([judgments[p["id"]]["season"]["choice"] for p in selected])
        seasonal = valid & np.isin(labels, SEASONS)
        confident = seasonal & np.array([judgments[p["id"]]["season"]["confidence"] >= .6 for p in selected])
        report["spaces"][name] = {"embedding_model": cache["meta"]["model"], "input_mode": mode,
            "dimensions": int(vectors.shape[1]), "hash_mismatch_ids": [p["id"] for p, ok in zip(selected, valid) if not ok],
            "four_seasons": neighbor_statistics(vectors[seasonal], labels[seasonal], trials),
            "four_seasons_confidence_0_6": neighbor_statistics(vectors[confident], labels[confident], trials),
            "all_labels": neighbor_statistics(vectors[valid], labels[valid], trials)}
    report["review_rows"] = [{"id": p["id"], "corpus": p["corpus"], "hyakunin_id": p["hyakunin_id"],
        "legacy_season": p["source_row"].get("season", ""), "legacy_theme": p["source_row"].get("theme", ""),
        "season": judgments[p["id"]]["season"]["choice"],
        "confidence": judgments[p["id"]]["season"]["confidence"],
        **{k: a["noul"] for k, a in judgments[p["id"]].items() if k != "season"}}
        for p in poems]
    return report, poems, judgments


def make_figures(report, poems, judgments):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from analyze_embeddings import pca_scores, primary_theme

    # Keep Japanese text editable in SVG; set a real Japanese font for raster verification.
    candidates = list(Path("/System/Library/Fonts").glob("ヒラギノ角ゴシック W3.ttc"))
    if candidates:
        font_manager.fontManager.addfont(str(candidates[0]))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(candidates[0])).get_name()
    else:
        plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]
    plt.rcParams.update({"svg.fonttype": "none", "font.size": 10, "axes.unicode_minus": False})
    colors = {"spring": "#278344", "summer": "#00838c", "autumn": "#c57816", "winter": "#4269ae",
              "mixed": "#9353a0", "unspecified": "#959b9b", "uncertain": "#303b3d"}
    themes = {"春": colors["spring"], "夏": colors["summer"], "秋": colors["autumn"], "冬": colors["winter"],
              "恋": "#c04f76", "雑": "#959b9b", "羇旅": "#8059aa", "離別": "#9a694d", "哀傷": "#596570"}
    for name in ("ogura_small", "shuka_small"):
        _, corpus, mode, filename = next(s for s in SPACES if s[0] == name)
        selected = [p for p in poems if p["corpus"] == corpus]
        vectors, valid = align_embeddings(selected, json.loads((ROOT / filename).read_text()), mode)
        # Same existing pure-Python PCA algorithm and seed; no Jev labels enter projection.
        coords, explained = pca_scores(vectors.tolist())
        xy = np.array([[c["x"], c["y"]] for c in coords])
        panels = 2 if corpus == "ogura" else 1
        fig, axes = plt.subplots(1, panels, figsize=(13 if panels == 2 else 8, 6.6), squeeze=False)
        for panel, ax in enumerate(axes[0]):
            legacy = panels == 2 and panel == 0
            mapping = themes if legacy else {LABELS[k]: v for k, v in colors.items()}
            labels = [primary_theme(p["source_row"]) if legacy else LABELS[judgments[p["id"]]["season"]["choice"]] for p in selected]
            for label, color in mapping.items():
                mask = np.array([l == label for l in labels])
                if mask.any():
                    ax.scatter(xy[mask, 0], xy[mask, 1], c=color, s=46, alpha=.85, label=f"{label} ({mask.sum()})", linewidths=.4, edgecolors="white")
            for i, p in enumerate(selected):
                if not legacy and judgments[p["id"]]["season"]["confidence"] < .6:
                    ax.scatter(*xy[i], s=78, facecolors="none", edgecolors="#212b32", linewidths=.8)
                if not valid[i]:
                    ax.scatter(*xy[i], marker="x", c="black", s=85)
            # A bounded set of readable labels, chosen for review rather than significance.
            ids = {"H002", "H009", "H010", "H017", "H053", "H066", "H067"} if corpus == "ogura" else {"S001", "S002", "S076", "S101"}
            for i, p in enumerate(selected):
                if p["id"] in ids:
                    ax.annotate(p["id"], xy[i], xytext=(4, 6), textcoords="offset points", fontsize=8)
            ax.set_title("既存の主題タグ" if legacy else "Jev が判定した主な季節", pad=14)
            ax.set_xlabel(f"PC1（寄与率 {explained['pc1']:.1%}）")
            ax.set_ylabel(f"PC2（寄与率 {explained['pc2']:.1%}）")
            ax.grid(alpha=.15)
            ax.spines[["top", "right"]].set_visible(False)
            ax.legend(loc="upper center", bbox_to_anchor=(.5, -.15), ncol=4, frameon=False, fontsize=9)
        fig.suptitle("小倉100首：位置を固定し、色だけを変える" if corpus == "ogura" else "百人秀歌101首：既存の埋め込みに季節判定を重ねる", fontsize=16, y=.99)
        fig.text(.5, .012, "外側の黒い輪：確信度0.6未満。×：入力ハッシュ不一致、近傍統計から除外。" if corpus == "ogura" else "外側の黒い輪：確信度0.6未満。小倉の図とは別にPCAを計算している。", ha="center", fontsize=9)
        fig.tight_layout(rect=(0, .05, 1, .96))
        stem = "jev-season-ogura" if corpus == "ogura" else "jev-season-shuka"
        svg_path = ROOT / "docs/figures" / f"{stem}.svg"
        fig.savefig(svg_path, metadata={"Date": None})
        # Matplotlib leaves trailing spaces in path data; keep publication diffs clean.
        svg_path.write_text("\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()) + "\n", encoding="utf-8")
        fig.savefig(RUN / f"{stem}.png", dpi=140)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=10000)
    parser.add_argument("--figures", action="store_true")
    parser.add_argument("--public-summary", action="store_true", help="Write aggregate-only JSON under docs; no poem text or vectors")
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be positive")
    report, poems, judgments = build_report(args.trials)
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    with (RUN / "review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report["review_rows"][0]))
        writer.writeheader()
        writer.writerows(report["review_rows"])
    if args.figures:
        make_figures(report, poems, judgments)
    if args.public_summary:
        public = {k: report[k] for k in ("meta", "corpora", "reference_comparison", "spaces")}
        public["shared"] = {k: report["shared"][k] for k in ("n", "agree_n", "note")}
        (ROOT / "docs/jev-season-summary.json").write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("review_rows", "shared")}, ensure_ascii=False, indent=2))
    print("shared", report["shared"]["agree_n"], "/", report["shared"]["n"])


if __name__ == "__main__":
    main()
