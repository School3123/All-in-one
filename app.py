import os
import shutil
import patoolib
import mimetypes
import tempfile
from datetime import datetime
from flask import Flask, request, send_file, jsonify, render_template_string, redirect, abort

# --- 設定 ---
BASE_DIR = os.getcwd()
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)

app = Flask(__name__)

# --- ヘルパー関数 ---
def get_size_format(b, factor=1024, suffix="B"):
    """バイト数を人間が読める形式に変換"""
    for unit in ["", "K", "M", "G", "T", "P"]:
        if b < factor:
            return f"{b:.2f}{unit}{suffix}"
        b /= factor
    return f"{b:.2f}Y{suffix}"

def safe_join(base, path):
    """ディレクトリトラバーサル対策を行ったパス結合"""
    if not path:
        return base
    # 結合して絶対パス化
    full_path = os.path.abspath(os.path.join(base, path))
    # ベースディレクトリ以下にあるか確認
    if not full_path.startswith(base):
        raise ValueError("Access denied")
    return full_path

def get_file_info(root_base, subpath):
    """指定されたパスのファイル一覧を取得"""
    target_dir = safe_join(root_base, subpath)
    files = []
    
    try:
        with os.scandir(target_dir) as entries:
            for entry in entries:
                stat = entry.stat()
                
                # アイコンとタイプの決定
                is_dir = entry.is_dir()
                ext = os.path.splitext(entry.name)[1].lower()
                
                icon = "📄"
                if is_dir: icon = "📁"
                elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']: icon = "📦"
                elif ext in ['.mp4', '.mkv', '.avi', '.mov']: icon = "🎬"
                elif ext in ['.mp3', '.wav', '.flac']: icon = "🎵"
                elif ext in ['.jpg', '.png', '.gif', '.webp']: icon = "🖼️"
                elif ext == '.torrent': icon = "🧲"
                elif ext in ['.py', '.js', '.html', '.css', '.json', '.txt', '.md']: icon = "📝"
                
                files.append({
                    "name": entry.name,
                    "path": os.path.join(subpath, entry.name).replace("\\", "/").strip("/"), # JS用相対パス
                    "size": get_size_format(stat.st_size) if not is_dir else "-",
                    "mtime": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                    "icon": icon,
                    "is_archive": ext in ['.zip', '.rar', '.7z', '.tar', '.gz'],
                    "type": "dir" if is_dir else "file",
                    "raw_mtime": stat.st_mtime
                })
    except Exception as e:
        print(f"Error scanning dir: {e}")
        return []
        
    # ディレクトリを先に、その後更新日時順
    return sorted(files, key=lambda x: (x["type"] != "dir", -x["raw_mtime"]))

def get_disk_usage():
    total, used, free = shutil.disk_usage(DOWNLOAD_DIR)
    percent = (used / total) * 100
    return {
        "total": get_size_format(total),
        "used": get_size_format(used),
        "free": get_size_format(free),
        "percent": round(percent, 1)
    }

# --- HTML Template ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pro File Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { background-color: #121212; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { background-color: #1e1e1e; border: 1px solid #333; margin-bottom: 20px; }
        .table { color: #e0e0e0; }
        .table-hover tbody tr:hover { background-color: #2c2c2c; }
        .btn-icon { padding: 0.25rem 0.5rem; font-size: 0.9rem; }
        .cursor-pointer { cursor: pointer; }
        .breadcrumb { background-color: transparent; padding: 0; margin-bottom: 0; }
        .breadcrumb-item a { color: #0d6efd; text-decoration: none; }
        .breadcrumb-item.active { color: #adb5bd; }
        .folder-link:hover { text-decoration: underline; color: #fff; }
    </style>
</head>
<body>

<div class="container py-4">
    <!-- Header & Disk Info -->
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h3 class="m-0"><i class="fa-solid fa-server text-primary"></i> File Manager</h3>
        <div class="text-end small text-muted">
            <span id="diskText">Loading...</span>
            <div class="progress mt-1" style="width: 150px; height: 6px;">
                <div id="diskBar" class="progress-bar bg-success" role="progressbar" style="width: 0%"></div>
            </div>
        </div>
    </div>

    <!-- Upload -->
    <div class="card mb-4">
        <div class="card-body">
            <h5 class="card-title mb-3"><i class="fa-solid fa-cloud-arrow-up"></i> Upload</h5>
            <form id="uploadForm">
                <div class="input-group">
                    <input type="file" class="form-control bg-dark text-light border-secondary" id="fileInput" name="files" multiple>
                    <button class="btn btn-primary" type="button" onclick="uploadFiles()">Start Upload</button>
                </div>
                <!-- Progress -->
                <div id="uploadProgressContainer" class="mt-3 d-none">
                    <div class="progress" style="height: 10px;">
                        <div id="uploadProgressBar" class="progress-bar progress-bar-striped progress-bar-animated" style="width: 0%"></div>
                    </div>
                </div>
            </form>
        </div>
    </div>

    <!-- Browser -->
    <div class="card">
        <div class="card-header bg-dark border-bottom border-secondary">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <ul class="nav nav-pills card-header-pills">
                    <li class="nav-item">
                        <a class="nav-link active" href="#" onclick="switchRoot('downloads', this)">Downloads</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" onclick="switchRoot('extracted', this)">Extracted</a>
                    </li>
                </ul>
                <input type="text" class="form-control form-control-sm w-25 bg-dark text-light border-secondary" id="searchInput" placeholder="Filter..." onkeyup="renderFiles()">
            </div>
            <!-- Breadcrumb Path Display -->
            <nav aria-label="breadcrumb">
                <ol class="breadcrumb" id="breadcrumbList">
                    <li class="breadcrumb-item active">/</li>
                </ol>
            </nav>
        </div>
        
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="table-dark">
                        <tr>
                            <th style="width: 55%">Name</th>
                            <th style="width: 15%">Size</th>
                            <th style="width: 20%">Date</th>
                            <th style="width: 10%" class="text-end">Action</th>
                        </tr>
                    </thead>
                    <tbody id="fileListBody"></tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<!-- Toast -->
<div class="toast-container position-fixed top-0 end-0 p-3">
    <div id="liveToast" class="toast align-items-center text-white bg-success border-0" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="d-flex">
            <div class="toast-body" id="toastMessage"></div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    let currentRoot = 'downloads';
    let currentPath = ''; // current subpath
    let allFiles = []; // loaded files cache

    document.addEventListener('DOMContentLoaded', () => {
        loadFiles();
        updateDisk();
    });

    function switchRoot(root, el) {
        currentRoot = root;
        currentPath = ''; // reset path
        document.querySelectorAll('.nav-link').forEach(e => e.classList.remove('active'));
        el.classList.add('active');
        loadFiles();
    }

    function navigate(relPath) {
        currentPath = relPath;
        loadFiles();
    }

    function goUp() {
        if (!currentPath) return;
        // パスを一つ上に戻す
        const parts = currentPath.split('/');
        parts.pop();
        currentPath = parts.join('/');
        loadFiles();
    }

    function loadFiles() {
        // Build URL parameters
        const url = `/api/list/${currentRoot}?path=${encodeURIComponent(currentPath)}`;
        
        fetch(url)
            .then(r => r.json())
            .then(data => {
                if(data.status === 'error') {
                    showToast(data.message, 'bg-danger');
                    return;
                }
                allFiles = data.files;
                updateBreadcrumb();
                renderFiles();
            });
    }

    function updateBreadcrumb() {
        const ol = document.getElementById('breadcrumbList');
        ol.innerHTML = '';
        
        // Root item
        let li = document.createElement('li');
        li.className = 'breadcrumb-item';
        li.innerHTML = `<a href="#" onclick="navigate('')"><i class="fa-solid fa-house"></i> Root</a>`;
        ol.appendChild(li);

        if (currentPath) {
            const parts = currentPath.split('/');
            let buildPath = '';
            parts.forEach((p, idx) => {
                buildPath += (buildPath ? '/' : '') + p;
                let item = document.createElement('li');
                item.className = 'breadcrumb-item';
                if (idx === parts.length - 1) {
                    item.classList.add('active');
                    item.innerText = p;
                } else {
                    item.innerHTML = `<a href="#" onclick="navigate('${buildPath}')">${p}</a>`;
                }
                ol.appendChild(item);
            });
        }
    }

    function renderFiles() {
        const tbody = document.getElementById('fileListBody');
        tbody.innerHTML = '';
        const filter = document.getElementById('searchInput').value.toLowerCase();

        // "Go Up" row
        if (currentPath) {
            tbody.innerHTML += `
                <tr class="cursor-pointer bg-dark" onclick="goUp()">
                    <td colspan="4"><i class="fa-solid fa-level-up-alt me-2"></i> .. (Go Up)</td>
                </tr>
            `;
        }

        const filtered = allFiles.filter(f => f.name.toLowerCase().includes(filter));
        
        if (filtered.length === 0) {
            tbody.innerHTML += '<tr><td colspan="4" class="text-center py-3 text-muted">Empty or no match.</td></tr>';
            return;
        }

        filtered.forEach(f => {
            let actions = '';
            let nameHtml = '';

            if (f.type === 'dir') {
                // Folder logic
                nameHtml = `<span class="folder-link cursor-pointer fw-bold text-info" onclick="navigate('${f.path}')">${f.icon} ${f.name}</span>`;
                // ZIP Download Button
                actions += `<a href="/api/zip/${currentRoot}?path=${encodeURIComponent(f.path)}" class="btn btn-sm btn-outline-info btn-icon me-1" title="Download as ZIP"><i class="fa-solid fa-file-zipper"></i> ZIP</a>`;
                // Delete
                actions += `<button class="btn btn-sm btn-outline-danger btn-icon" onclick="deleteItem('${f.path}')"><i class="fa-solid fa-trash"></i></button>`;
            } else {
                // File logic
                nameHtml = `<span>${f.icon} ${f.name}</span>`;
                // Extract (if archive)
                if (f.is_archive && currentRoot === 'downloads') {
                    actions += `<button class="btn btn-sm btn-outline-warning btn-icon me-1" onclick="extractItem('${f.path}')"><i class="fa-solid fa-box-open"></i></button>`;
                }
                // Download
                actions += `<a href="/api/download/${currentRoot}?path=${encodeURIComponent(f.path)}" class="btn btn-sm btn-outline-primary btn-icon me-1" target="_blank"><i class="fa-solid fa-download"></i></a>`;
                // Delete
                actions += `<button class="btn btn-sm btn-outline-danger btn-icon" onclick="deleteItem('${f.path}')"><i class="fa-solid fa-trash"></i></button>`;
            }

            const row = `
                <tr>
                    <td>${nameHtml}</td>
                    <td class="small text-muted">${f.size}</td>
                    <td class="small text-muted">${f.mtime}</td>
                    <td class="text-end">${actions}</td>
                </tr>
            `;
            tbody.innerHTML += row;
        });
    }

    function uploadFiles() {
        const input = document.getElementById('fileInput');
        if (input.files.length === 0) return showToast("No files selected.", "bg-warning");

        const formData = new FormData();
        for (let i = 0; i < input.files.length; i++) {
            formData.append('files', input.files[i]);
        }
        // Upload to current path
        formData.append('target_path', currentPath);

        const xhr = new XMLHttpRequest();
        document.getElementById('uploadProgressContainer').classList.remove('d-none');
        const pBar = document.getElementById('uploadProgressBar');

        xhr.upload.addEventListener("progress", (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                pBar.style.width = pct + "%";
            }
        });

        xhr.onload = () => {
            document.getElementById('uploadProgressContainer').classList.add('d-none');
            pBar.style.width = "0%";
            if (xhr.status === 200) {
                showToast("Upload success!", "bg-success");
                input.value = '';
                loadFiles();
                updateDisk();
            } else {
                showToast("Upload failed.", "bg-danger");
            }
        };

        xhr.open("POST", "/api/upload");
        xhr.send(formData);
    }

    function deleteItem(path) {
        if(!confirm(`Delete "${path}"?`)) return;
        fetch(`/api/delete/${currentRoot}?path=${encodeURIComponent(path)}`, {method: 'POST'})
            .then(r => r.json())
            .then(d => {
                if(d.status === 'ok') {
                    showToast("Deleted.", "bg-success");
                    loadFiles();
                    updateDisk();
                } else {
                    showToast("Error: " + d.message, "bg-danger");
                }
            });
    }

    function extractItem(path) {
        showToast("Extracting...", "bg-info");
        fetch(`/api/extract?path=${encodeURIComponent(path)}`, {method: 'POST'})
            .then(r => r.json())
            .then(d => {
                if(d.status === 'ok') showToast("Extracted!", "bg-success");
                else showToast("Extract error: " + d.message, "bg-danger");
            });
    }

    function updateDisk() {
        fetch('/api/disk').then(r => r.json()).then(d => {
            document.getElementById('diskText').innerText = `Free: ${d.free} / ${d.total}`;
            const bar = document.getElementById('diskBar');
            bar.style.width = d.percent + "%";
            bar.className = `progress-bar ${d.percent > 90 ? 'bg-danger' : 'bg-success'}`;
        });
    }

    function showToast(msg, cls) {
        const el = document.getElementById('liveToast');
        document.getElementById('toastMessage').innerText = msg;
        el.className = `toast align-items-center text-white border-0 ${cls}`;
        new bootstrap.Toast(el).show();
    }
</script>
</body>
</html>
"""

# --- API Endpoints ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/list/<root_name>')
def list_files(root_name):
    """ファイル一覧取得（サブフォルダ対応）"""
    base = DOWNLOAD_DIR if root_name == 'downloads' else EXTRACT_DIR
    subpath = request.args.get('path', '')
    
    try:
        files = get_file_info(base, subpath)
        return jsonify({"status": "ok", "files": files})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/download/<root_name>')
def download_file(root_name):
    """単一ファイルダウンロード"""
    base = DOWNLOAD_DIR if root_name == 'downloads' else EXTRACT_DIR
    subpath = request.args.get('path', '')
    
    try:
        full_path = safe_join(base, subpath)
        if os.path.isfile(full_path):
            return send_file(full_path, as_attachment=True)
        else:
            return abort(404, "File not found")
    except Exception as e:
        return abort(400, str(e))

@app.route('/api/zip/<root_name>')
def download_zip(root_name):
    """フォルダをZIP圧縮してダウンロード"""
    base = DOWNLOAD_DIR if root_name == 'downloads' else EXTRACT_DIR
    subpath = request.args.get('path', '')
    
    try:
        target_dir = safe_join(base, subpath)
        if not os.path.isdir(target_dir):
            return abort(400, "Target is not a directory")
            
        # フォルダ名を取得
        folder_name = os.path.basename(target_dir) or root_name
        
        # 一時ファイルとしてZIPを作成
        # tempfile.mkstempだとクリーンアップが面倒なので、メモリに乗るサイズか、
        # または shutil.make_archive で一時ディレクトリに作る
        temp_dir = tempfile.mkdtemp()
        archive_base = os.path.join(temp_dir, folder_name)
        
        # ZIP作成 (shutilは拡張子.zipを自動付与するのでbaseだけ渡す)
        zip_path = shutil.make_archive(archive_base, 'zip', target_dir)
        
        # ファイル送信後に削除するためのコールバック付きレスポンスを作るのが理想だが
        # Flask標準では難しいため、送信してOSの一時領域掃除に任せるか、
        # またはレスポンス後に削除する仕組みを入れる。
        # ここではシンプルに send_file して、一時ディレクトリは残るがOS再起動で消える前提とする
        # (Codespacesならコンテナ再起動で消えます)
        
        return send_file(zip_path, as_attachment=True, download_name=f"{folder_name}.zip")
        
    except Exception as e:
        return abort(400, str(e))

@app.route('/api/upload', methods=['POST'])
def upload_files():
    """現在のカレントフォルダにアップロード"""
    target_path_rel = request.form.get('target_path', '')
    base = DOWNLOAD_DIR # Uploads always go to downloads root or subfolders
    
    try:
        save_dir = safe_join(base, target_path_rel)
        if not os.path.exists(save_dir):
            return jsonify({"status": "error", "message": "Directory not found"}), 404

        if 'files' in request.files:
            for f in request.files.getlist('files'):
                if f.filename:
                    f.save(os.path.join(save_dir, f.filename))
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/delete/<root_name>', methods=['POST'])
def delete_item(root_name):
    base = DOWNLOAD_DIR if root_name == 'downloads' else EXTRACT_DIR
    subpath = request.args.get('path', '')
    
    try:
        target = safe_join(base, subpath)
        if os.path.isfile(target):
            os.remove(target)
        elif os.path.isdir(target):
            shutil.rmtree(target)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/extract', methods=['POST'])
def extract_archive():
    subpath = request.args.get('path', '')
    
    try:
        src = safe_join(DOWNLOAD_DIR, subpath)
        # 解凍先フォルダ名
        folder_name = os.path.splitext(os.path.basename(src))[0]
        dst = os.path.join(EXTRACT_DIR, folder_name)
        
        os.makedirs(dst, exist_ok=True)
        patoolib.extract_archive(src, outdir=dst)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/disk')
def disk_usage():
    return jsonify(get_disk_usage())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
