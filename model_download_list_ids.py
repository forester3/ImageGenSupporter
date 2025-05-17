import requests
import subprocess
import os
import ipywidgets as widgets
from IPython.display import display

def load_model_ids(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return [int(line.strip()) for line in f if line.strip().isdigit()]

def fetch_model_info(model_id):
    url = f"https://civitai.com/api/v1/model-versions/{model_id}"
    try:
        res = requests.get(url).json()
        return {
            "id": model_id,
            "name": res["name"],
            "file_name": res["files"][0]["name"],
            "download_url": res["files"][0]["downloadUrl"]
        }
    except Exception as e:
        print(f"ID {model_id} の取得に失敗: {e}")
        return None

def download_model(info, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    print(f"ダウンロード中: {info['file_name']}")
    cmd = [
        "aria2c",
        "--summary-interval=5",
        "--console-log-level=error",
        "-c", "-x", "16", "-s", "16", "-k", "1M",
        info["download_url"],
        "-d", output_dir,
        "-o", info["file_name"]
    ]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end="")
        process.wait()
        exit_code = process.returncode

        if exit_code == 0:
            print(f"\n{info['file_name']} のダウンロードが正常に終了しました。")
        elif exit_code == 27:
            print(f"\n{info['file_name']} は一部エラーありで完了しました（exit code 27）。")
        else:
            print(f"\n{info['file_name']} のダウンロードに失敗しました（exit code {exit_code}）。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

def create_download_ui(id_file, output_dir):
    model_ids = load_model_ids(id_file)
    model_infos = [fetch_model_info(mid) for mid in model_ids]
    model_infos = [info for info in model_infos if info]

    options = [f'{info["name"]} {info["file_name"]} (ID: {info["id"]})' for info in model_infos]

    select = widgets.SelectMultiple(
        options=options,
        description='選択(Ctrl＋)',
        layout={'width': 'max-content'},
        rows=min(len(options), 10)
    )
    download_button = widgets.Button(description="ダウンロード")
    output = widgets.Output()

    def on_download_clicked(b):
        with output:
            output.clear_output()
            selected = select.value
            if not selected:
                print("何も選択されていません。")
                return
            selected_infos = [info for info in model_infos if f'{info["name"]} {info["file_name"]} (ID: {info["id"]})' in selected]
            for info in selected_infos:
                download_model(info, output_dir)
            print("ダウンロード完了。")

    download_button.on_click(on_download_clicked)
    display(select, download_button, output)
