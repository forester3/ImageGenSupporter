import os
import re
import subprocess
import ipywidgets as widgets
from IPython.display import HTML, display
import requests

import manual_url_download as mud

TYPE_TO_DIR = {
    "Checkpoint": "checkpoints",
    "LORA": "loras",
    "LoCon": "loras",
    "DoRA": "loras",
    "TextualInversion": "embeddings",
    "Hypernetwork": "hypernetworks",
    "AestheticGradient": "embeddings",
    "VAE": "vae",
    "Controlnet": "controlnet",
    "Upscaler": "upscale_models",
    "MotionModule": "animatediff_models",
    "Poses": "poses",
    "Wildcards": "wildcards",
    "Other": "checkpoints",
}
DEFAULT_SUBDIR = "checkpoints"


def resolve_save_dir(base_dir, model_type):
    subdir = TYPE_TO_DIR.get(model_type, DEFAULT_SUBDIR)
    if model_type not in TYPE_TO_DIR:
        print(f"⚠️ 未知の種別 '{model_type}' のため '{DEFAULT_SUBDIR}' に保存します。")
    return os.path.join(base_dir, subdir)


def parse_model_entry(entry):
    """
    MODEL_DICTの値を解釈する。
    - 数値/文字列 -> (version_id, file_id=None, dir_override=None)
    - 辞書 -> (version_id, file_id, dir_override)
    """
    if isinstance(entry, dict):
        v_id = entry.get("version_id") or entry.get("id")
        f_id = entry.get("file_id")
        return v_id, f_id, entry.get("dir")
    return entry, None, None


def fetch_model_info(version_id, file_id=None):
    """version_id からモデル情報を取得し、file_id が指定されていればそのファイルを特定する"""
    url = f"https://civitai.com/api/v1/model-versions/{version_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            print(f"⚠️ Version ID {version_id} の取得に失敗しました (Status: {res.status_code})")
            return None

        data = res.json()
        files = data.get("files", [])
        if not files:
            print(f"⚠️ Version ID {version_id} にファイルが存在しません。")
            return None

        target_file = None
        # file_id が指定されている場合は該当するファイルを探す
        if file_id is not None:
            target_file = next((f for f in files if f.get("id") == file_id), None)
            if not target_file:
                print(f"⚠️ Version ID {version_id} 内に File ID {file_id} が見つかりません。標準ファイルを使用します。")

        # 未指定、または指定ファイルが見つからない場合は primary を選択
        if not target_file:
            target_file = next((f for f in files if f.get("primary")), files[0])

        return {
            "version_id": version_id,
            "file_id": target_file.get("id"),
            "model_id": data.get("modelId"),
            "name": data["name"],
            "file_name": target_file["name"],
            "download_url": target_file["downloadUrl"],
            "type": data.get("model", {}).get("type", "Other"),
        }
    except Exception as e:
        print(f"Version ID {version_id} の取得中にエラーが発生しました: {e}")
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

        for line in iter(process.stdout.readline, ''):
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
    return exit_code


def get_model_page_url_from_info(info):
    if info and "model_id" in info and "version_id" in info:
        return f"https://civitai.com/models/{info['model_id']}?modelVersionId={info['version_id']}"
    return None


def make_downloader_ui(model_dict, base_dir="./ComfyUI/models"):
    dropdown = widgets.Dropdown(
        options=list(model_dict.keys()),
        description="Model:"
    )
    url_input = widgets.Text(
        placeholder="ここにダウンロードURLを貼って下さい(認証後の直リンクなど)"
    )
    btn_download = widgets.Button(description="Download", button_style="success")
    out = widgets.Output()

    def on_model_changed(change):
        if change["type"] == "change" and change["name"] == "value":
            url_input.value = ""
    dropdown.observe(on_model_changed)

    def on_download_clicked(b):
        out.clear_output()
        with out:
            model_name = dropdown.value
            version_id, file_id, dir_override = parse_model_entry(model_dict[model_name])

            # URL手動入力時
            if url_input.value.strip():
                url = url_input.value.strip()
                if dir_override:
                    save_dir = os.path.join(base_dir, dir_override)
                    print(f"🟢 入力URLからダウンロード中… (モデル: {model_name}, 保存先: {save_dir} [手動指定])")
                else:
                    info = fetch_model_info(version_id, file_id=file_id)
                    model_type = info["type"] if info else "Other"
                    save_dir = resolve_save_dir(base_dir, model_type)
                    print(f"🟢 入力URLからダウンロード中… (モデル: {model_name}, 種別: {model_type} → {save_dir})")
                
                result = mud.download_with_aria2(url, save_dir)
                if result != 0:
                    print(f"⚠️ URLダウンロードに失敗しました: {result}")
                return

            # API参照時
            info = fetch_model_info(version_id, file_id=file_id)
            if info and "download_url" in info:
                if dir_override:
                    save_dir = os.path.join(base_dir, dir_override)
                    print(f"🟢 {model_name} (File: {info['file_name']}) を {save_dir} にダウンロード開始 [手動指定]")
                else:
                    save_dir = resolve_save_dir(base_dir, info["type"])
                    print(f"🟢 {model_name} (File: {info['file_name']}, 種別: {info['type']}) を {save_dir} にダウンロード開始")
                
                result = download_model(info, save_dir)
                if result in (22, 24):
                    print(f"⚠️ {model_name} の取得には認証が必要です。ブラウザでURLを取得して下さい。")
                    page_url = get_model_page_url_from_info(info)
                    if page_url:
                        display(HTML(f'<a href="{page_url}" target="_blank">{model_name} モデルページを開く</a>'))
            else:
                print(f"⚠️ {model_name} のダウンロード情報を取得できませんでした。")

    btn_download.on_click(on_download_clicked)
    display(widgets.VBox([dropdown, url_input, btn_download, out]))