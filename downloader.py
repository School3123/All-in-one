import sys
import os

# --- Codespaces対策: システムのライブラリパスを追加 ---
# これがないと 'ModuleNotFoundError: No module named 'libtorrent'' になります
sys.path.append("/usr/lib/python3/dist-packages")

import time
import requests
from urllib.parse import urlparse, unquote

# libtorrentのインポート
try:
    import libtorrent as lt
except ImportError:
    # パスを追加してもダメな場合の最終手段ガイダンス
    print("❌ エラー: libtorrent が読み込めません。")
    print("以下のコマンドで実行してみてください:")
    print("/usr/bin/python3 downloader.py \"リンク\"")
    sys.exit(1)

# 保存先フォルダの設定
SAVE_PATH = './downloads'

def get_filename_from_cd(cd):
    """Content-Dispositionヘッダーからファイル名を取得"""
    if not cd:
        return None
    fname = None
    if 'filename=' in cd:
        try:
            fname = cd.split('filename=')[1].strip('"\'')
        except:
            pass
    return fname

def download_http(url):
    """普通のURL（直リンク）からのダウンロード"""
    print(f"🔗 HTTP接続を開始: {url}")
    
    # ブラウザのふりをするためのヘッダー
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        with requests.get(url, stream=True, headers=headers) as r:
            r.raise_for_status()
            
            filename = get_filename_from_cd(r.headers.get('content-disposition'))
            if not filename:
                filename = os.path.basename(urlparse(url).path)
            if not filename or len(filename) < 2:
                filename = "downloaded_file.dat"
            
            if not os.path.exists(SAVE_PATH):
                os.makedirs(SAVE_PATH)
            
            full_path = os.path.join(SAVE_PATH, unquote(filename))
            total_length = r.headers.get('content-length')

            print(f"📥 ダウンロード開始: {filename}")

            with open(full_path, 'wb') as f:
                if total_length is None or int(total_length) == 0:
                    # サイズ不明の場合はそのまま書き込む
                    f.write(r.content)
                else:
                    dl = 0
                    total_length = int(total_length)
                    for data in r.iter_content(chunk_size=8192):
                        dl += len(data)
                        f.write(data)
                        
                        # ゼロ除算防止
                        if total_length > 0:
                            done = int(50 * dl / total_length)
                            percent = (dl / total_length) * 100
                            sys.stdout.write(f"\r[{'=' * done}{' ' * (50-done)}] {percent:.2f}%")
                            sys.stdout.flush()
            
            print(f"\n✅ 完了: {full_path}")

    except Exception as e:
        print(f"\n❌ エラー: {e}")

def download_torrent_session(handle):
    """Torrentのダウンロードループ処理"""
    print(f"⏳ メタデータを取得中... (最大60秒待機)")
    
    timeout = 0
    while not handle.has_metadata():
        time.sleep(1)
        timeout += 1
        if timeout % 10 == 0:
            print(f"   ...待機中 ({timeout}秒経過)")
        if timeout > 60:
            print("\n⚠️ タイムアウト: メタデータの取得に失敗しました。ピアが見つからない可能性があります。")
            return

    info = handle.get_torrent_info()
    print(f"📥 Torrent開始: {info.name()}")

    while not handle.is_seed():
        s = handle.status()
        progress = s.progress * 100
        
        state_str = ['Queued', 'Check', 'DL Meta', 'DL', 'Done', 'Seed', 'Alloc']
        state = state_str[s.state] if s.state < len(state_str) else 'Unknown'

        sys.stdout.write(
            f'\r[{state}] {progress:.2f}% '
            f'(↓{s.download_rate / 1000:.1f} kB/s, '
            f'↑{s.upload_rate / 1000:.1f} kB/s, '
            f'Peers: {s.num_peers})'
        )
        sys.stdout.flush()
        time.sleep(1)
    
    print("\n✅ Torrentダウンロード完了！")

def download_torrent(source_type, source_data):
    """Torrentダウンロード処理（Libtorrent 2.x対応版）"""
    if not os.path.exists(SAVE_PATH):
        os.makedirs(SAVE_PATH)

    # セッション設定
    ses = lt.session()
    ses.listen_on(6881, 6891)
    
    handle = None

    try:
        if source_type == 'magnet':
            print("🧲 マグネットリンクを解析中...")
            atp = lt.parse_magnet_uri(source_data)
            atp.save_path = SAVE_PATH
            handle = ses.add_torrent(atp)
        
        elif source_type == 'file':
            print(f"📄 Torrentファイルを読み込み中: {source_data}")
            info = lt.torrent_info(source_data)
            
            atp = lt.add_torrent_params()
            atp.ti = info
            atp.save_path = SAVE_PATH
            handle = ses.add_torrent(atp)

        download_torrent_session(handle)

    except Exception as e:
        print(f"\n❌ Torrentエラー: {e}")
        print("ヒント: マグネットリンクが正しいか、またはファイルが壊れていないか確認してください。")

def main():
    if len(sys.argv) < 2:
        print("使用法: python downloader.py \"<リンク または ファイルパス>\"")
        sys.exit(1)

    input_str = sys.argv[1]

    # 1. マグネットリンク
    if input_str.startswith("magnet:?"):
        download_torrent('magnet', input_str)

    # 2. Web上のURL (http/https)
    elif input_str.startswith("http://") or input_str.startswith("https://"):
        if input_str.lower().endswith(".torrent") or ".torrent?" in input_str.lower():
            print("🌐 Web上の.torrentファイルを検出。一時ダウンロードします...")
            try:
                # User-Agentを追加して拒否を防ぐ
                headers = {'User-Agent': 'Mozilla/5.0'}
                r = requests.get(input_str, headers=headers)
                temp_file = "temp_auto.torrent"
                with open(temp_file, 'wb') as f:
                    f.write(r.content)
                download_torrent('file', temp_file)
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"❌ .torrent取得エラー: {e}")
        else:
            download_http(input_str)

    # 3. ローカルファイル
    elif os.path.isfile(input_str):
        download_torrent('file', input_str)
    
    else:
        print("❌ エラー: 指定されたファイルまたはリンクが見つかりません。")

if __name__ == "__main__":
    main()
