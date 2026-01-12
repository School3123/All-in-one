# 📂 Terminal Downloader & Web File Manager

ダウンロード処理とファイル管理を分離した、安定的で高速なファイル管理システムです。
**重いダウンロード処理はターミナル**で行い、**ファイル管理と共有はWebブラウザ**で行います。

## ⚙️ 準備 (Setup)

Codespacesのターミナルで以下のコマンドを1回だけ実行して、必要なツールをインストールします。

```bash
# 1. ツール (aria2, 7zip, unrar) のインストール
sudo apt-get update && sudo apt-get install -y aria2 p7zip-full unrar

# 2. Pythonライブラリのインストール
pip install flask patool
