import csv
import os
from collections import defaultdict
from datetime import datetime
from glob import glob

# CSVファイルを処理し、平均サイクル長を計算する関数
def process_csv(input_csv_file, output_csv_file):
    with open(input_csv_file, "r") as f:
        rows = list(csv.reader(f))[1:]

    # 時間帯ごとの平均サイクル長を計算するためのデータ構造
    combination_hour_based_cycles = defaultdict(lambda: defaultdict(list))

    # 入力CSVファイルの行を処理
    for row in rows:
        timestamp, info_code, intersection, cycle_length = row[:4]
        dt = datetime.strptime(timestamp, "%Y/%m/%d %H:%M")
        year_month = dt.strftime("%Y%m")
        hour = dt.hour
        key = (info_code, intersection, year_month)
        combination_hour_based_cycles[key][hour].append(int(cycle_length))

    # 平均サイクル長を計算
    average_cycle_lengths = []
    for key, hour_based_cycles in combination_hour_based_cycles.items():
        for hour, cycle_lengths in hour_based_cycles.items():
            avg_cycle_length = sum(cycle_lengths) / len(cycle_lengths)
            info_code, intersection, year_month = key
            average_cycle_lengths.append(
                (info_code, intersection, year_month, hour, avg_cycle_length))
    
    # 出力CSVファイルに平均サイクル長を書き込む
    with open(output_csv_file, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["情報源コード", "交差点番号", "年月", "時間帯", "平均サイクル長"])
        for info_code, intersection, year_month, hour, avg_cycle_length in average_cycle_lengths:
            writer.writerow([info_code, intersection, year_month,
                            f"{hour:02d}:00", f"{avg_cycle_length:.2f}"])

# 入力フォルダと出力フォルダを指定
input_folder = "data"
output_folder = "out"
os.makedirs(output_folder, exist_ok=True)

# 入力フォルダ内のサブフォルダを取得
subfolders = [f.path for f in os.scandir(input_folder) if f.is_dir()]

# サブフォルダ内のCSVファイルを処理
for subfolder in subfolders:
    input_csv_files = glob(os.path.join(subfolder, "*制御*.csv"))

    for input_csv_file in input_csv_files:
        # 出力ファイル名を作成
        output_csv_file = os.path.join(output_folder, os.path.splitext(
            os.path.basename(input_csv_file))[0] + "_平均サイクル長.csv")
        process_csv(input_csv_file, output_csv_file)
        print(f"結果が {output_csv_file} に出力されました。")
