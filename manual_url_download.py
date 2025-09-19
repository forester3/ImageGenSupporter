import os
import subprocess
from ipywidgets import Output
from IPython.display import display, clear_output
import sys
from urllib.parse import urlparse, parse_qs, unquote
import re
import time

def get_filename_from_query(url):
    query = urlparse(url).query
    params = parse_qs(query)
    if 'response-content-disposition' in params:
        content_disp = params['response-content-disposition'][0]
        m = re.search(r'filename="?([^\";]+)"?', content_disp)
        if m:
            return m.group(1)
    return None

def get_filename(url):
    filename = get_filename_from_query(url)
    if filename:
        return filename
    path = urlparse(url).path
    filename = os.path.basename(path)
    filename = unquote(filename)
    if not filename:
        filename = 'downloaded_file'
    return filename

def download_with_aria2(url, save_dir):
    filename = get_filename(url)
    os.makedirs(save_dir, exist_ok=True)
    print(f"ダウンロード中: {filename}")
    cmd = [
        "aria2c",
        "--summary-interval=5",
        "--console-log-level=error",
        "-c", "-x", "16", "-s", "16", "-k", "1M",
        url,
        "-d", save_dir,
        "-o", filename
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end="")
    process.wait()
    exit_code = process.returncode

    if exit_code == 0:
        print(f"\n✅ {filename} のダウンロードが正常に終了しました。")
    else:
        print(f"\n⚠️ {filename} のダウンロード失敗しました(exit code {exit_code})")
        
    return exit_code

def download(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    for i in range(0, len(lines), 2):
        save_dir = lines[i].strip()
        url = lines[i + 1].strip()
        download_with_aria2(url, save_dir)
