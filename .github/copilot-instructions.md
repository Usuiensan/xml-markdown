# Copilot Instructions: Gemini Email Summary Worker

# 基本ルール
- 日本語で応答すること
- 必要に応じて、ユーザに質問を行い、要求を明確にすること
- 作業後、作業内容とユーザが次に取れる行動を説明すること
- 作業項目が多い場合は、段階に区切り、git commit を行いながら進めること
  - semantic commit（例: "feat:", "fix:", "docs:" などのprefixを付ける。詳細は [Conventional Commits](https://www.conventionalcommits.org/ja/v1.0.0/) を参照）を使用する
- コマンドの出力が確認できない場合、 get last command / check background terminal を使用して確認すること
- 変更したコードは、変更前と変更後の両方を示すこと。
- 変更したコードが動作するかどうか、動作確認を行うこと。

## 概要
このプロジェクトは、受信メールをGemini AIで分析・要約し、Discord Webhookに通知するCloudflare Workerです。

## アーキテクチャの特徴

### データフロー
1. **メール受信** → Cloudflare Email Routing経由で`email()`ハンドラーがトリガー
2. **メールパース** → `postal-mime`でテキスト/HTML抽出
3. **AI要約** → Gemini 2.5 Flash APIで構造化要約生成
4. **Discord通知** → Webhook経由でフォーマット済みメッセージ送信

### 重要な統合ポイント
- **Cloudflare Email Workers**: `email(message, env, ctx)`エントリーポイント
- **Gemini AI API**: `gemini-2.5-flash`モデルを使用、構造化プロンプトで緊急度・要約・返信ドラフト生成
- **Discord Webhooks**: テキスト形式とEmbed形式の2種類のペイロード

## プロジェクト固有のパターン

### 環境変数の使用
- `env.GEMINI_API_KEY`: Gemini API認証
- `env.DISCORD_WEBHOOK_URL`: Discord通知先

### エラーハンドリング戦略
- メイン処理エラー時はDiscordにEmbed形式でエラー通知
- `ctx.waitUntil()`でレスポンス時間を最適化

### Geminiプロンプト構造
特定のフォーマットで出力を制御：
```
緊急度: 【高⚠️・中・低】
(要約・重要事項)
返信ドラフト: または 返信不要
```

## 開発ワークフロー

### ローカル開発
```bash
npm start      # wrangler dev - ローカル開発サーバー
npm run dev    # 同上
```

### デプロイメント
```bash
npm run deploy # wrangler deploy - 本番環境へデプロイ
```

### 設定ファイル
- `wrangler.toml`: Worker設定、ログ有効化済み
- メインファイル: `src/worker.js`（192行）

## コーディングガイドライン

### 関数設計パターン
- メイン処理を`handleEmail()`に分離
- Discord用のペイロード生成を専用関数で分離（`createDiscordTextPayload`, `createErrorEmbedPayload`）
- API呼び出しを独立関数で実装（`getSummaryFromGemini`, `postToWebhook`）

### メール処理の優先順位
1. `parsedEmail.text`（プレーンテキスト）
2. `parsedEmail.html`（HTMLからタグ除去）
3. フォールバック: "（本文がありません）"

### 日本語対応
- 時刻表示: `Asia/Tokyo`タイムゾーン
- UI言語: 日本語メッセージ
- Geminiプロンプト: 日本語で構造化指示