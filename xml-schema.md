法令標準XMLスキーマ（XMLSchemaForJapaneseLaw_v3.xsd）の構成を、LLMがその構造や属性、要素間の階層関係を迅速かつ正確に理解できるよう、セマンティックなMarkdown形式に整理・修正しました。

各セクションには、タグの定義、属性、および許容される子要素を明示しています。

---

# 法令標準XMLスキーマ 仕様書

法令XMLは、「法令標準XMLスキーマ」（XSD）に基づき作成されています 。本ドキュメントでは、各タグの役割と属性の仕様を定義します。

**スキーマ入手先:** [https://laws.e-gov.go.jp/file/XMLSchemaForJapaneseLaw_v3.xsd](https://laws.e-gov.go.jp/file/XMLSchemaForJapaneseLaw_v3.xsd)

---

## 1. ルートおよびトップレベル要素

### `<Law>`（法令ルート）

法令XMLの最上位要素であり、法令の基本情報を属性として保持します 。

- **子要素:** `<LawNum>`, `<LawBody>`

- **属性:**
  | 属性名 | 必須 | 型/値 | 説明 |
  | :--- | :---: | :--- | :--- |
  | `Era` | Yes | Meiji, Taisho, Showa, Heisei, Reiwa | 法令番号の元号 |
  | `Year` | Yes | positiveInteger | 法令番号の年号 |
  | `Num` | Yes | positiveInteger | 法令番号の番号 |
  | `PromulgateMonth` | No | positiveInteger | 公布月 |
  | `PromulgateDay` | No | positiveInteger | 公布日 |
  | `LawType` | Yes | Constitution, Act, CabinetOrder, ImperialOrder, MinisterialOrdinance, Rule, Misc | 法令種別 |
  | `Lang` | Yes | ja, en | 言語（通常は "ja"） |

### `<LawNum>`（法令番号）

法令番号を文字列として格納します 。

- **子要素:** string

### `<LawBody>`（法令本体）

法令のメインコンテンツを格納する器です 。

- **子要素:** `<LawTitle>`, `<EnactStatement>`, `<TOC>`, `<Preamble>`, `<MainProvision>`, `<SupplProvision>`, `<AppdxTable>`, `<AppdxNote>`, `<AppdxStyle>`, `<Appdx>`, `<AppdxFig>`, `<AppdxFormat>`

- **属性:**
  | 属性名 | 型 | 説明 |
  | :--- | :--- | :--- |
  | `Subject` | string | 件名。戦前の法令など、題名がない場合に想定されたが、現在は主に題名を `<LawTitle>` に登録する |

---

## 2. 書き出し・前文・目次

### 法令題名と制定文

- **`<LawTitle>`**: 法令の題名を表します 。

- 属性: `Kana`（読み）, `Abbrev`（略称）, `AbbrevKana`（略称読み）

- **`<EnactStatement>`**: 制定文を表します 。

- **`<Preamble>`**: 前文を表します。子要素に `<Paragraph>` を持ちます 。

### `<TOC>`（目次）

目次構造を定義します 。

- **ラベル・項目要素:**
- `<TOCLabel>`: 目次のラベル 。

- `<TOCPreambleLabel>`: 目次中の「前文」項目 。

- `<TOCPart>`, `<TOCChapter>`, `<TOCSection>`, `<TOCSubsection>`, `<TOCDivision>`: 各階層（編・章・節・款・目）の目次項目 。

- `<TOCArticle>`: 目次中の「条」項目 。

- `<TOCSupplProvision>`: 目次中の「附則」項目 。

- `<TOCAppdxTableLabel>`: 目次中の「別表」項目 。

- **共通属性（TOC項目）:**
- `Num`: 番号 。

- `Delete`: 削除扱いの場合は `true` 。

---

## 3. 本則および附則の構造

### 基本構成

- **`<MainProvision>`**: 本則 。

- 属性 `Extract`: 抄録の場合は `true` 。

- **`<SupplProvision>`**: 附則 。

- 属性 `Type`: "New"（制定時）または "Amend"（改正時） 。

- 属性 `AmendLawNum`: 改正法令番号 。

### 階層構造要素（編・章・節・款・目）

これらは法令の論理構造を形成し、共通の属性を持ちます 。

- **要素名:** `<Part>`, `<Chapter>`, `<Section>`, `<Subsection>`, `<Division>`
- **共通属性:**
- `Num`: 番号（必須） 。

- `Delete`: 削除フラグ 。

- `Hide`: 非表示フラグ 。

---

## 4. 条・項・号・細分

### `<Article>`（条）

法令の基本単位です 。

- **子要素:** `<ArticleCaption>`（見出し）, `<ArticleTitle>`（条名）, `<Paragraph>`, `<SupplNote>` 。

- **属性:** `Num`, `Delete`, `Hide` 。

### `<Paragraph>`（項）

- **子要素:** `<ParagraphCaption>`, `<ParagraphNum>`, `<ParagraphSentence>`, `<Item>`, 等 。

- **属性:**
- `Num`: 番号（必須） 。

- `OldStyle`: 古い形式の初字位置 。

- `OldNum`: 項番号のない形式 。

### `<Item>`（号）および細分

「号」から「号の細分（10階層目）」まで定義されています 。

- **要素名:** `<Item>`, `<Subitem1>` 〜 `<Subitem10>`
- **共通構成:** `{要素名}Title`（番号）, `{要素名}Sentence`（本文）, および下位階層の要素 。

---

## 5. 文面・インライン・表図要素

### `<Sentence>`（条文）

最小の文面単位です。「本文」と「ただし書」などを区別します 。

- **属性:**
- `Num`: 番号 。

- `Function`: "main"（本文）または "proviso"（ただし書） 。

- `WritingMode`: "vertical"（縦書き）または "horizontal"（横書き） 。

### 表・図・算式

- **`<TableStruct>`**: 表構造。内部に `<Table>` を持ち、`TableRow`, `TableColumn` で構成されます 。

- **`<FigStruct>`**: 図構造。`<Fig src="...">` で外部ファイルを参照します 。

- **`<ArithFormula>`**: 算式 。

### インライン要素

- **`<Ruby>`**: ルビ。`<Rt>` 要素で振りがなを指定します 。

- **`<Line>`**: 傍線。属性 `Style`（solid, dotted等）を持ちます 。

- **`<Sup>`, `<Sub>**`: 上付き・下付き文字 。

---

## 6. 改正規定・別表・様式

### `<AmendProvision>`（改正規定）

既存の法令を改正するための規定を格納します 。

- **`<NewProvision>`**: 改正によって新しく挿入される条文等をこの中に記述します 。

### 別表・別記

- **`<AppdxTable>`**: 別表 。

- **`<AppdxNote>`**: 別記 。

- **`<AppdxStyle>`**: 別記様式 。

- **`<AppdxFormat>`**: 別記書式 。

- **`<AppdxFig>`**: 別図 。

---

## 7. その他

- **`<Remarks>`**: 備考。`<RemarksLabel>` と本文で構成されます 。

- **`<SupplNote>`**: 付記。道路交通法の罰則表記などに使用されます 。

---

このドキュメントをベースにした、特定のXMLタグ間の親子関係の詳細なバリデーションチェックリストを作成しましょうか？
