import xml.etree.ElementTree as ET

tree = ET.parse('道路交通法.xml')
root = tree.getroot()

def get_cell_text(cell):
    text_parts = []
    for elem in cell.iter():
        if elem.text:
            text_parts.append(elem.text.strip())
    return ''.join(text_parts)

# Row 1-5を詳しく調査
for article in root.findall('.//{*}Article'):
    title = article.find('{*}ArticleTitle')
    if title is not None and '第七十五条の二十四' in ET.tostring(title, encoding='unicode'):
        for table_struct in article.findall('.//{*}TableStruct'):
            for table in table_struct.findall('{*}Table'):
                rows = list(table.findall('{*}TableRow'))
                # Row 1-4を確認
                for i in [0, 1, 2, 3]:
                    if i < len(rows):
                        cols = rows[i].findall('{*}TableColumn')
                        print(f"\nRow {i}:")
                        for j, col in enumerate(cols):
                            text = get_cell_text(col)
                            rowspan = col.get('rowspan')
                            colspan = col.get('colspan')
                            print(f"  Col {j}: rowspan={rowspan}, colspan={colspan}")
                            print(f"    Text: {text[:50] if text else 'EMPTY'}")
