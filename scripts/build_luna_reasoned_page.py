#!/usr/bin/env python3
"""Render the independent Luna with-evidence run from its public comparison.

Only published results and the public poem reference table are read. The full
201-poem catalogue remains readable with JavaScript disabled.
"""

from __future__ import annotations

import argparse
from collections import Counter
import html
import json
from pathlib import Path
from urllib.parse import urlparse

from build_season_catalogue import CORPORA, EXPECTED_IDS, LABELS, public_poems


ROOT = Path(__file__).resolve().parents[1]


def e(value: object) -> str:
    return html.escape(str(value), quote=True)


def validate_data(data: dict, poems: dict) -> list[dict]:
    rows = data["rows"]
    if len(rows) != 201 or {row["id"] for row in rows} != EXPECTED_IDS:
        raise ValueError("comparison must include exactly the 201 unique poem IDs")
    meta = data["meta"]
    if meta.get("completed") != 201 or meta.get("total") != 201:
        raise ValueError("only a completed experiment can be published")
    if meta.get("model") != "gpt-5.6-luna" or meta.get("reasoning_effort") != "medium":
        raise ValueError("unexpected model or reasoning setting")
    sizes: Counter = Counter()
    changes: Counter = Counter()
    for row in rows:
        key = row["id"]
        corpus = "ogura" if key.startswith("H") else "shuka"
        if row["corpus"] != corpus or row["order"] != int(key[1:]):
            raise ValueError(f"ID, corpus and order disagree: {key}")
        for field in ("baseline_season", "reasoned_season", "jev_season"):
            if row[field] not in LABELS:
                raise ValueError(f"unknown {field}: {key}")
        evidence = row["evidence"]
        if (not isinstance(evidence, list) or len(evidence) > 2
                or any(not isinstance(phrase, str) or not phrase.strip() for phrase in evidence)):
            raise ValueError(f"invalid evidence phrases: {key}")
        matches = row["evidence_matches"]
        if not isinstance(matches, list) or len(matches) != len(evidence) or any(type(match) is not bool for match in matches):
            raise ValueError(f"invalid evidence match flags: {key}")
        if type(row["explanation_withheld"]) is not bool:
            raise ValueError(f"invalid explanation withholding flag: {key}")
        if not isinstance(row["explanation"], str) or (not row["explanation"].strip() and not row["explanation_withheld"]):
            raise ValueError(f"missing explanation: {key}")
        if row["explanation_withheld"] and row["explanation"]:
            raise ValueError(f"withheld explanation must not be included in public data: {key}")
        reference = row.get("reference")
        if reference:
            if not isinstance(reference.get("division"), str) or not reference["division"]:
                raise ValueError(f"missing reference division: {key}")
            parsed = urlparse(reference.get("source_url", ""))
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError(f"reference must use HTTPS: {key}")
            expected_h = key if corpus == "ogura" else poems[key]["shared_id"]
            scopes = {"direct"} if corpus == "ogura" else ({"shared_poem"} if expected_h else {"source_poem", "related_version"})
            if reference.get("scope") not in scopes or reference.get("ogura_id") != expected_h:
                raise ValueError(f"reference scope disagrees with poem correspondence: {key}")
        sizes[corpus] += 1
        changes[corpus] += row["baseline_season"] != row["reasoned_season"]
    for corpus in CORPORA:
        if data["corpora"][corpus]["n"] != sizes[corpus] or data["corpora"][corpus]["changed_n"] != changes[corpus]:
            raise ValueError(f"aggregate counts disagree with rows: {corpus}")
    return sorted(rows, key=lambda row: (row["corpus"] == "shuka", row["order"]))


def badge(season: str) -> str:
    return f'<span class="season-badge season-{season}">{LABELS[season]}</span>'


def render_row(row: dict, poem: dict) -> str:
    key = row["id"]
    changed = row["baseline_season"] != row["reasoned_season"]
    shared = poem["shared_id"]
    shared_note = (
        f'<small class="poem-note">表示は小倉同歌 <a href="../../../references/#id-{shared.lower()}">{shared}</a> '
        'の公開本文。秀歌の判定入力とは表記が異なる。</small>' if shared else ""
    )
    evidence = " ".join(f'<q>{e(phrase)}</q>' for phrase in row["evidence"])
    if not evidence:
        evidence = '<span class="unverified">語句の提示なし</span>'
    if not all(row["evidence_matches"]):
        evidence += '<small class="evidence-mismatch">入力と完全一致しない根拠語句</small>'
    explanation = "説明は全文引用を含むため表示を省略" if row["explanation_withheld"] else row["explanation"]
    reference = row.get("reference")
    if reference:
        scope_note = {
            "direct": "資料の分類・部立",
            "shared_poem": "小倉同歌の分類（秀歌の異文は未判定）",
            "source_poem": "出典歌の部立",
            "related_version": "出典歌の部立（異同あり）",
        }[reference["scope"]]
        reference_html = f'{scope_note}：<a href="{e(reference["source_url"])}">{e(reference["division"])}</a>'
        if reference.get("source_anthology"):
            reference_html += f' <span>（{e(reference["source_anthology"])}）</span>'
    else:
        reference_html = "資料の分類・部立：未確認"
    searchable = " ".join([key, poem["poet"], row.get("poet", ""), poem["text"], shared or "", *row["evidence"], row["explanation"]])
    return f'''          <article class="reasoned-poem" id="poem-{key.lower()}" data-corpus="{row['corpus']}" data-season="{row['reasoned_season']}" data-changed="{str(changed).lower()}" data-search="{e(searchable)}" aria-labelledby="heading-{key.lower()}">
            <header class="poem-heading">
              <h3 id="heading-{key.lower()}"><a class="poem-id" href="../../../references/#id-{key.lower()}">{key}</a> <span>{e(poem['poet'])}</span></h3>
              <span class="corpus-label">{CORPORA[row['corpus']]}</span>
              {'<span class="change-flag">判定が変わった</span>' if changed else '<span class="same-flag">判定は同じ</span>'}
            </header>
            <div class="poem-comparison">
              <p class="poem-text">{e(poem['text'])}{shared_note}</p>
              <div class="season-transition" aria-label="季節のみと根拠付きの判定比較">
                <div><span class="condition-label">季節のみ</span>{badge(row['baseline_season'])}</div>
                <span class="transition-arrow" aria-hidden="true">→</span>
                <div><span class="condition-label">根拠付き</span>{badge(row['reasoned_season'])}</div>
              </div>
            </div>
            <div class="model-explanation">
              <p class="evidence"><span class="explanation-label">Lunaが挙げた語句</span>{evidence}</p>
              <p><span class="explanation-label">Lunaの説明</span>{e(explanation)}</p>
            </div>
            <p class="comparison-reference">Jev：{LABELS[row['jev_season']]} <span aria-hidden="true">／</span> {reference_html}</p>
          </article>'''


def build_page(data: dict, references_html: str) -> str:
    poems = public_poems(references_html)
    rows = validate_data(data, poems)
    changed = sum(row["baseline_season"] != row["reasoned_season"] for row in rows)
    corpus_summary = "、".join(
        f'{label}{data["corpora"][corpus]["n"]}首中{data["corpora"][corpus]["changed_n"]}首'
        for corpus, label in (("ogura", "小倉"), ("shuka", "秀歌"))
    )
    options = "".join(f'<option value="{key}">{label}</option>' for key, label in LABELS.items())
    cards = "\n".join(render_row(row, poems[row["id"]]) for row in rows)
    return f'''<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Lunaに根拠も尋ねる | 意味空間で百人一首を読む</title>
    <meta name="description" content="GPT-5.6-Lunaに季節・語句・説明を求めた追加実験。小倉百人一首100首と百人秀歌101首で、季節のみの判定から何が変わったかを比較する。" />
    <link rel="canonical" href="https://dueyama.github.io/hyakunin-isshu-semantic-map/paper/seasons/luna-reasons/" />
    <meta property="og:locale" content="ja_JP" />
    <meta property="og:type" content="article" />
    <meta property="og:title" content="Lunaに根拠も尋ねる | 意味空間で百人一首を読む" />
    <meta property="og:description" content="季節のみの判定と、語句・説明を伴う新しい判定を201首で見比べる。" />
    <meta property="og:url" content="https://dueyama.github.io/hyakunin-isshu-semantic-map/paper/seasons/luna-reasons/" />
    <meta property="og:image" content="https://dueyama.github.io/hyakunin-isshu-semantic-map/figures/hero-heian-semantic-map.jpg" />
    <meta name="twitter:card" content="summary_large_image" />
    <link rel="icon" type="image/svg+xml" href="../../../favicon.svg" />
    <link rel="stylesheet" href="../../../assets/reading.css?v=20260710-review" />
    <link rel="stylesheet" href="../../../assets/season-list.css?v=20260920" />
    <link rel="stylesheet" href="../../../assets/luna-reasons.css?v=20260920" />
    <script src="../../../assets/luna-reasons.js?v=20260920" defer></script>
  </head>
  <body class="article article-one season-catalogue luna-reasons">
    <main>
      <nav aria-label="主なページ">
        <a href="../../../">トップ</a><a href="../">季節比較</a>
        <a href="../list/">Jev・Lunaの一覧</a><a href="./" aria-current="page">Luna根拠付き</a>
      </nav>
      <header class="article-hero">
        <p class="meta">意味空間で百人一首を読む 補章 / 追加実験</p>
        <h1>Lunaに根拠も尋ねる</h1>
        <p class="lead">季節だけを答えるときと、語句・説明も答えるとき。全201首で、判定がどう変わるかを見比べた。</p>
        <div class="project-credits" aria-label="制作クレジット">
          <span><b>分析・実装・本文整理:</b> Codex GPT-6 Astra Ultra</span>
          <span><b>季節判定・根拠説明:</b> OpenAI GPT-5.6-Luna</span>
        </div>
      </header>
      <section aria-labelledby="experiment-heading">
        <h2 id="experiment-heading">もう一つの条件で判定する</h2>
        <p>同じ<code>{e(data['meta']['model'])}</code>に、同じ判定用本文・季節の質問・七つの選択肢を渡し、今回は「季節」に加えて「根拠となる語句（最大2個、各8文字まで）」と「短い日本語の説明」を求めた。推論設定は前回と同じ<code>{e(data['meta']['reasoning_effort'])}</code>。前回の季節判定、Jevの判定、資料の分類はモデルに見せていない。</p>
        <p class="experiment-result"><b>季節の答えが変わったのは{changed}／201首</b>（{corpus_summary}）。前回の「季節のみ」の結果を保存したまま、別の実行として比較している。</p>
        <p>ここで読める説明は、Lunaが今回の回答として生成したもの。文学研究で確認された解釈や、モデル内部の思考過程ではない。語句が本文に現れることと、その解釈が妥当であることも別である。各条件を繰り返し実行してはいないため、判定の変化には実行ごとの揺れも含まれうる。<b>根拠を求めたことだけが変化の原因、あるいは精度向上の証拠とはいえない。</b></p>
        <details class="catalogue-notes">
          <summary>表示本文・資料・モデルの説明について</summary>
          <p>語句は取得したモデル出力をそのまま掲載し、実際の判定入力に完全一致する文字列がなければその旨を添えた。説明も取得した出力を掲載し、非公開の作業用本文を全文引用する場合には表示を省略している。秀歌の共通歌では、読みやすい公開済みの小倉本文を表示するため、<b>表示本文と秀歌の判定入力では表記が異なる</b>。このため、入力に一致する語句であっても、表示本文と同じ綴りで現れないことがある。</p>
          <p>「資料の分類・部立」は紹介資料の分類や出典歌集の部門であり、モデルが本文から答えた主な季節とは別の軸である。共通歌の秀歌欄は小倉同歌の参考情報で、秀歌の異文そのものを一首ずつ検証した分類ではない。Jevと資料の詳しい比較は<a href="../list/">一首ごとの判定一覧</a>に掲載した。</p>
          <p>歌本文と対応は<a href="../../../references/#id-map">公開済み歌番号対応表</a>から再掲。小倉本文は<a href="https://ja.wikisource.org/w/index.php?title=%E5%B0%8F%E5%80%89%E7%99%BE%E4%BA%BA%E4%B8%80%E9%A6%96&amp;oldid=240235">Japanese Wikisource「小倉百人一首」固定版 oldid 240235</a>に由来し、<a href="https://creativecommons.org/licenses/by-sa/3.0/deed.ja">CC BY-SA 3.0</a>の対象。秀歌のみの4首と対応は同表の<a href="../../../references/#ref-g-5">水垣久「百人秀歌」への出典記載</a>を引き継ぐ。<a href="../../../data_sources.md">本文の利用条件</a>。</p>
        </details>
      </section>
      <section class="catalogue-results" aria-labelledby="catalogue-heading">
        <h2 id="catalogue-heading">季節の判定と、Lunaが生成した説明</h2>
        <form class="catalogue-filters" id="reasoned-filters" hidden>
          <div class="filter-field"><label for="corpus-filter">歌集</label><select id="corpus-filter" name="corpus"><option value="all">両方の歌集</option><option value="ogura">小倉百人一首</option><option value="shuka">百人秀歌</option></select></div>
          <div class="filter-field"><label for="season-filter">根拠付きで判定された季節</label><select id="season-filter" name="season"><option value="all">すべての判定</option>{options}</select></div>
          <div class="filter-field reasoned-search"><label for="poem-search">歌番号・歌人・表示本文・説明</label><input id="poem-search" name="query" type="search" autocomplete="off" placeholder="例：H024、定家、紅葉" /></div>
          <label class="checkbox-field"><input id="changed-filter" name="changed" type="checkbox" />季節のみから判定が変わった歌だけ</label>
          <button type="reset" class="reset-filters">条件をリセット</button>
        </form>
        <p id="result-count" class="result-count" role="status" aria-live="polite" aria-atomic="true">201首を表示（小倉100首・秀歌101首）</p>
        <div id="reasoned-poems" class="reasoned-poems">
{cards}
        </div>
        <p id="no-results" class="no-results" hidden>条件に合う歌はありません。季節や検索語を変えてください。</p>
        <noscript><p class="note">JavaScriptを無効にしているため、絞り込みは表示していません。全201首はこのページで読めます。</p></noscript>
        <p class="catalogue-footer"><a href="../../../luna-reasoned-comparison.json">判定・語句・説明のJSON</a> ／ <a href="../#luna-reasons">追加実験の集計</a> ／ <a href="../list/">Jev・季節のみLunaの一覧</a></p>
      </section>
    </main>
  </body>
</html>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "docs/luna-reasoned-comparison.json")
    parser.add_argument("--references", type=Path, default=ROOT / "docs/references/index.html")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/paper/seasons/luna-reasons/index.html")
    args = parser.parse_args()
    page = build_page(json.loads(args.data.read_text(encoding="utf-8")), args.references.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8")
    print("Rendered all 201 Luna classifications with evidence and explanations.")


if __name__ == "__main__":
    main()
