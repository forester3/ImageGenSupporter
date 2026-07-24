import requests
import subprocess
import os, re
import ipywidgets as widgets
from IPython.display import display, HTML

import manual_url_download as mud

# --- CivitAIの種別 -> ComfyUIの保存先フォルダ名 マッピング ---
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
    "Other": "checkpoints",  # フォールバック
}
DEFAULT_SUBDIR = "checkpoints"


def resolve_save_dir(base_dir, model_type):
    """CivitAIの種別からComfyUIの保存先パスを決定する"""
    subdir = TYPE_TO_DIR.get(model_type, DEFAULT_SUBDIR)
    if model_type not in TYPE_TO_DIR:
        print(f"⚠️ 未知の種別 '{model_type}' のため '{DEFAULT_SUBDIR}' に保存します。")
    return os.path.join(base_dir, subdir)


def parse_model_entry(entry):
    """
    MODEL_DICTの値を解釈する。
    - entry が int/文字列の数字 -> (id, dir_override=None)
    - entry が {"id": 数字, "dir": "フォルダ名"} の辞書 -> (id, dir_override)
      "dir" は省略可能(その場合は自動判定に任せる)
    """
    if isinstance(entry, dict):
        return entry["id"], entry.get("dir")
    return entry, None


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
            "download_url": res["files"][0]["downloadUrl"],
            "type": res.get("model", {}).get("type", "Other"),
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

def create_download_ui(id_file, base_dir):
    """
    base_dir: ComfyUIの models フォルダ (例: f"{HOME_DIR}/ComfyUI/models")
    各モデルは種別ごとに自動で適切なサブフォルダに振り分けられる。
    id_file内の各IDは数字のみ(こちらのUIは保存先上書きには非対応)。
    """
    model_ids = load_model_ids(id_file)
    model_infos = [fetch_model_info(mid) for mid in model_ids]
    model_infos = [info for info in model_infos if info]

    options = [f'{info["name"]} {info["file_name"]} (ID: {info["id"]}) [{info["type"]}]' for info in model_infos]

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
            selected_infos = [
                info for info in model_infos
                if f'{info["name"]} {info["file_name"]} (ID: {info["id"]}) [{info["type"]}]' in selected
            ]
            for info in selected_infos:
                save_dir = resolve_save_dir(base_dir, info["type"])
                print(f"種別: {info['type']} → 保存先: {save_dir}")
                download_model(info, save_dir)
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


def make_downloader_ui(model_dict, base_dir="./ComfyUI/models"):
    """
    base_dir: ComfyUIの models フォルダ (例: f"{HOME_DIR}/ComfyUI/models")
    種別(Checkpoint/LoRA/VAEなど)ごとに自動でサブフォルダへ保存する。
    """
    dropdown = widgets.Dropdown(
        options=list(model_dict.keys()),
        description="Model:"
    )
    url_input = widgets.Text(
        placeholder="ここにダウンロードURLを貼って下さい(認証後の直リンクなど)"
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
            model_name = dropdown.value
            model_id, dir_override = parse_model_entry(model_dict[model_name])

            # URL入力があればURL優先(認証が必要なモデルをブラウザ経由で取得した場合など)
            if url_input.value.strip():
                url = url_input.value.strip()
                if dir_override:
                    save_dir = os.path.join(base_dir, dir_override)
                    print(f"🟢 入力URLからダウンロード中… (モデル: {model_name}, 保存先: {save_dir} [手動指定])")
                else:
                    # 種別判定は現在ドロップダウンで選択中のモデルのIDを使う
                    # (このURL自体は認証後のB2直リンク等でmodelVersionIdを含まないため)
                    info = fetch_model_info(model_id)
                    model_type = info["type"] if info else "Other"
                    if info is None:
                        print(f"⚠️ {model_name} (ID:{model_id}) の情報取得に失敗しました。")
                    save_dir = resolve_save_dir(base_dir, model_type)
                    print(f"🟢 入力URLからダウンロード中… (モデル: {model_name}, 種別: {model_type} → {save_dir})")
                result = mud.download_with_aria2(url, save_dir)
                if result != 0:
                    print(f"⚠️ URLダウンロードに失敗しました: {result}")
                return

            # URLが空ならIDダウンロード
            info = fetch_model_info(model_id)
            if info and "download_url" in info:
                if dir_override:
                    save_dir = os.path.join(base_dir, dir_override)
                    print(f"🟢 {model_name} (ID:{model_id}) を {save_dir} にダウンロード開始 [手動指定]")
                else:
                    save_dir = resolve_save_dir(base_dir, info["type"])
                    print(f"🟢 {model_name} (ID:{model_id}, 種別:{info['type']}) を {save_dir} にダウンロード開始")
                # 既存の download_model(info, output_dir) を使用
                result = download_model(info, save_dir)
                if result == 24 or result == 22:
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
