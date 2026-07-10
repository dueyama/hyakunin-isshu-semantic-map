# AI Researcher Guide

この文書は、他の研究者が本リポジトリをAIエージェントや大規模言語モデルに読ませ、百人一首・百人秀歌の意味配列分析を説明・点検・再生成・発展させるための案内です。人間向けの概要は `README.md`、公開前チェックは `docs/PUBLICATION.md`、読者向け更新履歴は `docs/updates/index.html` を参照してください。ローカル作業台帳 `docs/progress.md` は公開リポジトリには含めません。

## Intended Use

AIにこのリポジトリを読ませる場合は、次の目的を想定します。

- 研究目的、対象資料、方法、限界を説明する。
- 小倉百人一首と百人秀歌の配列差分を、過大評価せずに要約する。
- 意味層、主題層、配列・出典層を混同せずに読む。
- CSV、JSON、図、HTMLシリーズ記事を再生成する。
- raw本文、未確認翻刻、embedding vector、API keyが公開候補に入っていないか確認する。
- 今後の追試や発展案を、本文提供元の利用条件と公開境界を守って設計する。

このリポジトリは、AIが古典文学的結論を自律的に確定するためのものではありません。研究者が問い、対象本文、解釈、公開判断を行い、AIは実装、集計、可視化、文書化、検証、査読補助を担当します。

## First Files To Read

AIには、まず次の順番で読ませるとよいです。

1. `README.md`
   - プロジェクトの位置づけ、方法上の立場、公開物、再現前提、ライセンス。
2. `docs/paper/0/index.html`
   - 序章。シリーズの背景、埋め込み入門、方法、公開形式。
3. `docs/paper/index.html`
   - 第1章。百人秀歌と小倉百人一首を意味空間と歌順から比べる。
4. `docs/paper/2/index.html`
   - 第2章。10×10配置、枠外に置く一首、小倉側の三首を検査する。
5. `docs/paper/3/index.html`
   - 第3章。斜め配置と螺旋配置が作る隣接ペアを比べる。
6. `docs/paper/final/index.html`
   - 終章。シリーズ全体の到達点と限界をまとめる。
7. `docs/data_sources.md`
   - 利用候補データ、利用条件、未確認点。
8. `docs/method.md`
   - 正規化、埋め込み、隣接類似度、ランダム順比較、10×10ランダム配置。
9. `docs/model_notes.md`
   - 埋め込みモデル、入力形式、実行条件。
10. `docs/PUBLICATION.md`
   - 公開対象、公開しないもの、GitHub Pages設定、公開前チェック。
11. `docs/updates/index.html`
   - 公開後に読者へ示す更新概要。
12. `scripts/*.py`
   - CSV検証、正規化、タグベースJSON出力、配列分析、将来のembedding実行。

## What Is Not In The Public Repo

次のものは公開・追跡しません。

- `.env`
- API key / token
- ライセンス未確認のraw本文、翻刻、画像
- embedding cache
- embedding vector
- `_private/`, `docs/progress.md`, `docs/viewer/`, `public/data/`
- 大量の中間データ
- ローカル絶対パスを含む研究用出力

AIエージェントは、これらをgitに追加してはいけません。本文を再取得・再処理する場合は、各提供元の利用条件を確認し、raw本文やprocessed本文を公開commitに含めないでください。

例外的に、`data/hyakunin_isshu.csv` は Japanese Wikisource「小倉百人一首」から作成した初期データ候補です。このファイルと本文由来の正規化CSVは、Wikisourceページの CC BY-SA 3.0 条件に従い、校訂済み本文ではなく要照合データとして扱ってください。

`data/hyakunin_shuka.csv` と `data/metadata_poets.csv` は列構成だけを示す公開schema placeholderです。0行を「解析データがない」というエラーにはしませんが、完全な公開データセットと解釈してはいけません。

## Minimal Public Check Path

公開候補を点検するだけなら、まず次を実行します。

```bash
git status --short
python3 -m py_compile scripts/*.py
python3 scripts/build_dataset.py --check
python3 scripts/export_web_json.py --omit-text
git diff --check
```

## Full Re-run With Embeddings

埋め込みを再生成する場合は、OpenAI API key またはローカルembeddingモデルが必要です。`.env` に `OPENAI_API_KEY` を置く場合でも、`.env` は絶対にcommitしません。

再実行時には、次の点を必ず記録します。

- 対象データと出典URL
- 利用条件と公開境界
- 入力テキスト形式
- 正規化ポリシー
- embedding model
- vector dimension
- PCA/UMAPなどの投影法
- 歌順検査のランダム順と、10×10検査のランダム配置を区別したseed・試行数
- 出力JSON/CSVに未確認本文、embedding vector、ローカルパスが含まれないこと

## Interpretation Rules

AIは次の点を守って解釈します。

- この研究は、暗号説や隠された政治的意図を証明するものではない。
- 意味埋め込みの近さは、作者・撰者の意図、影響関係、典拠関係を直接証明しない。
- 現代語訳や主題タグは、原文そのものではなく、解釈を含む補助情報である。
- PCA/UMAP図は探索的投影であり、高次元空間の全構造を示すものではない。
- 百人秀歌との違いは、本文・配列・歌人差を分けて扱う。
- 日本語HTML本文を主本文として扱い、英語版は作成しない。
- 図や数値は結論ではなく、読む場所を探すための地図である。
- 10×10検査では、同数の独立ペア抽出ではなく、同じ100首を格子へ無作為に置き直す基準を使う。

## Suggested Initial Prompt For AI

別のAIにこのrepoを渡す場合、次のようなプロンプトから始めるとよいです。

```text
このリポジトリは、小倉百人一首と百人秀歌の歌順を、意味埋め込み、主題タグ、出典・配列情報から探索する公開研究リポジトリです。

まず README.md、AI_RESEARCHER_GUIDE.md、docs/method.md、docs/data_sources.md、docs/PUBLICATION.md を読んでください。

守ること:
- 暗号説や政治的意図を事実として書かない。
- 意味埋め込みの近さを、意図・引用・影響の証明として扱わない。
- ライセンス未確認の本文・画像を public/ や docs/ に置かない。
- .env、API key、embedding cache/vector、ローカル絶対パスをcommitしない。
- 変更後は、公開後なら docs/updates/index.html に読者向け概要を残す。ローカル作業台帳がある場合は、公開しない形で別途記録する。

まず、現在の公開物、再現コマンド、公開しないもの、未検証点、発展案を短く要約してください。
```

## Suggested Review Prompt

HTML本文や結果をAIに査読させる場合は、次の観点を指定するとよいです。

```text
このHTML読み物を、古典文学・デジタル人文学・NLPの探索的研究として査読してください。
新規性を過大評価していないか、意味埋め込みと文学的意図を混同していないか、
本文出典と利用条件が十分か、百人秀歌との比較が本文差・配列差・歌人差を区別しているか、
図表から読めることと読めないことが明確かを確認してください。

改善提案は、公開前に必要な修正、公開後Errataで足りる修正、次版以降の追試・追加図・追加対照実験に分けてください。
```

## License Summary

コードは MIT License、HTML読み物・図表・公開文書・制作プロセス・公開用派生データは CC BY 4.0 です。外部提供元の本文・翻刻・画像は本リポジトリ独自のライセンス対象外です。`data/hyakunin_isshu.csv` と本文由来の正規化CSVは Japanese Wikisource の CC BY-SA 3.0 条件に従います。
