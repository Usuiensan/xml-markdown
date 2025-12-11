import requests
import xml.etree.ElementTree as ET
import os
import sys

def fetch_law_data(law_name):
    # 1. 法令リストからLawIdを検索
    print(f"[{law_name}] を検索中...")
    list_url = "https://laws.e-gov.go.jp/api/1/lawlists/1"
    response = requests.get(list_url)
    root = ET.fromstring(response.content)
    
    law_id = None
    for law in root.findall(".//LawNameListInfo"):
        if law.find("LawName").text == law_name:
            law_id = law.find("LawId").text
            break
            
    if not law_id:
        print(f"Error: {law_name} が見つかりませんでした。")
        return None

    # 2. 条文データを取得
    print(f"条文データをダウンロード中... (https://laws.e-gov.go.jp/api/1/lawdata/{law_id})")
    detail_url = f"https://laws.e-gov.go.jp/api/1/lawdata/{law_id}"
    law_response = requests.get(detail_url)
    return law_response.content

def load_xml_from_file(file_path):
    """XMLファイルを読み込む"""
    if not os.path.exists(file_path):
        print(f"エラー: ファイル '{file_path}' が見つかりません。")
        return None
    
    if not file_path.lower().endswith('.xml'):
        print(f"エラー: ファイルはXML形式である必要があります。")
        return None
    
    try:
        print(f"XMLファイルを読み込み中... ({file_path})")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        print("XMLファイルを読み込みました。")
        return xml_data
    except Exception as e:
        print(f"エラー: ファイルの読み込みに失敗しました。({e})")
        return None

def convert_article_num(num_str):
    """Article Num属性を日本語表記に変換 (例: "38_3_2" -> "第38条の3の2")"""
    if not num_str:
        return ""
    parts = num_str.split("_")
    result = "第" + parts[0] + "条"
    for part in parts[1:]:
        result += "の" + part
    return result

def get_paragraph_label(p_num_attr, total_paragraphs):
    """Paragraph Num属性から項ラベルを生成
    複数項がある場合: "第1項"
    単一項の場合: "" (空文字列)"""
    if total_paragraphs == 1:
        return ""
    if not p_num_attr:
        return ""
    return f"第{p_num_attr}項"

def convert_item_num(num_str):
    """Item Num属性を日本語表記に変換 (例: "1" -> "第1号", "3_2" -> "第3の2号")"""
    if not num_str:
        return ""
    parts = num_str.split("_")
    result = "第" + parts[0]
    for part in parts[1:]:
        result += "の" + part
    return result + "号"

def normalize_text(text: str) -> str:
    """Collapse whitespace (including newlines) and trim."""
    if not text:
        return ""
    return " ".join(text.split())

def process_arith_formula(arith_formula):
    """ArithFormula要素を処理してMarkdown形式で返す
    数学公式を整形する"""
    if arith_formula is None:
        return ""
    
    # ArithFormula内のテキストを抽出
    formula_text = normalize_text(extract_text(arith_formula))
    if not formula_text:
        return ""
    
    # 数式をインラインコード形式またはブロック形式で出力
    # 複数行の場合はブロック、単一行の場合はインライン
    if "\n" in formula_text or len(formula_text) > 100:
        return f"```\n{formula_text}\n```\n\n"
    else:
        return f"`{formula_text}`\n\n"

def extract_text(element):
    """要素内のテキストを再帰的に抽出（子要素を含む）
    ルビ、上付き、下付きなどのテキスト修飾も処理"""
    if element is None:
        return ""
    
    text = element.text or ""
    
    for child in element:
        # ルビの処理
        if child.tag == "Ruby":
            ruby_text = child.text or ""
            rt = child.find("Rt")
            if rt is not None and rt.text:

                text += f"{{{ruby_text}|{rt.text}}}"
            else:
                text += ruby_text
        # 上付き、下付きの処理
        elif child.tag in ["Sup", "Sub"]:
            text += extract_text(child)
        # 傍線の処理
        elif child.tag == "Line":
            text += extract_text(child)
        # Column要素の処理（ItemSentenceの中の複数列の場合）
        elif child.tag == "Column":
            text += extract_text(child)
        # FigStruct / Fig 要素は extract_text では無視（別途処理）
        elif child.tag in ["FigStruct", "Fig"]:
            # テキストの場合のみ抽出
            pass
        # StyleStruct / NoteStruct / FormatStruct / Class は extract_text では無視
        elif child.tag in ["StyleStruct", "NoteStruct", "FormatStruct", "Class"]:
            # テキストの場合のみ抽出
            pass
        # その他の要素
        else:
            text += extract_text(child)
        
        # 兄弟要素のテキストを追加
        if child.tail:
            text += child.tail

    # 不要な改行・インデントをまとめる
    return normalize_text(text)

def extract_preamble(xml_root):
    """前文を抽出してMarkdown形式で返す"""
    preamble = xml_root.find(".//Preamble")
    if preamble is None:
        return ""
    
    markdown_text = "## 前文\n\n"
    
    paragraphs = preamble.findall("Paragraph")
    for para in paragraphs:
        sent = para.find(".//Sentence")
        if sent is not None:
            text = normalize_text(extract_text(sent))
            markdown_text += f"{text}\n\n"
    
    markdown_text += "\n"
    return markdown_text

def extract_enact_statement(xml_root):
    """制定文を抽出してMarkdown形式で返す"""
    enact_stmt = xml_root.find(".//EnactStatement")
    if enact_stmt is None:
        return ""
    
    markdown_text = "## 制定文\n\n"
    
    # EnactStatement内のParagraphを処理
    paragraphs = enact_stmt.findall("Paragraph")
    for para in paragraphs:
        sent = para.find(".//Sentence")
        if sent is not None:
            text = normalize_text(extract_text(sent))
            markdown_text += f"{text}\n\n"
    
    # EnactStatement直下のSentenceも処理
    for sent in enact_stmt.findall("./Sentence"):
        text = normalize_text(extract_text(sent))
        markdown_text += f"{text}\n\n"
    
    markdown_text += "\n"
    return markdown_text

def process_amend_provision(xml_root):
    """改正規定（AmendProvision）を処理してMarkdown形式で返す"""
    amend_provs = xml_root.findall(".//AmendProvision")
    if not amend_provs:
        return ""
    
    markdown_text = "# 改正規定\n\n"
    
    for amend_prov in amend_provs:
        # 改正対象の法令名を取得（AmendLawNameがあれば）
        amend_law_elem = amend_prov.find("AmendLawName")
        if amend_law_elem is not None:
            amend_law_name = normalize_text(extract_text(amend_law_elem))
            markdown_text += f"## {amend_law_name}\n\n"
        
        # 改正規定内の条を処理
        articles = amend_prov.findall("Article")
        for article in articles:
            markdown_text += process_article(article, 3)
    
    return markdown_text

def extract_toc(xml_root):
    """目次（TOC）を抽出してMarkdown形式で返す"""
    toc = xml_root.find(".//TOC")
    if toc is None:
        return ""
    
    markdown_text = "## 目次\n\n"
    
    # TOC内の各要素を処理
    for child in toc:
        markdown_text += process_toc_element(child, indent_level=0)
    
    markdown_text += "\n"
    return markdown_text

def process_toc_element(element, indent_level):
    """TOC内の要素を再帰的に処理"""
    markdown_text = ""
    indent = "  " * indent_level
    
    tag = element.tag
    
    # TOCLabel（目次ラベル）
    if tag == "TOCLabel":
        label_text = normalize_text(extract_text(element))
        markdown_text += f"{indent}- {label_text}\n"
    
    # TOCPreambleLabel（前文ラベル）
    elif tag == "TOCPreambleLabel":
        label_text = normalize_text(extract_text(element))
        markdown_text += f"{indent}- {label_text}\n"
    
    # TOCPart（編）
    elif tag == "TOCPart":
        part_title = element.find("PartTitle")
        if part_title is not None:
            title_text = normalize_text(extract_text(part_title))
            markdown_text += f"{indent}- {title_text}\n"
        
        # 子要素を処理
        for child in element:
            if child.tag in ["TOCChapter", "PartTitle"]:
                if child.tag == "TOCChapter":
                    markdown_text += process_toc_element(child, indent_level + 1)
    
    # TOCChapter（章）
    elif tag == "TOCChapter":
        chapter_title = element.find("ChapterTitle")
        if chapter_title is not None:
            title_text = normalize_text(extract_text(chapter_title))
            markdown_text += f"{indent}- {title_text}\n"
        
        # 子要素を処理
        for child in element:
            if child.tag in ["TOCSection", "ChapterTitle"]:
                if child.tag == "TOCSection":
                    markdown_text += process_toc_element(child, indent_level + 1)
    
    # TOCSection（節）
    elif tag == "TOCSection":
        section_title = element.find("SectionTitle")
        if section_title is not None:
            title_text = normalize_text(extract_text(section_title))
            markdown_text += f"{indent}- {title_text}\n"
        
        # 子要素を処理
        for child in element:
            if child.tag in ["TOCSubsection", "TOCDivision", "SectionTitle"]:
                if child.tag in ["TOCSubsection", "TOCDivision"]:
                    markdown_text += process_toc_element(child, indent_level + 1)
    
    # TOCSubsection（款）
    elif tag == "TOCSubsection":
        subsection_title = element.find("SubsectionTitle")
        if subsection_title is not None:
            title_text = normalize_text(extract_text(subsection_title))
            markdown_text += f"{indent}- {title_text}\n"
        
        # 子要素を処理
        for child in element:
            if child.tag in ["TOCDivision", "SubsectionTitle"]:
                if child.tag == "TOCDivision":
                    markdown_text += process_toc_element(child, indent_level + 1)
    
    # TOCDivision（目）
    elif tag == "TOCDivision":
        division_title = element.find("DivisionTitle")
        if division_title is not None:
            title_text = normalize_text(extract_text(division_title))
            markdown_text += f"{indent}- {title_text}\n"
    
    # TOCArticle（条）
    elif tag == "TOCArticle":
        article_num = element.get("Num", "")
        article_label = convert_article_num(article_num) if article_num else ""
        
        article_title = element.find("ArticleTitle")
        if article_title is not None:
            title_text = normalize_text(extract_text(article_title))
            if article_label:
                markdown_text += f"{indent}- {article_label} {title_text}\n"
            else:
                markdown_text += f"{indent}- {title_text}\n"
        elif article_label:
            markdown_text += f"{indent}- {article_label}\n"
    
    # TOCSupplProvision（附則）
    elif tag == "TOCSupplProvision":
        suppl_label = element.find("SupplProvisionLabel")
        if suppl_label is not None:
            label_text = normalize_text(extract_text(suppl_label))
            markdown_text += f"{indent}- {label_text}\n"
        
        # 子要素を処理
        for child in element:
            if child.tag == "TOCArticle":
                markdown_text += process_toc_element(child, indent_level + 1)
    
    # TOCAppdxTableLabel（別表ラベル）
    elif tag == "TOCAppdxTableLabel":
        label_text = normalize_text(extract_text(element))
        markdown_text += f"{indent}- {label_text}\n"
    
    # ArticleRange（条範囲）
    elif tag == "ArticleRange":
        range_text = normalize_text(extract_text(element))
        if range_text:
            markdown_text += f"{indent}  （{range_text}）\n"
    
    return markdown_text

def extract_suppl_provision(xml_root):
    """附則を抽出してMarkdown形式で返す"""
    suppl = xml_root.find(".//SupplProvision")
    if suppl is None:
        return ""
    
    markdown_text = "# 附則\n\n"
    
    # 附則ラベル
    suppl_label = suppl.find("SupplProvisionLabel")
    if suppl_label is not None:
        label_text = normalize_text(extract_text(suppl_label))
        markdown_text += f"## {label_text}\n\n"
    
    # 附則の条
    articles = suppl.findall("Article")
    for article in articles:
        article_num = article.get("Num", "")
        article_label = convert_article_num(article_num)
        markdown_text += f"### {article_label}\n"
        
        paragraphs = article.findall("Paragraph")
        for para in paragraphs:
            sent = para.find(".//Sentence")
            if sent is not None:
                text = normalize_text(extract_text(sent))
                markdown_text += f"- {text}\n"
        
        markdown_text += "\n"
    
    return markdown_text

def get_hierarchy_level(element_tag):
    """要素タグから階層レベルを取得（見出しレベル）
    Part: 2, Chapter: 3, Section: 4, Subsection: 5, Division: 6"""
    hierarchy_map = {
        "Part": 2,
        "Chapter": 3,
        "Section": 4,
        "Subsection": 5,
        "Division": 6
    }
    return hierarchy_map.get(element_tag, 2)

def process_structure_element(element, heading_level=None):
    """章・節などの構造要素を処理（再帰的）
    heading_level: 見出しレベル（#の数）。Noneの場合は要素タグから自動決定"""
    markdown_text = ""
    
    # heading_level が指定されていない場合は要素タグから自動決定
    element_tag = element.tag
    if heading_level is None:
        heading_level = get_hierarchy_level(element_tag)
    
    # タイトルを取得
    title_map = {
        "Part": "PartTitle",
        "Chapter": "ChapterTitle",
        "Section": "SectionTitle",
        "Subsection": "SubsectionTitle",
        "Division": "DivisionTitle"
    }
    
    title_tag = title_map.get(element_tag)
    
    if title_tag:
        title_elem = element.find(title_tag)
        if title_elem is not None:
            title_text = normalize_text(extract_text(title_elem))
            heading = "#" * heading_level
            markdown_text += f"{heading} {title_text}\n\n"
    
    # 子要素を処理
    # 次の階層の構造要素を処理
    hierarchy = ["Part", "Chapter", "Section", "Subsection", "Division"]
    current_index = hierarchy.index(element_tag) if element_tag in hierarchy else -1
    
    if current_index >= 0 and current_index < len(hierarchy) - 1:
        next_elem_name = hierarchy[current_index + 1]
        for child in element.findall(next_elem_name):
            # 次の階層の要素は自動的に適切なレベルが決定される
            markdown_text += process_structure_element(child)
    
    # 条を処理
    # 構造要素の配下の条は、見出しレベル+1のレベルを使用
    article_heading_level = heading_level + 1
    # ただし最大は H6 までなので、それ以上にならないようにする
    article_heading_level = min(article_heading_level, 6)
    for article in element.findall("Article"):
        markdown_text += process_article(article, article_heading_level)
    
    return markdown_text

def process_article(article, heading_level):
    """条を処理"""
    markdown_text = ""
    
    article_num = article.get("Num", "")
    article_label = convert_article_num(article_num)
    
    heading = "#" * heading_level
    # 条見出し（ArticleCaption）を付加
    caption = article.find("ArticleCaption")
    caption_text = normalize_text(extract_text(caption)) if caption is not None else ""

    markdown_text += f"{heading} {article_label}"
    if caption_text:
        markdown_text += f"{caption_text}\n"
    else:
        markdown_text += "\n"
    # 項を処理
    paragraphs = article.findall("Paragraph")
    total_paragraphs = len(paragraphs)
    
    for para in paragraphs:
        p_num_attr = para.get("Num", "")
        p_label = get_paragraph_label(p_num_attr, total_paragraphs)
        
        # ParagraphSentence（項の文章・柱書）を明示的に処理
        para_sent = para.find("ParagraphSentence")
        if para_sent is not None:
            # ParagraphSentence内のSentenceを処理
            sent = para_sent.find(".//Sentence")
            if sent is not None:
                sent_text = normalize_text(extract_text(sent))
                
                # 項が1つのみの場合は箇条書きなし、複数の場合は箇条書きで表示
                if total_paragraphs == 1:
                    markdown_text += f"{sent_text}\n"
                elif p_label:
                    markdown_text += f"- **{p_label}** {sent_text}\n"
                else:
                    markdown_text += f"- {sent_text}\n"
        else:
            # ParagraphSentenceがない場合は従来の方法でSentenceを探す
            sent = para.find(".//Sentence")
            if sent is not None:
                sent_text = normalize_text(extract_text(sent))
                
                # 項が1つのみの場合は箇条書きなし、複数の場合は箇条書きで表示
                if total_paragraphs == 1:
                    markdown_text += f"{sent_text}\n"
                elif p_label:
                    markdown_text += f"- **{p_label}** {sent_text}\n"
                else:
                    markdown_text += f"- {sent_text}\n"

        # 列記（List）を処理
        for list_elem in para.findall("List"):
            markdown_text += process_list(list_elem, indent_level=0)
        
        # 表を処理
        for table_struct in para.findall("TableStruct"):
            markdown_text += "\n"
            markdown_text += render_table_struct(table_struct, indent_level=0)
        for table in para.findall("Table"):
            markdown_text += "\n"
            markdown_text += render_table(table, indent_level=0)
        
        # 図を処理
        for fig_struct in para.findall("FigStruct"):
            markdown_text += "\n"
            markdown_text += process_fig_struct(fig_struct)
        for fig in para.findall("Fig"):
            markdown_text += "\n"
            markdown_text += process_fig(fig)
        
        # 様式項目（StyleStruct）を処理
        for style_struct in para.findall("StyleStruct"):
            markdown_text += "\n"
            markdown_text += process_style_struct(style_struct)
        
        # 記項目（NoteStruct）を処理
        for note_struct in para.findall("NoteStruct"):
            markdown_text += "\n"
            markdown_text += process_note_struct(note_struct)
        
        # 書式項目（FormatStruct）を処理
        for format_struct in para.findall("FormatStruct"):
            markdown_text += "\n"
            markdown_text += process_format_struct(format_struct)
        
        # 類（Class）を処理
        for class_elem in para.findall("Class"):
            markdown_text += "\n"
            markdown_text += process_class(class_elem)
        
        # 号を処理
        items = para.findall("Item")
        for item in items:
            markdown_text += process_item(item, 1)
    
    # 条の付記（SupplNote）を処理
    suppl_notes = article.findall("SupplNote")
    if suppl_notes:
        markdown_text += "\n"
        for suppl_note in suppl_notes:
            sent = suppl_note.find(".//Sentence")
            if sent is not None:
                text = normalize_text(extract_text(sent))
                markdown_text += f"*（{text}）*\n"
            else:
                # Sentenceがない場合は直接テキストを抽出
                text = normalize_text(extract_text(suppl_note))
                if text:
                    markdown_text += f"*（{text}）*\n"
    
    # 算式（ArithFormula）を処理
    arith_formulas = article.findall("ArithFormula")
    if arith_formulas:
        markdown_text += "\n"
        for arith_formula in arith_formulas:
            markdown_text += process_arith_formula(arith_formula)
    
    markdown_text += "\n"
    return markdown_text

def process_item(item, indent_level):
    """号を処理"""
    markdown_text = ""
    
    item_num = item.get("Num", "")
    item_label = convert_item_num(item_num)
    item_title_elem = item.find("ItemTitle")
    item_title = normalize_text(extract_text(item_title_elem)) if item_title_elem is not None else ""
    
    # ItemSentenceを取得
    item_sent = item.find("ItemSentence")
    if item_sent is not None:
        rendered = render_item_sentence(item_sent, indent_level, item_label, item_title)
        markdown_text += rendered
    else:
        # ItemSentenceがない場合は単純にSentenceを探す
        sent = item.find(".//Sentence")
        if sent is not None:
            sent_text = normalize_text(extract_text(sent))
            indent = "    " * indent_level
            markdown_text += f"{indent}- **{item_label}** {sent_text}\n"

    # 列記（List）を処理
    for list_elem in item.findall("List"):
        markdown_text += process_list(list_elem, indent_level=indent_level + 1)
    
    # ItemSentence の外側の表を処理（ItemSentence内のテーブルはrender_item_sentenceで処理済み）
    for table_struct in item.findall("TableStruct"):
        markdown_text += render_table_struct(table_struct, indent_level=indent_level)
    # Item直下のTable（ItemSentenceの外）を処理
    for table in item.findall("./Table"):
        markdown_text += render_table(table, indent_level=indent_level)
    
    # 図を処理
    for fig_struct in item.findall("FigStruct"):
        markdown_text += "\n"
        markdown_text += process_fig_struct(fig_struct)
    for fig in item.findall("Fig"):
        markdown_text += "\n"
        markdown_text += process_fig(fig)
    
    # 様式項目（StyleStruct）を処理
    for style_struct in item.findall("StyleStruct"):
        markdown_text += "\n"
        markdown_text += process_style_struct(style_struct)
    
    # 記項目（NoteStruct）を処理
    for note_struct in item.findall("NoteStruct"):
        markdown_text += "\n"
        markdown_text += process_note_struct(note_struct)
    
    # 書式項目（FormatStruct）を処理
    for format_struct in item.findall("FormatStruct"):
        markdown_text += "\n"
        markdown_text += process_format_struct(format_struct)
    
    # 類（Class）を処理
    for class_elem in item.findall("Class"):
        markdown_text += "\n"
        markdown_text += process_class(class_elem)
    
    # Subitem1～Subitem10を処理
    subitem_levels = [
        ("Subitem1", "Subitem1Sentence"),
        ("Subitem2", "Subitem2Sentence"),
        ("Subitem3", "Subitem3Sentence"),
        ("Subitem4", "Subitem4Sentence"),
        ("Subitem5", "Subitem5Sentence"),
        ("Subitem6", "Subitem6Sentence"),
        ("Subitem7", "Subitem7Sentence"),
        ("Subitem8", "Subitem8Sentence"),
        ("Subitem9", "Subitem9Sentence"),
        ("Subitem10", "Subitem10Sentence"),
    ]
    
    for i, (subitem_elem, sent_elem) in enumerate(subitem_levels):
        subitems = item.findall(subitem_elem)
        if subitems:
            sub_indent_level = indent_level + 1 + i
            for subitem in subitems:
                markdown_text += process_subitem(subitem, sub_indent_level)
    
    return markdown_text

def process_subitem(subitem, indent_level):
    """号の細分を処理"""
    markdown_text = ""
    
    title_elem_name = subitem.tag + "Title"
    title_elem = subitem.find(title_elem_name)
    label_text = normalize_text(extract_text(title_elem)) if title_elem is not None else ""
    if not label_text:
        label_text = ""

    sent_elem_name = subitem.tag + "Sentence"
    sent = subitem.find(sent_elem_name)
    
    if sent is not None:
        sent_text = normalize_text(extract_text(sent))
        indent = "    " * indent_level
        markdown_text += f"{indent}- **{label_text}** {sent_text}\n"
    
    # さらに下層の細分を処理する場合はここに追加
    
    return markdown_text

def render_item_sentence(item_sent, indent_level, item_label, item_title):
    """ItemSentenceを読みやすいMarkdownの1行に整形
    Columnが複数ある場合は「用語: 定義」の形で連結
    Table要素がある場合はテーブルとして処理"""
    indent = "    " * indent_level
    
    # ItemSentence内のTable要素を先に確認
    tables = item_sent.findall("Table")
    markdown_text = ""
    
    # 通常のColumn処理
    columns = item_sent.findall("Column")
    if columns:
        term = normalize_text(extract_text(columns[0]))
        definition_parts = [normalize_text(extract_text(col)) for col in columns[1:]]
        definition = " ".join([p for p in definition_parts if p])
        if not term:
            term = item_title
        label = f"**{item_label}**"
        if term and definition:
            markdown_text += f"{indent}- {label} {term}: {definition}\n"
        elif term:
            markdown_text += f"{indent}- {label} {term}\n"
        else:
            markdown_text += f"{indent}- {label} {definition}\n"
    else:
        # Columnが無い場合は通常のテキストを返す
        sent_text = normalize_text(extract_text(item_sent))
        label = f"**{item_label}**"
        markdown_text += f"{indent}- {label} {sent_text}\n"
    
    # ItemSentence内のTable要素を処理
    if tables:
        markdown_text += "\n"
        for table in tables:
            markdown_text += render_table(table, indent_level=indent_level)
    
    return markdown_text

def process_list(list_elem, indent_level):
    """列記（List）を処理する
    <List>要素内の<ListSentence>と<Sublist1～3>を階層的に処理"""
    markdown_text = ""
    indent = "    " * indent_level
    
    # ListSentence（柱書）を処理
    list_sentence = list_elem.find("ListSentence")
    if list_sentence is not None:
        sent = list_sentence.find(".//Sentence")
        if sent is not None:
            list_sent_text = normalize_text(extract_text(sent))
            markdown_text += f"{indent}{list_sent_text}\n"
    
    # Sublist1～Sublist3を処理（階層的に）
    sublist_levels = [
        ("Sublist1", "Sublist1Sentence", "Sublist2"),
        ("Sublist2", "Sublist2Sentence", "Sublist3"),
        ("Sublist3", "Sublist3Sentence", None),
    ]
    
    for i, (sublist_elem_tag, sent_elem_tag, next_sublist_tag) in enumerate(sublist_levels):
        subitems = list_elem.findall(sublist_elem_tag)
        if subitems:
            next_indent_level = indent_level + 1 + i
            for subitem in subitems:
                markdown_text += process_sublist_item(
                    subitem, 
                    next_indent_level, 
                    sent_elem_tag, 
                    next_sublist_tag
                )
    
    return markdown_text

def process_sublist_item(sublist_item, indent_level, sent_elem_tag, next_sublist_tag):
    """Sublist1～3の個別項目を処理"""
    markdown_text = ""
    indent = "    " * indent_level
    
    # 該当するSentence要素を取得
    sent = sublist_item.find(sent_elem_tag)
    if sent is None:
        sent = sublist_item.find(".//Sentence")
    
    if sent is not None:
        sent_text = normalize_text(extract_text(sent))
        markdown_text += f"{indent}- {sent_text}\n"
    
    # 次の階層のSublistがあれば処理
    if next_sublist_tag:
        next_subitems = sublist_item.findall(next_sublist_tag)
        if next_subitems:
            for next_item in next_subitems:
                # 次のSentence要素タグを生成（Sublist2 -> Sublist2Sentence など）
                next_sent_tag = next_sublist_tag + "Sentence"
                # さらに次のSublistタグを生成
                next_next_tag = None
                if next_sublist_tag == "Sublist2":
                    next_next_tag = "Sublist3"
                
                markdown_text += process_sublist_item(
                    next_item,
                    indent_level + 1,
                    next_sent_tag,
                    next_next_tag
                )
    
    return markdown_text

def render_table_struct(table_struct, indent_level=0):
    """TableStruct をMarkdownテーブルに変換"""
    markdown_text = ""
    indent = "    " * indent_level

    title = table_struct.find("TableStructTitle")
    if title is not None:
        title_text = normalize_text(extract_text(title))
        markdown_text += f"{indent}{title_text}\n"

    table = table_struct.find("Table")
    if table is not None:
        markdown_text += render_table(table, indent_level)

    return markdown_text

def render_table(table_elem, indent_level=0):
    """Table要素をMarkdownテーブル文字列に変換 (rowspan対応強化)
    
    グリッド構造を構築し、rowspanによる縦結合を正確に処理する
    """
    indent = "    " * indent_level

    # 1. ヘッダー行の処理
    header_row_elem = table_elem.find("TableHeaderRow")
    header_cols = []
    if header_row_elem is not None:
        header_cols = [normalize_text(extract_text(col)) for col in header_row_elem.findall("TableHeaderColumn")]
    
    # colspanを持つ行を収集 (備考として処理)
    remark_sentences = []
    
    # 2. 最大列数を決定
    max_cols = len(header_cols)
    for row_elem in table_elem.findall("TableRow"):
        cols = row_elem.findall("TableColumn")
        # colspan属性がある行は数える対象外
        if not (cols and cols[0].get("colspan")):
            max_cols = max(max_cols, len(cols))

    if max_cols == 0:
        max_cols = len(header_cols)

    # 3. グリッドの構築とrowspanの処理
    grid = []
    # rowspanで隠れるべきセル位置を追跡 (column_index: remaining_rowspan)
    rowspan_tracker = {} 

    # TableRowを処理
    for row_elem in table_elem.findall("TableRow"):
        cols = row_elem.findall("TableColumn")

        # colspan属性がある行は備考として処理
        if cols and cols[0].get("colspan"):
            sentences = cols[0].findall(".//Sentence")
            remark_sentences.extend([normalize_text(extract_text(sent)) for sent in sentences])
            continue
        
        current_row = [None] * max_cols  # None で初期化
        col_idx = 0
        
        # まず、rowspanで埋まっているセルにプレースホルダを挿入
        for i in range(max_cols):
            if i in rowspan_tracker and rowspan_tracker[i] > 0:
                current_row[i] = "#ROWSPAN_PLACEHOLDER#"
                rowspan_tracker[i] -= 1
            elif i in rowspan_tracker and rowspan_tracker[i] == 0:
                del rowspan_tracker[i]

        # TableColumnのデータを挿入
        for col in cols:
            # 既にプレースホルダが入っている位置をスキップ
            while col_idx < max_cols and current_row[col_idx] is not None:
                col_idx += 1 
            
            # 最大列数を超えていたら終了
            if col_idx >= max_cols:
                break
                
            # セル内容の抽出
            sentences = col.findall("Sentence")
            cell_content = " ".join([normalize_text(extract_text(sent)) for sent in sentences])
            
            current_row[col_idx] = cell_content
            
            # rowspanの追跡
            rowspan = int(col.get("rowspan", 1))
            if rowspan > 1:
                rowspan_tracker[col_idx] = rowspan - 1
            
            col_idx += 1

        # Noneを空文字列に変換
        current_row = [cell if cell is not None else "" for cell in current_row]
        grid.append(current_row)
        
    # 4. ヘッダーを正規化
    if not header_cols:
        if grid:
            header_cols = grid.pop(0)
        else:
            return ""

    header_cols = header_cols + [""] * (max_cols - len(header_cols))
    
    # 5. グリッドを整形し、Markdownに変換
    md_lines = []
    
    # ヘッダー行を出力
    md_lines.append(indent + "| " + " | ".join(header_cols) + " |")
    # 区切り線を出力
    md_lines.append(indent + "| " + " | ".join(["---"] * len(header_cols)) + " |")
    
    # データ行を出力
    # グリッド内の "#ROWSPAN_PLACEHOLDER#" を直上の行のデータで置き換える
    normalized_grid = []
    for row_idx, row in enumerate(grid):
        processed_row = []
        for col_idx, cell in enumerate(row):
            if cell == "#ROWSPAN_PLACEHOLDER#":
                # 前の行（ヘッダーまたはデータ）の同じ列からコピー
                if row_idx == 0:
                    # ヘッダーからのコピー
                    processed_row.append(header_cols[col_idx] if col_idx < len(header_cols) else "")
                else:
                    # 直前のデータ行からのコピー
                    processed_row.append(normalized_grid[row_idx - 1][col_idx] if col_idx < len(normalized_grid[row_idx - 1]) else "")
            else:
                processed_row.append(cell)
        normalized_grid.append(processed_row)
        md_lines.append(indent + "| " + " | ".join(processed_row) + " |")

    md_output = "\n".join(md_lines) + "\n\n"

    # 備考の出力 (colspan対応)
    if remark_sentences:
        md_output += f">  \n"
        for idx, sent in enumerate(remark_sentences):
            if sent:
                if idx == 0:
                    md_output += f"> **{sent}**  \n"
                else:
                    md_output += f"> {sent}  \n"
        md_output += f">  \n\n"
    return md_output

def extract_law_metadata(xml_root):
    """法令の基本属性（法令番号、公布日など）を抽出"""
    metadata_text = ""
    
    # ルート要素そのものがLaw要素の場合とLaw要素を子に持つ場合に対応
    law_elem = xml_root
    if law_elem.tag != "Law":
        law_elem = xml_root.find(".//Law")
    
    if law_elem is not None and law_elem.tag == "Law":
        # Law要素の属性を取得
        era = law_elem.get("Era", "")
        year = law_elem.get("Year", "")
        law_num = law_elem.get("Num", "")
        law_type = law_elem.get("LawType", "")
        promulgate_month = law_elem.get("PromulgateMonth", "")
        promulgate_day = law_elem.get("PromulgateDay", "")
        
        # 法令番号の表記を組立
        if era and year and law_num:
            era_name = {
                "Meiji": "明治", "Taisho": "大正", "Showa": "昭和",
                "Heisei": "平成", "Reiwa": "令和"
            }.get(era, era)
            law_type_name = {
                "Act": "法律", "CabinetOrder": "政令", "MinisterialOrdinance": "省令",
                "Rule": "規則"
            }.get(law_type, law_type)
            if law_type_name:
                metadata_text += f"**法令番号**: {era_name}{year}年{law_type_name}第{law_num}号\n\n"
        
        # 公布日
        if promulgate_month or promulgate_day:
            metadata_text += f"**公布日**: "
            if promulgate_month:
                metadata_text += f"{promulgate_month}月"
            if promulgate_day:
                metadata_text += f"{promulgate_day}日"
            metadata_text += "\n\n"
    
    # LawBody要素のSubject属性を確認
    law_body = xml_root.find(".//LawBody")
    if law_body is not None:
        subject = law_body.get("Subject", "")
        if subject:
            metadata_text += f"**件名**: {subject}\n\n"
    
    return metadata_text

def process_appdx_table(appdx_table):
    """別表（AppdxTable）を処理"""
    markdown_text = ""
    
    # AppdxTable のタイトル
    title = appdx_table.find("AppdxTableTitle")
    if title is not None:
        title_text = normalize_text(extract_text(title))
        markdown_text += f"## {title_text}\n\n"
    
    # Table を処理
    table = appdx_table.find("Table")
    if table is not None:
        markdown_text += render_table(table, indent_level=0)
    
    return markdown_text

def process_appdx_note(appdx_note):
    """別記（AppdxNote）を処理"""
    markdown_text = ""
    
    # AppdxNote のタイトル
    title = appdx_note.find("AppdxNoteTitle")
    if title is not None:
        title_text = normalize_text(extract_text(title))
        markdown_text += f"## {title_text}\n\n"
    
    # NoteStruct や Paragraph を処理
    for para in appdx_note.findall("Paragraph"):
        sent = para.find(".//Sentence")
        if sent is not None:
            text = normalize_text(extract_text(sent))
            markdown_text += f"{text}\n\n"
    
    # Table を処理
    for table_struct in appdx_note.findall("TableStruct"):
        markdown_text += render_table_struct(table_struct, indent_level=0)
    for table in appdx_note.findall("Table"):
        markdown_text += render_table(table, indent_level=0)
    
    return markdown_text

def process_appdx_style(appdx_style):
    """様式（AppdxStyle）を処理"""
    markdown_text = ""
    
    # AppdxStyle のタイトル
    title = appdx_style.find("AppdxStyleTitle")
    if title is not None:
        title_text = normalize_text(extract_text(title))
        markdown_text += f"## {title_text}\n\n"
    
    # StyleStruct を処理
    for style_struct in appdx_style.findall("StyleStruct"):
        struct_title = style_struct.find("StyleStructTitle")
        if struct_title is not None:
            struct_title_text = normalize_text(extract_text(struct_title))
            markdown_text += f"### {struct_title_text}\n\n"
        
        # Paragraph を処理
        for para in style_struct.findall("Paragraph"):
            sent = para.find(".//Sentence")
            if sent is not None:
                text = normalize_text(extract_text(sent))
                markdown_text += f"{text}\n\n"
    
    return markdown_text

def process_appdx_format(appdx_format):
    """書式（AppdxFormat）を処理"""
    markdown_text = ""
    
    # AppdxFormat のタイトル
    title = appdx_format.find("AppdxFormatTitle")
    if title is not None:
        title_text = normalize_text(extract_text(title))
        markdown_text += f"## {title_text}\n\n"
    
    # FormatStruct を処理
    for format_struct in appdx_format.findall("FormatStruct"):
        struct_title = format_struct.find("FormatStructTitle")
        if struct_title is not None:
            struct_title_text = normalize_text(extract_text(struct_title))
            markdown_text += f"### {struct_title_text}\n\n"
        
        # Paragraph を処理
        for para in format_struct.findall("Paragraph"):
            sent = para.find(".//Sentence")
            if sent is not None:
                text = normalize_text(extract_text(sent))
                markdown_text += f"{text}\n\n"
    
    return markdown_text

def process_appdx_fig(appdx_fig):
    """別図（AppdxFig）を処理"""
    markdown_text = ""
    
    # AppdxFig のタイトル
    title = appdx_fig.find("AppdxFigTitle")
    if title is not None:
        title_text = normalize_text(extract_text(title))
        markdown_text += f"## {title_text}\n\n"
    
    # FigStruct を処理
    for fig_struct in appdx_fig.findall("FigStruct"):
        markdown_text += process_fig_struct(fig_struct)
    
    return markdown_text

def process_appdx(appdx):
    """別（Appdx）を処理"""
    markdown_text = ""
    
    # Appdx のタイトル
    title = appdx.find("AppdxTitle")
    if title is not None:
        title_text = normalize_text(extract_text(title))
        markdown_text += f"## {title_text}\n\n"
    
    # Paragraph を処理
    for para in appdx.findall("Paragraph"):
        sent = para.find(".//Sentence")
        if sent is not None:
            text = normalize_text(extract_text(sent))
            markdown_text += f"{text}\n\n"
    
    return markdown_text

def process_fig_struct(fig_struct):
    """FigStruct（図構造）を処理"""
    markdown_text = ""
    
    # Fig タイトル
    fig_title = fig_struct.find("FigStructTitle")
    if fig_title is not None:
        title_text = normalize_text(extract_text(fig_title))
        markdown_text += f"### {title_text}\n\n"
    
    # Fig を処理
    fig = fig_struct.find("Fig")
    if fig is not None:
        markdown_text += process_fig(fig)
    
    return markdown_text

def process_fig(fig):
    """Fig（図）を処理"""
    markdown_text = ""
    
    # 図のファイル参照を取得
    src = fig.get("src", "")
    if src:
        markdown_text += f"![図]({src})\n\n"
    else:
        # src属性がない場合は説明文を抽出
        text = normalize_text(extract_text(fig))
        if text:
            markdown_text += f"*[図: {text}]*\n\n"
    
    return markdown_text

def process_style_struct(style_struct):
    """様式項目（StyleStruct）を処理"""
    markdown_text = ""
    
    title = style_struct.find("StyleStructTitle")
    if title is not None:
        title_text = normalize_text(extract_text(title))
        markdown_text += f"**{title_text}**\n\n"
    
    for para in style_struct.findall("Paragraph"):
        sent = para.find(".//Sentence")
        if sent is not None:
            text = normalize_text(extract_text(sent))
            markdown_text += f"{text}\n\n"
    
    return markdown_text

def process_note_struct(note_struct):
    """記項目（NoteStruct）を処理"""
    markdown_text = ""
    
    for para in note_struct.findall("Paragraph"):
        sent = para.find(".//Sentence")
        if sent is not None:
            text = normalize_text(extract_text(sent))
            markdown_text += f"{text}\n\n"
    
    return markdown_text

def process_format_struct(format_struct):
    """書式項目（FormatStruct）を処理"""
    markdown_text = ""
    
    title = format_struct.find("FormatStructTitle")
    if title is not None:
        title_text = normalize_text(extract_text(title))
        markdown_text += f"**{title_text}**\n\n"
    
    for para in format_struct.findall("Paragraph"):
        sent = para.find(".//Sentence")
        if sent is not None:
            text = normalize_text(extract_text(sent))
            markdown_text += f"{text}\n\n"
    
    return markdown_text

def process_class(class_elem):
    """類（Class）要素を処理"""
    markdown_text = ""
    
    class_title = class_elem.find("ClassTitle")
    if class_title is not None:
        title_text = normalize_text(extract_text(class_title))
        markdown_text += f"### {title_text}\n\n"
    
    # Paragraph を処理
    for para in class_elem.findall("Paragraph"):
        sent = para.find(".//Sentence")
        if sent is not None:
            text = normalize_text(extract_text(sent))
            markdown_text += f"{text}\n\n"
    
    return markdown_text

def parse_to_markdown(xml_content, law_name):
    """XML をMarkdownに変換する"""
    print("Markdownに変換中...")
    root = ET.fromstring(xml_content)
    markdown_text = f"# {law_name}\n\n"
    
    # メタデータ（法令番号、公布日など）を追加
    markdown_text += extract_law_metadata(root)
    
    # 目次を追加
    markdown_text += extract_toc(root)
    
    # 前文を追加
    markdown_text += extract_preamble(root)
    
    # 制定文を追加
    markdown_text += extract_enact_statement(root)
    
    # 本則を処理
    main_provision = root.find(".//MainProvision")
    if main_provision is not None:
        # 編を処理（見出しレベル自動決定）
        for part in main_provision.findall("Part"):
            markdown_text += process_structure_element(part)
        
        # 章を処理（見出しレベル自動決定）
        for chapter in main_provision.findall("Chapter"):
            markdown_text += process_structure_element(chapter)
        
        # 節を処理（見出しレベル自動決定）
        for section in main_provision.findall("Section"):
            markdown_text += process_structure_element(section)
        
        # 条を処理（最上位の条は H4）
        for article in main_provision.findall("Article"):
            markdown_text += process_article(article, 4)
    
    # 附則を追加
    markdown_text += extract_suppl_provision(root)
    
    # 改正規定を追加
    markdown_text += process_amend_provision(root)
    
    # 別系要素を処理（LawBody直下）
    law_body = root.find(".//LawBody")
    if law_body is not None:
        # 別表を処理
        for appdx_table in law_body.findall("AppdxTable"):
            markdown_text += "# 別表\n\n"
            markdown_text += process_appdx_table(appdx_table)
        
        # 別記を処理
        for appdx_note in law_body.findall("AppdxNote"):
            markdown_text += "# 別記\n\n"
            markdown_text += process_appdx_note(appdx_note)
        
        # 様式を処理
        for appdx_style in law_body.findall("AppdxStyle"):
            markdown_text += "# 様式\n\n"
            markdown_text += process_appdx_style(appdx_style)
        
        # 書式を処理
        for appdx_format in law_body.findall("AppdxFormat"):
            markdown_text += "# 書式\n\n"
            markdown_text += process_appdx_format(appdx_format)
        
        # 別図を処理
        for appdx_fig in law_body.findall("AppdxFig"):
            markdown_text += "# 別図\n\n"
            markdown_text += process_appdx_fig(appdx_fig)
        
        # 別を処理
        for appdx in law_body.findall("Appdx"):
            markdown_text += "# 別\n\n"
            markdown_text += process_appdx(appdx)
    
    return markdown_text

def save_markdown_file(law_name, md_output):
    """ファイルを保存し、既存ファイルがあれば上書き確認"""
    # 出力ディレクトリを指定
    output_dir = "output_Markdown"
    
    # 出力ディレクトリが存在しない場合は作成
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"出力ディレクトリを作成しました: {output_dir}")
    
    # ファイルパスを出力ディレクトリ内に設定
    filename = os.path.join(output_dir, f"{law_name}.md")
    
    # ファイルが既に存在する場合は確認
    if os.path.exists(filename):
        print(f"\n警告: ファイル '{filename}' は既に存在します。")
        while True:
            choice = input("上書きしますか？ (y/n): ").strip().lower()
            if choice == 'y':
                break
            elif choice == 'n':
                print("保存をキャンセルしました。")
                return False
            else:
                print("'y' または 'n' を入力してください。")
    
    # ファイルを保存
    with open(filename, "w", encoding="utf-8") as f:
        f.write(md_output)
    print(f"完了! ファイルを保存しました: {filename}")
    return True

# 実行
while True:
    print("\n" + "="*50)
    print("処理方法を選択してください:")
    print("  1: 法令名を入力して検索（APIを使用）")
    print("  2: XMLファイルのパスを指定（ローカルファイル）")
    print("  9: 終了")
    print("="*50)
    
    mode = input("選択してください (1/2/9): ").strip().lower()
    
    # 終了条件
    if mode == '9':
        print("プログラムを終了します。")
        break
    
    if mode == '1':
        # API経由で法令を取得
        law_name = input("法令名を入力してください: ").strip()
        
        # 入力バリデーション
        if not law_name:
            print("エラー: 法令名が入力されていません。もう一度入力してください。")
            continue
        
        # 法令データ取得と変換
        xml_data = fetch_law_data(law_name)
        if xml_data:
            md_output = parse_to_markdown(xml_data, law_name)
            save_markdown_file(law_name, md_output)
        else:
            print(f"法令 '{law_name}' の取得に失敗しました。")
    
    elif mode == '2':
        # ローカルXMLファイルを指定
        file_path = input("XMLファイルのパスを入力してください: ").strip()
        
        # 入力バリデーション
        if not file_path:
            print("エラー: ファイルパスが入力されていません。")
            continue
        
        # XMLファイルを読み込み
        xml_data = load_xml_from_file(file_path)
        if xml_data:
            # ファイル名から法令名を抽出（拡張子なし）
            law_name = os.path.splitext(os.path.basename(file_path))[0]
            md_output = parse_to_markdown(xml_data, law_name)
            save_markdown_file(law_name, md_output)
        else:
            print(f"ファイル '{file_path}' の処理に失敗しました。")
    
    else:
        print("エラー: 1、2、または 9 を入力してください。")