import requests
import xml.etree.ElementTree as ET
import os

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

def process_structure_element(element, heading_level):
    """章・節などの構造要素を処理（再帰的）
    heading_level: 見出しレベル（#の数）"""
    markdown_text = ""
    
    # タイトルを取得
    title_map = {
        "Part": "PartTitle",
        "Chapter": "ChapterTitle",
        "Section": "SectionTitle",
        "Subsection": "SubsectionTitle",
        "Division": "DivisionTitle"
    }
    
    element_tag = element.tag
    title_tag = title_map.get(element_tag)
    
    if title_tag:
        title_elem = element.find(title_tag)
        if title_elem is not None:
            title_text = normalize_text(extract_text(title_elem))
            heading = "#" * heading_level
            markdown_text += f"{heading} {title_text}\n\n"
    
    # 子要素を処理
    # 次の階層の構造要素を処理
    next_level = heading_level + 1
    hierarchy = ["Part", "Chapter", "Section", "Subsection", "Division"]
    current_index = hierarchy.index(element_tag) if element_tag in hierarchy else -1
    
    if current_index < len(hierarchy) - 1:
        next_elem_name = hierarchy[current_index + 1]
        for child in element.findall(next_elem_name):
            markdown_text += process_structure_element(child, next_level)
    
    # 条を処理
    for article in element.findall("Article"):
        markdown_text += process_article(article, next_level)
    
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

    markdown_text += f"{heading} {article_label}\n"
    if caption_text:
        markdown_text += f"{caption_text}\n"
    
    # 項を処理
    paragraphs = article.findall("Paragraph")
    total_paragraphs = len(paragraphs)
    
    for para in paragraphs:
        p_num_attr = para.get("Num", "")
        p_label = get_paragraph_label(p_num_attr, total_paragraphs)
        
        sent = para.find(".//Sentence")
        if sent is not None:
            sent_text = normalize_text(extract_text(sent))
            
            if p_label:
                markdown_text += f"- **{p_label}** {sent_text}\n"
            else:
                markdown_text += f"- {sent_text}\n"

        # 表を処理
        for table_struct in para.findall("TableStruct"):
            markdown_text += "\n"
            markdown_text += render_table_struct(table_struct, indent_level=0)
        for table in para.findall("Table"):
            markdown_text += "\n"
            markdown_text += render_table(table, indent_level=0)
        
        # 号を処理
        items = para.findall("Item")
        for item in items:
            markdown_text += process_item(item, 1)
    
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

    # 表を処理
    for table_struct in item.findall("TableStruct"):
        markdown_text += render_table_struct(table_struct, indent_level=indent_level)
    for table in item.findall("Table"):
        markdown_text += render_table(table, indent_level=indent_level)
    
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
    Columnが複数ある場合は「用語: 定義」の形で連結"""
    indent = "    " * indent_level
    columns = item_sent.findall("Column")

    if columns:
        term = normalize_text(extract_text(columns[0]))
        definition_parts = [normalize_text(extract_text(col)) for col in columns[1:]]
        definition = " ".join([p for p in definition_parts if p])
        if not term:
            term = item_title
        label = f"**{item_label}**"
        if term and definition:
            return f"{indent}- {label} {term}: {definition}\n"
        if term:
            return f"{indent}- {label} {term}\n"
        return f"{indent}- {label} {definition}\n"

    # Columnが無い場合は通常のテキストを返す
    sent_text = normalize_text(extract_text(item_sent))
    label = f"**{item_label}**"
    return f"{indent}- {label} {sent_text}\n"

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
    """Table要素をMarkdownテーブル文字列に変換
    
    縦結合セルの補完: データ行内で、空白セルがあれば、直上の行の同じ列のデータをコピー
    ヘッダー行: XMLのTableHeaderRowがあればそれを使用、なければTableRowの1行目をヘッダーとして処理
    """
    indent = "    " * indent_level

    header_row = table_elem.find("TableHeaderRow")
    header_cols = []
    if header_row is not None:
        header_cols = [normalize_text(extract_text(col)) for col in header_row.findall("TableHeaderColumn")]

    rows = []
    remark_sentences = []

    for row_elem in table_elem.findall("TableRow"):
        cols = row_elem.findall("TableColumn")

        # 備考行（colspanあり）はテーブル外に出す
        if cols and cols[0].get("colspan"):
            sentences = cols[0].findall(".//Sentence")
            remark_sentences.extend([normalize_text(extract_text(sent)) for sent in sentences])
            continue

        row_data = [normalize_text(extract_text(col)) for col in cols]
        if not row_data:
            continue

        rows.append(row_data)

    if not header_cols and not rows:
        return ""

    # TableHeaderRowがない場合、1行目をヘッダーにする
    if not header_cols and rows:
        header_cols = rows.pop(0)

    # 列数を決定
    col_count = max(len(header_cols), max(len(r) for r in rows) if rows else 0)
    
    # ヘッダーを正規化
    header_cols = header_cols + [""] * (col_count - len(header_cols))
    
    # データ行を正規化（列数を統一）
    normalized = [r + [""] * (col_count - len(r)) for r in rows]
    
    # 縦結合の補完: データ行内で、任意の列で空白セルがあれば、直上の行の同じ列のデータをコピー
    for row_idx in range(1, len(normalized)):
        for col_idx in range(col_count):
            if not normalized[row_idx][col_idx]:  # 空白セル
                normalized[row_idx][col_idx] = normalized[row_idx - 1][col_idx]

    md_lines = []
    
    # ヘッダー行を出力
    md_lines.append(indent + "| " + " | ".join(header_cols) + " |")
    # 区切り線を出力
    md_lines.append(indent + "| " + " | ".join(["---"] * col_count) + " |")
    
    # データ行を出力
    for row in normalized:
        md_lines.append(indent + "| " + " | ".join(row) + " |")

    md_output = "\n".join(md_lines) + "\n\n"

    if remark_sentences:
        md_output += f"{indent}**【】**\n"
        for sent in remark_sentences:
            if sent:
                md_output += f"{indent}- {sent}\n"
        md_output += "\n"

    return md_output

def parse_to_markdown(xml_content, law_name):
    """XML をMarkdownに変換する"""
    print("Markdownに変換中...")
    root = ET.fromstring(xml_content)
    markdown_text = f"# {law_name}\n\n"
    
    # 前文を追加
    markdown_text += extract_preamble(root)
    
    # 本則を処理
    main_provision = root.find(".//MainProvision")
    if main_provision is not None:
        # 編を処理
        for part in main_provision.findall("Part"):
            markdown_text += process_structure_element(part, 2)
        
        # 章を処理
        for chapter in main_provision.findall("Chapter"):
            markdown_text += process_structure_element(chapter, 2)
        
        # 節を処理
        for section in main_provision.findall("Section"):
            markdown_text += process_structure_element(section, 2)
        
        # 条を処理（最上位の条）
        for article in main_provision.findall("Article"):
            markdown_text += process_article(article, 2)
    
    # 附則を追加
    markdown_text += extract_suppl_provision(root)
    
    return markdown_text

def save_markdown_file(law_name, md_output):
    """ファイルを保存し、既存ファイルがあれば上書き確認"""
    filename = f"{law_name}.md"
    
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
    law_name = input("法令名を入力してください (終了する場合は 'q' を入力): ").strip()
    
    # 終了条件
    if law_name.lower() == 'q':
        print("プログラムを終了します。")
        break
    
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