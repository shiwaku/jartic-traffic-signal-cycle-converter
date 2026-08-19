import requests
import os

# URLの基本部分
base_url = "https://www.tmt.or.jp/research/index10_"

# ダウンロードするURL番号の範囲（2から47まで）
start_num = 2
end_num = 47

# HTMLファイルを保存するディレクトリ
save_dir = "HTML"

# ディレクトリが存在しない場合は作成
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

# 指定された範囲のURLからHTMLファイルをダウンロードし、ローカルに保存
for i in range(start_num, end_num + 1):
    url = f"{base_url}{i}.html"
    response = requests.get(url)

    # レスポンスが正常な場合（HTTPステータスコードが200の場合）
    if response.status_code == 200:
        # ファイル名をURLから抽出
        filename = url.split("/")[-1]

        # ファイルを保存するパスを作成
        save_path = os.path.join(save_dir, filename)

        # ファイルを書き込みモードで開き、ダウンロードした内容を保存
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(response.text)

        print(f"ダウンロード成功: {url} -> {save_path}")

    else:
        print(f"ダウンロード失敗: {url} (HTTPステータスコード: {response.status_code})")
