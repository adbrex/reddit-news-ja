# Reddit ニュース収集スクリプト（RSS版）

世界10サブレディットのホット記事（上位30本）を RSS で収集し、Claude Haiku で日本語要約して Markdown ファイルに保存します。

**Reddit API キー不要**で即実行できます。

## 必要環境

- Python 3.11 以上
- Anthropic API キー

## セットアップ

### 1. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を編集：

```
ANTHROPIC_API_KEY=取得した Anthropic API キー
```

Anthropic API キーは https://console.anthropic.com で取得できます。

## 実行

```bash
python collect_reddit.py
```

## 出力

- **ターミナル**: 結果をリアルタイムで表示
- **ファイル**: `output/news_YYYY-MM-DD.md` に保存

## 収集対象サブレディット

| サブレディット | テーマ |
|---|---|
| r/worldnews | 世界ニュース全般 |
| r/news | 米国・英語圏ニュース |
| r/geopolitics | 地政学 |
| r/technology | テクノロジー |
| r/science | サイエンス |
| r/business | ビジネス |
| r/economics | 経済 |
| r/environment | 環境 |
| r/europe | 欧州 |
| r/asia | アジア |

## 収集条件

- 各サブレディット hot 上位 3 本（合計 30 本）
- 24 時間以内の投稿を優先
- 重複記事は除外

## コスト目安（Claude Haiku 4.5）

| 実行頻度 | 月額概算 |
|---|---|
| 1回/日 | ~$0.22/月 |
| 4回/日 | ~$0.86/月 |
| 1回/時 | ~$5/月 |

※ プロンプトキャッシュにより繰り返し実行のコストを削減済み
