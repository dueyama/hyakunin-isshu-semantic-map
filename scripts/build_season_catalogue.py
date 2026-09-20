#!/usr/bin/env python3
"""Render the seasonal catalogue from public results and public reference text.

This script deliberately has no access to API caches or private poem inputs.
The 201 result rows remain readable when JavaScript is disabled.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    "spring": "春", "summer": "夏", "autumn": "秋", "winter": "冬",
    "mixed": "複数季節", "unspecified": "季節不特定", "uncertain": "判定困難",
}
EXPECTED_IDS = {f"H{i:03d}" for i in range(1, 101)} | {f"S{i:03d}" for i in range(1, 102)}
CORPORA = {"ogura": "小倉百人一首", "shuka": "百人秀歌"}


class ReferenceRows(HTMLParser):
    """Read only the already published H/S correspondence table."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: dict[str, dict] = {}
        self.row: dict | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "tr" and re.fullmatch(r"id-[hs]\d{3}", attr.get("id") or ""):
            key = attr["id"][3:].upper()
            if key in self.rows:
                raise ValueError(f"duplicate public reference row {key}")
            self.row = {"id": key, "cells": [], "links": []}
        elif self.row is not None and tag == "td":
            self.cell = []
        elif self.row is not None and tag == "a":
            self.row["links"].append(attr.get("href") or "")

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.row is not None and self.cell is not None:
            self.row["cells"].append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows[self.row["id"]] = self.row
            self.row = None
            self.cell = None


def public_poems(source: str) -> dict[str, dict]:
    parser = ReferenceRows()
    parser.feed(source)
    if set(parser.rows) != EXPECTED_IDS:
        raise ValueError("public reference table must contain exactly H001–H100 and S001–S101")
    poems: dict[str, dict] = {}
    for key, row in parser.rows.items():
        cells = row["cells"]
        if len(cells) != 5 or cells[0] != key:
            raise ValueError(f"unexpected public reference table layout: {key}")
        if key.startswith("H"):
            poems[key] = {"poet": cells[1], "text": cells[2], "shared_id": None}
    for key, row in parser.rows.items():
        if not key.startswith("S"):
            continue
        cells = row["cells"]
        matches = [link[4:].upper() for link in row["links"] if re.fullmatch(r"#id-h\d{3}", link)]
        if len(matches) > 1:
            raise ValueError(f"multiple Ogura correspondences: {key}")
        shared_id = matches[0] if matches else None
        text = poems[shared_id]["text"] if shared_id else cells[3]
        if not text or "参照" in text:
            raise ValueError(f"public poem text missing: {key}")
        poems[key] = {"poet": cells[2], "text": text, "shared_id": shared_id}
    return poems


def validate_data(data: dict, poems: dict[str, dict]) -> list[dict]:
    rows = data["rows"]
    if len(rows) != 201 or {row["id"] for row in rows} != EXPECTED_IDS:
        raise ValueError("comparison must contain one result for each of 201 poems")
    for row in rows:
        key = row["id"]
        corpus = "ogura" if key.startswith("H") else "shuka"
        if row["corpus"] != corpus or row["order"] != int(key[1:]):
            raise ValueError(f"inconsistent poem ID, corpus or order: {key}")
        if row["jev"] not in LABELS or (row["gpt"] is not None and row["gpt"] not in LABELS):
            raise ValueError(f"unknown model label: {key}")
        reference = row.get("reference")
        if reference:
            if not isinstance(reference.get("division"), str) or not reference["division"]:
                raise ValueError(f"missing reference division: {key}")
            parsed = urlparse(reference.get("source_url", ""))
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError(f"reference must link to an HTTPS source: {key}")
            expected_h = key if corpus == "ogura" else poems[key]["shared_id"]
            scopes = {"direct"} if corpus == "ogura" else ({"shared_poem"} if expected_h else {"source_poem", "related_version"})
            if reference.get("scope") not in scopes or reference.get("ogura_id") != expected_h:
                raise ValueError(f"reference scope does not match public correspondence: {key}")
    for name in ("jev_model", "gpt_model"):
        if not isinstance(data["meta"].get(name), str) or not data["meta"][name]:
            raise ValueError(f"missing model metadata: {name}")
    completed = sum(row["gpt"] is not None for row in rows)
    if data["meta"].get("gpt_completed") != completed or data["meta"].get("total_poems") != len(rows):
        raise ValueError("metadata completion counts must agree with the result rows")
    return sorted(rows, key=lambda row: (row["corpus"] == "shuka", row["order"]))


def e(value: object) -> str:
    return html.escape(str(value), quote=True)


def season_badge(value: str | None) -> str:
    if value is None:
        return '<span class="season-badge season-not-run">未実行</span>'
    return f'<span class="season-badge season-{value}">{LABELS[value]}</span>'


def render_row(row: dict, poem: dict) -> str:
    key = row["id"]
    reference = row.get("reference")
    shared = poem["shared_id"]
    shared_note = (
        f'<small class="poem-note">小倉同歌 <a href="#poem-{shared.lower()}">{shared}</a> の本文。'
        '秀歌の判定入力とは表記が異なる。</small>' if shared else ""
    )
    if reference:
        literature = f'<a href="{e(reference["source_url"])}">{e(reference["division"])}</a>'
        source = reference.get("source_anthology") or ""
        if reference.get("source_number"):
            source += f' {reference["source_number"]}番'
        if source:
            literature += f'<small class="source-note">{e(source)}</small>'
        scope_notes = {
            "direct": "紹介資料で確認した分類。",
            "shared_poem": "小倉同歌の参考。秀歌の異文は未判定。",
            "source_poem": "出典歌の部立。",
            "related_version": "出典歌の部立（異同あり）。",
        }
        literature += f'<small class="source-note">{scope_notes[reference["scope"]]}</small>'
    else:
        literature = '<span class="unverified">未確認</span>'
    mismatch = row["gpt"] is not None and row["jev"] != row["gpt"]
    search = " ".join([key, poem["poet"], row.get("poet", ""), poem["text"], shared or ""])
    return f'''              <tr id="poem-{key.lower()}" data-corpus="{row['corpus']}" data-jev="{row['jev']}" data-gpt="{row['gpt'] or 'not_run'}" data-disagreement="{str(mismatch).lower()}" data-search="{e(search)}">
                <th scope="row"><a class="poem-id" href="../../../references/#id-{key.lower()}">{key}</a><span class="corpus-label">{CORPORA[row['corpus']]}</span><span class="poet-name">{e(poem['poet'])}</span></th>
                <td class="poem-text">{e(poem['text'])}{shared_note}</td>
                <td>{season_badge(row['jev'])}</td>
                <td>{season_badge(row['gpt'])}{'<small class="disagreement-label">Jevと異なる</small>' if mismatch else ''}</td>
                <td class="literature-cell">{literature}</td>
              </tr>'''


def build_page(data: dict, references_html: str) -> str:
    poems = public_poems(references_html)
    rows = validate_data(data, poems)
    disagreements = Counter(row["corpus"] for row in rows if row["gpt"] is not None and row["jev"] != row["gpt"])
    compared = Counter(row["corpus"] for row in rows if row["gpt"] is not None)
    comparison_notes = []
    for corpus, label in (("ogura", "小倉"), ("shuka", "秀歌")):
        if compared[corpus]:
            comparison_notes.append(f"{label}は比較できた{compared[corpus]}首のうち、両モデルで異なる答えが{disagreements[corpus]}首")
        else:
            comparison_notes.append(f"{label}のGPT判定は未実行")
    comparison_note = "。".join(comparison_notes) + "。"
    model_options = "".join(f'<option value="{key}">{label}</option>' for key, label in LABELS.items())
    has_pending = data["meta"]["gpt_completed"] < data["meta"]["total_poems"]
    pending_note = "未実行の欄は季節判定として扱わない。" if has_pending else ""
    pending_option = '<option value="not_run">未実行（GPT）</option>' if has_pending else ""
    rendered_rows = "\n".join(render_row(row, poems[row["id"]]) for row in rows)
    return f'''<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>一首ごとの季節判定 | 意味空間で百人一首を読む</title>
    <meta name="description" content="小倉百人一首100首・百人秀歌101首について、JevとGPT-5.6-Lunaの季節判定、資料で確認した部立を一首ずつ比較する一覧。" />
    <link rel="canonical" href="https://dueyama.github.io/hyakunin-isshu-semantic-map/paper/seasons/list/" />
    <meta property="og:locale" content="ja_JP" />
    <meta property="og:type" content="article" />
    <meta property="og:title" content="一首ごとの季節判定 | 意味空間で百人一首を読む" />
    <meta property="og:description" content="Jev・GPT-5.6-Lunaの出力と、資料の部立を並べて読む。" />
    <meta property="og:url" content="https://dueyama.github.io/hyakunin-isshu-semantic-map/paper/seasons/list/" />
    <meta property="og:image" content="https://dueyama.github.io/hyakunin-isshu-semantic-map/figures/hero-heian-semantic-map.jpg" />
    <meta name="twitter:card" content="summary_large_image" />
    <link rel="icon" type="image/svg+xml" href="../../../favicon.svg" />
    <link rel="stylesheet" href="../../../assets/reading.css?v=20260710-review" />
    <link rel="stylesheet" href="../../../assets/season-list.css?v=20260920" />
    <script src="../../../assets/season-list.js?v=20260920" defer></script>
  </head>
  <body class="article article-one season-catalogue">
    <main>
      <nav aria-label="主なページ">
        <a href="../../../">トップ</a><a href="../">季節比較</a>
        <a href="./" aria-current="page">一首ごとの判定</a><a href="../../../references/">参照資料</a>
      </nav>
      <header class="article-hero">
        <p class="meta">意味空間で百人一首を読む 補章 / 季節判定の一覧</p>
        <h1>一首ごとの季節判定</h1>
        <p class="lead">歌を読みながら、モデルの答えと資料の分類を見比べる。小倉100首、秀歌101首の結果を並べた。</p>
        <div class="project-credits" aria-label="制作クレジット">
          <span><b>分析・実装・本文整理:</b> Codex GPT-6 Astra Ultra</span>
          <span><b>季節判定:</b> TypeSafe Jev / OpenAI GPT-5.6-Luna</span>
        </div>
        <p><a href="../luna-reasons/">追加実験：Lunaに根拠も求めた結果を見る →</a></p>
      </header>
      <section aria-labelledby="reading-guide">
        <h2 id="reading-guide">この一覧の読み方</h2>
        <p>JevとGPTに、同じ本文と七つの選択肢から「主な季節」を一つ選ぶよう求めた。ここに示すのは、それぞれのモデルを今回の条件で実行した結果である。{pending_note}<a href="../">実験の条件と集計を見る</a>。</p>
        <p><b>資料の分類・部立は、紹介資料の分類や、出典の歌集での部門</b>を示す。「恋」「羇旅」「雑」などの部にも季節の情景はあるため、本文を読むモデルの答えとは別の軸として並べた。四季以外の分類を「無季」という正解には扱わない。資料の欄を押すと確認元に移動する。</p>
        <p>秀歌の共通歌では、表示本文と資料の部立は小倉の対応歌を参照している。秀歌の実際の判定には別表記の作業用本文を用いたため、<b>表示本文は判定入力そのものではない</b>。資料の部立も、秀歌の異文を一首ずつ検証した結果ではない。</p>
        <details class="catalogue-notes">
          <summary>判定名・モデル・表示本文の出典</summary>
          <p>「複数季節」は主な季節を一つに絞れないという出力、「季節不特定」は主な季節を特定しないという出力、「判定困難」は本文を解釈しにくいという出力である。「季節不特定」は文学的な無季を確定するものではない。この一覧ではJevの確信度やGPTの自己申告値を正解率として示さない。</p>
          <p>モデル：<code>{e(data['meta']['jev_model'])}</code> ／ <code>{e(data['meta']['gpt_model'])}</code>。埋め込みモデルは季節を直接判定していないため、この一覧の判定列には含めていない。</p>
          <p>歌本文と対応は、当サイトの<a href="../../../references/#id-map">公開済み歌番号対応表</a>から再掲。小倉本文は<a href="https://ja.wikisource.org/w/index.php?title=%E5%B0%8F%E5%80%89%E7%99%BE%E4%BA%BA%E4%B8%80%E9%A6%96&amp;oldid=240235">Japanese Wikisource「小倉百人一首」固定版 oldid 240235</a>に由来し、<a href="https://creativecommons.org/licenses/by-sa/3.0/deed.ja">CC BY-SA 3.0</a>の対象。秀歌のみの4首と小倉対応は同表の<a href="../../../references/#ref-g-5">水垣久「百人秀歌」への出典記載</a>を引き継ぐ。<a href="../../../data_sources.md">本文の利用条件</a>。</p>
        </details>
      </section>
      <section class="catalogue-results" aria-labelledby="catalogue-heading">
        <h2 id="catalogue-heading">201首の比較</h2>
        <p>Jevは201首、GPTは{data['meta']['gpt_completed']}／{data['meta']['total_poems']}首で判定を取得。{comparison_note}不一致数は、誤りの数を確定したものではない。</p>
        <form class="catalogue-filters" id="season-filters" hidden>
          <div class="filter-field"><label for="corpus-filter">歌集</label><select id="corpus-filter" name="corpus"><option value="all">両方の歌集</option><option value="ogura">小倉百人一首</option><option value="shuka">百人秀歌</option></select></div>
          <div class="filter-field"><label for="model-filter">季節を絞るモデル</label><select id="model-filter" name="model"><option value="jev">Jev</option><option value="gpt">GPT-5.6-Luna</option><option value="either">どちらかのモデル</option></select></div>
          <div class="filter-field"><label for="season-filter">判定された季節</label><select id="season-filter" name="season"><option value="all">すべての判定</option>{model_options}{pending_option}</select></div>
          <div class="filter-field search-field"><label for="poem-search">歌番号・歌人・表示本文</label><input id="poem-search" name="query" type="search" autocomplete="off" placeholder="例：H024、春、定家" /></div>
          <label class="checkbox-field"><input id="disagreement-filter" name="disagreement" type="checkbox" />JevとGPTで異なる判定だけ</label>
          <button type="reset" class="reset-filters">条件をリセット</button>
        </form>
        <p id="result-count" class="result-count" role="status" aria-live="polite" aria-atomic="true">201首を表示（小倉100首・秀歌101首）</p>
        <p class="table-scroll-hint" id="table-scroll-hint">表は横にスクロールできます。歌番号から参照資料へ移動できます。</p>
        <div class="table-wrap season-table-wrap" tabindex="0" role="region" aria-label="一首ごとの季節比較表" aria-describedby="table-scroll-hint">
          <table class="season-table">
            <caption>各歌の季節判定と、資料で確認した分類・部立。Jev・GPTの列は今回のAPI出力。</caption>
            <thead><tr><th scope="col">歌番号・歌人</th><th scope="col">歌（公開参照表の本文）</th><th scope="col">Jev</th><th scope="col">GPT-5.6-Luna</th><th scope="col">資料の分類・部立</th></tr></thead>
            <tbody id="season-rows">
{rendered_rows}
            </tbody>
          </table>
        </div>
        <p id="no-results" class="no-results" hidden>条件に合う歌はありません。季節や検索語を変えてください。</p>
        <noscript><p class="note">JavaScriptを無効にしているため、絞り込みは表示していません。全201首はこの表で読めます。</p></noscript>
        <p class="catalogue-footer"><a href="../../../season-comparison.json">本文を含まない判定一覧JSON</a> ／ <a href="../">季節比較の説明へ戻る</a></p>
      </section>
    </main>
  </body>
</html>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "docs/season-comparison.json")
    parser.add_argument("--references", type=Path, default=ROOT / "docs/references/index.html")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/paper/seasons/list/index.html")
    args = parser.parse_args()
    page = build_page(json.loads(args.data.read_text(encoding="utf-8")), args.references.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8")
    print("Rendered 201 seasonal classifications from public results and reference text.")


if __name__ == "__main__":
    main()
