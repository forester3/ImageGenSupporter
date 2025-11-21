import requests
import subprocess
import os, re
import ipywidgets as widgets
from IPython.display import display, HTML

import manual_url_download as mud

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
        "--summary-interval=1",
        "--console-log-level=error",
        "-c", "-x", "16", "-s", "16", "-k", "1M",
        info["download_url"],
        "-d", output_dir,
        "-o", info["file_name"]
    ]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        progress = widgets.IntProgress(min=0, max=100, value=0, description='0%')
        display(progress)

        for line in iter(process.stdout.readline, ''):    # aria2cサマリーから進捗％を抽出
            match = re.search(r'\((\d+)%\)', line)
            if match:
                percent = int(match.group(1))
                progress.value = percent
                progress.description = f"{percent}%"

        process.wait()
        exit_code = process.returncode

        if exit_code == 0:
            progress.value = 100
            progress.description = "100%"
            print("✅ ダウンロードが終了しました。")
        else:
            print(f"⚠️ {info['file_name']} のダウンロードに失敗しました（exit code {exit_code}）。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")
    return exit_code

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

# CivitAI-DL functions
def get_model_page_url_from_version(version_id):
    """モデルバージョンIDから正しいページURLを生成"""
    api_url = f"https://civitai.com/api/v1/model-versions/{version_id}"
    try:
        res = requests.get(api_url).json()
        parent_model_id = res["modelId"]
        page_url = f"https://civitai.com/models/{parent_model_id}?modelVersionId={version_id}"
        return page_url
    except Exception as e:
        print(f"モデルページ取得に失敗: {e}")
        return None

def make_downloader_ui(model_dict, save_dir="./ComfyUI/models/checkpoints"):
    dropdown = widgets.Dropdown(
        options=list(model_dict.keys()),
        description="Model:"
    )
    url_input = widgets.Text(
        placeholder="ここにURLを貼って下さい"
    )
    btn_download = widgets.Button(description="Download", button_style="success")
    out = widgets.Output()

    # モデル切替時にURL欄をクリア
    def on_model_changed(change):
        if change["type"] == "change" and change["name"] == "value":
            url_input.value = ""
    dropdown.observe(on_model_changed)

    def on_download_clicked(b):
        out.clear_output()
        with out:
            # URL入力があればURL優先
            if url_input.value.strip():
                print("🟢 入力URLからダウンロード中…")
                result = mud.download_with_aria2(url_input.value.strip(), save_dir)
                if result != 0:
                    print(f"⚠️ URLダウンロードに失敗しました: {result}")
                return

            # URLが空ならIDダウンロード
            model_name = dropdown.value
            model_id = model_dict[model_name]

            info = fetch_model_info(model_id)
            if info and "download_url" in info:
                print(f"🟢 {model_name} (ID:{model_id}) をダウンロード開始")
                # 既存の download_model(info, output_dir) を使用
                result = download_model(info, save_dir)
                if result == 24:
                    print(f"⚠️ {model_name} の取得には認証が必要です。ブラウザでURLを取得して下さい。")
                    page_url = get_model_page_url_from_version(model_id)
                    if page_url:
                        display(HTML(f'<a href="{page_url}" target="_blank">{model_name} モデルページを開く</a>'))
                    else:
                        print("モデルページが見つかりません。")
            else:
                print(f"⚠️ {model_name} のダウンロードURLを取得できません。")

    btn_download.on_click(on_download_clicked)
    display(widgets.VBox([dropdown, url_input, btn_download, out]))



