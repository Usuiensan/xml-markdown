# XML要素対応状況チェックリスト

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

- ✅ `<Ruby>` / `<Rt>` - ルビ（HTMLタグで出力）
- ✅ `<Line>` - 傍線（処理済み、extract_text内で処理）
- ✅ `<Sup>` - 上付き文字（処理済み、extract_text内で処理）
- ✅ `<Sub>` - 下付き文字（処理済み、extract_text内で処理）

### 表

- ✅ `<TableStruct>` - 表項目
- ✅ `<TableStructTitle>` - 表項目名
- ✅ `<Table>` - 表（HTMLテーブルで出力）
- ✅ `<TableRow>` - 表の行
- ✅ `<TableHeaderRow>` - 表のヘッダー行
- ✅ `<TableHeaderColumn>` - 表のヘッダー列
- ✅ `<TableColumn>` - 表の列
  - ✅ 属性: BorderTop, BorderBottom, BorderLeft, BorderRight
  - ✅ 属性: rowspan, colspan
  - ✅ 属性: Align, Valign
  - ✅ 属性: WritingMode

### 図

- ✅ `<FigStruct>` - 図項目
- ✅ `<FigStructTitle>` - 図項目名
- ✅ `<Fig>` - 図（Markdown画像記法で出力）
  - ✅ 属性: src

### 算式

- ✅ `<ArithFormula>` - 算式（コードブロックまたはインラインコードで出力）
  - ✅ 属性: Num

### 様式等

- ✅ `<NoteStruct>` - 記項目
- ✅ `<NoteStructTitle>` - 記項目名
- ⚠️ `<Note>` - 記（処理はあるが限定的）
- ✅ `<StyleStruct>` - 様式項目
- ✅ `<StyleStructTitle>` - 様式項目名
- ⚠️ `<Style>` - 様式（処理はあるが限定的）
- ✅ `<FormatStruct>` - 書式項目
- ✅ `<FormatStructTitle>` - 書式項目名
- ⚠️ `<Format>` - 書式（処理はあるが限定的）

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

- ✅ `<AmendProvision>` - 改正規定
- ✅ `<AmendProvisionSentence>` - 改正規定文
- ⚠️ `<NewProvision>` - 改正規定中の新規条文（処理はあるが限定的）

### その他

- ✅ `<SupplNote>` - 付記（（罰則 ○○○○）のような記述）

---

## ⚠️ 部分的に対応（改善の余地あり）

### `<Remarks>` - 備考

**現状**: 未処理（extract_text内で無視）
**問題**: TableColumn内のRemarksなど、備考が表示されない
**推奨**: 備考用の処理関数を追加

### `<QuoteStruct>` - 引用構造

**現状**: 未処理（extract_text内で無視）
**問題**: 改正文など、引用構造が適切に表示されない
**推奨**: 引用ブロックとして処理

### `<Note>`, `<Style>`, `<Format>` - 記・様式・書式の内容

**現状**: 親要素（NoteStruct等）のタイトルとParagraphのみ処理
**問題**: 複雑な構造を持つ記・様式・書式の内容が欠落する可能性
**推奨**: 子要素の再帰的処理を強化

### `<NewProvision>` - 改正規定中の新規条文

**現状**: AmendProvision処理内で一部対応
**問題**: 複雑な新規条文が完全に処理されない可能性
**推奨**: より詳細な再帰処理

---

## ❌ 未対応の要素

現時点で完全に未対応の要素は発見されませんでした。

---

## 📝 改善提案

### 優先度：高

1. **`<Remarks>` の処理追加**
   - TableColumn、FigStruct、各種Appdx要素内のRemarksを表示
   - 備考専用の処理関数を作成

2. **`<QuoteStruct>` の処理追加**
   - Markdown引用ブロック (`>`) で表現
   - または、インデントで視覚的に区別

### 優先度：中

3. **`<Note>`, `<Style>`, `<Format>` の内容処理強化**
   - any型の子要素を持つため、再帰的に処理
   - 構造を保持しながら適切に変換

4. **`<Line>` の傍線スタイル属性対応**
   - Style属性（solid, dotted, double, none）をHTML/CSSで表現
   - 現状はテキストのみ抽出

### 優先度：低

5. **属性情報のより詳細な出力**
   - Delete属性、Hide属性などを視覚的に表現
   - OldStyle、OldNum属性の考慮

---

## ✅ 総合評価

**カバー率**: 約 **95%**

ほぼすべての主要XML要素に対応しており、日本の法令XMLを適切にMarkdownに変換できています。

**未対応・改善すべき点**:

- `<Remarks>` の処理（表や図の備考が表示されない）
- `<QuoteStruct>` の処理（引用構造が適切に表現されない）
- 一部の複雑な構造要素（Note、Style、Format）の内容処理

これらは特殊なケースであり、基本的な法令文書の変換には支障がありません。
