import re
import math

# --- 定数定義 ---

KANJI_MAP = {
    '〇': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9
}

UNIT_SMALL = {'十': 10, '百': 100, '千': 1000}
UNIT_LARGE = {'万': 10000, '億': 100000000, '兆': 1000000000000}

UNIT_PREFIXES = {
    'ギガ': 'G', 'メガ': 'M', 'キロ': 'k',
    'センチ': 'c', 'ミリ': 'm'
}

UNIT_BASES = {
    # 物理単位
    'メートル': 'm',
    'メートル毎時': 'm/h',
    'メートル毎分': 'm/min',
    'メートル毎秒': 'm/s',
    'メートル毎秒毎秒': 'm/s²',
    'グラム': 'g',
    'トン': 't',
    'リットル': 'L',
    'ニュートン': 'N',
    'ジュール': 'J',
    'ワット': 'W',
    'パーセント': '%',
    'パスカル': 'Pa',
    'ルクス': 'lx',
    'グレイ': 'Gy',
    'デシベル': 'dB',
    'オーム': 'Ω',
    'ヘクタール': 'ha',
    # 助数詞
    '倍': '倍', '枚': '枚', '回': '回',
    '個': '個', '点': '点', '冊': '冊'
}

UNIT_MODIFIERS = {'平方': '²', '立方': '³'}

# --- ヘルパー関数 ---

def parse_kanji_number(s):
    """漢数字文字列を数値(int/float)に変換する"""
    if not s:
        return None
    
    # すでに半角数字のみの場合はfloatとして返す
    if re.fullmatch(r'[0-9.]+', s):
        return float(s)

    # 小数点（・）を含む場合の処理
    if '・' in s:
        parts = s.split('・')
        if len(parts) != 2:
            return None
        
        integer_part = parse_kanji_number(parts[0])
        
        decimal_part_str = ''
        for char in parts[1]:
            if char in KANJI_MAP:
                decimal_part_str += str(KANJI_MAP[char])
            else:
                return None
        
        if integer_part is not None and decimal_part_str:
            return float(f"{integer_part}.{decimal_part_str}")
        return None

    # 位取り記法判定 (「〇」を含む、または十百千万億兆を含まず2文字以上)
    is_positional = '〇' in s or (not re.search(r'[十百千万億兆]', s) and len(s) > 1)
    
    if is_positional:
        res = ''
        for char in s:
            if char in KANJI_MAP:
                res += str(KANJI_MAP[char])
            else:
                return None
        return int(res)

    # 単位付き記法
    total = 0
    section_val = 0
    current_val = 0

    for char in s:
        if char in KANJI_MAP:
            current_val = KANJI_MAP[char]
        elif char in UNIT_SMALL:
            if current_val == 0:
                current_val = 1
            section_val += current_val * UNIT_SMALL[char]
            current_val = 0
        elif char in UNIT_LARGE:
            if current_val > 0:
                section_val += current_val
            if section_val == 0 and current_val == 0:
                section_val = 1
            total += section_val * UNIT_LARGE[char]
            section_val = 0
            current_val = 0
    
    total += section_val + current_val
    return total

def convert_unit_to_symbol(unit_str):
    """単位の変換（記号化するものと、そのままのもの）"""
    current = unit_str
    suffix = ''
    prefix = ''

    # 修飾子 (平方, 立方)
    for key, val in UNIT_MODIFIERS.items():
        if current.startswith(key):
            suffix = val
            current = current[len(key):]
            break
            
    # 接頭辞 (キロ, ミリ...)
    for key, val in UNIT_PREFIXES.items():
        if current.startswith(key):
            prefix = val
            current = current[len(key):]
            break
    
    # 基本単位
    if current in UNIT_BASES:
        base = UNIT_BASES[current]
        return f"{prefix}{base}{suffix}"
    
    return unit_str

def format_currency(num):
    """金額フォーマッター (例: 1億2345万)"""
    if num == 0:
        return '0'
    if not float(num).is_integer():
        return f"{num:,}" # 小数の場合は単純なカンマ区切り

    num = int(num)
    units = ['', '万', '億', '兆']
    parts = []
    n = num
    unit_index = 0

    while n > 0:
        chunk = n % 10000
        if chunk > 0:
            # チャンクごとにカンマ区切り + 単位
            parts.insert(0, f"{chunk:,}{units[unit_index]}")
        n //= 10000
        unit_index += 1
    
    return ''.join(parts)

# --- メイン変換関数 ---

def replace_kanji_references(text):
    if not text:
        return text

    processed = text
    
    # 漢数字のセット
    KANJI_NUM_CLASS = r'[〇一二三四五六七八九十百千万億兆・]+'

    # --- 正規表現定義 ---

    # 1. 金額
    regex_currency = re.compile(f'(金)?({KANJI_NUM_CLASS})(円|銭)')

    # 2. 単位付き数字
    unit_parts = '|'.join(map(re.escape, UNIT_BASES.keys()))
    regex_physical = re.compile(
        f'({KANJI_NUM_CLASS})((?:平方|立方)?(?:ギガ|メガ|キロ|センチ|ミリ)?(?:{unit_parts}))'
    )

    # 3. 法令番号
    regex_law_strict = re.compile(
        f'(第|同)({KANJI_NUM_CLASS})(条|項|号|編|章|節|款|目)'
    )

    # 4. 日付・元号
    regex_date = re.compile(
        r'(明治|大正|昭和|平成|令和)([〇一二三四五六七八九十百千]+)(年|年度|月|日)'
    )

    # 5. 期間・箇所
    regex_count = re.compile(
        r'([〇一二三四五六七八九十百千]+)(箇|か|カ|ヵ)(月|所|国)'
    )

    # 6. 枝番連鎖 (例: 条の二の三)
    regex_branch_chain = re.compile(
        r'([条項号編章節款目])((?:の[〇一二三四五六七八九十百千]+)+)'
    )

    # 7. 別表・別記様式 (例: 別表第一、別記様式第二十二の十一の三)
    regex_table_style = re.compile(
        f'(別表|別記様式|様式)(第)?({KANJI_NUM_CLASS})((?:[のノ][〇一二三四五六七八九十百千]+)*)'
    )

    # --- 適用順序 (JS版と同一) ---

    # A. 金額
    def repl_currency(match):
        prefix = match.group(1) or ''
        num_str = match.group(2)
        unit = match.group(3)
        num = parse_kanji_number(num_str)
        if num is not None:
            return f"{prefix}{format_currency(num)}{unit}"
        return match.group(0)
    
    processed = regex_currency.sub(repl_currency, processed)

    # B. 単位付き数字
    def repl_physical(match):
        num_str = match.group(1)
        unit_str = match.group(2)
        num = parse_kanji_number(num_str)
        symbol = convert_unit_to_symbol(unit_str)
        if num is not None:
            # floatの ".0" を消す簡易処理
            if isinstance(num, float) and num.is_integer():
                num = int(num)
            return f"{num}{symbol}"
        return match.group(0)

    processed = regex_physical.sub(repl_physical, processed)

    # C. 法令番号
    def repl_law(match):
        prefix = match.group(1)
        num_str = match.group(2)
        suffix = match.group(3)
        num = parse_kanji_number(num_str)
        if num is not None:
            return f"{prefix}{num}{suffix}"
        return match.group(0)

    processed = regex_law_strict.sub(repl_law, processed)

    # D. 別表・様式・別記様式
    def repl_table_style(match):
        prefix = match.group(1)
        dai = match.group(2) or '' # "第" は無い場合Noneになるため
        num_str = match.group(3)
        chain = match.group(4)
        
        num = parse_kanji_number(num_str)
        if num is None:
            return match.group(0)
        
        res = f"{prefix}{dai}{num}"
        
        if chain:
            # 枝番部分の数字を変換 (例: "の十一" -> "の11")
            def repl_chain_inner(m):
                n_str = m.group(1)
                n = parse_kanji_number(n_str)
                return f"の{n}" if n is not None else m.group(0)
            
            converted_chain = re.sub(r'[のノ]([〇一二三四五六七八九十百千]+)', repl_chain_inner, chain)
            res += converted_chain
            
        return res

    processed = regex_table_style.sub(repl_table_style, processed)

    # E. 日付
    def repl_date(match):
        prefix = match.group(1)
        num_str = match.group(2)
        suffix = match.group(3)
        num = parse_kanji_number(num_str)
        if num is not None:
            return f"{prefix}{num}{suffix}"
        return match.group(0)

    processed = regex_date.sub(repl_date, processed)

    # F. 期間・箇所
    def repl_count(match):
        num_str = match.group(1)
        # k = match.group(2) # 使わない
        suffix = match.group(3)
        num = parse_kanji_number(num_str)
        if num is not None:
            return f"{num}か{suffix}"
        return match.group(0)

    processed = regex_count.sub(repl_count, processed)

    # G. 枝番連鎖 (条項号などの後ろ)
    def repl_branch_chain(match):
        suffix = match.group(1)
        chain = match.group(2)
        
        def repl_chain_inner(m):
            n_str = m.group(1)
            n = parse_kanji_number(n_str)
            return f"の{n}" if n is not None else m.group(0)

        converted_chain = re.sub(r'[のノ]([〇一二三四五六七八九十百千]+)', repl_chain_inner, chain)
        return f"{suffix}{converted_chain}"

    processed = regex_branch_chain.sub(repl_branch_chain, processed)

    # H. 孤立した漢数字 (JS側でコメントアウトされていたため、ここでもコメントアウト状態とします)
    # regex_isolated = ...
    
    return processed

# --- 実行例 ---
if __name__ == "__main__":
    # テストケース
    test_texts = [
        "金一万五千円を支払う。",
        "時速六十キロメートル毎時で走行する。",
        "第百二十三条の二の五を参照。",
        "別表第一および別記様式第二十二の十一の三に基づく。",
        "令和五年四月一日施行。",
        "三箇月の期間。",
        "七百五十ミリメートル。",
        "千二百三十四倍。",
    ]

    print("--- 変換結果 ---")
    for text in test_texts:
        converted = replace_kanji_references(text)
        print(f"原文: {text}")
        print(f"変換: {converted}")
        print("-" * 20)