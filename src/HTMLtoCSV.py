import csv
import glob
from bs4 import BeautifulSoup
import os

# CSVファイルからデータを読み込み、辞書に格納
filename_mapping = {}
with open('source_code_information.csv', 'r', newline='', encoding='utf-8') as csvfile:
    csv_reader = csv.reader(csvfile)
    next(csv_reader)  # ヘッダー行をスキップ
    for row in csv_reader:
        filename, code, police, prefecture = row
        filename_mapping[filename] = {
            'code': code, 'police': police, 'prefecture': prefecture}

# 新しいCSVファイルにデータを書き込む
with open('intersection_position.csv', 'w', newline='', encoding='utf-8') as csvfile:
    csv_writer = csv.writer(csvfile)

    # ヘッダー行を書き込む
    header = ['value', 'lon', 'lat', '交差点番号', '情報源コード', '都道府県警察名', '都道府県']
    csv_writer.writerow(header)

    # ファイル名が index10_*.html の形式に一致するすべてのファイルを開く
    for filepath in glob.glob("./HTML/index10_*.html"):
        filename = os.path.basename(filepath)
        with open(filepath, encoding='utf-8') as file:
            html = file.read()

            # HTMLを解析
            soup = BeautifulSoup(html, 'html.parser')

            # 辞書から情報源コード、都道府県警察名、都道府県を取得
            info = filename_mapping.get(filename)
            if info:
                code = info['code']
                police = info['police']
                prefecture = info['prefecture']
            else:
                code = ''
                police = ''
                prefecture = ''

            # optionタグを取得し、CSV形式に変換
            for option in soup.find_all('option'):
                value = option.get('value')
                lon = option.get('lon')
                lat = option.get('lat')
                text = option.text

                if value and lon and lat:
                    row = [value, lon, lat, text, code, police, prefecture]
                    csv_writer.writerow(row)

print('CSVファイルに情報を追加し、変換が完了しました。')
