# TypeSafe / Jev のAPIキー設定

このプロジェクトの TypeSafe スキルは `.agents/skills/typesafe-ai/` に導入済みです。

## 推奨: OpenAI と同じ環境変数方式

このプロジェクトでは `OPENAI_API_KEY` と同様に、`TYPESAFE_API_KEY` を環境変数で渡します。`.env` の読み込みは不要です。

普段使用する `~/.zshrc` をエディタで開き、既存の OpenAI の設定と同じように次の行を追加してください。実際のキーはエディタ内で入力します。

```zsh
export TYPESAFE_API_KEY='ここにAPIキー'
```

保存後、新しいターミナルを開くか、現在のターミナルで `source ~/.zshrc` を実行してください。既に起動しているアプリの環境には自動反映されません。

以下は `.env` を使用したい場合の代替手順です。

## 代替: キーのファイル保存

プロジェクト直下の `.env` をエディタで開き、次の空欄にキーを入れます。

```sh
TYPESAFE_API_KEY='ここにAPIキー'
```

`.env` は Git 対象外です。既存の変数は残してください。共有用の `.env.example` に実際のキーを書かないでください。

## ターミナルへの読み込み

プロジェクト直下で、自分で管理する `.env` を次のように読み込みます。

```sh
set -a
source .env
set +a
```

以降、このターミナルから起動する Python などに環境変数が渡ります。`.env` を置くだけでは自動で読み込まれません。

ファイルを使わず、zsh で入力する場合は次の方法ならキーが画面やコマンド履歴に表示されません。

```zsh
read -rs 'TYPESAFE_API_KEY?TypeSafe API key: '
printf '\n'
export TYPESAFE_API_KEY
```

設定確認は値を表示せずに行えます。

```sh
python3 -c 'import os; print("設定済み" if os.environ.get("TYPESAFE_API_KEY") else "未設定")'
```

[公式Python SDK](https://docs.typesafe.ai/sdk/python) は `TYPESAFE_API_KEY` を環境変数から読み取ります。公開HTMLやブラウザ側のJavaScriptへキーを埋め込まないでください。

API接続確認と季節判定コードの実装・初回比較を完了しました。解析の入力条件と再実行手順は [季節比較の方法](jev_season_method.md) を参照してください。
