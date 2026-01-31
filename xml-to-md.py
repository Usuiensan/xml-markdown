import requests
import xml.etree.ElementTree as ET
import os
import sys
import argparse
import glob
import hashlib
from datetime import datetime

# ==========================================
# テーブル処理設定（グローバル）
# ==========================================
# TABLE_PROCESSING_MODE: "hybrid" または "strict"
#   - "hybrid"  : Border属性からrowspanを自動推測（デフォルト）
#   - "strict"  : rowspan属性のみ使用、Border属性は無視
TABLE_PROCESSING_MODE = "hybrid"

# ログ出力設定（トラブル診断用）
TABLE_ROWSPAN_DEBUG = False

# ==========================================
# ユーティリティ関数
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
                text += f"<ruby>{ruby_text}<rt>{rt.text}</rt></ruby>"
            else:
                text += ruby_text
        # 傍線（スタイル属性考慮）
        elif child.tag == "Line":
            line_style = child.get("Style", "solid")
            line_text = extract_text(child)
            if line_style == "dotted":
                text += f"<u style='text-decoration-style: dotted'>{line_text}</u>"
            elif line_style == "double":
                text += f"<u style='text-decoration-style: double'>{line_text}</u>"
            elif line_style == "none":
                text += line_text
            else:  # solid
                text += f"<u>{line_text}</u>"
        # 上付き・下付き
        elif child.tag in ["Sup", "Sub", "Column"]:
            text += extract_text(child)
        # QuoteStruct（引用構造）を処理
        elif child.tag == "QuoteStruct":
            text += process_quote_struct(child)
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

def process_quote_struct(quote_elem):
    """引用構造を処理（Markdown引用ブロックとして表現）"""
    if quote_elem is None:
        return ""
    # QuoteStruct内の全テキストを抽出して引用ブロックとして整形
    # 複雑な構造の場合は再帰的に処理
    content = ""
    for child in quote_elem:
        if child.tag == "Sentence":
            # normalize_textを使わずに直接extract_textを呼ぶ（二重正規化を避ける）
            content += child.text or ""
            for subchild in child:
                content += (subchild.text or "") + (subchild.tail or "")
        else:
            content += (child.text or "") + (child.tail or "")
    return f"「{content.strip()}」"

def process_remarks(remarks_elem):
    """備考を処理"""
    if remarks_elem is None:
        return ""
    md = ""
    label = remarks_elem.find("RemarksLabel")
    if label is not None:
        label_text = normalize_text(extract_text(label))
        line_break = label.get("LineBreak", "false") == "true"
        if line_break:
            md += f" **{label_text} ** \n\n"
        else:
            md += f" **{label_text} ** \n"
    
    # 備考の項目
    for item in remarks_elem.findall("Item"):
        item_num = item.get("Num", "")
        item_label = convert_item_num(item_num) if item_num else ""
        item_sent = item.find("ItemSentence")
        if item_sent is not None:
            sent_text = normalize_text(extract_text(item_sent))
            md += f"- {item_label} {sent_text}\n"
    
    # 備考の文章
    for sentence in remarks_elem.findall("Sentence"):
        sent_text = normalize_text(extract_text(sentence))
        md += f"{sent_text}\n"
    
    return md

# --- LawBody/MainProvision から法令情報を抽出するヘルパー関数 ---

def extract_law_title_from_root(root):
    """XMLのルート要素から法令名(LawTitle)を抽出する"""
    try:
        title_elem = root.find(".//LawTitle")
        if title_elem is not None:
            return normalize_text(extract_text(title_elem))
        
        law_body = root.find(".//LawBody")
        if law_body is not None:
            subject = law_body.get("Subject")
            if subject:
                return subject
                
        return "名称不明法令"
    except Exception:
        return "名称不明法令"


def extract_law_id_from_root(root):
    """XMLルートから法令ID（可能であればLawId、次にLawNum）を抽出する"""
    try:
        target_root = root
        if root.tag == "law_data_response":
            full_text = root.find("law_full_text")
            if full_text is not None:
                inner_law = full_text.find("Law")
                if inner_law is not None:
                    target_root = inner_law

        lid = target_root.find('.//LawId')
        if lid is not None and (lid.text and lid.text.strip()):
            return lid.text.strip()

        lnum = target_root.find('.//LawNum')
        if lnum is not None and (lnum.text and lnum.text.strip()):
            return lnum.text.strip()

        law = target_root if target_root.tag == 'Law' else target_root.find('.//Law')
        if law is not None:
            era = law.get('Era', '')
            year = law.get('Year', '')
            num = law.get('Num', '')
            if era and year and num:
                return f"{era}{year}_{num}"

        return None
    except Exception:
        return None

# ==========================================
# XML要素処理関数 (Markdownレンダリング)
# ==========================================

# NOTE: これらの関数は、メインの parse_to_markdown や他の処理関数から呼び出されます。

def process_arith_formula(arith_formula):
    if arith_formula is None: return ""
    formula_text = normalize_text(extract_text(arith_formula))
    if not formula_text: return ""
    if "\n" in formula_text or len(formula_text) > 100:
        return f"```\n{formula_text}\n```\n\n"
    else:
        return f"`{formula_text}`\n\n"

def process_fig(fig):
    src = fig.get("src", "")
    alt = normalize_text(extract_text(fig))
    if src: return f"![{alt}]({src})\n\n"
    return f"*[図: {alt}]*\n\n"

def process_fig_struct(fs):
    title = fs.find("FigStructTitle")
    t_text = normalize_text(extract_text(title)) if title is not None else ""
    md = f"### {t_text}\n\n"
    
    # Remarksを処理
    for remarks in fs.findall("Remarks"):
        remarks_text = process_remarks(remarks)
        if remarks_text:
            md += f"{remarks_text}\n\n"
    
    fig = fs.find("Fig")
    if fig is not None: md += process_fig(fig)
    return md

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

def process_style_struct(ss): return _struct_common(ss, "StyleStructTitle", "**")
def process_note_struct(ns): return _struct_common(ns, "NoteStructTitle", "")
def process_format_struct(fs): return _struct_common(fs, "FormatStructTitle", "**")
def process_class(cls): return _struct_common(cls, "ClassTitle", "### ")

def calculate_rowspan_from_border(table, row_idx, col_idx, body_rows, cell):
    """
    Border属性からrowspanを自動推測（ハイブリッドモード用）
    
    ロジック:
    - 明示的なrowspan属性があれば使用
    - なければBorderBottom="none"で内容ありのセルをチェック
    - 次行から連続してBorderTop="none"で内容が空のセルが何個続くかカウント
    - rowspan = 1 + (連続空セル数)
    """
    rowspan = int(cell.get('rowspan', 1))
    
    if rowspan > 1:
        # 明示的指定あり → そのまま使用
        if TABLE_ROWSPAN_DEBUG:
            print(f"[calc_rowspan] Row {row_idx}, Col {col_idx}: rowspan={rowspan} (明示的指定)")
        return rowspan
    
    # rowspan属性なし or rowspan=1の場合、Border属性をチェック
    border_bottom = cell.get('BorderBottom', 'solid')
    cell_text = normalize_text(extract_text(cell))
    
    if border_bottom == 'none' and cell_text:
        # 次行以降をスキャン
        extended_rowspan = 1
        for next_row_idx in range(row_idx + 1, len(body_rows)):
            next_row = body_rows[next_row_idx]
            next_cols = next_row.findall('{*}TableColumn')
            
            if col_idx < len(next_cols):
                next_cell = next_cols[col_idx]
                next_border_top = next_cell.get('BorderTop', 'solid')
                next_text = normalize_text(extract_text(next_cell))
                
                # BorderTop="none"で内容が空 → 継続してカウント
                if next_border_top == 'none' and not next_text:
                    extended_rowspan += 1
                    if TABLE_ROWSPAN_DEBUG:
                        print(f"[calc_rowspan] Row {row_idx}, Col {col_idx}: 次行{next_row_idx}も占有続行")
                else:
                    # パターン終了
                    if TABLE_ROWSPAN_DEBUG:
                        print(f"[calc_rowspan] Row {row_idx}, Col {col_idx}: Row {next_row_idx}で終了")
                    break
            else:
                break
        
        if extended_rowspan > 1:
            if TABLE_ROWSPAN_DEBUG:
                print(f"[calc_rowspan] Row {row_idx}, Col {col_idx}: rowspan={extended_rowspan} (Border属性から推測)")
            return extended_rowspan
    
    if TABLE_ROWSPAN_DEBUG and border_bottom == 'none' and not cell_text:
        print(f"[calc_rowspan] Row {row_idx}, Col {col_idx}: rowspan=1 (空セル)")
    
    return rowspan

def render_table(table, indent):
    indent_str = "  " * indent
    html_lines = []
    
    # テーブルのWritingMode属性を取得（デフォルト: horizontal-tb）
    writing_mode = table.get("WritingMode", "horizontal-tb")
    
    # CSSクラスを決定
    table_class = 'writing-mode-vertical' if writing_mode == "vertical-rl" else 'writing-mode-horizontal'
    
    html_lines.append(f'{indent_str}<table class="{table_class}">')
    
    # ヘッダー行処理
    header = table.find("TableHeaderRow")
    body_rows = list(table.findall("TableRow"))
    
    # rowspan/colspan追跡用：(行インデックス, 列インデックス) -> (rowspan, colspan)
    # これにより、各セルが複数行・複数列を占有する場合を追跡
    rowspan_tracking = {}  
    
    # ヘッダーセルの処理
    if header is not None:
        html_lines.append(f"{indent_str}  <thead>")
        html_lines.append(f"{indent_str}    <tr>")
        for header_col in header.findall("TableHeaderColumn"):
            col_text = normalize_text(extract_text(header_col))
            attrs = get_cell_attributes(header_col, "th")
            html_lines.append(f'{indent_str}      <th{attrs}>{col_text}</th>')
        html_lines.append(f"{indent_str}    </tr>")
        html_lines.append(f"{indent_str}  </thead>")
    elif body_rows:
        # TableHeaderRowが存在しない場合、最初のTableRowをヘッダーとして使用
        html_lines.append(f"{indent_str}  <thead>")
        html_lines.append(f"{indent_str}    <tr>")
        for col in body_rows[0].findall("TableColumn"):
            col_text = normalize_text(extract_text(col))
            attrs = get_cell_attributes(col, "th")
            html_lines.append(f'{indent_str}      <th{attrs}>{col_text}</th>')
        html_lines.append(f"{indent_str}    </tr>")
        html_lines.append(f"{indent_str}  </thead>")
        body_rows = body_rows[1:]  # ヘッダーとして使用した行を除外
    
    # ボディ行処理
    if body_rows:
        html_lines.append(f"{indent_str}  <tbody>")
        
        for row_idx, row in enumerate(body_rows):
            html_lines.append(f"{indent_str}    <tr>")
            
            # 各行のセルを処理するため、XMLに記載されたセルのループ
            cols = row.findall("TableColumn")
            
            # この行の出力位置（XMLセルの位置と異なる可能性）
            output_col_idx = 0
            for xml_col_idx, col in enumerate(cols):
                # 出力位置をスキップして、占有されていない列までスキップ
                while (row_idx, output_col_idx) in rowspan_tracking:
                    output_col_idx += 1
                
                col_text = normalize_text(extract_text(col))
                colspan = int(col.get("colspan", 1))
                
                # ===== モード分岐：rowspan計算 =====
                if TABLE_PROCESSING_MODE == "hybrid":
                    rowspan = calculate_rowspan_from_border(table, row_idx, output_col_idx, body_rows, col)
                else:  # "strict"
                    rowspan = int(col.get("rowspan", 1))
                
                # セルを出力（計算されたrowspanを属性に反映）
                attrs = get_cell_attributes(col, "td", rowspan_override=rowspan)
                html_lines.append(f'{indent_str}      <td{attrs}>{col_text}</td>')
                
                # rowspan/colspanを追跡：このセルが占有する領域を記録
                for r in range(row_idx, row_idx + rowspan):
                    for c in range(output_col_idx, output_col_idx + colspan):
                        rowspan_tracking[(r, c)] = True
                
                # 次のセルの出力位置
                output_col_idx += colspan
            
            html_lines.append(f"{indent_str}    </tr>")
        
        html_lines.append(f"{indent_str}  </tbody>")
    
    html_lines.append(f"{indent_str}</table>")
    
    return "\n".join(html_lines) + "\n\n"

def get_cell_attributes(cell, cell_type="td", rowspan_override=None):
    """テーブルセルの属性をHTMLのstyle属性に変換
    
    枠線のBorder属性を CSS border-*-style に変換することで、
    論理的には連結されていないが見た目上つながっているセルの意図を保つ。
    
    Args:
        cell: XML要素
        cell_type: "td" または "th"
        rowspan_override: 計算されたrowspan値（指定時はXML属性を上書き）
    """
    attrs = []
    
    # rowspan、colspan
    # rowspan_overrideが指定されていれば、それを優先（ハイブリッドモード用）
    if rowspan_override is not None:
        rowspan = str(rowspan_override)
    else:
        rowspan = cell.get("rowspan")
    
    colspan = cell.get("colspan")
    
    if rowspan:
        attrs.append(f'rowspan="{rowspan}"')
    if colspan:
        attrs.append(f'colspan="{colspan}"')
    
    # テキスト配置（Align）
    align = cell.get("Align")
    valign = cell.get("Valign")
    
    style_parts = []
    
    # 枠線スタイル（Border属性をCSS border-*-styleに変換）
    border_map = {
        "BorderTop": "border-top-style",
        "BorderBottom": "border-bottom-style",
        "BorderLeft": "border-left-style",
        "BorderRight": "border-right-style"
    }
    
    for border_attr, css_prop in border_map.items():
        border_value = cell.get(border_attr)
        if border_value:
            # solid, none, dotted, double をそのままCSS値として使用
            style_parts.append(f"{css_prop}: {border_value}")
    
    # テキスト配置
    if align:
        if align == "left":
            style_parts.append("text-align: left")
        elif align == "center":
            style_parts.append("text-align: center")
        elif align == "right":
            style_parts.append("text-align: right")
        elif align == "justify":
            style_parts.append("text-align: justify")
    
    if valign:
        if valign == "top":
            style_parts.append("vertical-align: top")
        elif valign == "middle":
            style_parts.append("vertical-align: middle")
        elif valign == "bottom":
            style_parts.append("vertical-align: bottom")
    
    if style_parts:
        attrs.append(f'style="{"; ".join(style_parts)}"')
    
    if attrs:
        return " " + " ".join(attrs)
    return ""

def render_table_struct(ts, indent):
    html = ""
    indent_str = "  " * indent
    title = ts.find("TableStructTitle")
    if title is not None: 
        title_text = normalize_text(extract_text(title))
        html += f"{indent_str}<div class=\"table-struct\">\n"
        html += f"{indent_str}  <div class=\"table-struct-title\">{title_text}</div>\n"
    
    # Remarksを処理
    for remarks in ts.findall("Remarks"):
        remarks_text = process_remarks(remarks)
        if remarks_text:
            html += f"{indent_str}  {remarks_text}\n"
    
    tbl = ts.find("Table")
    if tbl is not None:
        html += render_table(tbl, indent + 1)
    if title is not None:
        html += f"{indent_str}</div>\n"
    return html

def process_list(list_elem, indent_level):
    md = ""
    indent = "  " * indent_level
    ls = list_elem.find("ListSentence")
    if ls:
        sent = ls.find(".//Sentence")
        if sent is not None:
            md += f"{indent}{normalize_text(extract_text(sent))}\n"
            
    for i in range(1, 4):
        tag = f"Sublist{i}"
        for sub in list_elem.findall(tag):
            sent_tag = f"Sublist{i}Sentence"
            s_elem = sub.find(sent_tag)
            if s_elem is None: s_elem = sub.find(".//Sentence")
            if s_elem is not None:
                md += f"{indent}  - {normalize_text(extract_text(s_elem))}\n"
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
        # ItemSentence内のSentence（複数対応：本文＋ただし書き）
        sentences = item_sent.findall("Sentence")
        if not sentences:
            sentences = item_sent.findall(".//Sentence")
            
        text = ""
        if sentences:
            text = "".join([normalize_text(extract_text(s)) for s in sentences])
        else:
            text = normalize_text(extract_text(item_sent))
            
        md += f"{indent}- **{label}** {text}\n"
        
    for t in item_sent.findall("Table"):
        md += "\n" + render_table(t, indent_level)
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
        # Item直下にSentenceがある場合のフォールバック（複数のSentenceに対応）
        sentences = item.findall(".//Sentence")
        if sentences:
            text = "".join([normalize_text(extract_text(s)) for s in sentences])
            md += f"{indent}- **{label}** {text}\n"
            
    md += process_child_elements(item, indent_level)
    
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
    
    indent = "  " * indent_level
    
    # SubitemSentenceの処理（複数Sentence対応）
    sub_sent = subitem.find(sent_tag_name)
    if sub_sent is not None:
        sentences = sub_sent.findall("Sentence")
        if not sentences: # Sentenceタグが無い場合
             sentences = sub_sent.findall(".//Sentence") # 子孫を探す
        
        s_text = ""
        if sentences:
            s_text = "".join([normalize_text(extract_text(s)) for s in sentences])
        else:
            s_text = normalize_text(extract_text(sub_sent))
    else:
        # Subitem直下のSentenceフォールバック
        sentences = subitem.findall(".//Sentence")
        s_text = "".join([normalize_text(extract_text(s)) for s in sentences])

    md += f"{indent}- **{label}** {s_text}\n"
    return md

# --- 附則別表など構造要素の処理関数 ---

def _appdx_common(elem):
    md = ""
    for child in elem:
        if "Title" in child.tag:
            md += f"## {normalize_text(extract_text(child))}\n\n"
            break
    
    # RelatedArticleNum（関係条文番号）を処理
    for rel_art in elem.findall("RelatedArticleNum"):
        rel_text = normalize_text(extract_text(rel_art))
        if rel_text:
            md += f"*{rel_text}*\n\n"
    
    for p in elem.findall("Paragraph"):
        s = p.find(".//Sentence")
        if s is not None: md += f"{normalize_text(extract_text(s))}\n\n"
    for ts in elem.findall("TableStruct"): md += render_table_struct(ts, 0)
    for t in elem.findall("Table"): md += render_table(t, 0)
    for ss in elem.findall("StyleStruct"): md += process_style_struct(ss)
    for fs in elem.findall("FormatStruct"): md += process_format_struct(fs)
    for ns in elem.findall("NoteStruct"): md += process_note_struct(ns)
    for fig_s in elem.findall("FigStruct"): md += process_fig_struct(fig_s)
    
    # Remarksを処理
    for remarks in elem.findall("Remarks"):
        remarks_text = process_remarks(remarks)
        if remarks_text:
            md += f"{remarks_text}\n\n"
    
    # Item（項目）を処理
    for item in elem.findall("Item"):
        md += process_item(item, 0)
    
    return md

def process_appdx_table(elem): 
    """別表を処理"""
    md = ""
    # AppdxTableTitleを処理
    title = elem.find("AppdxTableTitle")
    if title is not None:
        md += f"## {normalize_text(extract_text(title))}\n\n"
    
    # RelatedArticleNum（関係条文番号）を処理
    for rel_art in elem.findall("RelatedArticleNum"):
        rel_text = normalize_text(extract_text(rel_art))
        if rel_text:
            md += f"*{rel_text}*\n\n"
    
    # TableStructを処理
    for ts in elem.findall("TableStruct"): 
        md += render_table_struct(ts, 0)
    
    # 直接のTableを処理
    for t in elem.findall("Table"): 
        md += render_table(t, 0)
    
    # Remarksを処理
    for remarks in elem.findall("Remarks"):
        remarks_text = process_remarks(remarks)
        if remarks_text:
            md += f"{remarks_text}\n\n"
    
    # Item（項目）を処理
    for item in elem.findall("Item"):
        md += process_item(item, 0)
    
    return md
def process_appdx_note(elem): return _appdx_common(elem)
def process_appdx_style(elem): return _appdx_common(elem)
def process_appdx_format(elem): return _appdx_common(elem)
def process_appdx_fig(elem): return process_fig_struct(elem.find("FigStruct")) if elem.find("FigStruct") is not None else ""
def process_appdx(elem): return _appdx_common(elem)

# --- 構造要素処理関数 (Part, Chapter, Articleなど) ---

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

def process_single_paragraph(para, total_p):
    """MainProvision直下のParagraphを処理するヘルパー関数"""
    md = ""
    p_num = para.get("Num", "")
    p_label = get_paragraph_label(p_num, total_p)
    
    # Sentence処理 (本文 + ただし書きに対応)
    sent_text = ""
    para_sent = para.find("ParagraphSentence")
    
    if para_sent is not None:
        sentences = para_sent.findall("Sentence")
        if sentences:
            sent_text = "".join([normalize_text(extract_text(s)) for s in sentences])
        else:
            sent_text = normalize_text(extract_text(para_sent))
    else:
        sentences = para.findall("Sentence")
        if sentences:
            sent_text = "".join([normalize_text(extract_text(s)) for s in sentences])
    
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
            p_num = para.get("Num", "")
            p_label = get_paragraph_label(p_num, total_p)
            
            # Sentence処理 (本文 + ただし書きに対応)
            sent_text = ""
            para_sent = para.find("ParagraphSentence")
            
            if para_sent is not None:
                sentences = para_sent.findall("Sentence")
                if sentences:
                    sent_text = "".join([normalize_text(extract_text(s)) for s in sentences])
                else:
                    sent_text = normalize_text(extract_text(para_sent))
            else:
                sentences = para.findall("Sentence")
                if sentences:
                    sent_text = "".join([normalize_text(extract_text(s)) for s in sentences])

            if total_p == 1:
                md += f"{sent_text}\n"
            elif p_label:
                md += f"- **{p_label}** {sent_text}\n"
            else:
                md += f"- {sent_text}\n"
            
            md += process_child_elements(para, 0)
            
            for item in para.findall("Item"):
                md += process_item(item, 1)
    else:
        md += process_child_elements(article, 0)
        
        # Article直下のSentence (本文 + ただし書き)
        sent_text = ""
        sentences = article.findall("./Sentence")
        if sentences:
            sent_text = "".join([normalize_text(extract_text(s)) for s in sentences])
            md += f"{sent_text}\n"
            
        for item in article.findall("Item"):
            md += process_item(item, 1)

    for note in article.findall("SupplNote"):
        md += f"\n*（{normalize_text(extract_text(note))}）*\n"
    for arith in article.findall("ArithFormula"):
        md += "\n" + process_arith_formula(arith)
    
    md += "\n"
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
    
    if not suppl.findall("Article") and not suppl.findall("Chapter"):
         for para in suppl.findall("Paragraph"):
            sent = para.find(".//Sentence")
            if sent is not None:
                md += f"- {normalize_text(extract_text(sent))}\n"
    
    md += process_all_appdx(suppl)

    return md

def process_all_appdx(parent_element):
    """別表、別記、様式などをまとめて処理"""
    md = ""
    appdx_tables = parent_element.findall("AppdxTable")
    if appdx_tables:
        md += "# 別表\n\n"
        for appdx_table in appdx_tables:
            md += process_appdx_table(appdx_table)
    
    appdx_notes = parent_element.findall("AppdxNote")
    if appdx_notes:
        md += "# 別記\n\n"
        for appdx_note in appdx_notes:
            md += process_appdx_note(appdx_note)
    
    appdx_styles = parent_element.findall("AppdxStyle")
    if appdx_styles:
        md += "# 様式\n\n"
        for appdx_style in appdx_styles:
            md += process_appdx_style(appdx_style)
    
    appdx_formats = parent_element.findall("AppdxFormat")
    if appdx_formats:
        md += "# 書式\n\n"
        for appdx_format in appdx_formats:
            md += process_appdx_format(appdx_format)
    
    appdx_figs = parent_element.findall("AppdxFig")
    if appdx_figs:
        md += "# 別図\n\n"
        for appdx_fig in appdx_figs:
            md += process_appdx_fig(appdx_fig)
    
    appdxs = parent_element.findall("Appdx")
    if appdxs:
        md += "# 別\n\n"
        for appdx in appdxs:
            md += process_appdx(appdx)
    
    return md

def get_table_css_style():
    """テーブル用のCSSスタイルを返す
    
    HTML表の枠線スタイルを正確に表現するためのCSS。
    border-*-style属性で見た目上つながっているが論理的には連結されていない
    セルの意図を保つ。
    """
    return """<style>
table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
}

table td, table th {
  border: 1px solid black;
  padding: 8px;
  text-align: left;
}

/* Border style attributes */
td, th {
  border-width: 1px;
  border-color: black;
}

/* border-*-style で none を指定したセルは枠線を非表示にする */
td[style*="border-top-style: none"], 
th[style*="border-top-style: none"] {
  border-top: none;
}

td[style*="border-bottom-style: none"], 
th[style*="border-bottom-style: none"] {
  border-bottom: none;
}

td[style*="border-left-style: none"], 
th[style*="border-left-style: none"] {
  border-left: none;
}

td[style*="border-right-style: none"], 
th[style*="border-right-style: none"] {
  border-right: none;
}

/* dotted スタイルを指定したセル */
td[style*="border-top-style: dotted"], 
th[style*="border-top-style: dotted"] {
  border-top-style: dotted;
}

td[style*="border-bottom-style: dotted"], 
th[style*="border-bottom-style: dotted"] {
  border-bottom-style: dotted;
}

td[style*="border-left-style: dotted"], 
th[style*="border-left-style: dotted"] {
  border-left-style: dotted;
}

td[style*="border-right-style: dotted"], 
th[style*="border-right-style: dotted"] {
  border-right-style: dotted;
}

/* double スタイルを指定したセル */
td[style*="border-top-style: double"], 
th[style*="border-top-style: double"] {
  border-top-style: double;
}

td[style*="border-bottom-style: double"], 
th[style*="border-bottom-style: double"] {
  border-bottom-style: double;
}

td[style*="border-left-style: double"], 
th[style*="border-left-style: double"] {
  border-left-style: double;
}

td[style*="border-right-style: double"], 
th[style*="border-right-style: double"] {
  border-right-style: double;
}
</style>
"""

def extract_law_metadata(root, revision_meta=None):
    """
    法令のメタデータを抽出する。
    revision_meta: API v2から取得した改正情報(dict)
    """
    md = ""
    law = root if root.tag == "Law" else root.find(".//Law")
    try:
        lid = extract_law_id_from_root(root)
        if lid:
            md += f"**法令ID**: {lid}\n\n"
    except Exception:
        pass
    if law is not None:
        era = law.get("Era", "")
        year = law.get("Year", "")
        num = law.get("Num", "")
        ltype = law.get("LawType", "")
        
        era_map = {"Meiji":"明治", "Taisho":"大正", "Showa":"昭和", "Heisei":"平成", "Reiwa":"令和"}
        type_map = {"Act":"法律", "CabinetOrder":"政令", "MinisterialOrdinance":"省令", "Rule":"規則", "Constitution":"憲法"}
        
        if era and year and num:
            if ltype == "Constitution":
                md += f"**法令番号**: {era_map.get(era, era)}{year}年 憲法\n\n"
            else:
                md += f"**法令番号**: {era_map.get(era, era)}{year}年{type_map.get(ltype, ltype)}第{num}号\n\n"
        
        pm = law.get("PromulgateMonth", "")
        pd = law.get("PromulgateDay", "")
        if pm or pd:
            md += f"**公布日**: {pm}月{pd}日\n\n"

        if revision_meta:
            amend_date = revision_meta.get('amendment_enforcement_date')
            amend_title = revision_meta.get('amendment_law_title')
            amend_num = revision_meta.get('amendment_law_num')
            
            if amend_date:
                md += f"**施行日**: {amend_date}\n\n"
            
            if amend_title or amend_num:
                md += "**最終改正**:\n"
                if amend_title:
                    md += f"- 法令名: {amend_title}\n"
                if amend_num:
                    md += f"- 番号: {amend_num}\n"
                md += "\n"

        title_elem = law.find('.//LawTitle')
        if title_elem is not None:
            kana = title_elem.get('Kana', '')
            abbrev = title_elem.get('Abbrev', '')
            abbrev_kana = title_elem.get('AbbrevKana', '')
            
            if kana:
                md += f"**読み仮名**: {kana}\n\n"
            
            if abbrev:
                abbrevs = abbrev.split(',')
                kanas = abbrev_kana.split(',') if abbrev_kana else []
                
                md += "**略称**:\n"
                for i, abbr in enumerate(abbrevs):
                    reading = kanas[i] if i < len(kanas) else ""
                    if reading:
                        md += f"- {abbr} ({reading})\n"
                    else:
                        md += f"- {abbr}\n"
                md += "\n"
            elif abbrev_kana:
                md += f"**略称（読み）※頭文字のみの場合あり**: {abbrev_kana}\n\n"
            
    return md

# ==========================================
# Main Parser
# ==========================================

def parse_to_markdown(xml_content, law_name_override=None):
    """XMLバイナリデータをMarkdown文字列に変換"""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"XMLパースエラー: {e}")
        return "", "", None, None, None

    revision_meta = {}
    enforcement_date = None
    
    if root.tag == "law_data_response":
        rev_info = root.find("revision_info")
        if rev_info is not None:
            enforcement_date = extract_text(rev_info.find("amendment_enforcement_date"))
            
            revision_meta['amendment_enforcement_date'] = enforcement_date
            revision_meta['amendment_law_title'] = extract_text(rev_info.find("amendment_law_title"))
            revision_meta['amendment_law_num'] = extract_text(rev_info.find("amendment_law_num"))
            revision_meta['amendment_type'] = extract_text(rev_info.find("amendment_type"))
            
        full_text = root.find("law_full_text")
        if full_text is not None:
            inner_law = full_text.find("Law")
            if inner_law is not None:
                root = inner_law
            else:
                print("警告: law_data_response内にLaw要素が見つかりませんでした。")
        else:
             print("警告: law_data_response内にlaw_full_text要素が見つかりませんでした。")

    if law_name_override:
        law_name = law_name_override
    else:
        law_name = extract_law_title_from_root(root)

    print(f"変換開始: {law_name}")

    abbrev = ""
    try:
        title_elem = root.find('.//LawTitle')
        if title_elem is not None:
            raw_abbrev = title_elem.get('Abbrev', '')
            if raw_abbrev:
                abbrev = raw_abbrev.split(',')[0].strip()
    except Exception:
        abbrev = ""

    law_id = extract_law_id_from_root(root)

    markdown_text = f"# {law_name}\n\n"
    # CSS スタイルを先頭に追加（テーブルの枠線表示用）
    markdown_text += get_table_css_style()
    markdown_text += "\n"
    markdown_text += extract_law_metadata(root, revision_meta)
    
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
    
    return markdown_text, law_name, abbrev, law_id, enforcement_date

# ==========================================
# ファイルI/O および API処理関数
# ==========================================

def fetch_law_data(law_name, asof_date=None):
    """e-Gov API v2から法令XMLを取得"""
    print(f"[{law_name}] を検索中... (API v2)")
    try:
        laws_url = "https://laws.e-gov.go.jp/api/2/laws"
        params = {
            "law_title": law_name,
            "limit": 5  
        }
        
        response = requests.get(laws_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        law_id = None
        found_title = ""
        
        if data.get("laws"):
            for law in data["laws"]:
                revision = law.get("revision_info", {})
                title = revision.get("law_title", "")
                if title == law_name:
                    law_id = law["law_info"]["law_id"]
                    found_title = title
                    break
            
            if not law_id and len(data["laws"]) > 0:
                law = data["laws"][0]
                law_id = law["law_info"]["law_id"]
                found_title = law["revision_info"]["law_title"]
                print(f"完全一致が見つからないため、'{found_title}' を取得します。")

        if not law_id:
            print(f"Error: '{law_name}' が見つかりませんでした。")
            return None

        data_url = f"https://laws.e-gov.go.jp/api/2/law_data/{law_id}"
        data_params = {"response_format": "xml"}
        
        if asof_date:
            data_params["asof"] = asof_date
            print(f"条文データをダウンロード中 (時点: {asof_date})...")
        else:
            print(f"条文データをダウンロード中...")
        
        law_response = requests.get(data_url, params=data_params, timeout=30)
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

def save_markdown_file(law_name, md_output, force_overwrite=False, abbrev=None, law_id=None, enforcement_date=None):
    """ファイルを保存し、既存ファイルがあれば上書き確認"""
    safe_law_name = "".join(c for c in law_name if c not in '<>:"/\\|?*')
    date_suffix = f"_{enforcement_date.replace('-', '')}" if enforcement_date else ""
    
    output_dir = "output_Markdown"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    filename = os.path.join(output_dir, f"{safe_law_name}{date_suffix}.md")
    
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
    
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(md_output)
        print(f"[保存完了] {filename}")
        return True
    except Exception as e:
        print(f"ファイルの保存中にエラーが発生しました: {e}")
        return False


def process_from_api(law_name, force=False, asof_date=None):
    """APIから法令を取得して保存"""
    xml_data = fetch_law_data(law_name, asof_date)
    if xml_data:
        md_output, real_law_name, abbrev, law_id, enforcement_date = parse_to_markdown(xml_data, law_name)
        if md_output:
            save_markdown_file(real_law_name, md_output, force_overwrite=force, abbrev=abbrev, law_id=law_id, enforcement_date=enforcement_date)

def process_from_file(file_path, force=False):
    """ローカルファイルから変換して保存"""
    xml_data = load_xml_from_file(file_path)
    if xml_data:
        md_output, real_law_name, abbrev, law_id, enforcement_date = parse_to_markdown(xml_data)
        if md_output:
            save_markdown_file(real_law_name, md_output, force_overwrite=force, abbrev=abbrev, law_id=law_id, enforcement_date=enforcement_date)

def process_law_list_file(list_file_path="law_list.txt", force=True, asof_date=None):
    """法令リストファイルを読み込んで一括処理"""
    if not os.path.exists(list_file_path):
        print(f"エラー: リストファイル '{list_file_path}' が見つかりません。")
        return

    print(f"\n--- リスト処理開始: {list_file_path} ---")
    if asof_date:
        print(f"--- 適用時点: {asof_date} ---")
        
    try:
        with open(list_file_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
        
        count = 0
        for line in lines:
            law_name = line.strip()
            if not law_name or law_name.startswith(";") or law_name.startswith("#"):
                continue
                
            print(f"\n[{count+1}] 処理中: {law_name}")
            process_from_api(law_name, force=force, asof_date=asof_date)
            count += 1
            
        print(f"\n--- 一括処理完了 ({count}件) ---")
        
    except Exception as e:
        print(f"リスト処理中にエラーが発生しました: {e}")

# ==========================================
# Main Execution Block
# ==========================================

def get_asof_date_input():
    while True:
        current_date = datetime.now().strftime("%Y-%m-%d")
        print(f"\n適用時点 (asof) を指定してください。")
        date_raw = input(f"（例: {current_date} / 空Enterで最新版を取得）: ").strip()
        
        if not date_raw:
            return None
        
        try:
            datetime.strptime(date_raw, "%Y-%m-%d")
            return date_raw
        except ValueError:
            print("エラー: 日付形式が YYYY-MM-DD 形式でありません。")

def main():
    parser = argparse.ArgumentParser(description="Japanese Law XML to Markdown Converter")
    parser.add_argument("--law", help="法令名を指定してAPIから取得・変換します (確認なしで上書き)")
    parser.add_argument("--list", nargs="?", const="law_list.txt", help="法令リストファイルを指定して一括処理します (デフォルト: law_list.txt)")
    parser.add_argument("--asof", help="--law または --list 使用時に適用する法令の時点(YYYY-MM-DD)")
    parser.add_argument("--table-mode", choices=["hybrid", "strict"], default="hybrid", 
                        help="テーブル処理モード: hybrid(Border属性から推測) または strict(rowspan属性のみ) [デフォルト: hybrid]")
    parser.add_argument("--table-debug", action="store_true", help="テーブルrowspan計算のデバッグログを出力")
    
    args = parser.parse_args()
    
    # グローバル変数を引数から設定
    global TABLE_PROCESSING_MODE, TABLE_ROWSPAN_DEBUG
    TABLE_PROCESSING_MODE = args.table_mode
    TABLE_ROWSPAN_DEBUG = args.table_debug
    
    if TABLE_ROWSPAN_DEBUG:
        print(f"[デバッグ] TABLE_PROCESSING_MODE={TABLE_PROCESSING_MODE}")
        print(f"[デバッグ] TABLE_ROWSPAN_DEBUG=True")

    if args.law:
        process_from_api(args.law, force=True, asof_date=args.asof)
        sys.exit(0)
    
    if args.list:
        process_law_list_file(args.list, force=True, asof_date=args.asof)
        sys.exit(0)

    while True:
        try:
            print("\n" + "="*50)
            print("処理方法を選択してください:")
            print("  1: 法令名を入力して検索（APIを使用）")
            print("  2: XMLファイルのパス、またはフォルダを指定（ローカル）")
            print("  3: 法令リスト(law_list.txt)から一括処理")
            print("  0: 終了")
            print("="*50)
            
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
                asof_date = get_asof_date_input() 
                process_from_api(law_name, force=False, asof_date=asof_date)
            else:
                print("エラー: 法令名が入力されていません。")
        
        elif mode == '2':
            path_input = input("XMLファイルのパス、またはフォルダパス: ").strip()
            path_input = path_input.strip('"').strip("'")
            
            if not path_input:
                print("パスが入力されていません。")
                continue
                
            if os.path.isdir(path_input):
                xml_files = glob.glob(os.path.join(path_input, "*.xml"))
                if not xml_files:
                    print(f"フォルダ内にXMLファイルが見つかりませんでした: {path_input}")
                    continue
                
                print(f"\n--- フォルダ一括処理開始: {len(xml_files)}件 ---")
                for xml_file in xml_files:
                    print(f"処理中: {os.path.basename(xml_file)}")
                    process_from_file(xml_file, force=True)
                print("--- 完了 ---")
                
            elif os.path.isfile(path_input):
                process_from_file(path_input, force=False)
            else:
                print(f"エラー: パスが見つかりません: {path_input}")

        elif mode == '3':
            default_list = "law_list.txt"
            user_list = input(f"リストファイル名を入力 (Enterで '{default_list}'): ").strip()
            target_list = user_list if user_list else default_list
            asof_date = get_asof_date_input() 
            
            process_law_list_file(target_list, force=True, asof_date=asof_date)
            
        else:
            print("1, 2, 3, または 0 を入力してください。")

if __name__ == "__main__":
    main()