# -*- coding: utf-8 -*-
# CSVファイルのマージ
import glob
import pandas as pd

def CsvFileMerge():
    # フォルダ内のファイルパスを取得
    All_Files = glob.glob('./out/*.csv', recursive=True)
    print(All_Files)

    # フォルダ中の全CSVをマージ
    list = []
    for file in All_Files:
        list.append(pd.read_csv(file, index_col=0,
                    encoding='cp932', dtype=object))
        print(file)
        df = pd.concat(list, sort=False)

    # CSV出力
    df.to_csv('national_Control_202302_Average_Cycle.csv')
    print(u'処理終了')

CsvFileMerge()


