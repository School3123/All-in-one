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

def run_aria2(uri, is_file=False):
    """aria2cを使ってダウンロードを実行"""
    cmd = ["aria2c", "--dir", DOWNLOAD_DIR, "--seed-time=0"]
    
    if is_file:
        # ローカルのTorrentファイルパスの場合
        cmd.append(uri)
    else:
        # MagnetリンクやWeb URLの場合
        cmd.append(uri)
    
    try:
        # バックグラウンドではなく、同期的に実行して結果を表示(長時間は非推奨だが簡易実装のため)
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

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
tab1, tab2, tab3 = st.tabs(["⬇️ Download (Torrent/URL)", "📦 Extract (Zip/Rar/7z)", "file_folder File Share & Server"])

# --- Tab 1: ダウンローダー ---
with tab1:
    st.header("Downloader")
    st.info("Magnetリンク, Web URL, または .torrentファイルを処理します。")

    # 入力タイプ選択
    input_type = st.radio("入力タイプを選択:", ("Magnet Link / Web URL", ".torrent File Upload"))

    if input_type == "Magnet Link / Web URL":
        url_input = st.text_input("URL または Magnet Link を貼り付け:")
        if st.button("ダウンロード開始 (URL/Magnet)"):
            if url_input:
                with st.spinner('aria2cでダウンロード中... (完了までお待ちください)'):
                    success, log = run_aria2(url_input)
                    if success:
                        st.success("ダウンロード完了！")
                    else:
                        st.error("エラーが発生しました。")
                    with st.expander("ログを表示"):
                        st.code(log)
            else:
                st.warning("URLを入力してください。")

    elif input_type == ".torrent File Upload":
        uploaded_torrent = st.file_uploader("Torrentファイルをアップロード", type=["torrent"])
        if uploaded_torrent is not None:
            if st.button("ダウンロード開始 (.torrent)"):
                # 一旦保存
                saved, path = save_uploaded_file(uploaded_torrent, DOWNLOAD_DIR)
                if saved:
                    with st.spinner('aria2cでダウンロード中...'):
                        success, log = run_aria2(path, is_file=True)
                        if success:
                            st.success("ダウンロード完了！")
                            # Torrentファイル自体は削除してもよいが残しておく
                        else:
                            st.error("エラーが発生しました。")
                        with st.expander("ログを表示"):
                            st.code(log)

# --- Tab 2: 解凍ツール ---
with tab2:
    st.header("Archive Extractor")
    
    # downloadディレクトリ内の圧縮ファイルを探す
    all_files = get_files(DOWNLOAD_DIR)
    # 一般的な圧縮形式のみフィルタリング
    archive_files = [f for f in all_files if f.lower().endswith(('.zip', '.rar', '.7z', '.tar', '.gz'))]

    if not archive_files:
        st.write(f"`{DOWNLOAD_DIR}` に圧縮ファイルが見つかりません。")
    else:
        target_archive = st.selectbox("解凍するファイルを選択:", archive_files)
        
        if st.button("解凍を実行"):
            if target_archive:
                try:
                    with st.spinner('解凍中...'):
                        # 出力先フォルダ名を作成（ファイル名に基づく）
                        folder_name = os.path.splitext(os.path.basename(target_archive))[0]
                        out_path = os.path.join(EXTRACT_DIR, folder_name)
                        os.makedirs(out_path, exist_ok=True)
                        
                        patoolib.extract_archive(target_archive, outdir=out_path)
                        st.success(f"解凍成功！ 保存先: `{out_path}`")
                except Exception as e:
                    st.error(f"解凍エラー: {str(e)}")

# --- Tab 3: ファイルサーバー & シェア ---
with tab3:
    st.header("File Server & Share")
    
    col1, col2 = st.columns(2)

    # アップロード機能 (File Share - Send)
    with col1:
        st.subheader("📤 Upload (Share)")
        st.write("ファイルをサーバー(`downloads`フォルダ)にアップロードします。")
        user_file = st.file_uploader("ファイルを選択", accept_multiple_files=True)
        if user_file:
            for f in user_file:
                saved, path = save_uploaded_file(f, DOWNLOAD_DIR)
                if saved:
                    st.toast(f"アップロード完了: {f.name}")

    # ダウンロード機能 (File Downloader - Serve)
    with col2:
        st.subheader("📥 Server Files (Download)")
        st.write("サーバー上のファイルをダウンロードできます。")
        
        # 表示するディレクトリを選択
        view_dir = st.radio("表示ディレクトリ:", [DOWNLOAD_DIR, EXTRACT_DIR])
        
        server_files = get_files(view_dir)
        
        if not server_files:
            st.write("ファイルはありません。")
        else:
            # テーブル風に表示
            for filepath in server_files:
                filename = os.path.basename(filepath)
                filesize = os.path.getsize(filepath) / (1024 * 1024) # MB conversion
                
                c1, c2 = st.columns([3, 1])
                c1.text(f"{filename} ({filesize:.2f} MB)")
                
                with open(filepath, "rb") as f:
                    btn = c2.download_button(
                        label="Download",
                        data=f,
                        file_name=filename,
                        mime="application/octet-stream"
                    )

    if st.button("ファイルリストを更新"):
        st.rerun()
