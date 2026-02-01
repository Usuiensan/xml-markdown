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

# 画像ダウンロード設定
DOWNLOAD_IMAGES = True  # 画像を自動ダウンロードするかどうか

# ==========================================
# ユーティリティ関数
# ==========================================

def download_image_from_api(law_revision_id, src_attr, image_dir):
    """e-Gov APIから画像をダウンロードして保存
    
    Args:
        law_revision_id: 法令履歴ID（例: 411AC0000000127_19990813_000000000000000）
        src_attr: Fig要素のsrc属性（例: ./pict/H11HO127-001.jpg）
        image_dir: 画像保存先ディレクトリ
    
    Returns:
        str: 保存された画像の相対パス、失敗時はNone
    """
    if not DOWNLOAD_IMAGES or not law_revision_id or not src_attr:
        return None
    
    # 画像保存ディレクトリの作成
    os.makedirs(image_dir, exist_ok=True)
    
    # ファイル名を抽出（例: ./pict/H11HO127-001.jpg → H11HO127-001.jpg）
    filename = os.path.basename(src_attr)
    
    # 保存先パス
    save_path = os.path.join(image_dir, filename)
    
    # 既にダウンロード済みの場合はスキップ
    if os.path.exists(save_path):
        print(f"[画像] 既存: {filename}")
        return os.path.join(os.path.basename(image_dir), filename)
    
    # APIエンドポイント（修正版）
    api_url = f"https://laws.e-gov.go.jp/api/2/attachment/{law_revision_id}"
    params = {"src": src_attr}
    
    try:
        print(f"[画像] ダウンロード中: {filename}")
        response = requests.get(api_url, params=params, timeout=30)
        
        if response.status_code == 200:
            # 画像を保存
            with open(save_path, 'wb') as f:
                f.write(response.content)
            print(f"[画像] 保存完了: {save_path}")
            
            # 相対パスを返す（Markdownから参照するため）
            return os.path.join(os.path.basename(image_dir), filename)
        else:
            print(f"[警告] 画像ダウンロード失敗: {filename} (HTTP {response.status_code})")
            return None
    
    except Exception as e:
        print(f"[エラー] 画像ダウンロード失敗: {filename} - {str(e)}")
        return None

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

def process_table_column_content(col_elem, law_revision_id=None, image_dir=None):
    """TableColumn内の構造要素を処理してHTMLセル内容を生成
    
    TableColumnには <Sentence>, <Item>, <Paragraph>, <Column> などの構造要素が
    含まれることがあります。これらを改行で繋ぎ、階層構造を維持します。
    
    スキーマ上の可能な子要素:
    <Part> | <Chapter> | <Section> | <Subsection> | <Division> | <Article> | 
    <Paragraph> | <Item> | <Subitem1-10> | <FigStruct> | <Remarks> | <Sentence> | <Column>
    
    Args:
        col_elem: TableColumn要素
        law_revision_id: 法令履歴ID（画像ダウンロード用）
        image_dir: 画像保存先ディレクトリ
    
    Returns:
        str: HTMLセル内容（改行を<br>タグで表現）
    """
    if col_elem is None:
        return ""
    
    parts = []
    
    # 子要素を順次処理
    for child in col_elem:
        tag = child.tag
        
        if tag == "Sentence":
            # Sentence要素は改行区切りで使われることが多い
            text = normalize_text(extract_text(child))
            if text:
                parts.append(text)
        
        elif tag == "Column":
            # Column要素も改行として扱う
            for sentence in child.findall("Sentence"):
                text = normalize_text(extract_text(sentence))
                if text:
                    parts.append(text)
        
        elif tag == "Item":
            # 号（Item）の処理
            item_num = child.get("Num", "")
            item_label = convert_item_num(item_num) if item_num else ""
            item_sent = child.find("ItemSentence")
            if item_sent is not None:
                sent_text = normalize_text(extract_text(item_sent))
                parts.append(f"{item_label} {sent_text}")
            # Itemの子要素（Subitem1など）も処理
            for subitem_level in range(1, 11):
                for subitem in child.findall(f"Subitem{subitem_level}"):
                    subitem_text = process_subitem_in_table(subitem, subitem_level)
                    if subitem_text:
                        parts.append(subitem_text)
        
        elif tag == "Paragraph":
            # 項の処理
            p_num = child.get("Num", "1")
            para_sent = child.find("ParagraphSentence")
            if para_sent is not None:
                sent_text = normalize_text(extract_text(para_sent))
                parts.append(f"({p_num}) {sent_text}")
        
        elif tag == "Remarks":
            # 備考の処理
            remarks_text = process_remarks_in_table(child)
            if remarks_text:
                parts.append(remarks_text)
        
        elif tag == "FigStruct":
            # 図の処理（HTMLテーブル内なので is_in_table=True）
            fig = child.find("Fig")
            if fig is not None:
                fig_text = process_fig(fig, law_revision_id, image_dir, is_in_table=True)
                if fig_text:
                    parts.append(fig_text.strip())
        
        elif tag in ["Article", "Part", "Chapter", "Section", "Subsection", "Division"]:
            # これらの構造要素は稀だが、スキーマ上は可能
            # タイトルとテキストを取得
            struct_text = normalize_text(extract_text(child))
            if struct_text:
                parts.append(struct_text)
        
        # Subitem1-10の直接出現にも対応
        elif tag.startswith("Subitem") and tag[7:].isdigit():
            level = int(tag[7:])
            subitem_text = process_subitem_in_table(child, level)
            if subitem_text:
                parts.append(subitem_text)
    
    # テキストがなく、直接のテキストノードがある場合
    if not parts:
        direct_text = normalize_text(extract_text(col_elem))
        if direct_text:
            return direct_text
    
    # 改行で結合（HTML内なので<br>タグを使用）
    return "<br>".join(parts) if parts else ""

def process_subitem_in_table(subitem_elem, level):
    """表内のSubitem要素を処理"""
    if subitem_elem is None:
        return ""
    
    num = subitem_elem.get("Num", "")
    title_elem = subitem_elem.find(f"Subitem{level}Title")
    sent_elem = subitem_elem.find(f"Subitem{level}Sentence")
    
    # インデント（レベルに応じて）
    indent = "　" * level
    
    parts = []
    if title_elem is not None:
        title_text = normalize_text(extract_text(title_elem))
        parts.append(f"{indent}{title_text}")
    
    if sent_elem is not None:
        sent_text = normalize_text(extract_text(sent_elem))
        parts.append(f"{indent}{sent_text}")
    
    return " ".join(parts)

def process_remarks_in_table(remarks_elem):
    """表内のRemarks要素を処理"""
    if remarks_elem is None:
        return ""
    
    parts = []
    label = remarks_elem.find("RemarksLabel")
    if label is not None:
        label_text = normalize_text(extract_text(label))
        parts.append(label_text)
    
    for item in remarks_elem.findall("Item"):
        item_num = item.get("Num", "")
        item_label = convert_item_num(item_num) if item_num else ""
        item_sent = item.find("ItemSentence")
        if item_sent is not None:
            sent_text = normalize_text(extract_text(item_sent))
            parts.append(f"{item_label} {sent_text}")
    
    for sentence in remarks_elem.findall("Sentence"):
        sent_text = normalize_text(extract_text(sentence))
        if sent_text:
            parts.append(sent_text)
    
    return "<br>".join(parts)

def process_quote_struct(quote_elem):
    """引用構造を処理（改行を維持）
    
    QuoteStructは「図として捉える改正」などで使用され、
    改行が意味を持つ場合があります。normalize_textで改行を潰さず、
    preタグまたは引用記法で改行を保持します。
    """
    if quote_elem is None:
        return ""
    
    # 改行を維持したままテキストを抽出
    content_parts = []
    for child in quote_elem:
        if child.tag == "Sentence":
            # Sentenceごとに改行
            text = extract_text(child).strip()
            if text:
                content_parts.append(text)
        elif child.tag == "Line":
            text = extract_text(child).strip()
            if text:
                content_parts.append(text)
        else:
            # その他の要素
            text = extract_text(child).strip()
            if text:
                content_parts.append(text)
    
    # 改行を保持してpreタグで表現
    content = "\n".join(content_parts)
    if content:
        return f"```\n{content}\n```\n\n"
    return ""

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
            md += f"**{label_text}**\n\n"
        else:
            md += f"**{label_text}**\n\n"
    
    # 備考の項目
    for item in remarks_elem.findall("Item"):
        item_num = item.get("Num", "")
        item_label = convert_item_num(item_num) if item_num else ""
        item_sent = item.find("ItemSentence")
        if item_sent is not None:
            sent_text = normalize_text(extract_text(item_sent))
            md += f"- {item_label}\n{sent_text}\n"
    
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
    """算式を処理（Num属性とテキスト、改行を保持）
    
    normalize_text()を使用すると改行が失われ計算式が崩壊するため、
    extract_text()のみを使用して改行を保持する。
    """
    if arith_formula is None: return ""
    
    # 改行を保持するためnormalize_text()は使わない
    formula_text = extract_text(arith_formula)
    if not formula_text: return ""
    
    # Num属性（算式番号）を取得
    formula_num = arith_formula.get("Num", "")
    num_label = f"（式{formula_num}）" if formula_num else ""
    
    # 改行を含む算式は常にコードブロックで表示
    if "\n" in formula_text or len(formula_text) > 100:
        return f"{num_label}\n```\n{formula_text}\n```\n\n"
    else:
        return f"{num_label} `{formula_text}`\n\n"

def process_arith_formula_num(arith_formula_num):
    """算式番号を処理"""
    if arith_formula_num is None: return ""
    text = normalize_text(extract_text(arith_formula_num))
    if not text: return ""
    return f"**{text}**\n\n"

def process_fig(fig, law_revision_id=None, image_dir=None, is_in_table=False):
    """図を処理（src属性で画像参照、またはテキスト説明）
    
    画像が含まれる場合、e-Gov APIから自動的にダウンロードして保存します。
    
    Args:
        fig: Fig要素
        law_revision_id: 法令履歴ID（画像ダウンロード用）
        image_dir: 画像保存先ディレクトリ
        is_in_table: HTMLテーブル内かどうか（Trueの場合は<img>タグを使用）
    """
    if fig is None: return ""
    
    src = fig.get("src", "")
    alt = normalize_text(extract_text(fig))
    
    if src:
        # 画像をダウンロード（DOWNLOAD_IMAGES=Trueの場合）
        if DOWNLOAD_IMAGES and law_revision_id and image_dir:
            local_path = download_image_from_api(
                law_revision_id,
                src,
                image_dir
            )
            
            if local_path:
                # ダウンロード成功 - ローカルパスを使用
                if is_in_table:
                    # HTMLテーブル内では<img>タグを使用
                    return f'<img src="{local_path}" alt="{alt}" />'
                else:
                    return f"![{alt}]({local_path})\n\n"
            else:
                # ダウンロード失敗 - 元のパスを使用（警告付き）
                print(f"[警告] 画像参照: {src} (ダウンロード失敗、元のパスを使用)")
                if is_in_table:
                    return f'<img src="{src}" alt="{alt}" />'
                else:
                    return f"![{alt}]({src})\n\n"
        else:
            # 画像ダウンロードが無効、または必要な情報がない場合
            if is_in_table:
                return f'<img src="{src}" alt="{alt}" />'
            else:
                return f"![{alt}]({src})\n\n"
    elif alt:
        # src がない場合は説明テキストとして出力
        return f"*[図: {alt}]*\n\n"
    else:
        # テキストもない場合は最小出力
        return f"*[図]*\n\n"

def process_fig_struct(fs):
    title = fs.find("FigStructTitle")
    t_text = normalize_text(extract_text(title)) if title is not None else ""
    md = f" **{t_text}** \n\n"
    
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

def build_logical_table_grid(rows, law_revision_id=None, image_dir=None):
    """
    XMLの行データから論理グリッドを構築
    
    rowspan属性を展開し、各セルの状態（テキスト、rowspan、Border属性）を保持する
    
    Args:
        rows: TableRow要素のリスト
        law_revision_id: 法令履歴ID（画像ダウンロード用）
        image_dir: 画像保存先ディレクトリ
    
    Returns:
        grid: 二次元リスト、各要素は {'text': str, 'bt': str, 'bb': str, 'rs': int, 'remaining_rs': int}
    """
    if not rows:
        return []
    
    # 最大列数を求める（colspan考慮）
    max_cols = 0
    for row in rows:
        cols = row.findall("TableColumn")
        col_count = sum(int(col.get('colspan', 1)) for col in cols)
        max_cols = max(max_cols, col_count)
    
    if max_cols == 0:
        return []
    
    grid = []
    
    for r_idx, row in enumerate(rows):
        cols = row.findall("TableColumn")
        
        # 現在の行のグリッドを初期化（前の行からのrowspanを考慮）
        current_grid_row = [None] * max_cols
        
        # 前の行からの継続分を埋める（rowspan > 1）
        if r_idx > 0:
            for c_idx in range(max_cols):
                if c_idx < len(grid[r_idx - 1]) and grid[r_idx - 1][c_idx]:
                    prev_cell = grid[r_idx - 1][c_idx]
                    if prev_cell.get('remaining_rs', 1) > 1:
                        # rowspan継続
                        new_cell = {
                            'text': '',  # 継続分はテキスト空
                            'bt': prev_cell.get('bt', 'solid'),
                            'bb': prev_cell.get('bb', 'solid'),
                            'rs': prev_cell.get('rs', 1),
                            'remaining_rs': prev_cell.get('remaining_rs', 1) - 1,
                            'is_continuation': True
                        }
                        current_grid_row[c_idx] = new_cell
        
        # 現在の行のセルをグリッドに配置
        grid_col_idx = 0
        for col_idx, col in enumerate(cols):
            # 空きがある列を見つける
            while grid_col_idx < max_cols and current_grid_row[grid_col_idx] is not None:
                grid_col_idx += 1
            
            if grid_col_idx < max_cols:
                # ✨ 改善: TableColumn内の構造要素を処理（画像パラメータも渡す）
                col_text = process_table_column_content(col, law_revision_id, image_dir)
                rowspan = int(col.get('rowspan', 1))
                colspan = int(col.get('colspan', 1))
                bt = col.get('BorderTop', 'solid')
                bb = col.get('BorderBottom', 'solid')
                
                cell_data = {
                    'text': col_text,
                    'bt': bt,
                    'bb': bb,
                    'rs': rowspan,
                    'remaining_rs': rowspan,
                    'colspan': colspan,
                    'is_continuation': False
                }
                
                # colspan分のセルを配置
                for cs_idx in range(colspan):
                    if grid_col_idx + cs_idx < max_cols:
                        if cs_idx == 0:
                            current_grid_row[grid_col_idx + cs_idx] = cell_data
                        else:
                            # colspan継続分
                            current_grid_row[grid_col_idx + cs_idx] = {
                                'text': '',
                                'bt': bt,
                                'bb': bb,
                                'rs': rowspan,
                                'remaining_rs': rowspan,
                                'is_colspan_continuation': True
                            }
                
                grid_col_idx += colspan
        
        grid.append(current_grid_row)
    
    return grid


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

def _check_table_has_non_solid_border(table, header, body_rows):
    """✨ NEW: テーブル内に solid 以外の border-style があるかを確認
    
    Args:
        table: Table要素
        header: TableHeaderRow要素（None可）
        body_rows: TableRow要素のリスト
    
    Returns:
        bool: True = solid以外あり（スタイル指定必要）、False = 全てsolid（スタイル指定不要）
    """
    # ヘッダーセルをチェック
    if header is not None:
        for col in header.findall("TableHeaderColumn"):
            for border_attr in ["BorderTop", "BorderBottom", "BorderLeft", "BorderRight"]:
                border_val = col.get(border_attr, "solid")
                if border_val != "solid":
                    return True
    
    # ボディセルをチェック
    for row in body_rows:
        for col in row.findall("TableColumn"):
            for border_attr in ["BorderTop", "BorderBottom", "BorderLeft", "BorderRight"]:
                border_val = col.get(border_attr, "solid")
                if border_val != "solid":
                    return True
    
    # 全て solid
    return False

def render_table(table, indent, law_revision_id=None, image_dir=None):
    """
    テーブルをHTMLにレンダリング
    
    提供されたプログラム例を参考に、Border属性を考慮した論理的なグリッド処理を実装。
    見た目上つながっているが論理的には連結されていないセルを正確に処理。
    
    ✨ 改善: テーブル内の全セルの border-style が "solid" の場合はスタイル指定を一切しない。
    1セルでも "none" | "dotted" | "double" があれば全セルに対してスタイル指定を行う。
    
    Args:
        table: Table要素
        indent: インデントレベル
        law_revision_id: 法令履歴ID（画像ダウンロード用）
        image_dir: 画像保存先ディレクトリ
    """
    indent_str = "  " * indent
    html_lines = []
    
    # テーブルのWritingMode属性を取得
    writing_mode = table.get("WritingMode", "horizontal-tb")
    table_class = 'writing-mode-vertical' if writing_mode == "vertical-rl" else 'writing-mode-horizontal'
    
    html_lines.append(f'{indent_str}<table class="{table_class}">')
    
    # ヘッダー行処理
    header = table.find("TableHeaderRow")
    body_rows = list(table.findall("TableRow"))
    
    # ✨ NEW: テーブル内の全セルをスキャンして、solid 以外の border-style があるかを確認
    has_non_solid_border = _check_table_has_non_solid_border(table, header, body_rows)
    
    # ヘッダーセルの処理
    if header is not None:
        html_lines.append(f"{indent_str}  <thead>")
        html_lines.append(f"{indent_str}    <tr>")
        for header_col in header.findall("TableHeaderColumn"):
            # ヘッダーセルは構造が単純なので従来通り
            col_text = normalize_text(extract_text(header_col))
            attrs = get_cell_attributes(header_col, "th", enable_border_style=has_non_solid_border)
            html_lines.append(f'{indent_str}      <th{attrs}>{col_text}</th>')
        html_lines.append(f"{indent_str}    </tr>")
        html_lines.append(f"{indent_str}  </thead>")
    elif body_rows:
        # TableHeaderRowが存在しない場合、最初のTableRowをヘッダーとして使用
        html_lines.append(f"{indent_str}  <thead>")
        html_lines.append(f"{indent_str}    <tr>")
        for col in body_rows[0].findall("TableColumn"):
            # ✨ 改善: ヘッダーでも構造要素を処理（画像パラメータも渡す）
            col_text = process_table_column_content(col, law_revision_id, image_dir)
            attrs = get_cell_attributes(col, "th", enable_border_style=has_non_solid_border)
            html_lines.append(f'{indent_str}      <th{attrs}>{col_text}</th>')
        html_lines.append(f"{indent_str}    </tr>")
        html_lines.append(f"{indent_str}  </thead>")
        body_rows = body_rows[1:]  # ヘッダーとして使用した行を除外
    
    # ボディ行処理（グリッドベース）
    if body_rows:
        # 論理グリッドを構築（画像パラメータも渡す）
        grid = build_logical_table_grid(body_rows, law_revision_id, image_dir)
        
        if grid:
            html_lines.append(f"{indent_str}  <tbody>")
            
            # グリッドから見た目上のセルを出力
            # 注：rowspan継続分や colspan継続分は skip する
            for r_idx, grid_row in enumerate(grid):
                html_lines.append(f"{indent_str}    <tr>")
                
                for c_idx, cell in enumerate(grid_row):
                    if cell is None:
                        continue
                    
                    # 継続分（rowspan/colspan）はスキップ
                    if cell.get('is_continuation') or cell.get('is_colspan_continuation'):
                        continue
                    
                    col_text = cell['text']
                    rowspan = cell.get('rs', 1)
                    colspan = cell.get('colspan', 1)
                    
                    # セルの属性を生成（Border属性は既に cell に含まれている）
                    attrs = []
                    if rowspan > 1:
                        attrs.append(f'rowspan="{rowspan}"')
                    if colspan > 1:
                        attrs.append(f'colspan="{colspan}"')
                    
                    # ✨ 改善: has_non_solid_border フラグに基づいてスタイル出力を制御
                    if has_non_solid_border:
                        # Border スタイルをCSSに変換
                        style_parts = []
                        border_map = {
                            'bt': 'border-top-style',
                            'bb': 'border-bottom-style'
                        }
                        for border_key, css_prop in border_map.items():
                            border_val = cell.get(border_key, 'solid')
                            if border_val:
                                style_parts.append(f"{css_prop}: {border_val}")
                        
                        if style_parts:
                            attrs.append(f'style="{"; ".join(style_parts)}"')
                    # else: solid のみの場合はスタイル指定しない
                    
                    attrs_str = " " + " ".join(attrs) if attrs else ""
                    html_lines.append(f'{indent_str}      <td{attrs_str}>{col_text}</td>')
                
                html_lines.append(f"{indent_str}    </tr>")
            
            html_lines.append(f"{indent_str}  </tbody>")
    
    html_lines.append(f"{indent_str}</table>")
    
    return "\n".join(html_lines) + "\n\n"

def get_cell_attributes(cell, cell_type="td", rowspan_override=None, enable_border_style=True):
    """テーブルセルの属性をHTMLのstyle属性に変換
    
    枠線のBorder属性を CSS border-*-style に変換することで、
    論理的には連結されていないが見た目上つながっているセルの意図を保つ。
    
    Args:
        cell: XML要素
        cell_type: "td" または "th"
        rowspan_override: 計算されたrowspan値（指定時はXML属性を上書き）
        enable_border_style: border-style をスタイル属性に含めるかどうか（デフォルト: True）
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
    
    # ✨ 改善: enable_border_style フラグに基づいて border-style を出力するかを制御
    if enable_border_style:
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

def render_table_struct(ts, indent, law_revision_id=None, image_dir=None):
    """
    TableStruct要素をHTMLに変換
    
    Args:
        ts: TableStruct要素
        indent: インデントレベル
        law_revision_id: 法令履歴ID（画像ダウンロード用）
        image_dir: 画像保存先ディレクトリ
    """
    html = ""
    indent_str = "  " * indent
    title = ts.find("TableStructTitle")
    if title is not None: 
        title_text = normalize_text(extract_text(title))
        html += f"{indent_str}<div class=\"table-struct\">\n"
        html += f"{indent_str}  <div class=\"table-struct-title\">{title_text}</div>\n\n"
    
    # Remarksを処理
    for remarks in ts.findall("Remarks"):
        remarks_text = process_remarks(remarks)
        if remarks_text:
            html += f"{indent_str}  {remarks_text}\n\n"
    
    tbl = ts.find("Table")
    if tbl is not None:
        html += render_table(tbl, indent + 1, law_revision_id, image_dir)
    if title is not None:
        html += f"{indent_str}</div>\n\n"
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

def process_column(column):
    """Column要素を処理（通常は ItemSentence 内で使用）"""
    if column is None: return ""
    # 複数の Column がある場合は用語-定義形式
    sentences = column.findall("Sentence")
    if sentences:
        return "".join([normalize_text(extract_text(s)) for s in sentences])
    else:
        return normalize_text(extract_text(column))

def process_child_elements(parent, indent, law_revision_id=None, image_dir=None):
    md = ""
    for list_elem in parent.findall("List"): md += process_list(list_elem, indent)
    for ts in parent.findall("TableStruct"): md += "\n" + render_table_struct(ts, indent, law_revision_id, image_dir)
    for t in parent.findall("Table"): md += "\n" + render_table(t, indent, law_revision_id, image_dir)
    for fs in parent.findall("FigStruct"): md += "\n" + process_fig_struct(fs, law_revision_id, image_dir)
    for f in parent.findall("Fig"): md += "\n" + process_fig(f, law_revision_id, image_dir)
    for ss in parent.findall("StyleStruct"): md += "\n" + process_style_struct(ss)
    for ns in parent.findall("NoteStruct"): md += "\n" + process_note_struct(ns)
    for fs in parent.findall("FormatStruct"): md += "\n" + process_format_struct(fs)
    for cls in parent.findall("Class"): md += "\n" + process_class(cls)
    # Column 要素（独立している場合）も処理
    for col in parent.findall("Column"):
        col_text = process_column(col)
        if col_text:
            md += f"{col_text}\n\n"
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

def _appdx_common(elem, law_revision_id=None, image_dir=None):
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
    for ts in elem.findall("TableStruct"): md += render_table_struct(ts, 0, law_revision_id, image_dir)
    for t in elem.findall("Table"): md += render_table(t, 0, law_revision_id, image_dir)
    for ss in elem.findall("StyleStruct"): md += process_style_struct(ss)
    for fs in elem.findall("FormatStruct"): md += process_format_struct(fs)
    for ns in elem.findall("NoteStruct"): md += process_note_struct(ns)
    for fig_s in elem.findall("FigStruct"): md += process_fig_struct(fig_s, law_revision_id, image_dir)
    
    # Remarksを処理
    for remarks in elem.findall("Remarks"):
        remarks_text = process_remarks(remarks)
        if remarks_text:
            md += f"{remarks_text}\n\n"
    
    # Item（項目）を処理
    for item in elem.findall("Item"):
        md += process_item(item, 0)
    
    return md

def process_appdx_table(elem, law_revision_id=None, image_dir=None): 
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
        md += render_table_struct(ts, 0, law_revision_id, image_dir)
    
    # 直接のTableを処理
    for t in elem.findall("Table"): 
        md += render_table(t, 0, law_revision_id, image_dir)
    
    # Remarksを処理
    for remarks in elem.findall("Remarks"):
        remarks_text = process_remarks(remarks)
        if remarks_text:
            md += f"{remarks_text}\n\n"
    
    # Item（項目）を処理
    for item in elem.findall("Item"):
        md += process_item(item, 0)
    
    return md

def process_appdx_note(elem, law_revision_id=None, image_dir=None): 
    """別記を処理"""
    return _appdx_common(elem, law_revision_id, image_dir)

def process_appdx_style(elem, law_revision_id=None, image_dir=None): 
    """別記様式を処理"""
    return _appdx_common(elem, law_revision_id, image_dir)

def process_appdx_format(elem, law_revision_id=None, image_dir=None): 
    """別記書式を処理"""
    return _appdx_common(elem, law_revision_id, image_dir)

def process_appdx_fig(elem): 
    """別図を処理"""
    if elem is None: return ""
    # FigStructを処理
    fig_struct = elem.find("FigStruct")
    if fig_struct is not None:
        return process_fig_struct(fig_struct)
    # FigStruct がない場合は相互参照を処理
    md = ""
    title = elem.find("AppdxFigTitle")
    if title is not None:
        md += f"## {normalize_text(extract_text(title))}\n\n"
    for rel_art in elem.findall("RelatedArticleNum"):
        rel_text = normalize_text(extract_text(rel_art))
        if rel_text:
            md += f"*{rel_text}*\n\n"
    return md if md else ""

def process_appdx(elem): 
    """付録を処理（算式などを含む）"""
    if elem is None: return ""
    md = ""
    # ArithFormulaNum（算式番号）を処理
    for arith_num in elem.findall("ArithFormulaNum"):
        md += process_arith_formula_num(arith_num)
    # RelatedArticleNum（関係条文番号）を処理
    for rel_art in elem.findall("RelatedArticleNum"):
        rel_text = normalize_text(extract_text(rel_art))
        if rel_text:
            md += f"*{rel_text}*\n\n"
    # ArithFormula（算式）を処理
    for arith in elem.findall("ArithFormula"):
        md += process_arith_formula(arith)
    # Remarks（備考）を処理
    for remarks in elem.findall("Remarks"):
        remarks_text = process_remarks(remarks)
        if remarks_text:
            md += f"{remarks_text}\n\n"
    return md

def process_suppl_provision_appdx_table(elem, law_revision_id=None, image_dir=None):
    """附則別表を処理"""
    if elem is None: return ""
    md = ""
    title = elem.find("SupplProvisionAppdxTableTitle")
    if title is not None:
        md += f"## {normalize_text(extract_text(title))}\n\n"
    # RelatedArticleNum（関係条文番号）を処理
    for rel_art in elem.findall("RelatedArticleNum"):
        rel_text = normalize_text(extract_text(rel_art))
        if rel_text:
            md += f"*{rel_text}*\n\n"
    # TableStruct を処理
    for ts in elem.findall("TableStruct"):
        md += render_table_struct(ts, 0, law_revision_id, image_dir)
    return md

def process_suppl_provision_appdx_style(elem):
    """附則様式を処理"""
    if elem is None: return ""
    md = ""
    title = elem.find("SupplProvisionAppdxStyleTitle")
    if title is not None:
        md += f"## {normalize_text(extract_text(title))}\n\n"
    # RelatedArticleNum（関係条文番号）を処理
    for rel_art in elem.findall("RelatedArticleNum"):
        rel_text = normalize_text(extract_text(rel_art))
        if rel_text:
            md += f"*{rel_text}*\n\n"
    # StyleStruct を処理
    for ss in elem.findall("StyleStruct"):
        md += process_style_struct(ss)
    return md

def process_suppl_provision_appdx(elem):
    """附則付録を処理（算式などを含む）"""
    if elem is None: return ""
    md = ""
    # ArithFormulaNum（算式番号）を処理
    for arith_num in elem.findall("ArithFormulaNum"):
        md += process_arith_formula_num(arith_num)
    # RelatedArticleNum（関係条文番号）を処理
    for rel_art in elem.findall("RelatedArticleNum"):
        rel_text = normalize_text(extract_text(rel_art))
        if rel_text:
            md += f"*{rel_text}*\n\n"
    # ArithFormula（算式）を処理
    for arith in elem.findall("ArithFormula"):
        md += process_arith_formula(arith)
    return md

# --- 構造要素処理関数 (Part, Chapter, Articleなど) ---

def process_amend_provision(xml_root, law_revision_id=None, image_dir=None):
    """改正規定を処理（NewProvision内の全構造要素に対応）
    
    NewProvisionはスキーマ上、以下の要素を含むことができます:
    <LawTitle> | <Preamble> | <TOC> | <Part> | <Chapter> | <Section> | 
    <Subsection> | <Division> | <Article> | <Paragraph> | <Item> | など
    
    これらを適切に処理して改正内容を出力します。
    
    Args:
        xml_root: XML root要素
        law_revision_id: 法令履歴ID（画像ダウンロード用）
        image_dir: 画像保存先ディレクトリ
    """
    amend_provs = xml_root.findall(".//AmendProvision")
    if not amend_provs: return ""
    
    md = "# 改正規定\n\n"
    
    for amend_prov in amend_provs:
        # 改正規定文の処理
        for amend_sent in amend_prov.findall("AmendProvisionSentence"):
            for sentence in amend_sent.findall("Sentence"):
                text = normalize_text(extract_text(sentence))
                if text:
                    md += f"{text}\n\n"
        
        # NewProvision内の構造要素を処理
        for new_prov in amend_prov.findall("NewProvision"):
            md += process_new_provision(new_prov, law_revision_id, image_dir)
    
    return md

def process_new_provision(new_prov, law_revision_id=None, image_dir=None):
    """NewProvision（改正規定中の新規条文）を処理
    
    NewProvisionには法令本体と同様の構造が含まれるため、
    構造要素を順次処理します。
    
    Args:
        new_prov: NewProvision要素
        law_revision_id: 法令履歴ID（画像ダウンロード用）
        image_dir: 画像保存先ディレクトリ
    """
    md = ""
    
    # LawTitle（法令名の改正の場合）
    law_title = new_prov.find("LawTitle")
    if law_title is not None:
        title_text = normalize_text(extract_text(law_title))
        md += f"## {title_text}\n\n"
    
    # Preamble（前文）
    preamble = new_prov.find("Preamble")
    if preamble is not None:
        md += "### 前文\n\n"
        for para in preamble.findall("Paragraph"):
            para_text = normalize_text(extract_text(para))
            md += f"{para_text}\n\n"
    
    # 構造要素（Part, Chapter, Section など）
    for part in new_prov.findall("Part"):
        md += process_structure_element(part, 2)
    
    for chapter in new_prov.findall("Chapter"):
        md += process_structure_element(chapter, 2)
    
    for section in new_prov.findall("Section"):
        md += process_structure_element(section, 3)
    
    for subsection in new_prov.findall("Subsection"):
        md += process_structure_element(subsection, 4)
    
    for division in new_prov.findall("Division"):
        md += process_structure_element(division, 4)
    
    # Article（条）
    for article in new_prov.findall("Article"):
        md += process_article(article, 3)
    
    # Paragraph（項）- Article外の直接出現
    for para in new_prov.findall("Paragraph"):
        md += process_single_paragraph(para, 1)
    
    # Item（号）- Paragraph外の直接出現
    for item in new_prov.findall("Item"):
        md += process_item(item, 1)
    
    # TableStruct（表）
    for table_struct in new_prov.findall("TableStruct"):
        md += render_table_struct(table_struct, 0, law_revision_id, image_dir)
    
    # FigStruct（図）
    for fig_struct in new_prov.findall("FigStruct"):
        md += process_fig_struct(fig_struct, law_revision_id, image_dir)
    
    # StyleStruct（様式）
    for style_struct in new_prov.findall("StyleStruct"):
        md += process_style_struct(style_struct)
    
    # NoteStruct（記）
    for note_struct in new_prov.findall("NoteStruct"):
        md += process_note_struct(note_struct)
    
    # FormatStruct（書式）
    for format_struct in new_prov.findall("FormatStruct"):
        md += process_format_struct(format_struct)
    
    # Remarks（備考）
    for remarks in new_prov.findall("Remarks"):
        md += process_remarks(remarks)
    
    # 別表等
    for appdx_table in new_prov.findall("AppdxTable"):
        md += process_appdx_table(appdx_table)
    
    for appdx_note in new_prov.findall("AppdxNote"):
        md += process_appdx_note(appdx_note)
    
    for appdx_style in new_prov.findall("AppdxStyle"):
        md += process_appdx_style(appdx_style)
    
    for appdx in new_prov.findall("Appdx"):
        md += process_appdx(appdx)
    
    for appdx_fig in new_prov.findall("AppdxFig"):
        md += process_appdx_fig(appdx_fig)
    
    for appdx_format in new_prov.findall("AppdxFormat"):
        md += process_appdx_format(appdx_format)
    
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

def process_article(article, heading_level=4):
    """条の処理（常にH4で出力）
    
    Args:
        article: Article要素
        heading_level: 見出しレベル（デフォルト4、Article固定アンカー）
    """
    md = ""
    num = article.get("Num", "")
    label = convert_article_num(num)
    caption = article.find("ArticleCaption")
    cap_text = normalize_text(extract_text(caption)) if caption is not None else ""
    
    # Articleは常にH4で出力（固定アンカー）
    md += f"#### {label}{cap_text}\n"
    
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
        md += f"\n*{normalize_text(extract_text(note))}*\n"
    for arith in article.findall("ArithFormula"):
        md += "\n" + process_arith_formula(arith)
    
    md += "\n"
    return md

def get_hierarchy_level(tag):
    """
    階層要素のMarkdown見出しレベルを取得
    

    - Part: H1 (#)
    - Chapter: H2 (##)
    - Section: H3 (###)
    - Subsection/Division: 太字（見出しレベルを消費しない）
    - Article: H4 (####) ※ただし、Articleは固定でH4
    """
    return {"Part": 1, "Chapter": 2, "Section": 3}.get(tag, 2)

def process_structure_element(element, heading_level=None):
    """構造要素（Part/Chapter/Section/Subsection/Division）を処理
    
    階層マッピング:
    - Part: H1 (#)
    - Chapter: H2 (##)
    - Section: H3 (###)
    - Subsection: 太字（**第三款 〇〇**）
    - Division: 太字（**第一目 〇〇**）
    
    Article（条）は常にH4 (####) で固定。
    """
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
            # Subsection/Divisionは太字で出力（見出しレベルを消費しない）
            if element.tag in ["Subsection", "Division"]:
                md += f"**{normalize_text(extract_text(t_elem))}**\n\n"
            else:
                md += f"{'#' * heading_level} {normalize_text(extract_text(t_elem))}\n\n"
    
    hierarchy = ["Part", "Chapter", "Section", "Subsection", "Division"]
    if element.tag in hierarchy:
        idx = hierarchy.index(element.tag)
        if idx < len(hierarchy) - 1:
            next_tag = hierarchy[idx + 1]
            for child in element.findall(next_tag):
                md += process_structure_element(child)
    
    # Articleは常にH4で固定
    for article in element.findall("Article"):
        md += process_article(article, 4)
    
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
    
    # 附則別表を処理
    suppl_appdx_tables = suppl.findall("SupplProvisionAppdxTable")
    if suppl_appdx_tables:
        md += "## 附則別表\n\n"
        for table in suppl_appdx_tables:
            md += process_suppl_provision_appdx_table(table)
    
    # 附則様式を処理
    suppl_appdx_styles = suppl.findall("SupplProvisionAppdxStyle")
    if suppl_appdx_styles:
        md += "## 附則様式\n\n"
        for style in suppl_appdx_styles:
            md += process_suppl_provision_appdx_style(style)
    
    # 附則付録を処理
    suppl_appdxs = suppl.findall("SupplProvisionAppdx")
    if suppl_appdxs:
        md += "## 附則付録\n\n"
        for appdx in suppl_appdxs:
            md += process_suppl_provision_appdx(appdx)

    return md

def process_all_appdx(parent_element, law_revision_id=None, image_dir=None):
    """別表、別記、様式などをまとめて処理
    
    Args:
        parent_element: 親要素
        law_revision_id: 法令履歴ID（画像ダウンロード用）
        image_dir: 画像保存先ディレクトリ
    """
    md = ""
    appdx_tables = parent_element.findall("AppdxTable")
    if appdx_tables:
        md += "# 別表\n\n"
        for appdx_table in appdx_tables:
            md += process_appdx_table(appdx_table, law_revision_id, image_dir)
    
    appdx_notes = parent_element.findall("AppdxNote")
    if appdx_notes:
        md += "# 別記\n\n"
        for appdx_note in appdx_notes:
            md += process_appdx_note(appdx_note, law_revision_id, image_dir)
    
    appdx_styles = parent_element.findall("AppdxStyle")
    if appdx_styles:
        md += "# 様式\n\n"
        for appdx_style in appdx_styles:
            md += process_appdx_style(appdx_style, law_revision_id, image_dir)
    
    appdx_formats = parent_element.findall("AppdxFormat")
    if appdx_formats:
        md += "# 書式\n\n"
        for appdx_format in appdx_formats:
            md += process_appdx_format(appdx_format, law_revision_id, image_dir)
    
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
# cssは外部で読み込む想定のためコメントアウト
# def get_table_css_style():
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

def parse_to_markdown(xml_content, law_name_override=None, law_revision_id=None, image_dir=None):
    """XMLバイナリデータをMarkdown文字列に変換
    
    Args:
        xml_content: XMLバイナリデータ
        law_name_override: 法令名の上書き
        law_revision_id: 法令履歴ID（画像ダウンロード用）
        image_dir: 画像保存先ディレクトリ
    """
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
    # markdown_text += get_table_css_style()
    # cssスタイルは外部で追加する場合があるためコメントアウト
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
    markdown_text += process_amend_provision(root, law_revision_id, image_dir)
    
    law_body = root.find(".//LawBody")
    if law_body is not None:
        markdown_text += process_all_appdx(law_body, law_revision_id, image_dir)
    
    return markdown_text, law_name, abbrev, law_id, enforcement_date

# ==========================================
# ファイルI/O および API処理関数
# ==========================================

def fetch_law_data(law_name, asof_date=None):
    """e-Gov API v2から法令XMLを取得
    
    Returns:
        tuple: (xml_data, law_revision_id) または (None, None)
    """
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
        law_revision_id = None
        found_title = ""
        
        if data.get("laws"):
            for law in data["laws"]:
                revision = law.get("revision_info", {})
                title = revision.get("law_title", "")
                if title == law_name:
                    law_id = law["law_info"]["law_id"]
                    law_revision_id = revision.get("law_revision_id")
                    found_title = title
                    break
            
            if not law_id and len(data["laws"]) > 0:
                law = data["laws"][0]
                law_id = law["law_info"]["law_id"]
                law_revision_id = law["revision_info"].get("law_revision_id")
                found_title = law["revision_info"]["law_title"]
                print(f"完全一致が見つからないため、'{found_title}' を取得します。")

        if not law_id:
            print(f"Error: '{law_name}' が見つかりませんでした。")
            return None, None

        data_url = f"https://laws.e-gov.go.jp/api/2/law_data/{law_id}"
        data_params = {"response_format": "xml"}
        
        if asof_date:
            data_params["asof"] = asof_date
            print(f"条文データをダウンロード中 (時点: {asof_date})...")
        else:
            print(f"条文データをダウンロード中...")
        
        law_response = requests.get(data_url, params=data_params, timeout=30)
        law_response.raise_for_status()
        
        print(f"[法令履歴ID] {law_revision_id}")
        
        return law_response.content, law_revision_id
        
    except requests.exceptions.RequestException as e:
        print(f"通信エラーが発生しました: {e}")
        return None, None
    except ET.ParseError:
        print("XMLの解析に失敗しました。")
        return None, None

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

def save_markdown_file(law_name, md_output, force_overwrite=False, abbrev=None, law_id=None, enforcement_date=None, image_dir=None):
    """ファイルを保存し、既存ファイルがあれば上書き確認
    
    Args:
        law_name: 法令名
        md_output: Markdown出力
        force_overwrite: 強制上書きフラグ
        abbrev: 略称
        law_id: 法令ID
        enforcement_date: 施行日
        image_dir: 画像保存先ディレクトリ（既に設定済みの場合）
    """
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
    """APIから法令を取得して保存
    
    Args:
        law_name: 法令名
        force: 強制上書きフラグ
        asof_date: 時点指定（YYYY-MM-DD形式）
    """
    xml_data, law_revision_id = fetch_law_data(law_name, asof_date)
    if xml_data:
        # 画像保存ディレクトリを準備
        # まず一時的にパースして法令名と施行日を取得
        root = ET.fromstring(xml_data)
        real_law_name = extract_law_title_from_root(root)
        enforcement_date = None
        if root.tag == "law_data_response":
            rev_info = root.find("revision_info")
            if rev_info is not None:
                enforcement_date = extract_text(rev_info.find("amendment_enforcement_date"))
        
        safe_law_name = "".join(c for c in real_law_name if c not in '<>:"/\\|?*')
        date_suffix = f"_{enforcement_date.replace('-', '')}" if enforcement_date else ""
        output_dir = "output_Markdown"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        image_dir_name = f"{safe_law_name}{date_suffix}_images"
        image_dir = os.path.join(output_dir, image_dir_name)
        
        # 最終的なMarkdownを生成（law_revision_idとimage_dirを渡す）
        md_output, real_law_name, abbrev, law_id, enforcement_date = parse_to_markdown(xml_data, law_name, law_revision_id, image_dir)
        if md_output:
            save_markdown_file(real_law_name, md_output, force_overwrite=force, abbrev=abbrev, law_id=law_id, enforcement_date=enforcement_date, image_dir=image_dir)

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
    parser.add_argument("--no-images", action="store_true", help="画像の自動ダウンロードを無効化")
    
    args = parser.parse_args()
    
    # グローバル変数を引数から設定
    global TABLE_PROCESSING_MODE, TABLE_ROWSPAN_DEBUG, DOWNLOAD_IMAGES
    TABLE_PROCESSING_MODE = args.table_mode
    TABLE_ROWSPAN_DEBUG = args.table_debug
    DOWNLOAD_IMAGES = not args.no_images  # --no-imagesが指定されていない場合はTrue
    
    if TABLE_ROWSPAN_DEBUG:
        print(f"[デバッグ] TABLE_PROCESSING_MODE={TABLE_PROCESSING_MODE}")
        print(f"[デバッグ] TABLE_ROWSPAN_DEBUG=True")
    
    if not DOWNLOAD_IMAGES:
        print(f"[設定] 画像の自動ダウンロード: 無効")

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