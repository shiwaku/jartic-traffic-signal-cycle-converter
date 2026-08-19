# -*- coding: utf-8 -*-
import os
import csv
import json
import datetime
import time
import configparser
import requests
import zipfile
from io import StringIO
import io

# 都道府県名（ローマ字）のリストを作成する
PrefRomanlist = []

# csvファイルの読み込み
with open('D:/交通データ/JARTIC/kousaten_PrefRoman.csv') as f:
    # header = next(csv.reader(f))
    for row in csv.reader(f):
        s = row[0]
        PrefRomanlist.append(s)

# print(PrefRomanlist)

# 更新日・作成日を入力する
UpdateDate = '202304030911'
CreDate = '2023_02'

# 出力フォルダパスを作成する
OutFolderPath = 'D:/交通データ/JARTIC/03_交差点制御情報/'

# フォルダを作成する
new_dir_path = OutFolderPath + UpdateDate
os.mkdir(new_dir_path)

# 都道府県名のリストでループ
for PrefRoman in PrefRomanlist:
    # URL指定
    url = "https://www.jartic.or.jp/d/opendata/" + \
        UpdateDate + "/typeC_" + PrefRoman + "_" + CreDate + ".zip"
    # データをURLから取得する
    r = requests.get(url, stream=True)
    # zipファイルとして保存する
    saveFile = new_dir_path + "/" + "typeC_" + PrefRoman + "_" + CreDate + ".zip"
    with open(saveFile, 'wb') as f:
        f.write(r.content)
        print(PrefRoman)

print(u'処理終了')
