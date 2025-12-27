import os
import patoolib
import shutil
from flask import Flask, request, send_from_directory, render_template_string, redirect

# --- 設定 ---
DOWNLOAD_DIR = os.path.abspath("downloads")
EXTRACT_DIR = os.path.abspath("extracted")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)

app = Flask(__name__)

# --- デザイン (HTML/CSS) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Manager & Share</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f0f2f5; padding-top: 20px; }
        .card { box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: none; margin-bottom: 20px; }
        .btn-action { width: 40px; }
        .nav-tabs .nav-link.active { background-color: #fff; border-bottom-color: #fff; font-weight: bold; }
    </style>
</head>
<body>
<div class="container">
    <h2 class="mb-4 text-center">📂 File Manager & Share</h2>

    <div class="row">
        <!-- Upload Section -->
        <div class="col-md-12">
            <div class="card">
                <div class="card-header bg-primary text-white">📤 Upload to Server</div>
                <div class="card-body">
                    <form action="/upload" method="post" enctype="multipart/form-data" class="d-flex gap-2">
                        <input type="file" name="files" class="form-control" multiple>
                        <button class="btn btn-primary" type="submit">Upload</button>
                    </form>
                    <small class="text-muted">PCからサーバーへファイルを転送します。Torrentファイルもここでアップロードできます。</small>
                </div>
            </div>
        </div>

        <!-- File List Section -->
        <div class="col-md-12">
            <div class="card">
                <div class="card-header bg-white">
                    <ul class="nav nav-tabs card-header-tabs">
                        <li class="nav-item"><a class="nav-link active" data-bs-toggle="tab" href="#dl-tab">📥 Downloads</a></li>
                        <li class="nav-item"><a class="nav-link" data-bs-toggle="tab" href="#ex-tab">📦 Extracted</a></li>
                    </ul>
                </div>
                <div class="card-body">
                    <div class="tab-content">
                        <!-- Downloads Tab -->
                        <div class="tab-pane fade show active" id="dl-tab">
                            <div class="d-flex justify-content-end mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="location.reload()">🔄 Refresh</button>
                            </div>
                            <div class="list-group">
                                {% for f in downloads %}
                                <div class="list-group-item d-flex justify-content-between align-items-center">
                                    <div class="text-truncate" style="max-width: 60%;" title="{{f}}">
                                        {% if f.endswith('.torrent') %}🧲{% else %}📄{% endif %} {{f}}
                                    </div>
                                    <div class="btn-group">
                                        {% if f.endswith(('.zip','.rar','.7z','.tar','.gz')) %}
                                        <a href="/extract/downloads/{{f}}" class="btn btn-sm btn-outline-warning" title="Extract">📦 Unzip</a>
                                        {% endif %}
                                        <a href="/download/downloads/{{f}}" class="btn btn-sm btn-outline-success" title="Download to PC">⬇️ DL</a>
                                        <a href="/delete/downloads/{{f}}" class="btn btn-sm btn-outline-danger" onclick="return confirm('Delete?')" title="Delete">🗑️</a>
                                    </div>
                                </div>
                                {% else %}
                                <div class="text-center text-muted py-4">No files found. Use terminal to download files.</div>
                                {% endfor %}
                            </div>
                        </div>
                        
                        <!-- Extracted Tab -->
                        <div class="tab-pane fade" id="ex-tab">
                            <div class="d-flex justify-content-end mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="location.reload()">🔄 Refresh</button>
                            </div>
                            <div class="list-group">
                                {% for f in extracted %}
                                <div class="list-group-item d-flex justify-content-between align-items-center">
                                    <div class="text-truncate" style="max-width: 80%;" title="{{f}}">📂 {{f}}</div>
                                    <div class="btn-group">
                                        <a href="/download/extracted/{{f}}" class="btn btn-sm btn-outline-success">⬇️ DL</a>
                                        <a href="/delete/extracted/{{f}}" class="btn btn-sm btn-outline-danger" onclick="return confirm('Delete?')">🗑️</a>
                                    </div>
                                </div>
                                {% else %}
                                <div class="text-center text-muted py-4">No extracted files.</div>
                                {% endfor %}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# --- ルーティング ---
@app.route('/')
def index():
    # 更新日時順にソート
    dl = sorted(os.listdir(DOWNLOAD_DIR), key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_DIR, x)), reverse=True)
    ex = sorted(os.listdir(EXTRACT_DIR), key=lambda x: os.path.getmtime(os.path.join(EXTRACT_DIR, x)), reverse=True)
    return render_template_string(HTML_TEMPLATE, downloads=dl, extracted=ex)

@app.route('/upload', methods=['POST'])
def upload():
    if 'files' in request.files:
        for f in request.files.getlist('files'):
            if f.filename:
                f.save(os.path.join(DOWNLOAD_DIR, f.filename))
    return redirect('/')

@app.route('/download/<folder>/<path:filename>')
def download(folder, filename):
    d = DOWNLOAD_DIR if folder == 'downloads' else EXTRACT_DIR
    return send_from_directory(d, filename, as_attachment=True)

@app.route('/delete/<folder>/<path:filename>')
def delete(folder, filename):
    d = DOWNLOAD_DIR if folder == 'downloads' else EXTRACT_DIR
    path = os.path.join(d, filename)
    try:
        if os.path.isfile(path): os.remove(path)
        else: shutil.rmtree(path)
    except Exception as e:
        print(e)
    return redirect('/')

@app.route('/extract/downloads/<path:filename>')
def extract(filename):
    try:
        src = os.path.join(DOWNLOAD_DIR, filename)
        dst = os.path.join(EXTRACT_DIR, os.path.splitext(filename)[0])
        os.makedirs(dst, exist_ok=True)
        patoolib.extract_archive(src, outdir=dst)
    except Exception as e:
        print(f"Error: {e}")
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
