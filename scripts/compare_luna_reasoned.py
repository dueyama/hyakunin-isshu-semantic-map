#!/usr/bin/env python3
"""Compare two frozen Luna runs and export bounded, generated explanations."""
from __future__ import annotations

import argparse
from collections import Counter
import html
import json

import gpt_seasons
import gpt_seasons_reasoned as reasoned
from jev_seasons import ROOT, LABELS, digest, encoded, load_poems
from normalize_waka import normalize_text


def bounded_public_explanation(answer, input_text, all_input_forms):
    """Preserve model snippets verbatim; flag mismatches rather than repairing them.

    Never export an explanation that reproduces a complete normalized input poem.
    Raw output remains private in all cases, including withheld explanations.
    """
    evidence = list(answer["evidence"])
    matches = [s in input_text for s in evidence]
    combined = normalize_text(answer["explanation"] + "".join(evidence))
    withheld = any(form in combined for form in all_input_forms)
    return {"evidence": evidence, "evidence_matches": matches,
            "explanation": "" if withheld else answer["explanation"],
            "explanation_withheld": withheld}


def build_report():
    poems = load_poems()
    baseline_public = json.loads((ROOT / "docs/season-comparison.json").read_text())
    by_id = {r["id"]: r for r in baseline_public["rows"]}
    if len(by_id) != len(poems) or set(by_id) != {p["id"] for p in poems}:
        raise ValueError("Public baseline IDs must exactly cover the inputs")
    all_forms = {normalize_text(line) for p in poems for line in p["text"].splitlines() if line}
    if any(len(form) <= 16 for form in all_forms):
        raise ValueError("Evidence limit must be shorter than every complete input form")
    rows, entries = [], []
    for p in poems:
        baseline = gpt_seasons.load_result(p)
        base_season = gpt_seasons.validate_response(baseline["response"])["season"]
        entry = reasoned.load_result(p)  # A missing or invalid result stops publication.
        answer = reasoned.validate_response(entry["response"])
        entries.append(entry)
        old, new = baseline["request"], entry["request"]
        for key in ("model", "reasoning", "input", "max_output_tokens", "store"):
            if old[key] != new[key]:
                raise ValueError("Conditions differ beyond explanation instruction/schema: " + key)
        if new["instructions"] != old["instructions"] + "\n\n" + reasoned.EXPLANATION_INSTRUCTIONS:
            raise ValueError("Principal instructions must be preserved exactly")
        public = by_id[p["id"]]
        if public["gpt"] != base_season:
            raise ValueError("Public baseline does not match cached baseline")
        rows.append({"id": p["id"], "corpus": p["corpus"], "order": p["order"],
            "poet": public["poet"], "baseline_season": base_season,
            "reasoned_season": answer["season"], "jev_season": public["jev"],
            "reference": public["reference"],
            **bounded_public_explanation(answer, p["text"], all_forms)})
    report = {"meta": {"model": reasoned.MODEL, "condition": "with_evidence",
        "reasoning_effort": "medium", "max_output_tokens": 4096, "completed": len(rows), "total": len(poems),
        "schema_field_order": ["season", "evidence", "explanation"],
        "additional_instructions_sha256": digest(reasoned.EXPLANATION_INSTRUCTIONS),
        "evidence_max_items": 2, "evidence_max_characters_each": 8, "explanation_max_characters": 180,
        "baseline_public_json_sha256": digest(encoded(baseline_public)),
        "input_and_principal_criteria_unchanged": True,
        "first_request_at": min(e["created_at"] for e in entries),
        "last_request_at": max(e["created_at"] for e in entries),
        "usage": {k: sum(e["response"]["usage"][k] for e in entries)
                  for k in ("input_tokens", "output_tokens", "total_tokens")},
        "evidence_mismatch_ids": [r["id"] for r in rows if not all(r["evidence_matches"])],
        "withheld_explanation_ids": [r["id"] for r in rows if r["explanation_withheld"]],
        "note": "Two single-run conditions; differences do not isolate an explanation effect from run variation. "
                "Explanations are model-generated justifications, not verified annotations or internal reasoning traces."},
        "corpora": {}, "shared": {}, "rows": rows}
    inverse = {v: k for k, v in LABELS.items()}
    for corpus in ("ogura", "shuka"):
        selected = [r for r in rows if r["corpus"] == corpus]
        changed = [r for r in selected if r["baseline_season"] != r["reasoned_season"]]
        reference = [r for r in selected if r["reference"]["season"]]
        report["corpora"][corpus] = {"n": len(selected), "changed_n": len(changed),
            "changed_ids": [r["id"] for r in changed],
            "baseline_counts": dict(Counter(r["baseline_season"] for r in selected)),
            "reasoned_counts": dict(Counter(r["reasoned_season"] for r in selected)),
            "jev_agree_n": sum(r["reasoned_season"] == r["jev_season"] for r in selected),
            "reference_seasonal": {"n": len(reference),
                "baseline_agree_n": sum(r["baseline_season"] == inverse[r["reference"]["season"]] for r in reference),
                "reasoned_agree_n": sum(r["reasoned_season"] == inverse[r["reference"]["season"]] for r in reference)},
            "transitions": [{"from": a, "to": b, "n": n}
                            for (a, b), n in sorted(Counter((r["baseline_season"], r["reasoned_season"]) for r in changed).items())]}
    lookup = {r["id"]: r for r in rows}
    shared = [r for r in rows if r["corpus"] == "shuka" and r["reference"]["ogura_id"]]
    for key in ("baseline_season", "reasoned_season"):
        diffs = [r["id"] for r in shared if r[key] != lookup[r["reference"]["ogura_id"]][key]]
        report["shared"][key] = {"n": len(shared), "agree_n": len(shared) - len(diffs), "difference_ids": diffs}
    return report


def article_section(report):
    out = ['<section id="luna-reasons">', '<h2>8. Lunaに根拠も求めてみる</h2>',
        '<p>もう一つの条件として、Lunaに「季節・根拠となる短い語句・日本語の説明」を一緒に求めた。本文、主季節の指示と七択、モデル、推論medium、出力上限は前回と同じで、追加したのは説明の指示と出力項目である。前回の答えや文献の分類は見せず、全201首を改めて判定した。</p>',
        '<div class="table-wrap"><table><caption>表S-7. Lunaの季節のみ条件と、根拠付き条件の比較。</caption>',
        '<thead><tr><th>対象</th><th>季節が変わった歌</th><th>資料の季節と一致：季節のみ → 根拠付き</th></tr></thead><tbody>']
    for corpus, name in (("ogura", "小倉"), ("shuka", "秀歌")):
        c = report["corpora"][corpus]
        r = c["reference_seasonal"]
        out.append(f'<tr><th>{name}{c["n"]}首</th><td>{c["changed_n"]}／{c["n"]}首</td>' +
            f'<td>{r["baseline_agree_n"]}／{r["n"]} → {r["reasoned_agree_n"]}／{r["n"]}首</td></tr>')
    out += ['</tbody></table></div>']
    changed = [r for r in report["rows"] if r["baseline_season"] != r["reasoned_season"]]
    if changed:
        out += ['<div class="table-wrap"><table><caption>判定が変わった全ての歌。説明はLunaの生成文。</caption>',
            '<thead><tr><th>歌</th><th>季節のみ → 根拠付き</th><th>根拠付き条件の説明</th></tr></thead><tbody>']
        for r in changed:
            out.append(f'<tr><th><a href="./luna-reasons/#poem-{r["id"].lower()}">{r["id"]}</a></th>' +
                f'<td>{LABELS[r["baseline_season"]]} → {LABELS[r["reasoned_season"]]}</td>' +
                f'<td>{html.escape(r["explanation"] or "全文引用を含むため説明は省略")}</td></tr>')
        out += ['</tbody></table></div>']
        h012 = next((r for r in changed if r["id"] == "H012"), None)
        if h012 and "七夕" in h012["explanation"]:
            out.append('<p>H012の説明では、入力本文にない「七夕」という場面が補われている。説明が付いたことで、判定だけでは見えなかったこのような読みの補足も確認できる。ここでは、その場面設定を文献で確認した事実として採用しない。</p>')
    else:
        out.append('<p>今回は、説明を求めても201首の季節ラベルは全て同じだった。根拠付き一覧で、どの語を手がかりにした説明が出たかを読める。</p>')
    shared = report["shared"]["reasoned_season"]
    out += [f'<p>根拠付き条件での小倉・秀歌の共通97首の判定一致は{shared["agree_n"]}／{shared["n"]}首。季節のみ条件では97／97首だった。</p>',
        '<p>両条件は推論設定mediumで、後の条件だけ内部推論を有効にしたわけではない。得た説明はモデルが生成した短い説明であり、文学的に検証済みの注釈や内部の思考過程そのものではない。また各条件一回の実行なので、判定の変化を説明要求の効果と通常の実行変動に分けることはできない。</p>',
        '<p><a href="./luna-reasons/">Luna根拠付き：全201首の説明と変更点を見る →</a></p>', '</section>']
    mismatch_ids = report["meta"]["evidence_mismatch_ids"]
    if mismatch_ids:
        out.insert(-2, f'<p>根拠語句を入力本文と照合すると、{len(mismatch_ids)}首（' +
                   '・'.join(mismatch_ids) + '）で表記が完全には一致しなかった。一覧では生成された表記を直さず、該当箇所に注記した。引用の一致を確認する検査であって、説明の文学的な妥当性の検証ではない。</p>')
    return '\n      '.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-article", action="store_true")
    args = parser.parse_args()
    report = build_report()
    (ROOT / "docs/luna-reasoned-comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if args.update_article:
        path = ROOT / "docs/paper/seasons/index.html"
        text = path.read_text()
        start, end = "<!-- luna-reasoned-results:start -->", "<!-- luna-reasoned-results:end -->"
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError("Missing or duplicate article result markers")
        before, rest = text.split(start)
        _, after = rest.split(end)
        path.write_text(before + start + "\n      " + article_section(report) + "\n      " + end + after)
    print(json.dumps({k: report[k] for k in ("meta", "corpora", "shared")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
