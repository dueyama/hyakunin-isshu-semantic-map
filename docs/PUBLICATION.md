# GitHub / GitHub Pages 公開チェックリスト

この文書は、`hyakunin-isshu-semantic-map` を公開研究リポジトリとして出す前の確認用メモです。今回は論文・PDFではなく、GitHub Pages上で読める更新可能なHTMLシリーズ記事として公開します。公開物、公開しないもの、更新履歴、ライセンスを分けて管理します。

- GitHub repository: <https://github.com/dueyama/hyakunin-isshu-semantic-map>
- GitHub Pages: <https://dueyama.github.io/hyakunin-isshu-semantic-map/>

## 公開するもの

現行の公開候補:

- `README.md`
- `AI_RESEARCHER_GUIDE.md`
- `docs/index.html`
- `docs/favicon.svg`
- `docs/paper/0/index.html`
- `docs/paper/index.html`
- `docs/paper/2/index.html`
- `docs/paper/3/index.html`
- `docs/paper/final/index.html`
- `docs/references/index.html`
- `docs/glossary/index.html`
- `docs/updates/index.html`
- `docs/assets/reading.css`
- `docs/data_sources.md`
- `docs/method.md`
- `docs/model_notes.md`
- `docs/first_findings.md`
- `docs/literature_notes.md`
- `docs/figures/` 以下の、HTML本文で参照する公開用図版
- `scripts/*.py`
- `data/hyakunin_isshu.csv`: Japanese Wikisource由来の初期データ候補。CC BY-SA 3.0として扱う。
- 利用条件確認済みの派生データ

今後追加する公開候補:

- 追加図: `docs/figures/*.png`
- 読者向けの更新履歴: `docs/updates/index.html`
- インタラクティブビューアを復活させる場合は、本文・データ利用条件・公開対象JSONを再確認してから別途公開する。

## 公開しないもの

- `.env`
- OpenAI API key / GitHub token / other secrets
- ライセンス未確認のraw本文、翻刻、画像
- `data/raw/` に置いた取得元確認中データ
- embedding cache
- embedding vector
- `data/embeddings/`
- `_private/`
- `docs/viewer/`
- `docs/progress.md`
- `docs/hyakunin_shuka_comparison_notes.md`
- `public/data/`
- Proレビュー用Markdown/zip
- 生成元画像や未採用画像
- 大量の中間出力
- ローカル絶対パスを含む研究用出力

## 公開用履歴の考え方

`docs/progress.md` はローカル作業台帳として保持しますが、公開リポジトリには載せません。レビューzip名、非公開フォルダ名、細かな作業ログが含まれるためです。読者向けには `docs/updates/index.html` に、本文の追加、数値の変更、図の差し替え、解釈の修正など、読む側に意味のある更新だけをまとめます。

GitHubのコミット履歴は、実際の変更単位を追える技術的な記録として残します。細かな表記修正や内部処理の変更は、必要な場合を除いて更新履歴ページには載せません。公開後は、必要に応じて該当するGitHubコミットやリリースへのリンクも添えます。

初回公開前には、最新状態だけでなくgit履歴も含めて、秘密情報、未確認本文、embedding cache、ローカル絶対パスが追跡されていないことを確認します。

## GitHub Pages 設定

1. GitHub に repository を作成する。
2. ローカルで remote を追加し、`main` を push する。
3. GitHub repository settings で Pages を有効化する。
4. Source は `Deploy from a branch`、branch は `main`、folder は `/docs` を選ぶ。
5. 公開URLで次を確認する。
   - `index.html` が表示される。
   - `paper/0/` と `paper/` でHTMLシリーズ記事が表示される。
   - 主要図、データ出典、ライセンス、更新履歴への導線が表示される。

## 公開前コマンド

```bash
git status --short
python3 -m py_compile scripts/*.py
python3 -m html.parser docs/index.html docs/paper/0/index.html docs/paper/index.html docs/paper/2/index.html docs/paper/3/index.html docs/paper/final/index.html docs/glossary/index.html docs/references/index.html docs/updates/index.html
python3 scripts/build_dataset.py --check
python3 scripts/check_site_links.py
python3 scripts/check_publication_safety.py
python3 scripts/export_web_json.py --omit-text
rg -n 'sk[-][A-Za-z0-9]' README.md AI_RESEARCHER_GUIDE.md docs scripts
rg -n '/Users|/private|Documents/Codex|file://' README.md AI_RESEARCHER_GUIDE.md docs scripts
git diff --check
```

現行公開はGitHub Pagesの `/docs` 直配信です。ビルド工程は使いません。ローカル確認は、必要なら `python3 -m http.server 8889 -d docs` などで行います。

gitリポジトリ化後は、次も確認します。

```bash
git grep --cached -n 'sk[-][A-Za-z0-9]'
git log --all --oneline -G'sk[-][A-Za-z0-9]'
git log --all --oneline -G'/Users|Documents/Codex'
git ls-files | rg '^\.env$|^_private/|^data/raw/|^data/embeddings/|^docs/viewer/|^docs/progress\.md$|^docs/hyakunin_shuka_comparison_notes\.md$|^public/data/'
```

## 公開後の運用

- HTML本文は固定版ではなく、文献確認や追加解析に応じて更新する。
- 誤記、リンク切れ、図表ラベル、数値、補足説明、解釈変更が見つかった場合は、必要に応じて本文を直す。
- 大きな解釈変更や数値変更は、公開後は `docs/updates/index.html` に読者向け概要として記録する。ローカル作業台帳を使う場合も、公開リポジトリには含めない。
- GitHub Release や tag は必須にしない。切る場合も、論文の確定版ではなく、その時点のスナップショットとして扱う。

## 言語方針

公開本文は日本語HTMLのみとします。英語版は当面作成せず、言語切替UIも置きません。英訳を使った埋め込み比較は、本文中の実験的な話題として扱う場合がありますが、サイト全体の英語版公開とは分けて管理します。

## ライセンス

- 解析コード: MIT License。リポジトリ直下の `LICENSE-CODE` を参照する。
- HTML読み物、図表、公開文書、制作プロセス、公開用派生データ: Creative Commons Attribution 4.0 International (CC BY 4.0)。リポジトリ直下の `LICENSE-CONTENT` を参照する。
- 外部提供元の本文・翻刻・画像: 本リポジトリ独自のライセンス対象には含めない。`data/hyakunin_isshu.csv` と本文由来の正規化CSVは Japanese Wikisource の CC BY-SA 3.0 条件に従う。その他の元本文の利用は各提供元の利用条件に従う。
