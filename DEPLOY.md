# Web公開（Streamlit Community Cloud）

## 公開するファイル

- saiview.py
- requirements.txt
- location_picker/index.html（入力用地図に必要）
- .streamlit/config.toml
- .gitignore

`.streamlit/secrets.toml` はアップロードしないでください。現在のリポジトリでは、このファイルがすでにGit管理されているため、既存の履歴をそのまま新しい公開リポジトリへ送らないでください。履歴にキーが含まれている場合はSupabase側でキーの交換も必要です。

## 公開手順

1. 上記ファイルを、接続キーを含まないGitHubリポジトリへ保存します。既存のGit履歴を持ち込まない新規リポジトリでも構いません。
2. https://share.streamlit.io/ でログインし、「Create app」からGitHubリポジトリとブランチを選びます。
3. Main file path は `saiview.py` にします。
4. Advanced settings の Secrets に、ローカルの `.streamlit/secrets.toml` の内容を設定します。キーはチャットやGitHubへ貼らず、Secrets欄へ直接入力してください。
5. Deploy を実行し、公開URLで現在地取得・位置調整・保存・集計を確認します。

## 利用URL

- スマホ入力：公開URLに `?view=report` を付ける
- PC集計：公開URLに `?view=dashboard` を付ける

現在はどちらの画面にもログイン制限がありません。公開するとURLを知る人が登録情報を閲覧・CSV出力できます。

https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
