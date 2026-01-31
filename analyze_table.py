import xml.etree.ElementTree as ET

tree = ET.parse('道路交通法.xml')
root = tree.getroot()

def get_cell_text(cell):
    text_parts = []
    for elem in cell.iter():
        if elem.text:
            text_parts.append(elem.text.strip())
    return ''.join(text_parts)

print("=" * 80)
print("第七十五条の二十四のテーブル構造分析")
print("=" * 80)

for article in root.findall('.//{*}Article'):
    title = article.find('{*}ArticleTitle')
    if title is not None and '第七十五条の二十四' in ET.tostring(title, encoding='unicode'):
        for table_struct in article.findall('.//{*}TableStruct'):
            for table in table_struct.findall('{*}Table'):
                rows = list(table.findall('{*}TableRow'))
                
                for i, row in enumerate(rows):
                    cols = row.findall('{*}TableColumn')
                    print(f"\n{'='*80}")
                    print(f"Row {i}: {len(cols)}列")
                    
                    for j, col in enumerate(cols):
                        text = get_cell_text(col)
                        rowspan = col.get('rowspan')
                        colspan = col.get('colspan')
                        border_top = col.get('BorderTop')
                        border_bottom = col.get('BorderBottom')
                        border_left = col.get('BorderLeft')
                        border_right = col.get('BorderRight')
                        
                        print(f"\n  Col {j}:")
                        print(f"    rowspan={rowspan}, colspan={colspan}")
                        print(f"    Border: Top={border_top}, Bottom={border_bottom}, Left={border_left}, Right={border_right}")
                        print(f"    Text: {text[:60] if text else '【空】'}")
                        
                        # 異常検出
                        if border_top == 'none' and border_bottom == 'none' and not text:
                            print(f"    ⚠️ 警告: 上下ボーダーがnoneで内容が空 → 前の行のrowspan漏れの可能性")
                        elif border_top == 'none' and not rowspan and text:
                            print(f"    ⚠️ 警告: BorderTop=noneだが内容あり → 前の行からの続きの可能性")
                        elif border_bottom == 'none' and not rowspan:
                            print(f"    ℹ️ 情報: BorderBottom=none → 次の行に続く可能性（rowspan必要？）")

print("\n" + "="*80)
print("分析完了")
print("="*80)
