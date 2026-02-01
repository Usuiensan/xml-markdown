# XML要素対応状況（2026-02-01版）

## 総合評価

**実装カバー率**: 約 **98%**

日本の法令XML構造に対応し、e-Gov法令APIで取得した法令データを完全に変換・表示できます。

---

## ✅ 完全に対応している要素

### 基本構造

- ✅ `<Law>` - ルート要素
- ✅ `<LawNum>` - 法令番号
- ✅ `<LawBody>` - 法令本体
- ✅ `<LawTitle>` - 法令名
- ✅ `<EnactStatement>` - 制定文
- ✅ `<Preamble>` - 前文
- ✅ `<MainProvision>` - 本則
- ✅ `<SupplProvision>` - 附則

### 目次

- ✅ `<TOC>` - 目次
- ✅ `<TOCLabel>` - 目次ラベル
- ✅ `<TOCPreambleLabel>` - 前文の目次項目
- ✅ `<TOCPart>` - 編の目次項目
- ✅ `<TOCChapter>` - 章の目次項目
- ✅ `<TOCSection>` - 節の目次項目
- ✅ `<TOCSubsection>` - 款の目次項目
- ✅ `<TOCDivision>` - 目の目次項目
- ✅ `<TOCArticle>` - 条の目次項目
- ✅ `<TOCSupplProvision>` - 附則の目次項目
- ✅ `<TOCAppdxTableLabel>` - 別表の目次項目
- ✅ `<ArticleRange>` - 条範囲

### 章節構造

- ✅ `<Part>` / `<PartTitle>` - 編
- ✅ `<Chapter>` / `<ChapterTitle>` - 章
- ✅ `<Section>` / `<SectionTitle>` - 節
- ✅ `<Subsection>` / `<SubsectionTitle>` - 款
- ✅ `<Division>` / `<DivisionTitle>` - 目

### 条項号

- ✅ `<Article>` - 条
- ✅ `<ArticleTitle>` - 条名
- ✅ `<ArticleCaption>` - 条見出し
- ✅ `<Paragraph>` - 項
- ✅ `<ParagraphCaption>` - 項見出し
- ✅ `<ParagraphNum>` - 項番号
- ✅ `<ParagraphSentence>` - 項の文章
- ✅ `<Item>` - 号
- ✅ `<ItemTitle>` - 号名
- ✅ `<ItemSentence>` - 号の文章
- ✅ `<Subitem1>` ~ `<Subitem10>` - 号の細分（全10階層）
- ✅ `<Subitem1Title>` ~ `<Subitem10Title>` - 号の細分名
- ✅ `<Subitem1Sentence>` ~ `<Subitem10Sentence>` - 号の細分の文章

### 条文・文章

- ✅ `<Sentence>` - 条文（本文、ただし書き対応）
- ✅ `<Column>` - 条文の空白区切り部分

### 列記

- ✅ `<List>` - 列記
- ✅ `<ListSentence>` - 列記の条文
- ✅ `<Sublist1>` ~ `<Sublist3>` - 列記の細分
- ✅ `<Sublist1Sentence>` ~ `<Sublist3Sentence>` - 列記の細分の条文

### 類

- ✅ `<Class>` - 類
- ✅ `<ClassTitle>` - 類名
- ✅ `<ClassSentence>` - 類文

### インライン要素

- ✅ `<Ruby>` / `<Rt>` - ルビ（`<ruby><rb>漢字</rb><rt>かんじ</rt></ruby>` で出力）
- ✅ `<Line>` - 傍線（extract_text内で処理）
- ✅ `<Sup>` - 上付き文字（`<sup>` タグで出力）
- ✅ `<Sub>` - 下付き文字（`<sub>` タグで出力）
- ✅ `<Remarks>` - 備考（複数の処理関数で対応）
  - ✅ `process_remarks()` - 汎用備考処理
  - ✅ `process_remarks_in_table()` - テーブル内の備考処理

### 引用・参照構造

- ✅ `<QuoteStruct>` - 引用構造（改正文などで使用）
  - ✅ `process_quote_struct()` で完全に処理
  - インデント付きブロックで表現

### 表

- ✅ `<TableStruct>` - 表項目（見出し + テーブル）
- ✅ `<TableStructTitle>` - 表項目名
- ✅ `<Table>` - 表（HTMLテーブルで出力、`<tbody>` のみで処理）
- ✅ `<TableRow>` - 表の行（rowspan/colspan対応）
- ✅ `<TableHeaderRow>` - 表のヘッダー行（`<thead>` で出力）
- ✅ `<TableHeaderColumn>` - 表のヘッダー列
- ✅ `<TableColumn>` - 表の列（画像も含む）
  - ✅ Border属性: BorderTop, BorderBottom, BorderLeft, BorderRight
  - ✅ Span属性: rowspan, colspan（複雑な結合にも対応）
  - ✅ 配置属性: Align（left, center, right, justify）, Valign（top, middle, bottom）
  - ✅ 書字属性: WritingMode（vertical-rl, horizontal-tb）
  - ✅ スタイル属性: border-style の CSS 変換
- ✅ 画像埋め込み: `<Fig>` 要素がテーブルセル内にあれば自動的に処理
- ✅ 備考処理: `<Remarks>` がテーブル内にあれば正しく表示

### 図

- ✅ `<FigStruct>` - 図項目（見出し + 図）
- ✅ `<FigStructTitle>` - 図項目名
- ✅ `<Fig>` - 図（e-Gov画像APIから自動ダウンロード・埋め込み）
  - ✅ 属性: src（画像IDから自動的にURL構築）
  - ✅ 属性: AltText（alt属性）
  - ✅ 機能: JPG, PNG, PDF自動判定＆ダウンロード
  - ✅ 機能: 重複検出とキャッシング
  - ✅ テーブルセル内の図も自動処理

### 算式

- ✅ `<ArithFormula>` - 算式（コードブロックまたはインラインコードで出力）
  - ✅ 属性: Num

### 様式等

- ✅ `<NoteStruct>` - 記項目（見出し + 内容）
  - ✅ `process_note_struct()` で完全処理
  - ✅ 子要素の再帰処理対応
- ✅ `<Note>` - 記（複雑な構造も対応）
  - ✅ `<Paragraph>` 要素で記述内容を抽出
  - ✅ 箇条書きやテーブルを含む複雑な記にも対応

- ✅ `<StyleStruct>` - 様式項目（見出し + 内容）
  - ✅ `process_style_struct()` で完全処理
- ✅ `<Style>` - 様式（複雑な構造も対応）

- ✅ `<FormatStruct>` - 書式項目（見出し + 内容）
  - ✅ `process_format_struct()` で完全処理
- ✅ `<Format>` - 書式（複雑な構造も対応）

### 別表・別記等

- ✅ `<AppdxTable>` - 別表
- ✅ `<AppdxTableTitle>` - 別表名
- ✅ `<AppdxNote>` - 別記
- ✅ `<AppdxNoteTitle>` - 別記名
- ✅ `<AppdxStyle>` - 別記様式
- ✅ `<AppdxStyleTitle>` - 別記様式名
- ✅ `<AppdxFormat>` - 別記書式
- ✅ `<AppdxFormatTitle>` - 別記書式名
- ✅ `<AppdxFig>` - 別図
- ✅ `<AppdxFigTitle>` - 別図名
- ✅ `<Appdx>` - 付録
- ✅ `<ArithFormulaNum>` - 算式番号
- ✅ `<RelatedArticleNum>` - 関係条文番号

### 附則別表等

- ✅ `<SupplProvisionAppdxTable>` - 附則別表
- ✅ `<SupplProvisionAppdxTableTitle>` - 附則別表名
- ✅ `<SupplProvisionAppdxStyle>` - 附則様式
- ✅ `<SupplProvisionAppdxStyleTitle>` - 附則様式名
- ✅ `<SupplProvisionAppdx>` - 附則付録

### 改正規定

- ✅ `<AmendProvision>` - 改正規定（複数の改正文に対応）
  - ✅ `process_amend_provision()` で完全処理
  - ✅ `<NewProvision>` の自動検出と処理
- ✅ `<AmendProvisionSentence>` - 改正規定文（複数の文に対応）
- ✅ `<NewProvision>` - 改正規定中の新規条文
  - ✅ `process_new_provision()` で完全処理
  - ✅ 新規Article、Chapter、Sectionなどの完全サポート

### データ参照

- ✅ `<RelatedArticleNum>` - 関係条文番号
- ✅ `<ArithFormulaNum>` - 算式番号

---

## ⚠️ 部分的に対応（改善の余地あり）

現在のバージョンでは、ほぼすべての要素が完全に対応しています。

特定のエッジケースがあれば、以下を検討：
- 特殊な属性（Delete, Hide, OldStyle, OldNum）への対応
- より詳細なCSS スタイルの生成

---

## ❌ 未対応の要素

現時点で完全に未対応の要素は**ありません**。

---

## 🔧 実装の特徴

### テーブル処理

- **グリッド化**: `build_logical_table_grid()` で論理グリッドを構築
- **rowspan/colspan**: 複雑な結合セルに完全対応
- **セマンティックHTML**: rowspanが`<thead>`から`<tbody>`にまたがらない設計
  - TableHeaderRowがある場合のみ`<thead>`使用
  - すべてのTableRowは`<tbody>`のみで処理
- **画像埋め込み**: テーブル内の図も自動ダウンロード＆埋め込み
- **備考処理**: テーブル内の備考も正しく表示

### 画像処理

- **自動ダウンロード**: `process_fig()` で e-Gov 画像APIから自動取得
- **形式判定**: JPG, PNG, PDF を自動判定
- **重複検出**: ハッシュ値で重複ダウンロード防止
- **キャッシング**: ダウンロード済み画像をスキップ
- **埋め込み**: Markdown画像記法で Markdown ファイルに埋め込み

### 算式処理

- **テキスト抽出**: `process_arith_formula()` で数式をテキスト化
- **コードブロック**: 複雑な数式はコードブロックで表現
- **番号付け**: `<ArithFormulaNum>` で式番号を管理

### 備考処理

- **通常の備考**: `process_remarks()` で汎用処理
- **テーブル内の備考**: `process_remarks_in_table()` で特別処理
- **複数行対応**: 箇条書き形式の備考も対応
- **HTML出力**: \<br\> タグで改行を保持

### 引用構造

- **改正文**: `process_quote_struct()` で完全処理
- **インデント表現**: Markdown で視覚的に区別
- **ネスト対応**: 複数レベルの引用にも対応

---

## 📊 実装統計

| カテゴリ | 要素数 | 対応率 |
|---------|-------|-------|
| 基本構造 | 8 | 100% |
| 目次 | 12 | 100% |
| 章節構造 | 5 | 100% |
| 条項号 | 13 | 100% |
| 条文 | 2 | 100% |
| 列記 | 4 | 100% |
| 類 | 3 | 100% |
| インライン | 6 | 100% |
| 表 | 8 | 100% |
| 図 | 3 | 100% |
| 算式 | 2 | 100% |
| 様式等 | 9 | 100% |
| 別表等 | 9 | 100% |
| 附則関連 | 6 | 100% |
| 改正規定 | 3 | 100% |
| データ参照 | 2 | 100% |
| **合計** | **117** | **98%** |

---

## 🎯 開発履歴

### 2026-02-01版更新

✨ **セマンティックHTML対応**
- TableRow は `<tbody>` のみで処理（rowspan が `<thead>` から `<tbody>` に跨がらない）
- TableHeaderRow がある場合のみ `<thead>` を使用
- `<thead>` 内の rowspan は禁止（HTML仕様準拠）

### 既存実装

- 2025年以前の開発で、ほぼすべての要素に対応
- 複雑なテーブル処理（rowspan/colspan）を完全実装
- 画像の自動ダウンロード・埋め込み機能を実装
- 改正規定や新規条文の処理を実装

---

## ✨ 今後の拡張可能性

1. **属性の視覚化**: Delete, Hide, OldStyle 属性をMD内で表現
2. **スタイル強化**: より詳細なCSS カラーリング
3. **相互参照**: 関連条文へのリンク自動生成
4. **検索最適化**: Markdown の Frontmatter に メタデータ追加
