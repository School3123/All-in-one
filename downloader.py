import sys
import os
import subprocess
import shutil

# 保存先
DOWNLOAD_DIR = os.path.abspath("downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Magnet用トラッカーリスト
TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://9.rarbg.com:2810/announce",
    "udp://tracker.openbittorrent.com:80/announce",
    "udp://opentracker.i2p.rocks:6969/announce",
    "https://tracker.tamersunion.org:443/announce",
    "http://tracker1.itzmx.com:8080/announce",
    "udp://tracker.torrent.eu.org:451/announce"
]

def main():
    if not shutil.which("aria2c"):
        print("❌ エラー: aria2c がインストールされていません。")
        print("実行してください: sudo apt-get install -y aria2")
        return

    if len(sys.argv) < 2:
        print("\n📥 Simple Terminal Downloader")
        print("使い方: python downloader.py \"<URL or Magnet or FilePath>\"")
        return

    target = sys.argv[1].strip()
    
    # 基本コマンド構築
    cmd = [
        "aria2c",
        f"--dir={DOWNLOAD_DIR}",
        "--seed-time=0",            # 完了後シードしない
        "--summary-interval=1",     # 1秒ごとに更新
        "--max-connection-per-server=16",
        "--file-allocation=none",   # 省メモリ: ファイル事前確保なし
        "--disk-cache=0",           # 省メモリ: キャッシュなし
        f"--bt-tracker={','.join(TRACKERS)}"
    ]
    
    # 入力タイプ判定
    if os.path.isfile(target):
        # ローカルファイル (.torrentなど)
        print(f"📄 ローカルファイルを読み込み: {target}")
        cmd.append(target)
    else:
        # URL / Magnet
        print(f"🔗 リンクをダウンロード: {target[:60]}...")
        cmd.append(target)

    print("-" * 40)
    print("🚀 ダウンロードを開始します (Ctrl+C で停止)")
    print("-" * 40)

    try:
        # ターミナルに直接出力させる
        subprocess.run(cmd)
        print("\n✅ 処理が終了しました。")
    except KeyboardInterrupt:
        print("\n🛑 ユーザーにより停止されました。")

if __name__ == "__main__":
    main()
