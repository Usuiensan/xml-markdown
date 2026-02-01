import requests
import re

# 平成11年法令第127号（不正競争防止法の一部を改正する法律の施行期日を定める政令）
url = 'https://laws.e-gov.go.jp/api/2/law_data/411AC0000000127'
params = {'response_format': 'xml'}

print("XMLデータを取得中...")
response = requests.get(url, params=params, timeout=30)

if response.status_code == 200:
    content = response.text
    
    # Fig要素を検索
    if '<Fig' in content:
        figs = re.findall(r'<Fig[^>]*src="([^"]+)"', content)
        print(f'\n見つかった画像: {len(figs)}個')
        for i, fig in enumerate(figs[:10], 1):
            print(f'  {i}. {fig}')
    else:
        print('Fig要素が見つかりませんでした')
else:
    print(f'HTTPエラー: {response.status_code}')
