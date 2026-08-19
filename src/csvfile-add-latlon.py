# -*- coding: utf-8 -*-
# コード表を元に読みやすいデータに変換する
import pandas as pd
import csv

# 出力CSVファイルオープン
output_csvfile = "./signal_cycle.csv"
with open(output_csvfile, 'a', encoding='UTF-8') as f:
    # ヘッダー行出力
    fieldnames = ['情報源コード', '交差点番号', '年月', '時間帯', '平均サイクル長', 'lon', 'lat']
    csvfile_writer = csv.DictWriter(
        f, fieldnames=fieldnames, lineterminator='\n')
    csvfile_writer.writeheader()

    # CSVファイルをデータフレームに格納
    data = pd.read_csv(
        "./national_Control_202302_Average_Cycle.csv", dtype=object).values.tolist()

    # 交差点位置を辞書に読み込み
    csv_file_todouhuken = "intersection_position.csv"
    with open(csv_file_todouhuken, mode="r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader)
        # 辞書にデータを追加（キー：情報源コード+交差点番号、値：経度、緯度）
        dict_lonlat = {row[4] + "_" + row[3]: row[1] + "_" + row[2] for row in reader}

    print(len(data))

    for i in range(len(data)):

        # 経度、緯度取得
        lonlat = data[i][0] + "_" + data[i][1]
        if lonlat in dict_lonlat:
            res_lonlat = dict_lonlat[lonlat].split('_')

        # 出力CSVファイルに書き込む
        csvfile_writer.writerow({
            '情報源コード': data[i][0],
            '交差点番号': data[i][1],
            '年月': data[i][2],
            '時間帯': data[i][3],
            '平均サイクル長': data[i][4],
            'lon': res_lonlat[0],
            'lat': res_lonlat[1]
        })

    print(u'処理終了')
