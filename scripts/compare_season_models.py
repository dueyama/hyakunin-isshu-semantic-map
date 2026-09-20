#!/usr/bin/env python3
"""Compare cached seasonal judgments and publish labels/reference metadata only."""
from __future__ import annotations

import argparse
from collections import Counter
import html
import json

import numpy as np

import gpt_seasons
from jev_seasons import ROOT, MODEL, LABELS, SEASONS, QUESTIONS, digest, encoded, load_poems, load_result
from compare_jev_seasons import SPACES, align_embeddings, neighbor_statistics


def agreement(rows, left="jev", right="gpt"):
    selected = [r for r in rows if r[left] is not None and r[right] is not None]
    different = [r["id"] for r in selected if r[left] != r[right]]
    return {"n": len(selected), "agree_n": len(selected) - len(different),
            "difference_ids": different}


def build_report(trials=10000, allow_partial=False):
    poems = load_poems()
    references = json.loads((ROOT / "docs/season-references.json").read_text())
    ogura_refs = {r["ogura_id"]: r for r in references["rows"]}
    unique_refs = {r["shuka_id"]: r for r in references["shuka_unique_rows"]}
    if set(ogura_refs) != {f"H{i:03d}" for i in range(1, 101)}:
        raise ValueError("Reference IDs do not cover Ogura")
    rows, gpt_entries = [], []
    for p in poems:
        jev = load_result(p)["response"]["answers"]["season"]["choice"]
        gpt = None
        if gpt_seasons.cache_path(p).exists():
            entry = gpt_seasons.load_result(p)
            gpt_entries.append(entry)
            gpt = gpt_seasons.validate_response(entry["response"])["season"]
        elif not allow_partial:
            raise ValueError("Missing GPT result: " + p["id"])
        h = f"H{p['hyakunin_id']:03d}" if p["hyakunin_id"] else None
        ref = ogura_refs[h] if h else unique_refs[p["id"]]
        scope = "direct" if p["corpus"] == "ogura" else "shared_poem" if h else (
            "related_version" if p["id"] == "S090" else "source_poem")
        reference = {"division": ref["reference_division"], "season": ref["season_annotation"],
                     "strict_season": ref["reference_season"], "source_url": ref["source_url"],
                     "source_anthology": ref["source_anthology"], "source_number": ref.get("source_number"),
                     "ogura_id": h, "scope": scope}
        # Explicit allowlist: never copy input, raw responses or unpublished poem text.
        rows.append({"id": p["id"], "corpus": p["corpus"], "order": p["order"],
                     "poet": p["source_row"]["poet_jp"], "jev": jev, "gpt": gpt,
                     "legacy_season": p["source_row"].get("season", ""), "reference": reference})
    report = {"meta": {"jev_model": MODEL, "gpt_model": gpt_seasons.MODEL,
        "gpt_reasoning_effort": "medium", "gpt_max_output_tokens": 4096,
        "gpt_structured_output": "Single season enum; no generated confidence or rationale",
        "principal_question_sha256": digest(encoded(QUESTIONS["season"])),
        "same_text_and_principal_criteria": True, "jev_questions_per_poem": 7, "gpt_questions_per_poem": 1,
        "gpt_completed": len(gpt_entries), "total_poems": len(poems),
        "gpt_usage": {key: sum(e["response"]["usage"][key] for e in gpt_entries)
                      for key in ("input_tokens", "output_tokens", "total_tokens")},
        "gpt_first_request_at": min((e["created_at"] for e in gpt_entries), default=None),
        "gpt_last_request_at": max((e["created_at"] for e in gpt_entries), default=None),
        "reference_checked_date": references["checked_date"],
        "note": "Single-run experimental observations; agreement is not literary accuracy."},
        "corpora": {}, "shared": {}, "spaces": {}, "rows": rows}
    inverse = {v: k for k, v in LABELS.items()}
    for corpus in ("ogura", "shuka"):
        selected = [r for r in rows if r["corpus"] == corpus]
        info = {"n": len(selected), "models": {}, "model_agreement": agreement(selected)}
        for model in ("jev", "gpt"):
            completed = [r for r in selected if r[model] is not None]
            # Shuka shared-poem reference is indirect; report separately by corpus.
            seasonal_ref = [r for r in completed if r["reference"]["season"]]
            strict_ref = [r for r in completed if r["reference"]["strict_season"]]
            info["models"][model] = {"completed": len(completed),
                "season_counts": dict(Counter(r[model] for r in completed)),
                "reference_seasonal": {"n": len(seasonal_ref),
                    "agree_n": sum(r[model] == inverse[r["reference"]["season"]] for r in seasonal_ref),
                    "difference_ids": [r["id"] for r in seasonal_ref if r[model] != inverse[r["reference"]["season"]]]},
                "reference_strict_four_seasons": {"n": len(strict_ref),
                    "agree_n": sum(r[model] == inverse[r["reference"]["strict_season"]] for r in strict_ref)}}
        info["confusion_jev_rows_gpt_columns"] = {
            a: {b: sum(r["jev"] == a and r["gpt"] == b for r in selected) for b in LABELS}
            for a in LABELS}
        report["corpora"][corpus] = info
    by_id = {r["id"]: r for r in rows}
    common = [r for r in rows if r["corpus"] == "shuka" and r["reference"]["ogura_id"]]
    for model in ("jev", "gpt"):
        pairs = [{"id": r["id"], "shuka": r[model], "ogura": by_id[r["reference"]["ogura_id"]][model]}
                 for r in common]
        report["shared"][model] = agreement(pairs, "ogura", "shuka")
    for name, corpus, mode, filename in SPACES:
        selected = [p for p in poems if p["corpus"] == corpus]
        vectors, valid = align_embeddings(selected, json.loads((ROOT / filename).read_text()), mode)
        a = np.array([by_id[p["id"]]["jev"] for p in selected], dtype=object)
        b = np.array([by_id[p["id"]]["gpt"] for p in selected], dtype=object)
        common_valid = valid & (b != None)  # noqa: E711; elementwise object-array comparison
        intersection = common_valid & np.isin(a, SEASONS) & np.isin(b, SEASONS)
        report["spaces"][name] = {"same_population_all_labels": {
            "jev": neighbor_statistics(vectors[common_valid], a[common_valid], trials),
            "gpt": neighbor_statistics(vectors[common_valid], b[common_valid], trials)},
            "both_models_four_seasons": {
                "ids": [p["id"] for p, ok in zip(selected, intersection) if ok],
                "jev": neighbor_statistics(vectors[intersection], a[intersection], trials),
                "gpt": neighbor_statistics(vectors[intersection], b[intersection], trials)}}
    return report


def article_section(report):
    """Keep reader-facing counts in sync with the exact published result rows."""
    out = ['<section id="gpt">', '<h2>7. GPTにも同じ季節を尋ねる</h2>',
        '<p>まず「季節のみ」の条件として、同じ本文と主季節の質問をGPT-5.6-Lunaにも渡した。Jevの判定や文献の分類を教えて答えを合わせる操作はしていない。両者の出力を比較すると、次のようになった。</p>',
        '<div class="table-wrap"><table><caption>表S-4. 同じ入力に対するモデル間の一致と、資料の季節との対応。</caption>',
        '<thead><tr><th>対象</th><th>JevとGPTの一致</th><th>資料の季節とJev</th><th>資料の季節とGPT</th></tr></thead><tbody>']
    for corpus, label in (("ogura", "小倉"), ("shuka", "秀歌")):
        info = report["corpora"][corpus]
        values = [info["model_agreement"], info["models"]["jev"]["reference_seasonal"],
                  info["models"]["gpt"]["reference_seasonal"]]
        out.append(f'<tr><th>{label}{info["n"]}首</th>' + ''.join(
            f'<td>{v["agree_n"]}／{v["n"]}首</td>' if v["n"] else '<td>未実行</td>' for v in values) + '</tr>')
    out += ['</tbody></table></div>',
        '<p>資料との比較は季節が明示された歌に限る。小倉は四季部立32首とH026「雑（秋）」の計33首、秀歌は小倉の対応歌33首と独自歌の春2首の計35首である。秀歌の共通歌の参照は小倉側の分類なので、異文を検証した正解データではない。</p>',
        '<div class="table-wrap"><table><caption>表S-5. GPTの季節のみ条件で選んだ主な季節。</caption>',
        '<thead><tr><th>対象</th><th>判定済み</th><th>春</th><th>夏</th><th>秋</th><th>冬</th><th>季節不特定</th><th>複数／困難</th></tr></thead><tbody>']
    for corpus, label in (("ogura", "小倉"), ("shuka", "秀歌")):
        info = report["corpora"][corpus]["models"]["gpt"]
        c = info["season_counts"]
        if not info["completed"]:
            out.append(f'<tr><th>{label}</th><td>0首</td><td colspan="6">未実行</td></tr>')
        else:
            out.append(f'<tr><th>{label}</th><td>{info["completed"]}首</td>' + ''.join(
                f'<td>{c.get(k, 0)}</td>' for k in SEASONS + ["unspecified"]) +
                f'<td>{c.get("mixed", 0)}／{c.get("uncertain", 0)}</td></tr>')
    out += ['</tbody></table></div>']
    different = [r for r in report["rows"] if r["corpus"] == "ogura" and r["gpt"] is not None and r["jev"] != r["gpt"]]
    out += ['<div class="table-wrap"><table><caption>表S-6. 小倉でモデルの答えが異なった全例。</caption>',
        '<thead><tr><th>歌</th><th>Jev</th><th>GPT</th><th>資料の分類</th></tr></thead><tbody>']
    for r in different:
        out.append(f'<tr><th><a href="./list/#poem-{r["id"].lower()}">{r["id"]}</a></th>' +
            f'<td>{LABELS[r["jev"]]}</td><td>{LABELS[r["gpt"]]}</td><td>{html.escape(r["reference"]["division"])}</td></tr>')
    out += ['</tbody></table></div>',
        '<p>H064・H078ではGPTが資料と同じ冬を選んだ。一方、H083は資料が雑で、Jevは季節不特定、GPTは秋だった。文献と違う分類でも、問うているのが部立か、本文の場面かによって意味が変わる。全ての歌を四季へ押し込む比較にはしない。</p>']
    shared = report["shared"]["gpt"]
    if shared["n"]:
        out.append(f'<p>小倉と秀歌の共通歌に対するGPTの一致は{shared["agree_n"]}／{shared["n"]}首。Jevは81／97首だった。小倉と秀歌で表記・読みの追加条件が異なるため、これは同一入力を繰り返した安定性試験ではない。</p>')
    elif report["meta"]["gpt_completed"] < report["meta"]["total_poems"]:
        out.append('<p class="note">秀歌のGPT判定は未実行。一覧では未実行と表示し、不一致数や季節の集計に含めていない。</p>')
    out += ['<details><summary>同じ歌の集合にそろえて、埋め込みの近傍とも比べる</summary>',
        '<p>JevとGPTがともに春夏秋冬を選んだ歌の共通部分を先に取り出し、その中で上位5近傍を計算した。各行では同じ歌・同じ近傍に二つの分類を重ねる。無作為期待値は各モデルの季節別首数を保って計算する。</p>',
        '<div class="table-wrap"><table><caption>両モデルが四季を選んだ同一集合での近傍比較。括弧内は無作為期待値。</caption>',
        '<thead><tr><th>意味空間</th><th>対象</th><th>Jev同季節率</th><th>GPT同季節率</th></tr></thead><tbody>']
    for key, name in (("ogura_small", "小倉 small"), ("ogura_large", "小倉 large"), ("shuka_small", "秀歌 small")):
        info = report["spaces"][key]["both_models_four_seasons"]
        if not info["gpt"]["available"]:
            continue
        out.append(f'<tr><th>{name}</th><td>{info["gpt"]["n"]}首</td>' + ''.join(
            f'<td>{info[m]["same_label_neighbor_rate"]:.1%}（{info[m]["random_expectation"]:.1%}）</td>' for m in ("jev", "gpt")) + '</tr>')
    out += ['</tbody></table></div>',
        '<p>今回の小倉の共通37首は、両モデルのラベル自体が全て同じだった。そのため近傍率も同じになり、追加の性能証拠にはならない。集合の選び方が表S-2とは異なるため、そちらとの率の大小を性能差として読まない。この表も分類と意味の近さの対応であり、どちらのモデルが正しく季節を読んだかの判定ではない。季節不特定を含む同一全体集合の結果は比較JSONに記録した。</p></details>',
        '<p><a href="./list/">201首の一覧で、両モデルと文献を並べて読む →</a></p>', '</section>']
    return '\n      '.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=10000)
    parser.add_argument("--allow-partial", action="store_true", help="Explicitly mark absent GPT results null")
    parser.add_argument("--update-article", action="store_true", help="Update the marked results section of the article")
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be positive")
    report = build_report(args.trials, args.allow_partial)
    (ROOT / "docs/season-comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if args.update_article:
        path = ROOT / "docs/paper/seasons/index.html"
        text = path.read_text()
        start, end = "<!-- season-model-results:start -->", "<!-- season-model-results:end -->"
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError("Missing or repeated article result markers")
        before, rest = text.split(start)
        _, after = rest.split(end)
        path.write_text(before + start + "\n      " + article_section(report) + "\n      " + end + after)
    print(json.dumps({k: report[k] for k in ("meta", "corpora", "shared")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
