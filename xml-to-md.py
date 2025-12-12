import requests
import xml.etree.ElementTree as ET
import os
import sys
import argparse
import glob
import hashlib

# ==========================================
# ユーティリティ関数
# ==========================================

def fetch_law_data(law_name):
    """e-Gov APIから法令XMLを取得"""
    print(f"[{law_name}] を検索中...")
    try:
        # 1. 法令リストからLawIdを検索
        list_url = "https://laws.e-gov.go.jp/api/1/lawlists/1"
        response = requests.get(list_url, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        law_id = None
        for law in root.findall(".//LawNameListInfo"):
            if law.find("LawName").text == law_name:
                law_id = law.find("LawId").text
                break
                
        if not law_id:
            print(f"Error: '{law_name}' が見つかりませんでした。")
            return None

        # 2. 条文データを取得
        print(f"条文データをダウンロード中... (https://laws.e-gov.go.jp/api/1/lawdata/{law_id})")
        detail_url = f"https://laws.e-gov.go.jp/api/1/lawdata/{law_id}"
        law_response = requests.get(detail_url, timeout=30)
        law_response.raise_for_status()
        return law_response.content
        
    except requests.exceptions.RequestException as e:
        print(f"通信エラーが発生しました: {e}")
        return None
    except ET.ParseError:
        print("XMLの解析に失敗しました。")
        return None

def load_xml_from_file(file_path):
    """XMLファイルを読み込む"""
    if not os.path.exists(file_path):
        print(f"エラー: ファイル '{file_path}' が見つかりません。")
        return None
    
    try:
        print(f"XMLファイルを読み込み中... ({os.path.basename(file_path)})")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        return xml_data
    except Exception as e:
        print(f"エラー: ファイルの読み込みに失敗しました。({e})")
        return None

def extract_law_title_from_root(root):
    """XMLのルート要素から法令名(LawTitle)を抽出する"""
    try:
        # LawTitleを探す（階層が変わる可能性があるため .// を使用）
        title_elem = root.find(".//LawTitle")
        if title_elem is not None:
            return normalize_text(extract_text(title_elem))
        
        # 見つからない場合はSubject属性などを探すが、基本はLawTitle
        law_body = root.find(".//LawBody")
        if law_body is not None:
            subject = law_body.get("Subject")
            if subject:
                return subject
                
        return "名称不明法令"
    except Exception:
        return "名称不明法令"

def save_markdown_file(law_name, md_output, force_overwrite=False, abbrev=None):
    """ファイルを保存し、既存ファイルがあれば上書き確認
    force_overwrite=True の場合は確認せずに上書きする
    """
    # ファイル名に使用できない文字を置換
    safe_law_name = "".join(c for c in law_name if c not in '<>:"/\\|?*')
    
    # 出力ディレクトリを指定
    output_dir = "output_Markdown"
    
    # 出力ディレクトリが存在しない場合は作成
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # ファイルパスを出力ディレクトリ内に設定
    filename = os.path.join(output_dir, f"{safe_law_name}.md")
    
    # 上書き確認 (強制上書きモードでない場合のみ)
    if os.path.exists(filename) and not force_overwrite:
        print(f"\n警告: ファイル '{filename}' は既に存在します。")
        while True:
            choice_raw = input("上書きしますか？ (y/n): ").strip()
            choice = normalize_yes_no(choice_raw)
            if choice == 'y':
                break
            elif choice == 'n':
                print("保存をキャンセルしました。")
                return False
            else:
                print("'y' または 'n' を入力してください。")
    
    # ファイルを保存
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(md_output)
        print(f"[保存完了] {filename}")
        return True
    except Exception as e:
        # 上書き確認でキャンセルされた場合はここには来ない
        print(f"ファイルの保存中にエラーが発生しました: {e}")

        # 1) 略称が与えられていれば試す
        if abbrev:
            safe_abbrev = "".join(c for c in abbrev if c not in '<>:"/\\|?*')
            if safe_abbrev:
                try_name = os.path.join(output_dir, f"{safe_abbrev}.md")
                try:
                    with open(try_name, "w", encoding="utf-8") as f:
                        f.write(md_output)
                    print(f"[保存完了 - 略称使用] {try_name}")
                    return True
                except Exception as e2:
                    print(f"略称での保存に失敗しました: {e2}")

        # 2) それでも失敗したら法令名を切り詰めてハッシュを付与して試す
        try:
            hash_suffix = hashlib.sha1(law_name.encode("utf-8")).hexdigest()[:8]
        except Exception:
            hash_suffix = "unkn"

        # ベース名の最大長（安全側に短めに設定）
        max_base_len = 120
        base = safe_law_name
        if len(base) > max_base_len:
            base = base[:max_base_len]

        truncated_name = f"{base}_{hash_suffix}"
        try_name2 = os.path.join(output_dir, f"{truncated_name}.md")
        try:
            with open(try_name2, "w", encoding="utf-8") as f:
                f.write(md_output)
            print(f"[保存完了 - 切詰め] {try_name2}")
            return True
        except Exception as e3:
            print(f"切詰め名での保存にも失敗しました: {e3}")
            return False

# ==========================================
# テキスト処理・整形関数
# ==========================================

def normalize_text(text: str) -> str:
    """空白・改行を除去して1行にする"""
    if not text:
        return ""
    return " ".join(text.split())

def normalize_numeric_input(s: str) -> str:
    """全角数字を半角に変換"""
    if not s:
        return s
    trans = str.maketrans('０１２３４５６７８９', '0123456789')
    return s.translate(trans)

def normalize_yes_no(s: str) -> str:
    """y/nの正規化"""
    if not s:
        return s
    trans = str.maketrans('ｙｎＹＮ', 'ynyn')
    return s.translate(trans).strip().lower()

def extract_text(element):
    """要素内のテキストを再帰的に抽出（Ruby等の処理含む）"""
    if element is None:
        return ""
    
    text = element.text or ""
    
    for child in element:
        # ルビ
        if child.tag == "Ruby":
            ruby_text = child.text or ""
            rt = child.find("Rt")
            if rt is not None and rt.text:
                text += f"{{{ruby_text}|{rt.text}}}"
            else:
                text += ruby_text
        # 上付き・下付き・傍線
        elif child.tag in ["Sup", "Sub", "Line", "Column"]:
            text += extract_text(child)
        # 図・構造要素は無視
        elif child.tag in ["FigStruct", "Fig", "StyleStruct", "NoteStruct", "FormatStruct", "Class"]:
            pass
        else:
            text += extract_text(child)
        
        if child.tail:
            text += child.tail

    return normalize_text(text)

def convert_article_num(num_str):
    if not num_str: return ""
    parts = num_str.split("_")
    result = "第" + parts[0] + "条"
    for part in parts[1:]:
        result += "の" + part
    return result

def get_paragraph_label(p_num_attr, total_paragraphs):
    # 項が1つだけの場合は番号を表示しないことが多い
    if total_paragraphs == 1: return ""
    if not p_num_attr: return ""
    return f"第{p_num_attr}項"

def convert_item_num(num_str):
    if not num_str: return ""
    parts = num_str.split("_")
    result = "第" + parts[0]
    for part in parts[1:]:
        result += "の" + part
    return result + "号"

# ==========================================
# Markdown変換ロジック (主要部分)
# ==========================================

def parse_to_markdown(xml_content, law_name_override=None):
    """XMLバイナリデータをMarkdown文字列に変換"""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"XMLパースエラー: {e}")
        return ""

    if law_name_override:
        law_name = law_name_override
    else:
        law_name = extract_law_title_from_root(root)

    print(f"変換開始: {law_name}")

    # 可能であれば略称を抽出（保存失敗時に使用する）
    abbrev = ""
    try:
        title_elem = root.find('.//LawTitle')
        if title_elem is not None:
            raw_abbrev = title_elem.get('Abbrev', '')
            if raw_abbrev:
                # カンマ区切りの最初の略称を一次候補とする
                abbrev = raw_abbrev.split(',')[0].strip()
    except Exception:
        abbrev = ""

    markdown_text = f"# {law_name}\n\n"
    markdown_text += extract_law_metadata(root)
    markdown_text += extract_toc(root)
    markdown_text += extract_preamble(root)
    markdown_text += extract_enact_statement(root)
    
    main_provision = root.find(".//MainProvision")
    if main_provision is not None:
        for part in main_provision.findall("Part"):
            markdown_text += process_structure_element(part)
        for chapter in main_provision.findall("Chapter"):
            markdown_text += process_structure_element(chapter)
        for section in main_provision.findall("Section"):
            markdown_text += process_structure_element(section)
        for article in main_provision.findall("Article"):
            markdown_text += process_article(article, 4)
            
        # 【修正】MainProvision直下のParagraph（条がない法令）に対応
        direct_paragraphs = main_provision.findall("Paragraph")
        if direct_paragraphs:
            total_p = len(direct_paragraphs)
            for para in direct_paragraphs:
                markdown_text += process_single_paragraph(para, total_p)
    
    markdown_text += extract_suppl_provision(root)
    markdown_text += process_amend_provision(root)
    
    law_body = root.find(".//LawBody")
    if law_body is not None:
        markdown_text += process_all_appdx(law_body)
    
    return markdown_text, law_name, abbrev

def process_single_paragraph(para, total_p):
    """MainProvision直下のParagraphを処理するヘルパー関数"""
    md = ""
    p_num = para.get("Num", "")
    p_label = get_paragraph_label(p_num, total_p)
    
    # Sentence処理
    sent_text = ""
    para_sent = para.find("ParagraphSentence")
    target_sent = para_sent.find(".//Sentence") if para_sent is not None else para.find(".//Sentence")
    if target_sent is not None:
        sent_text = normalize_text(extract_text(target_sent))
    
    if p_label:
        md += f"**{p_label}** {sent_text}\n\n"
    else:
        md += f"{sent_text}\n\n"
    
    # Paragraph直下の要素（TableStructなど）
    md += process_child_elements(para, 0)
    
    # Item処理
    for item in para.findall("Item"):
        md += process_item(item, 1)
        
    return md

def process_all_appdx(parent_element):
    """別表、別記、様式などをまとめて処理"""
    md = ""
    for appdx_table in parent_element.findall("AppdxTable"):
        md += "# 別表\n\n" + process_appdx_table(appdx_table)
    for appdx_note in parent_element.findall("AppdxNote"):
        md += "# 別記\n\n" + process_appdx_note(appdx_note)
    for appdx_style in parent_element.findall("AppdxStyle"):
        md += "# 様式\n\n" + process_appdx_style(appdx_style)
    for appdx_format in parent_element.findall("AppdxFormat"):
        md += "# 書式\n\n" + process_appdx_format(appdx_format)
    for appdx_fig in parent_element.findall("AppdxFig"):
        md += "# 別図\n\n" + process_appdx_fig(appdx_fig)
    for appdx in parent_element.findall("Appdx"):
        md += "# 別\n\n" + process_appdx(appdx)
    return md

# --- 以下、詳細な要素処理関数群 ---

def process_arith_formula(arith_formula):
    if arith_formula is None: return ""
    formula_text = normalize_text(extract_text(arith_formula))
    if not formula_text: return ""
    if "\n" in formula_text or len(formula_text) > 100:
        return f"```\n{formula_text}\n```\n\n"
    else:
        return f"`{formula_text}`\n\n"

def extract_preamble(xml_root):
    preamble = xml_root.find(".//Preamble")
    if preamble is None: return ""
    md = "## 前文\n\n"
    for para in preamble.findall("Paragraph"):
        sent = para.find(".//Sentence")
        if sent is not None:
            md += f"{normalize_text(extract_text(sent))}\n\n"
    return md + "\n"

def extract_enact_statement(xml_root):
    enact = xml_root.find(".//EnactStatement")
    if enact is None: return ""
    md = "## 制定文\n\n"
    for para in enact.findall("Paragraph"):
        sent = para.find(".//Sentence")
        if sent is not None:
            md += f"{normalize_text(extract_text(sent))}\n\n"
    for sent in enact.findall("./Sentence"):
        md += f"{normalize_text(extract_text(sent))}\n\n"
    return md + "\n"

def process_amend_provision(xml_root):
    amend_provs = xml_root.findall(".//AmendProvision")
    if not amend_provs: return ""
    md = "# 改正規定\n\n"
    for amend_prov in amend_provs:
        name = amend_prov.find("AmendLawName")
        if name is not None:
            md += f"## {normalize_text(extract_text(name))}\n\n"
        for article in amend_prov.findall("Article"):
            md += process_article(article, 3)
    return md

def extract_toc(xml_root):
    toc = xml_root.find(".//TOC")
    if toc is None: return ""
    md = "## 目次\n\n"
    for child in toc:
        md += process_toc_element(child, 0)
    return md + "\n"

def process_toc_element(element, indent):
    md = ""
    spaces = "  " * indent
    tag = element.tag
    text = normalize_text(extract_text(element))
    
    # タイトル要素を持つコンテナの場合、タイトルを抽出
    title_tags = ["PartTitle", "ChapterTitle", "SectionTitle", "SubsectionTitle", "DivisionTitle", "ArticleTitle", "SupplProvisionLabel"]
    title_text = ""
    for t_tag in title_tags:
        t_elem = element.find(t_tag)
        if t_elem is not None:
            title_text = normalize_text(extract_text(t_elem))
            break
            
    if tag == "TOCLabel" or tag == "TOCPreambleLabel" or tag == "TOCAppdxTableLabel":
        md += f"{spaces}- {text}\n"
    elif tag == "TOCArticle":
        num = element.get("Num", "")
        label = convert_article_num(num)
        article_title = element.find("ArticleTitle")
        a_text = normalize_text(extract_text(article_title)) if article_title is not None else ""
        md += f"{spaces}- {label} {a_text}\n"
    elif tag == "ArticleRange":
        if text: md += f"{spaces}  （{text}）\n"
    elif title_text:
        md += f"{spaces}- {title_text}\n"
        # 子要素を再帰処理
        for child in element:
            if child.tag.startswith("TOC") and child.tag != tag:
                 md += process_toc_element(child, indent + 1)
    
    return md

def extract_suppl_provision(xml_root):
    suppl = xml_root.find(".//SupplProvision")
    if suppl is None: return ""
    md = "# 附則\n\n"
    label = suppl.find("SupplProvisionLabel")
    if label is not None:
        md += f"## {normalize_text(extract_text(label))}\n\n"
    
    for chapter in suppl.findall("Chapter"):
        md += process_structure_element(chapter)
    for article in suppl.findall("Article"):
        md += process_article(article, 3)
    
    # 附則のみで条がない場合（項のみの場合）の対応
    if not suppl.findall("Article") and not suppl.findall("Chapter"):
         for para in suppl.findall("Paragraph"):
            sent = para.find(".//Sentence")
            if sent is not None:
                md += f"- {normalize_text(extract_text(sent))}\n"
    
    # 附則別表など
    md += process_all_appdx(suppl)

    return md

def get_hierarchy_level(tag):
    return {"Part": 2, "Chapter": 3, "Section": 4, "Subsection": 5, "Division": 6}.get(tag, 2)

def process_structure_element(element, heading_level=None):
    if heading_level is None:
        heading_level = get_hierarchy_level(element.tag)
    
    md = ""
    title_map = {
        "Part": "PartTitle", "Chapter": "ChapterTitle", "Section": "SectionTitle",
        "Subsection": "SubsectionTitle", "Division": "DivisionTitle"
    }
    title_tag = title_map.get(element.tag)
    if title_tag:
        t_elem = element.find(title_tag)
        if t_elem is not None:
            md += f"{'#' * heading_level} {normalize_text(extract_text(t_elem))}\n\n"
    
    hierarchy = ["Part", "Chapter", "Section", "Subsection", "Division"]
    if element.tag in hierarchy:
        idx = hierarchy.index(element.tag)
        if idx < len(hierarchy) - 1:
            next_tag = hierarchy[idx + 1]
            for child in element.findall(next_tag):
                md += process_structure_element(child)
    
    for article in element.findall("Article"):
        md += process_article(article, min(heading_level + 1, 6))
    
    return md

def process_article(article, heading_level):
    md = ""
    num = article.get("Num", "")
    label = convert_article_num(num)
    caption = article.find("ArticleCaption")
    cap_text = normalize_text(extract_text(caption)) if caption is not None else ""
    
    md += f"{'#' * heading_level} {label}{cap_text}\n"
    
    paragraphs = article.findall("Paragraph")
    total_p = len(paragraphs)
    
    if total_p > 0:
        for para in paragraphs:
            # 記事内のパラグラフ処理は既存ロジックを維持しつつ、ヘルパー関数を使う手もあるが
            # インデントやリスト形式が違う場合があるため、既存コードを維持します。
            p_num = para.get("Num", "")
            p_label = get_paragraph_label(p_num, total_p)
            
            # Sentence処理
            sent_text = ""
            para_sent = para.find("ParagraphSentence")
            target_sent = para_sent.find(".//Sentence") if para_sent is not None else para.find(".//Sentence")
            if target_sent is not None:
                sent_text = normalize_text(extract_text(target_sent))
            
            if total_p == 1:
                md += f"{sent_text}\n"
            elif p_label:
                md += f"- **{p_label}** {sent_text}\n"
            else:
                md += f"- {sent_text}\n"
            
            # Paragraph直下の要素
            md += process_child_elements(para, 0)
            
            # Item処理
            for item in para.findall("Item"):
                md += process_item(item, 1)
    else:
        # Paragraphが無い場合（Article直下）
        md += process_child_elements(article, 0)
        # Sentence
        sent = article.find("./Sentence")
        if sent is not None:
            md += f"{normalize_text(extract_text(sent))}\n"
        # Item
        for item in article.findall("Item"):
            md += process_item(item, 1)

    # 共通末尾（SupplNote, ArithFormula）
    for note in article.findall("SupplNote"):
        md += f"\n*（{normalize_text(extract_text(note))}）*\n"
    for arith in article.findall("ArithFormula"):
        md += "\n" + process_arith_formula(arith)
    
    md += "\n"
    return md

def process_child_elements(parent, indent):
    md = ""
    for list_elem in parent.findall("List"): md += process_list(list_elem, indent)
    for ts in parent.findall("TableStruct"): md += "\n" + render_table_struct(ts, indent)
    for t in parent.findall("Table"): md += "\n" + render_table(t, indent)
    for fs in parent.findall("FigStruct"): md += "\n" + process_fig_struct(fs)
    for f in parent.findall("Fig"): md += "\n" + process_fig(f)
    for ss in parent.findall("StyleStruct"): md += "\n" + process_style_struct(ss)
    for ns in parent.findall("NoteStruct"): md += "\n" + process_note_struct(ns)
    for fs in parent.findall("FormatStruct"): md += "\n" + process_format_struct(fs)
    for cls in parent.findall("Class"): md += "\n" + process_class(cls)
    return md

def process_item(item, indent_level):
    md = ""
    num = item.get("Num", "")
    label = convert_item_num(num)
    title_elem = item.find("ItemTitle")
    title = normalize_text(extract_text(title_elem)) if title_elem is not None else ""
    
    item_sent = item.find("ItemSentence")
    indent = "  " * indent_level
    
    if item_sent is not None:
        md += render_item_sentence(item_sent, indent_level, label, title)
    else:
        sent = item.find(".//Sentence")
        if sent is not None:
            md += f"{indent}- **{label}** {normalize_text(extract_text(sent))}\n"
            
    md += process_child_elements(item, indent_level)
    
    # Subitems
    for i in range(1, 11):
        tag = f"Subitem{i}"
        sent_tag = f"Subitem{i}Sentence"
        for sub in item.findall(tag):
            md += process_subitem(sub, indent_level + i, tag, sent_tag)
            
    return md

def process_subitem(subitem, indent_level, tag_name, sent_tag_name):
    md = ""
    title = subitem.find(f"{tag_name}Title")
    label = normalize_text(extract_text(title)) if title is not None else ""
    sent = subitem.find(sent_tag_name)
    if sent is None: sent = subitem.find(".//Sentence")
    
    indent = "  " * indent_level
    s_text = normalize_text(extract_text(sent)) if sent is not None else ""
    md += f"{indent}- **{label}** {s_text}\n"
    return md

def render_item_sentence(item_sent, indent_level, label, title):
    md = ""
    indent = "  " * indent_level
    cols = item_sent.findall("Column")
    
    if cols:
        term = normalize_text(extract_text(cols[0]))
        defs = [normalize_text(extract_text(c)) for c in cols[1:]]
        definition = " ".join(filter(None, defs))
        if not term: term = title
        
        display = f"**{label}**"
        if term and definition: display += f" {term}: {definition}"
        elif term: display += f" {term}"
        else: display += f" {definition}"
        md += f"{indent}- {display}\n"
    else:
        sent = item_sent.find(".//Sentence") 
        if sent is None: sent = item_sent 
        text = normalize_text(extract_text(sent))
        md += f"{indent}- **{label}** {text}\n"
        
    for t in item_sent.findall("Table"):
        md += "\n" + render_table(t, indent_level)
    return md

def process_list(list_elem, indent_level):
    md = ""
    indent = "  " * indent_level
    ls = list_elem.find("ListSentence")
    if ls:
        sent = ls.find(".//Sentence")
        if sent is not None:
            md += f"{indent}{normalize_text(extract_text(sent))}\n"
            
    # Sublist 1-3
    for i in range(1, 4):
        tag = f"Sublist{i}"
        for sub in list_elem.findall(tag):
            sent_tag = f"Sublist{i}Sentence"
            s_elem = sub.find(sent_tag)
            if s_elem is None: s_elem = sub.find(".//Sentence")
            if s_elem is not None:
                md += f"{indent}  - {normalize_text(extract_text(s_elem))}\n"
    return md

# --- Table, Fig, Structs (簡易実装) ---

def render_table_struct(ts, indent):
    md = ""
    title = ts.find("TableStructTitle")
    if title is not None: md += f"{'  '*indent}{normalize_text(extract_text(title))}\n"
    tbl = ts.find("Table")
    if tbl is not None: md += render_table(tbl, indent)
    return md

def render_table(table, indent):
    # Table processing logic
    indent_str = "  " * indent
    md_lines = []
    
    header = table.find("TableHeaderRow")
    rows = table.findall("TableRow")
    
    # カラム抽出ヘルパー
    def get_cols(row):
        return [normalize_text(extract_text(c)) for c in row.findall("TableColumn") or row.findall("TableHeaderColumn")]

    h_cols = get_cols(header) if header is not None else []
    
    # 最大カラム数計算
    max_cols = len(h_cols)
    grid = []
    for r in rows:
        c = get_cols(r)
        max_cols = max(max_cols, len(c))
        grid.append(c)
        
    if not h_cols and grid: h_cols = grid.pop(0) # ヘッダーなしの場合
    
    # パディング
    h_cols += [""] * (max_cols - len(h_cols))
    
    md_lines.append(indent_str + "| " + " | ".join(h_cols) + " |")
    md_lines.append(indent_str + "| " + " | ".join(["---"]*max_cols) + " |")
    
    for row in grid:
        row += [""] * (max_cols - len(row))
        md_lines.append(indent_str + "| " + " | ".join(row) + " |")
        
    return "\n".join(md_lines) + "\n\n"

def process_fig_struct(fs):
    title = fs.find("FigStructTitle")
    t_text = normalize_text(extract_text(title)) if title is not None else ""
    md = f"### {t_text}\n\n"
    fig = fs.find("Fig")
    if fig is not None: md += process_fig(fig)
    return md

def process_fig(fig):
    src = fig.get("src", "")
    alt = normalize_text(extract_text(fig))
    if src: return f"![{alt}]({src})\n\n"
    return f"*[図: {alt}]*\n\n"

def process_style_struct(ss): return _struct_common(ss, "StyleStructTitle", "**")
def process_note_struct(ns): return _struct_common(ns, "NoteStructTitle", "")
def process_format_struct(fs): return _struct_common(fs, "FormatStructTitle", "**")
def process_class(cls): return _struct_common(cls, "ClassTitle", "### ")

def _struct_common(elem, title_tag, mark):
    md = ""
    title = elem.find(title_tag)
    if title is not None:
        md += f"{mark}{normalize_text(extract_text(title))}{mark}\n\n"
    for para in elem.findall("Paragraph"):
        sent = para.find(".//Sentence")
        if sent is not None:
             md += f"{normalize_text(extract_text(sent))}\n\n"
    return md

def extract_law_metadata(root):
    md = ""
    law = root if root.tag == "Law" else root.find(".//Law")
    if law is not None:
        era = law.get("Era", "")
        year = law.get("Year", "")
        num = law.get("Num", "")
        ltype = law.get("LawType", "")
        
        era_map = {"Meiji":"明治", "Taisho":"大正", "Showa":"昭和", "Heisei":"平成", "Reiwa":"令和"}
        type_map = {"Act":"法律", "CabinetOrder":"政令", "MinisterialOrdinance":"省令", "Rule":"規則"}
        
        if era and year and num:
            md += f"**法令番号**: {era_map.get(era, era)}{year}年{type_map.get(ltype, ltype)}第{num}号\n\n"
        
        pm = law.get("PromulgateMonth", "")
        pd = law.get("PromulgateDay", "")
        if pm or pd:
            md += f"**公布日**: {pm}月{pd}日\n\n"
            
        # LawTitleの属性（読み仮名、略称、略称読み）をメタデータに追加
        title_elem = law.find('.//LawTitle')
        if title_elem is not None:
            kana = title_elem.get('Kana', '')
            abbrev = title_elem.get('Abbrev', '')
            abbrev_kana = title_elem.get('AbbrevKana', '')
            
            if kana:
                md += f"**読み仮名**: {kana}\n\n"
            
            # 略称と読みをカンマで分割してペアで表示
            if abbrev:
                abbrevs = abbrev.split(',')
                # 読みがない場合や数が合わない場合に備える
                kanas = abbrev_kana.split(',') if abbrev_kana else []
                
                md += "**略称**:\n"
                for i, abbr in enumerate(abbrevs):
                    # 対応する読みがあればカッコ書きで追加
                    reading = kanas[i] if i < len(kanas) else ""
                    if reading:
                        md += f"- {abbr} ({reading})\n"
                    else:
                        md += f"- {abbr}\n"
                md += "\n"
            elif abbrev_kana:
                # 略称がなく読みだけある場合（稀）
                md += f"**略称（読み）**: {abbrev_kana}\n\n"
            
    return md

def process_appdx_table(elem): return render_table(elem.find("Table"), 0) if elem.find("Table") is not None else ""
def process_appdx_note(elem): return _appdx_common(elem)
def process_appdx_style(elem): return _appdx_common(elem)
def process_appdx_format(elem): return _appdx_common(elem)
def process_appdx_fig(elem): return process_fig_struct(elem.find("FigStruct")) if elem.find("FigStruct") is not None else ""
def process_appdx(elem): return _appdx_common(elem)

def _appdx_common(elem):
    md = ""
    # タイトル
    for child in elem:
        if "Title" in child.tag:
            md += f"## {normalize_text(extract_text(child))}\n\n"
            break
    # 内容
    for p in elem.findall("Paragraph"):
        s = p.find(".//Sentence")
        if s is not None: md += f"{normalize_text(extract_text(s))}\n\n"
    for ts in elem.findall("TableStruct"): md += render_table_struct(ts, 0)
    for t in elem.findall("Table"): md += render_table(t, 0)
    for ss in elem.findall("StyleStruct"): md += process_style_struct(ss)
    for fs in elem.findall("FormatStruct"): md += process_format_struct(fs)
    return md

# ==========================================
# メイン処理ロジック (CLI / Interactive)
# ==========================================

def process_from_api(law_name, force=False):
    """APIから法令を取得して保存"""
    xml_data = fetch_law_data(law_name)
    if xml_data:
        md_output, real_law_name, abbrev = parse_to_markdown(xml_data, law_name)
        if md_output:
            save_markdown_file(real_law_name, md_output, force_overwrite=force, abbrev=abbrev)

def process_from_file(file_path, force=False):
    """ローカルファイルから変換して保存"""
    xml_data = load_xml_from_file(file_path)
    if xml_data:
        # ファイルから読み込むが、法令名はXML内から自動取得する
        md_output, real_law_name, abbrev = parse_to_markdown(xml_data)
        if md_output:
            save_markdown_file(real_law_name, md_output, force_overwrite=force, abbrev=abbrev)

def process_law_list_file(list_file_path="law_list.txt", force=True):
    """法令リストファイルを読み込んで一括処理"""
    if not os.path.exists(list_file_path):
        print(f"エラー: リストファイル '{list_file_path}' が見つかりません。")
        return

    print(f"\n--- リスト処理開始: {list_file_path} ---")
    try:
        # BOM付きUTF-8にも対応できる 'utf-8-sig' を使用
        with open(list_file_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
        
        count = 0
        for line in lines:
            law_name = line.strip()
            # 空行やコメント（;や#で始まる行）はスキップ
            if not law_name or law_name.startswith(";") or law_name.startswith("#"):
                continue
                
            print(f"\n[{count+1}] 処理中: {law_name}")
            process_from_api(law_name, force=force)
            count += 1
            
        print(f"\n--- 一括処理完了 ({count}件) ---")
        
    except Exception as e:
        print(f"リスト処理中にエラーが発生しました: {e}")


def main():
    # 1. コマンドライン引数の定義
    parser = argparse.ArgumentParser(description="Japanese Law XML to Markdown Converter")
    parser.add_argument("--law", help="法令名を指定してAPIから取得・変換します (確認なしで上書き)")
    parser.add_argument("--list", nargs="?", const="law_list.txt", help="法令リストファイルを指定して一括処理します (デフォルト: law_list.txt)")
    
    args = parser.parse_args()

    # 2. 引数によるバッチ処理モード
    if args.law:
        process_from_api(args.law, force=True)
        sys.exit(0)
    
    if args.list:
        process_law_list_file(args.list, force=True)
        sys.exit(0)

    # 3. 引数がない場合は対話モード
    while True:
        try:
            print("\n" + "="*50)
            print("処理方法を選択してください:")
            print("  1: 法令名を入力して検索（APIを使用）")
            print("  2: XMLファイルのパス、またはフォルダを指定（ローカル）")
            print("  3: 法令リスト(law_list.txt)から一括処理")
            print("  0: 終了")
            print("="*50)
            
            # 入力待機 (Ctrl+C対応)
            mode_raw = input("選択してください (1/2/3/0): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            break

        mode = normalize_numeric_input(mode_raw).lower()
        
        if mode == '0':
            print("プログラムを終了します。")
            break
        
        elif mode == '1':
            law_name = input("法令名を入力してください: ").strip()
            if law_name:
                process_from_api(law_name, force=False)
            else:
                print("エラー: 法令名が入力されていません。")
        
        elif mode == '2':
            path_input = input("XMLファイルのパス、またはフォルダパス: ").strip()
            # 引用符の除去（パスのコピー貼り付け対応）
            path_input = path_input.strip('"').strip("'")
            
            if not path_input:
                print("パスが入力されていません。")
                continue
                
            if os.path.isdir(path_input):
                # ディレクトリなら一括処理
                xml_files = glob.glob(os.path.join(path_input, "*.xml"))
                if not xml_files:
                    print(f"フォルダ内にXMLファイルが見つかりませんでした: {path_input}")
                    continue
                
                print(f"\n--- フォルダ一括処理開始: {len(xml_files)}件 ---")
                for xml_file in xml_files:
                    print(f"処理中: {os.path.basename(xml_file)}")
                    process_from_file(xml_file, force=True) # 一括なので強制上書き
                print("--- 完了 ---")
                
            elif os.path.isfile(path_input):
                # 単一ファイル
                process_from_file(path_input, force=False)
            else:
                print(f"エラー: パスが見つかりません: {path_input}")

        elif mode == '3':
            # law_list.txt (または指定ファイル) から一括処理
            default_list = "law_list.txt"
            user_list = input(f"リストファイル名を入力 (Enterで '{default_list}'): ").strip()
            target_list = user_list if user_list else default_list
            process_law_list_file(target_list, force=True)
            
        else:
            print("1, 2, 3, または 0 を入力してください。")

if __name__ == "__main__":
    main()