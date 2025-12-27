import os
import shutil
import patoolib
import tempfile
from datetime import datetime
from flask import Flask, request, send_file, jsonify, render_template_string, abort

# --- 設定 ---
BASE_DIR = os.getcwd()
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)

app = Flask(__name__)

# --- ヘルパー関数 ---
def get_size_format(b, factor=1024, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P"]:
        if b < factor:
            return f"{b:.2f}{unit}{suffix}"
        b /= factor
    return f"{b:.2f}Y{suffix}"

def safe_join(base, path):
    """ディレクトリトラバーサル対策を行ったパス結合"""
    if not path:
        return base
    full_path = os.path.abspath(os.path.join(base, path))
    if not full_path.startswith(base):
        raise ValueError("Access denied")
    return full_path

def get_file_info(root_base, subpath):
    target_dir = safe_join(root_base, subpath)
    files = []
    
    try:
        with os.scandir(target_dir) as entries:
            for entry in entries:
                stat = entry.stat()
                is_dir = entry.is_dir()
                ext = os.path.splitext(entry.name)[1].lower()
                
                # アイコンとタイプの決定
                icon = "📄"
                if is_dir: icon = "📁"
                elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']: icon = "📦"
                elif ext in ['.mp4', '.mkv', '.avi', '.mov']: icon = "🎬"
                elif ext in ['.mp3', '.wav', '.flac']: icon = "🎵"
                elif ext in ['.jpg', '.png', '.gif', '.webp']: icon = "🖼️"
                
                files.append({
                    "name": entry.name,
                    "path": os.path.join(subpath, entry.name).replace("\\", "/").strip("/"),
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
        
    return sorted(files, key=lambda x: (x["type"] != "dir", -x["raw_mtime"]))

def get_disk_usage():
    total, used, free = shutil.disk_usage(DOWNLOAD_DIR)
    percent = (used / total) * 100
    return {
        "total": get_size_format(total),
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
    <title>File Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { background-color: #121212; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { background-color: #1e1e1e; border: 1px solid #333; margin-bottom: 20px; }
        .table { color: #e0e0e0; }
        .table-hover tbody tr:hover { background-color: #2c2c2c; }
        .folder-link:hover { text-decoration: underline; color: #fff; cursor: pointer; }
        .breadcrumb-item a { text-decoration: none; color: #0d6efd; }
    </style>
</head>
<body>

<div class="container py-4">
    <!-- Header -->
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
            <div class="input-group">
                <input type="file" class="form-control bg-dark text-light border-secondary" id="fileInput" multiple>
                <button class="btn btn-primary" onclick="uploadFiles()">Start Upload</button>
            </div>
            <div id="uploadProgressContainer" class="mt-2 d-none">
                <div class="progress" style="height: 10px;">
                    <div id="uploadProgressBar" class="progress-bar progress-bar-striped progress-bar-animated" style="width: 0%"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- Browser -->
    <div class="card">
        <div class="card-header bg-dark border-bottom border-secondary">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <ul class="nav nav-pills card-header-pills">
                    <li class="nav-item"><a class="nav-link active" href="#" onclick="switchRoot('downloads', this)">Downloads</a></li>
                    <li class="nav-item"><a class="nav-link" href="#" onclick="switchRoot('extracted', this)">Extracted</a></li>
                </ul>
                <button class="btn btn-sm btn-outline-secondary" onclick="loadFiles()">🔄 Refresh</button>
            </div>
            <nav aria-label="breadcrumb">
                <ol class="breadcrumb mb-0" id="breadcrumbList"></ol>
            </nav>
        </div>
        
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="table-dark">
                        <tr>
                            <th style="width: 50%">Name</th>
                            <th style="width: 15%">Size</th>
                            <th style="width: 20%">Date</th>
                            <th style="width: 15%" class="text-end">Actions</th>
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
    let currentPath = '';

    document.addEventListener('DOMContentLoaded', () => { loadFiles(); updateDisk(); });

    function switchRoot(root, el) {
        currentRoot = root;
        currentPath = '';
        document.querySelectorAll('.nav-link').forEach(e => e.classList.remove('active'));
        el.classList.add('active');
        loadFiles();
    }

    function navigate(path) {
        currentPath = path;
        loadFiles();
    }

    function goUp() {
        if (!currentPath) return;
        const parts = currentPath.split('/');
        parts.pop();
        currentPath = parts.join('/');
        loadFiles();
    }

    function loadFiles() {
        fetch(`/api/list/${currentRoot}?path=${encodeURIComponent(currentPath)}`)
            .then(r => r.json())
            .then(data => {
                renderFiles(data.files);
                updateBreadcrumb();
            });
    }

    function renderFiles(files) {
        const tbody = document.getElementById('fileListBody');
        tbody.innerHTML = '';

        if (currentPath) {
            tbody.innerHTML += `<tr class="bg-dark" onclick="goUp()" style="cursor:pointer;"><td colspan="4"><i class="fa-solid fa-level-up-alt"></i> .. (Go Up)</td></tr>`;
        }

        if (!files || files.length === 0) {
            tbody.innerHTML += '<tr><td colspan="4" class="text-center text-muted">No files found.</td></tr>';
            return;
        }

        files.forEach(f => {
            let actions = '';
            let nameHtml = '';

            if (f.type === 'dir') {
                nameHtml = `<span class="folder-link fw-bold text-info" onclick="navigate('${f.path}')">${f.icon} ${f.name}</span>`;
                // フォルダZIPダウンロード
                actions += `<a href="/api/zip/${currentRoot}?path=${encodeURIComponent(f.path)}" class="btn btn-sm btn-outline-info me-1" title="Download ZIP"><i class="fa-solid fa-file-zipper"></i> ZIP</a>`;
                actions += `<button class="btn btn-sm btn-outline-danger" onclick="deleteItem('${f.path}')"><i class="fa-solid fa-trash"></i></button>`;
            } else {
                nameHtml = `<span>${f.icon} ${f.name}</span>`;
                
                // ★ 解凍ボタン (Archiveのみ表示) ★
                if (f.is_archive && currentRoot === 'downloads') {
                    actions += `<button class="btn btn-sm btn-warning text-dark fw-bold me-2" onclick="extractItem('${f.path}')"><i class="fa-solid fa-box-open"></i> 解凍</button>`;
                }

                // ダウンロードボタン
                actions += `<a href="/api/download/${currentRoot}?path=${encodeURIComponent(f.path)}" class="btn btn-sm btn-outline-primary me-1"><i class="fa-solid fa-download"></i> DL</a>`;
                // 削除ボタン
                actions += `<button class="btn btn-sm btn-outline-danger" onclick="deleteItem('${f.path}')"><i class="fa-solid fa-trash"></i></button>`;
            }

            tbody.innerHTML += `
                <tr>
                    <td>${nameHtml}</td>
                    <td class="small text-muted">${f.size}</td>
                    <td class="small text-muted">${f.mtime}</td>
                    <td class="text-end">${actions}</td>
                </tr>
            `;
        });
    }

    function updateBreadcrumb() {
        const ol = document.getElementById('breadcrumbList');
        ol.innerHTML = `<li class="breadcrumb-item"><a href="#" onclick="navigate('')">Root</a></li>`;
        if (currentPath) {
            let acc = '';
            currentPath.split('/').forEach((p, i, arr) => {
                acc += (acc ? '/' : '') + p;
                if (i === arr.length - 1) ol.innerHTML += `<li class="breadcrumb-item active text-light">${p}</li>`;
                else ol.innerHTML += `<li class="breadcrumb-item"><a href="#" onclick="navigate('${acc}')">${p}</a></li>`;
            });
        }
    }

    function extractItem(path) {
        showToast("解凍を開始しました...", "bg-info");
        fetch(`/api/extract?path=${encodeURIComponent(path)}`, {method: 'POST'})
            .then(r => r.json())
            .then(d => {
                if(d.status === 'ok') showToast("✅ 解凍完了！ (Extractedタブを確認)", "bg-success");
                else showToast("❌ 解凍エラー: " + d.message, "bg-danger");
            });
    }

    function deleteItem(path) {
        if(!confirm(`削除しますか？\n${path}`)) return;
        fetch(`/api/delete/${currentRoot}?path=${encodeURIComponent(path)}`, {method: 'POST'})
            .then(() => {
                showToast("削除しました", "bg-secondary");
                loadFiles();
                updateDisk();
            });
    }

    function uploadFiles() {
        const input = document.getElementById('fileInput');
        if (input.files.length === 0) return;
        
        const formData = new FormData();
        for (let f of input.files) formData.append('files', f);
        formData.append('target_path', currentPath);

        const xhr = new XMLHttpRequest();
        document.getElementById('uploadProgressContainer').classList.remove('d-none');
        const pBar = document.getElementById('uploadProgressBar');

        xhr.upload.onprogress = (e) => {
            if(e.lengthComputable) pBar.style.width = Math.round((e.loaded / e.total) * 100) + "%";
        };
        xhr.onload = () => {
            document.getElementById('uploadProgressContainer').classList.add('d-none');
            pBar.style.width = "0%";
            showToast("アップロード完了！", "bg-success");
            input.value = '';
            loadFiles();
            updateDisk();
        };
        xhr.open("POST", "/api/upload");
        xhr.send(formData);
    }

    function updateDisk() {
        fetch('/api/disk').then(r => r.json()).then(d => {
            document.getElementById('diskText').innerText = `Free: ${d.free} / ${d.total}`;
            document.getElementById('diskBar').style.width = d.percent + "%";
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

# --- API ---
@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/list/<root_name>')
def list_files(root_name):
    base = DOWNLOAD_DIR if root_name == 'downloads' else EXTRACT_DIR
    try:
        files = get_file_info(base, request.args.get('path', ''))
        return jsonify({"status": "ok", "files": files})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/download/<root_name>')
def download_file(root_name):
    base = DOWNLOAD_DIR if root_name == 'downloads' else EXTRACT_DIR
    try:
        return send_file(safe_join(base, request.args.get('path', '')), as_attachment=True)
    except Exception as e:
        return abort(404)

@app.route('/api/zip/<root_name>')
def zip_folder(root_name):
    base = DOWNLOAD_DIR if root_name == 'downloads' else EXTRACT_DIR
    try:
        target = safe_join(base, request.args.get('path', ''))
        folder_name = os.path.basename(target) or root_name
        temp_dir = tempfile.mkdtemp()
        zip_path = shutil.make_archive(os.path.join(temp_dir, folder_name), 'zip', target)
        return send_file(zip_path, as_attachment=True, download_name=f"{folder_name}.zip")
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/extract', methods=['POST'])
def extract():
    try:
        src = safe_join(DOWNLOAD_DIR, request.args.get('path', ''))
        folder_name = os.path.splitext(os.path.basename(src))[0]
        dst = os.path.join(EXTRACT_DIR, folder_name)
        os.makedirs(dst, exist_ok=True)
        patoolib.extract_archive(src, outdir=dst)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/delete/<root_name>', methods=['POST'])
def delete(root_name):
    base = DOWNLOAD_DIR if root_name == 'downloads' else EXTRACT_DIR
    try:
        t = safe_join(base, request.args.get('path', ''))
        if os.path.isfile(t): os.remove(t)
        else: shutil.rmtree(t)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/upload', methods=['POST'])
def upload():
    try:
        save_dir = safe_join(DOWNLOAD_DIR, request.form.get('target_path', ''))
        for f in request.files.getlist('files'):
            if f.filename: f.save(os.path.join(save_dir, f.filename))
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/disk')
def disk(): return jsonify(get_disk_usage())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
