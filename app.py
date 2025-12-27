import streamlit as st
import subprocess
import os
import shutil
import patoolib
import time
from glob import glob

# --- 設定 ---
DOWNLOAD_DIR = "downloads"
EXTRACT_DIR = "extracted"

# ディレクトリの作成
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)

# --- 重要なトラッカーリスト (CodespacesでMagnetを動かすために必須) ---
TRACKERS_LIST = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://9.rarbg.com:2810/announce",
    "udp://tracker.openbittorrent.com:80/announce",
    "udp://opentracker.i2p.rocks:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "https://tracker.tamersunion.org:443/announce",
    "http://tracker1.itzmx.com:8080/announce"
]
TRACKERS_STR = ",".join(TRACKERS_LIST)

# --- 関数群 ---

def run_aria2_live(uri, is_file=False):
    """
    aria2cを使ってダウンロードを実行し、進捗をリアルタイム表示する
    """
    # 基本オプション
    # --bt-tracker: トラッカーを追加してピアを見つけやすくする
    # --seed-time=0: ダウンロード完了後にシード（アップロード）をしない
    # --allow-overwrite=true: 同名ファイルがあってもエラーにしない
    cmd = [
        "aria2c", 
        f"--dir={os.path.abspath(DOWNLOAD_DIR)}", 
        "--seed-time=0", 
        "--summary-interval=1",
        "--allow-overwrite=true",
        f"--bt-tracker={TRACKERS_STR}" 
    ]
    
    if is_file:
        cmd.append(uri)
    else:
        cmd.append(uri)

    # ターミナル表示用のUI
    st.write("### 📟 Terminal Output")
    terminal_window = st.empty()
    
    output_buffer = []

    try:
        # Popenでプロセスを開始
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        start_time = time.time()
        
        while True:
            line = process.stdout.readline()
            
            if not line and process.poll() is not None:
                break
            
            if line:
                line = line.strip()
                if line:
                    output_buffer.append(line)
                    # 最新の15行を表示
                    terminal_window.code("\n".join(output_buffer[-15:]), language="bash")

        if process.returncode == 0:
            return True, output_buffer
        else:
            return False, output_buffer

    except Exception as e:
        return False, [str(e)]

def save_uploaded_file(uploaded_file, dest_dir):
    try:
        path = os.path.join(dest_dir, uploaded_file.name)
        with open(path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return True, path
    except Exception as e:
        return False, str(e)

def get_files(directory):
    files = []
    # 絶対パスで取得してトラブル回避
    abs_directory = os.path.abspath(directory)
    for root, dirs, filenames in os.walk(abs_directory):
        for filename in filenames:
            filepath = os.path.join(root, filename)
            files.append(filepath)
    return files

# --- UI構築 (Streamlit) ---
st.set_page_config(page_title="All-in-One File Manager", layout="wide")
st.title("📂 All-in-One Downloader & File Manager")

# ファイルリスト更新用のセッションステート
if 'refresh' not in st.session_state:
    st.session_state['refresh'] = 0

# タブの定義
tab1, tab2, tab3 = st.tabs(["⬇️ Download (Live)", "📦 Extract", "file_folder File Share"])

# --- Tab 1: ダウンローダー ---
with tab1:
    st.header("Downloader")
    st.caption("MagnetリンクやURLを入力してください。Codespaces環境向けにトラッカーを自動追加します。")

    input_type = st.radio("入力タイプ:", ("Magnet Link / Web URL", ".torrent File Upload"), horizontal=True)

    if input_type == "Magnet Link / Web URL":
        url_input = st.text_input("URL / Magnet Link:")
        if st.button("Download Start", type="primary"):
            if url_input:
                st.info("aria2cを起動しました...")
                success, log = run_aria2_live(url_input)
                if success:
                    st.success("✅ ダウンロード完了！ 'File Share' タブを確認してください。")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ エラーが発生しました。ログを確認してください。")
            else:
                st.warning("URLを入力してください。")

    elif input_type == ".torrent File Upload":
        uploaded_torrent = st.file_uploader("Torrentファイルをアップロード", type=["torrent"])
        if uploaded_torrent is not None:
            if st.button("Download Start (.torrent)", type="primary"):
                saved, path = save_uploaded_file(uploaded_torrent, DOWNLOAD_DIR)
                if saved:
                    st.info("aria2cを起動しました...")
                    success, log = run_aria2_live(path, is_file=True)
                    if success:
                        st.success("✅ ダウンロード完了！")
                        st.rerun()
                    else:
                        st.error("❌ エラーが発生しました。")

# --- Tab 2: 解凍ツール ---
with tab2:
    st.header("Archive Extractor")
    
    if st.button("ファイルリストを更新", key="refresh_extract"):
        st.rerun()

    all_files = get_files(DOWNLOAD_DIR)
    archive_files = [f for f in all_files if f.lower().endswith(('.zip', '.rar', '.7z', '.tar', '.gz'))]

    if not archive_files:
        st.info(f"圧縮ファイルが見つかりません。({DOWNLOAD_DIR})")
    else:
        # パスが見やすいようにファイル名だけ表示する辞書を作成
        file_map = {os.path.basename(f): f for f in archive_files}
        selected_filename = st.selectbox("解凍するファイル:", list(file_map.keys()))
        
        if st.button("解凍を実行", type="primary"):
            target_path = file_map[selected_filename]
            st.code(f"Extracting: {selected_filename} ...", language="bash")
            try:
                folder_name = os.path.splitext(selected_filename)[0]
                out_path = os.path.join(EXTRACT_DIR, folder_name)
                os.makedirs(out_path, exist_ok=True)
                
                patoolib.extract_archive(target_path, outdir=out_path)
                
                st.success(f"✅ 解凍成功！ 保存先: extracted/{folder_name}")
            except Exception as e:
                st.error(f"解凍エラー: {str(e)}")

# --- Tab 3: ファイルサーバー & シェア ---
with tab3:
    st.header("File Server & Share")
    
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("📤 Upload to Server")
        user_file = st.file_uploader("PCからサーバーへ送信", accept_multiple_files=True)
        if user_file:
            for f in user_file:
                saved, path = save_uploaded_file(f, DOWNLOAD_DIR)
                if saved:
                    st.toast(f"アップロード完了: {f.name}")
            time.sleep(1)
            st.rerun()

    with col2:
        st.subheader("📥 Download from Server")
        
        # ディレクトリ選択
        dir_option = st.radio("フォルダ選択:", ["downloads (Raw Files)", "extracted (Unzipped)"], horizontal=True)
        target_dir = DOWNLOAD_DIR if "downloads" in dir_option else EXTRACT_DIR

        # ファイル一覧取得
        server_files = get_files(target_dir)

        if not server_files:
            st.warning("ファイルがありません。")
        else:
            # 新しい順にソート
            server_files.sort(key=os.path.getmtime, reverse=True)
            
            st.write(f"**Files in {dir_option}:**")
            for filepath in server_files:
                filename = os.path.basename(filepath)
                try:
                    size_mb = os.path.getsize(filepath) / (1024 * 1024)
                except:
                    size_mb = 0
                
                # レイアウト
                c1, c2 = st.columns([3, 1])
                c1.text(f"📄 {filename} ({size_mb:.2f} MB)")
                
                # ダウンロードボタン
                # ファイルを開いてボタンに渡す
                with open(filepath, "rb") as f:
                    file_data = f.read()
                    c2.download_button(
                        label="⬇️ Download",
                        data=file_data,
                        file_name=filename,
                        mime="application/octet-stream",
                        key=f"btn_{filepath}"
                    )
                st.divider()

    if st.button("🔄 最新の情報に更新"):
        st.rerun()
