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

# --- 関数群 ---

def run_aria2_live(uri, is_file=False):
    """
    aria2cを使ってダウンロードを実行し、進捗をリアルタイム表示する
    """
    cmd = ["aria2c", "--dir", DOWNLOAD_DIR, "--seed-time=0", "--summary-interval=1"]
    
    if is_file:
        cmd.append(uri)
    else:
        cmd.append(uri)

    # ターミナル表示用のプレースホルダーを作成
    terminal_title = st.empty()
    terminal_window = st.empty()
    terminal_title.write("### 📟 Terminal Output")
    
    # ログを蓄積するリスト
    output_buffer = []

    try:
        # Popenでプロセスを開始（出力をパイプで取得）
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # エラーも標準出力に含める
            text=True,
            bufsize=1, # 行バッファリング
            universal_newlines=True
        )

        # プロセスが終了するまでループ
        while True:
            # 1行読み込む
            line = process.stdout.readline()
            
            if not line and process.poll() is not None:
                break
            
            if line:
                # ログに追加
                line = line.strip()
                if line:
                    output_buffer.append(line)
                    
                    # UI更新: 最新の20行を表示（スクロールのような挙動にする）
                    # aria2cの進捗バーは大量の行を吐く場合があるため、表示を間引くか最新のみ表示
                    display_log = "\n".join(output_buffer[-20:]) 
                    terminal_window.code(display_log, language="bash")

        return process.poll() == 0, output_buffer

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
    for root, dirs, filenames in os.walk(directory):
        for filename in filenames:
            filepath = os.path.join(root, filename)
            files.append(filepath)
    return files

# --- UI構築 (Streamlit) ---
st.set_page_config(page_title="All-in-One File Manager", layout="wide")
st.title("📂 All-in-One Downloader & File Manager")

# タブの定義
tab1, tab2, tab3 = st.tabs(["⬇️ Download (Live Terminal)", "📦 Extract", "file_folder File Share"])

# --- Tab 1: ダウンローダー (ライブ表示版) ---
with tab1:
    st.header("Downloader")
    st.info("Magnetリンク, Web URL, または .torrentファイルを処理します。")

    # 入力タイプ選択
    input_type = st.radio("入力タイプを選択:", ("Magnet Link / Web URL", ".torrent File Upload"))

    if input_type == "Magnet Link / Web URL":
        url_input = st.text_input("URL または Magnet Link を貼り付け:")
        if st.button("ダウンロード開始 (URL/Magnet)"):
            if url_input:
                st.write("起動中...")
                success, log = run_aria2_live(url_input)
                if success:
                    st.success("✅ ダウンロード完了！")
                else:
                    st.error("❌ エラーが発生しました。")
            else:
                st.warning("URLを入力してください。")

    elif input_type == ".torrent File Upload":
        uploaded_torrent = st.file_uploader("Torrentファイルをアップロード", type=["torrent"])
        if uploaded_torrent is not None:
            if st.button("ダウンロード開始 (.torrent)"):
                saved, path = save_uploaded_file(uploaded_torrent, DOWNLOAD_DIR)
                if saved:
                    st.write("起動中...")
                    success, log = run_aria2_live(path, is_file=True)
                    if success:
                        st.success("✅ ダウンロード完了！")
                    else:
                        st.error("❌ エラーが発生しました。")

# --- Tab 2: 解凍ツール ---
with tab2:
    st.header("Archive Extractor")
    
    all_files = get_files(DOWNLOAD_DIR)
    archive_files = [f for f in all_files if f.lower().endswith(('.zip', '.rar', '.7z', '.tar', '.gz'))]

    if not archive_files:
        st.write(f"`{DOWNLOAD_DIR}` に圧縮ファイルが見つかりません。")
    else:
        target_archive = st.selectbox("解凍するファイルを選択:", archive_files)
        
        if st.button("解凍を実行"):
            if target_archive:
                # 解凍もログが見えるように簡易的なライブ表示を実装
                term_placeholder = st.empty()
                term_placeholder.code(f"Extracting: {target_archive} ...", language="bash")
                try:
                    folder_name = os.path.splitext(os.path.basename(target_archive))[0]
                    out_path = os.path.join(EXTRACT_DIR, folder_name)
                    os.makedirs(out_path, exist_ok=True)
                    
                    # patoolは標準出力キャプチャが難しいため同期実行し完了を表示
                    patoolib.extract_archive(target_archive, outdir=out_path)
                    
                    term_placeholder.code(f"Extracting: {target_archive} ... Done!\nSaved to: {out_path}", language="bash")
                    st.success(f"解凍成功！")
                except Exception as e:
                    st.error(f"解凍エラー: {str(e)}")

# --- Tab 3: ファイルサーバー & シェア ---
with tab3:
    st.header("File Server & Share")
    
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📤 Upload (Share)")
        st.write("ファイルをサーバーへアップロード")
        user_file = st.file_uploader("ファイルを選択", accept_multiple_files=True)
        if user_file:
            for f in user_file:
                saved, path = save_uploaded_file(f, DOWNLOAD_DIR)
                if saved:
                    st.toast(f"アップロード完了: {f.name}")

    with col2:
        st.subheader("📥 Server Files (Download)")
        st.write("サーバー上のファイルをダウンロード")
        
        view_dir = st.radio("表示ディレクトリ:", [DOWNLOAD_DIR, EXTRACT_DIR])
        
        server_files = get_files(view_dir)
        
        if not server_files:
            st.info("ファイルはありません。")
        else:
            # 最新のファイルが上に来るようにソート
            server_files.sort(key=os.path.getmtime, reverse=True)
            
            for filepath in server_files:
                filename = os.path.basename(filepath)
                try:
                    filesize = os.path.getsize(filepath) / (1024 * 1024)
                except:
                    filesize = 0
                
                c1, c2 = st.columns([3, 1])
                c1.text(f"{filename} ({filesize:.2f} MB)")
                
                with open(filepath, "rb") as f:
                    btn = c2.download_button(
                        label="Download",
                        data=f,
                        file_name=filename,
                        mime="application/octet-stream",
                        key=filepath # ユニークキーを設定
                    )

    if st.button("🔄 ファイルリスト更新"):
        st.rerun()
