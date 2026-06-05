# -*- coding: utf-8 -*-
"""
Standalone FastAPI web server for M1 document parsing engine.
Endpoints: GET /, POST /parse, GET /status
"""

from __future__ import annotations

import json
import logging
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, File, Form, UploadFile
    from fastapi.responses import HTMLResponse
except ImportError:
    FastAPI = None

# ===========================================================================
# Component availability
# ===========================================================================

def _safe_has(pkg: str) -> bool:
    """Check if a package is importable WITHOUT triggering segfaults.
    Uses subprocess to isolate the import — if it crashes, only the subprocess dies."""
    import subprocess, sys
    try:
        r = subprocess.run(
            [sys.executable, "-c", f"import {pkg}"],
            capture_output=True, timeout=10
        )
        return r.returncode == 0
    except Exception:
        return False

def _tesseract_ok() -> bool:
    """True only if both pytesseract wrapper AND tesseract binary are present."""
    if not _safe_has("pytesseract"):
        return False
    import shutil
    if shutil.which("tesseract"):
        return True
    from pathlib import Path
    for p in [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
              r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]:
        if Path(p).exists():
            return True
    return False

_COMPONENTS = {
    "backends": {
        "docling": {"ok": _safe_has("docling"), "name": "Docling (IBM)", "install": "pip install docling>=2.94.0"},
        "marker":  {"ok": False, "name": "Marker (skeleton stub)", "install": "pip install marker-pdf"},
        "mineru":  {"ok": False, "name": "MinerU (skeleton stub)", "install": "pip install magic-pdf"},
    },
    "ocr": {
        "easyocr":   {"ok": _safe_has("easyocr"), "name": "EasyOCR", "install": "pip install easyocr"},
        "paddleocr": {"ok": _safe_has("paddleocr"), "name": "PaddleOCR", "install": "pip install paddlepaddle paddleocr"},
        "tesseract": {"ok": _tesseract_ok(), "name": "Tesseract", "install": "pip install pytesseract + install tesseract binary from https://github.com/UB-Mannheim/tesseract/wiki"},
        "suryaocr":  {"ok": False, "name": "SuryaOCR (not supported by Docling pipeline)", "install": "Not supported. Use PaddleOCR or EasyOCR instead."},
    },
}

# ===========================================================================
# HTML page (dropdowns pre-populated server-side)
# ===========================================================================

def _option(value: str, label: str, selected: bool = False, disabled: bool = False) -> str:
    s = " selected" if selected else ""
    d = " disabled" if disabled else ""
    return f'<option value="{value}"{s}{d}>{label}</option>'

def _status_dot(ok: bool) -> str:
    return "green" if ok else "#ccc"

def build_page() -> str:
    c = _COMPONENTS
    be_opts = "".join([
        _option("docling", "Docling (IBM) — PDF/DOCX/XLSX/PPTX/HTML/Images", True),
        _option("marker", "Marker — PDF/Images only (not implemented)", disabled=True),
        _option("mineru", "MinerU — PDF only (not implemented)", disabled=True),
    ])
    ocr_opts = "".join([
        _option("easyocr", "EasyOCR (default)", selected=True),
        _option("paddleocr", "PaddleOCR (best Chinese)" if c['ocr']['paddleocr']['ok'] else "PaddleOCR (not installed)"),
        _option("tesseract", "Tesseract (CPU)" if c['ocr']['tesseract']['ok'] else "Tesseract (not installed)"),
        _option("suryaocr", c['ocr']['suryaocr']['name'], disabled=True),
    ])
    vlm_opts = "".join([
        _option("", "Standard Pipeline (no VLM)", selected=True),
        _option("granite_docling", "GraniteDocling (needs model download ~2GB)"),
        _option("deepseek_ocr", "DeepSeek-OCR 2 (needs Ollama setup)"),
        _option("paddleocr_vl", "PaddleOCR-VL 1.5 (needs GPU + Linux)"),
    ])
    status_html = "".join([
        f'<span style="display:flex;align-items:center;gap:4px;font-size:0.82em"><span style="width:8px;height:8px;border-radius:50%;background:{_status_dot(v["ok"])};flex-shrink:0"></span>{v["name"]}{("" if v["ok"] else " -- "+v["install"])}</span>'
        for v in c["ocr"].values()
    ] + [
        f'<span style="display:flex;align-items:center;gap:4px;font-size:0.82em"><span style="width:8px;height:8px;border-radius:50%;background:{_status_dot(v["ok"])};flex-shrink:0"></span>{v["name"]}</span>'
        for v in c["backends"].values()
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>M1 Document Parser</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 1000px; margin: 20px auto; padding: 20px; background: #f5f5f5; color: #333; }}
  h1 {{ font-size: 1.4em; margin-bottom: 4px; }}
  .subtitle {{ color: #666; margin-bottom: 12px; font-size: 0.9em; }}
  .status-panel {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; }}
  .status-panel summary {{ cursor: pointer; font-weight: 600; font-size: 0.9em; margin-bottom: 6px; }}
  .status-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4px 16px; }}
  .drop-zone {{
    border: 2px dashed #bbb; border-radius: 8px; padding: 30px; text-align: center;
    background: #fff; margin-bottom: 12px; cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
  }}
  .drop-zone:hover {{ border-color: #4a90d9; background: #f0f6ff; }}
  .drop-zone.drag-over {{ border-color: #2563eb; border-style: solid; background: #e0eeff; }}
  .drop-zone p {{ color: #888; font-size: 0.92em; }}
  .drop-zone .formats {{ font-size: 0.8em; color: #aaa; margin-top: 4px; }}
  .file-list {{ margin-bottom: 12px; }}
  .file-item {{ display: flex; align-items: center; gap: 8px; padding: 6px 10px;
                background: #fff; border: 1px solid #eee; border-radius: 4px; margin-bottom: 4px; font-size: 0.9em; }}
  .file-item .name {{ flex: 1; }}
  .file-item .size {{ color: #888; font-size: 0.85em; }}
  .file-item .remove {{ cursor: pointer; color: #c00; font-weight: bold; font-size: 1.1em; border: none; background: none; padding: 2px 6px; }}
  .file-item .remove:hover {{ background: #fee; border-radius: 3px; }}
  select, button, input[type=text] {{ padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 0.9em; background: #fff; }}
  select:focus, input[type=text]:focus {{ outline: none; border-color: #4a90d9; }}
  button {{ background: #4a90d9; color: #fff; border: none; cursor: pointer; padding: 9px 20px; font-size: 0.92em; }}
  button:hover:not(:disabled) {{ background: #357abd; }}
  button:disabled {{ background: #bbb; cursor: not-allowed; }}
  .options {{ display: flex; gap: 10px; align-items: flex-end; margin-bottom: 12px; flex-wrap: wrap; }}
  .opt-group {{ display: flex; flex-direction: column; gap: 2px; }}
  .opt-group label {{ font-size: 0.78em; color: #777; font-weight: 500; }}
  .result {{ background: #fff; border-radius: 8px; padding: 16px; margin-top: 12px; display: none; }}
  .result pre {{ background: #f8f8f8; padding: 14px; border-radius: 4px; font-size: 0.85em;
                 line-height: 1.5; max-height: 400px; overflow: auto; white-space: pre-wrap; }}
  .error {{ color: #c00; background: #fee; padding: 10px; border-radius: 4px; font-size: 0.9em; }}
  .success-ok {{ color: #2a0; }}
  .btn-sm {{ padding: 4px 10px; font-size: 0.8em; border-radius: 3px; border: 1px solid #ccc; background: #f8f8f8; cursor: pointer; }}
  .btn-sm:hover {{ background: #e8e8e8; }}
  .meta-line {{ display: flex; gap: 6px; align-items: center; flex-wrap: wrap; font-size: 0.82em; color: #666; margin-bottom: 4px; }}
  .meta-tag {{ background: #e8f0fe; color: #2563eb; padding: 1px 6px; border-radius: 3px; font-weight: 500; }}
  .meta-stats {{ color: #888; }}
  .meta-time {{ color: #4caf50; font-weight: 500; margin-left: auto; }}
  .progress-bar {{ height: 6px; background: #e0e0e0; border-radius: 3px; margin: 8px 0; }}
  .progress-bar .fill {{ height: 100%; background: #4a90d9; border-radius: 3px; transition: width 0.3s; width: 0%; }}
  .notes {{ background: #fffbe6; border: 1px solid #ffe58f; border-radius: 6px; padding: 10px 14px; font-size: 0.84em; color: #8a6d3b; line-height: 1.6; }}
  .notes code {{ background: #f0e8c8; padding: 1px 4px; border-radius: 2px; font-size: 0.95em; }}
</style>
</head>
<body>
<h1>M1 Document Parser</h1>
<p class="subtitle">Marine &amp; Offshore Expert System &mdash; Standalone Document Parsing</p>

<details class="status-panel">
  <summary>Component Status</summary>
  <div class="status-grid">{status_html}</div>
</details>

<div class="drop-zone" id="dropZone">
  <p>Drop files here, or click to browse</p>
  <p class="formats">PDF &middot; DOCX &middot; XLSX &middot; PPTX &middot; HTML &middot; JPG &middot; PNG &middot; TIFF &middot; BMP</p>
</div>
<input type="file" id="fileInput" style="display:none" multiple
  accept=".pdf,.docx,.xlsx,.pptx,.html,.htm,.jpg,.jpeg,.png,.tiff,.tif,.bmp">

<div class="file-list" id="fileList"></div>

<div class="options">
  <div class="opt-group"><label for="backend">Backend</label>
    <select id="backend">{be_opts}</select></div>
  <div class="opt-group"><label for="ocr">OCR Engine</label>
    <select id="ocr">{ocr_opts}</select></div>
  <div class="opt-group"><label for="format">Format</label>
    <select id="format">
      <option value="md">Markdown</option>
      <option value="html">HTML</option>
      <option value="json">JSON</option>
    </select></div>
  <div class="opt-group"><label for="vlm">VLM (PDF only)</label>
    <select id="vlm">
      <option value="">Standard Pipeline</option>
      <option value="granite_docling">GraniteDocling (lightweight)</option>
      <option value="deepseek_ocr">DeepSeek-OCR 2 (efficient)</option>
      <option value="paddleocr_vl">PaddleOCR-VL 1.5 (best CN)</option>
    </select></div>
  <div class="opt-group"><label for="pages">Pages</label>
    <input type="text" id="pages" placeholder="all" style="width:60px"></div>
  <div class="opt-group"><label for="outdir">Output Dir</label>
    <input type="text" id="outdir" placeholder="./output" style="width:130px"></div>
  <div style="display:flex;gap:14px;align-items:center">
    <label style="font-size:0.88em;display:flex;align-items:center;gap:4px;cursor:pointer">
      <input type="checkbox" id="picDesc"> Picture Desc</label>
    <label style="font-size:0.88em;display:flex;align-items:center;gap:4px;cursor:pointer">
      <input type="checkbox" id="exportTbls"> Export Tables CSV</label>
  </div>
  <button id="parseBtn" disabled>Parse All</button>
  <button id="clearBtn" style="background:#888" disabled>Clear All</button>
</div>

<div class="notes">
  <strong>Output Dir:</strong> Set a path like <code>./output</code> to save page images and figures to disk.
  Without it, only text is returned. Gray OCR options are not installed -- will fall back to EasyOCR.
  Marker and MinerU are not yet implemented.
</div>

<div id="resultsArea"></div>

<script>
var _COMPONENTS = {json.dumps(_COMPONENTS)};
window.onerror = function(msg, url, line) {{
  document.getElementById('resultsArea').innerHTML =
    '<div class="error">JS Error: ' + msg + ' (line ' + line + '). Try Ctrl+F5 refresh.</div>';
  return false;
}};

// Dynamic dropdown linking: OCR and VLM depend on Backend choice
var backendSel = document.getElementById('backend');
var ocrSel = document.getElementById('ocr');
var vlmSel = document.getElementById('vlm');
var picDescCb = document.getElementById('picDesc');

function updateLinkedOptions() {{
  var be = backendSel.value;
  // Marker/MinerU have built-in OCR and don't use VLM
  var builtin = (be === 'marker' || be === 'mineru');
  ocrSel.disabled = builtin;
  vlmSel.disabled = builtin;
  picDescCb.disabled = builtin;
  if (builtin) {{
    picDescCb.checked = false;
  }}
}}
backendSel.addEventListener('change', updateLinkedOptions);
updateLinkedOptions();

var selectedFiles = [], isParsing = false;
var dz = document.getElementById('dropZone');
var fi = document.getElementById('fileInput');
var fileList = document.getElementById('fileList');
var btn = document.getElementById('parseBtn');
var clearBtn = document.getElementById('clearBtn');
var resultsArea = document.getElementById('resultsArea');

function updateUI() {{
  btn.disabled = selectedFiles.length === 0 || isParsing;
  clearBtn.disabled = selectedFiles.length === 0 || isParsing;
  dz.querySelector('p:first-child').textContent = selectedFiles.length === 0
    ? 'Drop files here, or click to browse'
    : 'Click to add more (' + selectedFiles.length + ' selected)';
  fileList.innerHTML = selectedFiles.map(function(f, i) {{
    return '<div class="file-item"><span class="name">' + esc(f.name) + '</span>' +
      '<span class="size">' + fmtSize(f.size) + '</span>' +
      '<button class="remove" onclick="removeFile(' + i + ')">x</button></div>';
  }}).join('');
}}

function addFiles(newFiles) {{
  for (var i = 0; i < newFiles.length; i++) {{
    var found = false;
    for (var j = 0; j < selectedFiles.length; j++) {{
      if (selectedFiles[j].name === newFiles[i].name && selectedFiles[j].size === newFiles[i].size) {{ found = true; break; }}
    }}
    if (!found) selectedFiles.push(newFiles[i]);
  }}
  updateUI();
}}

function removeFile(idx) {{ selectedFiles.splice(idx, 1); updateUI(); }}
function clearAll() {{ selectedFiles = []; resultsArea.innerHTML = ''; updateUI(); }}

dz.onclick = function() {{ fi.click(); }};
dz.ondragover = function(e) {{ e.preventDefault(); dz.classList.add('drag-over'); }};
dz.ondragleave = function() {{ dz.classList.remove('drag-over'); }};
dz.ondrop = function(e) {{
  e.preventDefault(); dz.classList.remove('drag-over');
  if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
}};
fi.onchange = function() {{ if (fi.files.length) {{ addFiles(fi.files); fi.value = ''; }} }};
clearBtn.onclick = clearAll;

function fmtSize(b) {{
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  return (b/1048576).toFixed(1) + ' MB';
}}

// Load saved config on startup
fetch('/config').then(r => r.json()).then(cfg => {{
  if (cfg.output_dir) document.getElementById('outdir').value = cfg.output_dir;
}}).catch(() => {{}});

// Auto-save output_dir when changed
document.getElementById('outdir').addEventListener('change', function() {{
  fetch('/config', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{output_dir: this.value}}) }});
}});

// Warn about unavailable components before parsing
function checkUnavailable() {{
  var be = backendSel.value;
  var ocr = ocrSel.value;
  var vlm = vlmSel.value;
  var occ = _COMPONENTS ? _COMPONENTS.ocr : null;

  if (be !== 'docling') {{
    return 'Backend "' + be + '" is not yet implemented. Only Docling works.';
  }}
  if (occ && occ[ocr] && !occ[ocr].ok && ocr !== 'suryaocr') {{
    return 'Warning: ' + occ[ocr].name + ' not installed.\\nWill fall back to EasyOCR.\\n\\nInstall: ' + occ[ocr].install;
  }}
  if (vlm && vlm !== '' && !picDescCb.checked) {{
    return 'VLM preset "' + vlm + '" selected but Picture Desc is NOT checked.\\nVLM only takes effect when Picture Desc is enabled.\\n\\nContinue with Standard Pipeline (no VLM)?';
  }}
  return null;
}}

btn.onclick = async function() {{
  if (!selectedFiles.length || isParsing) return;
  var warn = checkUnavailable();
  if (warn && !confirm(warn + '\\n\\nContinue anyway?')) return;
  isParsing = true; updateUI(); btn.textContent = 'Parsing...'; resultsArea.innerHTML = '';
  var b = document.getElementById('backend').value;
  var o = document.getElementById('ocr').value;
  var f = document.getElementById('format').value;
  var od = document.getElementById('outdir').value;
  var vl = document.getElementById('vlm').value;
  var pg = document.getElementById('pages').value;
  var pd = document.getElementById('picDesc').checked ? '1' : '0';
  var et = document.getElementById('exportTbls').checked ? '1' : '0';

  resultsArea.innerHTML = '<div class="progress-bar"><div class="fill" id="pf"></div></div>' +
    '<p style="font-size:0.85em;color:#888" id="pt">0/' + selectedFiles.length + '</p>';
  var pf = document.getElementById('pf'), pt = document.getElementById('pt');

  for (var i = 0; i < selectedFiles.length; i++) {{
    pt.textContent = (i+1) + '/' + selectedFiles.length + ': ' + selectedFiles[i].name;
    var fd = new FormData();
    fd.append('file', selectedFiles[i]);
    fd.append('backend', b); fd.append('ocr', o); fd.append('format', f);
    fd.append('output_dir', od); fd.append('vlm_preset', vl);
    fd.append('max_pages', pg); fd.append('picture_description', pd); fd.append('export_tables', et);

    try {{
      var resp = await fetch('/parse', {{ method:'POST', body:fd }});
      var data = await resp.json();
      var div = document.createElement('div');
      div.className = 'result'; div.style.display = 'block'; div.style.marginBottom = '8px';

      if (data.success) {{
        var display = f === 'json' ? JSON.stringify(data.result, null, 2)
          : f === 'html' ? (data.html || data.markdown || '')
          : (data.markdown || '(empty)');
        var truncated = display.length > 3000;
        var preview = truncated ? display.substring(0, 3000) + '...(truncated)' : display;
        var metaLine = '';
        if (data.metadata) {{
          var m = data.metadata;
          if (m.classification_society) metaLine += '<span class="meta-tag">'+esc(m.classification_society)+'</span> ';
          if (m.version_year) metaLine += '<span class="meta-tag">'+m.version_year+'</span> ';
          if (m.chapter_section) metaLine += '<span class="meta-tag">'+esc(m.chapter_section)+'</span> ';
          if (m.language) metaLine += '<span class="meta-tag">'+m.language+'</span> ';
        }}
        metaLine += '<span class="meta-stats">'+data.page_count+' pages, '+data.figure_count+' figs, '+data.table_count+' tables</span>';
        metaLine += '<span class="meta-time">'+(data.parse_time_sec||'?')+'s</span>';
        if (data.output_dir) metaLine += ' <span class="meta-stats">saved: '+esc(data.output_dir)+'</span>';
        div.innerHTML =
          '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'+
            '<strong class="success-ok">OK</strong> '+esc(selectedFiles[i].name)+
            '<button class="btn-sm" onclick="copyText(this)" data-text="'+escAttr(display)+'">Copy</button>'+
          '</div><div class="meta-line">'+metaLine+'</div>'+
          (f==='html'
            ? '<div style="background:#fafafa;padding:12px;border:1px solid #eee;border-radius:4px;max-height:300px;overflow:auto">'+preview+'</div>'
            : '<pre style="max-height:250px">'+esc(preview)+'</pre>');
        if (data.tables_csv) {{
          div.innerHTML += '<div style="margin-top:4px"><button class="btn-sm" onclick="copyText(this)" data-text="'+escAttr(data.tables_csv)+'">Copy Tables CSV</button></div>';
        }}
      }} else {{
        div.innerHTML = '<strong class="error">FAIL</strong> '+esc(selectedFiles[i].name)+
          '<div class="error" style="margin-top:4px">'+esc(data.error||'')+'</div>'+
          '<button class="btn-sm" style="margin-top:6px" onclick="retryOne('+i+')">Retry</button>';
      }}
      resultsArea.appendChild(div);
    }} catch(err) {{
      var ed = document.createElement('div');
      ed.className = 'result'; ed.style.display = 'block';
      ed.innerHTML = '<strong class="error">ERROR</strong> '+esc(selectedFiles[i].name)+
        '<div class="error">Network: '+esc(err.message)+'</div>'+
        '<button class="btn-sm" style="margin-top:6px" onclick="retryOne('+i+')">Retry</button>';
      resultsArea.appendChild(ed);
    }}
    pf.style.width = ((i+1)/selectedFiles.length*100)+'%';
  }}
  pt.textContent = 'Done. '+selectedFiles.length+' file(s) processed.';
  isParsing = false; btn.textContent = 'Parse All'; updateUI();
}};

async function retryOne(idx) {{
  if (isParsing || !selectedFiles[idx]) return;
  isParsing = true; updateUI();
  var fd = new FormData();
  fd.append('file', selectedFiles[idx]);
  fd.append('backend', document.getElementById('backend').value);
  fd.append('ocr', document.getElementById('ocr').value);
  fd.append('format', document.getElementById('format').value);
  fd.append('output_dir', document.getElementById('outdir').value);
  fd.append('vlm_preset', document.getElementById('vlm').value);
  fd.append('max_pages', document.getElementById('pages').value);
  fd.append('picture_description', document.getElementById('picDesc').checked?'1':'0');
  fd.append('export_tables', document.getElementById('exportTbls').checked?'1':'0');
  try {{
    var resp = await fetch('/parse', {{method:'POST', body:fd}});
    var data = await resp.json();
    var div = document.createElement('div');
    div.className = 'result'; div.style.display = 'block'; div.style.marginBottom='8px';
    if (data.success) {{
      div.innerHTML = '<strong class="success-ok">RETRY OK</strong> '+esc(selectedFiles[idx].name)+
        '<pre style="max-height:200px">'+esc((data.markdown||'').substring(0,2000))+'</pre>';
    }} else {{
      div.innerHTML = '<strong class="error">RETRY FAILED</strong> '+esc(selectedFiles[idx].name)+
        '<div class="error">'+esc(data.error||'')+'</div>';
    }}
    resultsArea.appendChild(div);
  }} catch(err) {{
    var ed = document.createElement('div');
    ed.className = 'result'; ed.style.display = 'block';
    ed.innerHTML = '<span class="error">Retry error: '+esc(err.message)+'</span>';
    resultsArea.appendChild(ed);
  }}
  isParsing = false; updateUI();
}}

function copyText(btn) {{
  var text = btn.getAttribute('data-text');
  navigator.clipboard.writeText(text).then(function() {{
    var orig = btn.textContent;
    btn.textContent = 'Copied!'; btn.style.background = '#4caf50';
    setTimeout(function() {{ btn.textContent = orig; btn.style.background = ''; }}, 1500);
  }});
}}

function esc(s) {{
  if (!s) return '';
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}}

function escAttr(s) {{
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}}
</script>
</body>
</html>"""

# ===========================================================================
# Config persistence
# ===========================================================================

_CONFIG_PATH = Path("m1_parser_config.json")

def _load_config() -> dict:
    try:
        if _CONFIG_PATH.exists():
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def _save_config(data: dict) -> None:
    try:
        _CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

# ===========================================================================
# App
# ===========================================================================

def create_app() -> "FastAPI":
    if FastAPI is None:
        raise ImportError("FastAPI not installed. pip install fastapi uvicorn python-multipart")

    app = FastAPI(title="M1 Document Parser", version="0.2.0")

    @app.get("/")
    async def root():
        return HTMLResponse(content=build_page())

    @app.get("/status")
    async def status():
        return _COMPONENTS

    @app.get("/config")
    async def get_config():
        cfg = _load_config()
        cfg.setdefault("output_dir", "./output")
        return cfg

    @app.post("/config")
    async def save_config(data: dict):
        cfg = _load_config()
        cfg.update(data)
        _save_config(cfg)
        return {"ok": True}

    @app.post("/parse")
    async def parse(
        file: UploadFile = File(...),
        backend: str = Form("docling"),
        ocr: str = Form("easyocr"),
        format: str = Form("md"),
        output_dir: str = Form(""),
        vlm_preset: str = Form(""),
        max_pages: str = Form(""),
        picture_description: str = Form("0"),
        export_tables: str = Form("0"),
    ):
        suffix = Path(file.filename or "upload").suffix or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        logger.info("Parsing: filename=%s doc_name=%s", file.filename, Path(file.filename or "document").stem)

        # Validate pages input
        pages_val = None
        if max_pages.strip():
            try:
                pages_val = int(max_pages.strip())
                if pages_val < 1:
                    return {"success": False, "error": f"Pages must be >= 1, got {pages_val}"}
                if pages_val > 5000:
                    return {"success": False, "error": f"Pages must be <= 5000, got {pages_val}"}
            except ValueError:
                return {"success": False, "error": f"Invalid pages value: {max_pages!r}. Enter a number like 10."}

        # Persist output_dir setting
        if output_dir.strip():
            _save_config({"output_dir": output_dir.strip()})

        try:
            from m1_parser.core.converter import convert, ParseOptions
            options = ParseOptions(
                backend=backend,
                ocr_engine=ocr,
                vlm_preset=vlm_preset or None,
                output_dir=output_dir or None,
                output_formats=[format],
                doc_name=Path(file.filename or "document").stem,
                max_pages=pages_val,
                picture_description=picture_description == "1",
                export_tables=export_tables == "1",
            )
            result = convert(tmp_path, options)
            if result.success:
                # Auto-store chunks in M2 for retrieval
                m2_status = "not stored"
                try:
                    from m2_storage.factory import create_storage_manager
                    from contracts.document import Chunk, DocumentMetadata, Domain, ClassificationSociety
                    import hashlib

                    mgr = create_storage_manager("deploy.yaml")
                    await mgr.initialize()

                    # Create chunks from parsed markdown
                    lines = [l.strip() for l in result.markdown.split("\n") if l.strip() and not l.strip().startswith("# ")]
                    chunks = []
                    for i, line in enumerate(lines[:50]):  # cap at 50 chunks
                        cid = hashlib.md5(line.encode()).hexdigest()[:12]
                        soc = ClassificationSociety(result.metadata.get("classification_society", "DNV") or "DNV")
                        chunks.append(Chunk(
                            chunk_id=cid, text=line,
                            metadata=DocumentMetadata(
                                source_filename=file.filename or "upload",
                                domain=Domain.GENERAL,
                                classification_society=soc,
                                language=result.metadata.get("language", "en"),
                            ),
                            chunk_type="clause", position_in_document=i,
                        ))

                    # Embed + store in ChromaDB
                    if chunks:
                        def _embed(t, d=256):
                            h = int(hashlib.md5(t.encode()).hexdigest(), 16)
                            return [(h >> j) & 0xFF for j in range(0, d*8, 8)]
                        await mgr.vector_store.insert(chunks, [_embed(c.text) for c in chunks])
                        try: await mgr.doc_index.index(chunks)
                        except Exception: pass
                        m2_status = f"stored {len(chunks)} chunks"
                    await mgr.close()
                except Exception as e2:
                    m2_status = f"M2 unavailable: {e2}"

                return {
                    "success": True, "doc_id": result.doc_id,
                    "markdown": result.markdown, "html": result.html,
                    "result": result.json_dict,
                    "page_count": result.page_count,
                    "figure_count": result.figure_count,
                    "table_count": result.table_count,
                    "output_dir": result.output_dir,
                    "metadata": result.metadata,
                    "parse_time_sec": result.parse_time_sec,
                    "tables_csv": result.tables_csv,
                    "m2_status": m2_status,
                }
            return {"success": False, "error": result.error or "Unknown error"}
        except Exception as e:
            logger.exception("Parse failed: %s", file.filename)
            return {"success": False, "error": str(e)}
        finally:
            try: Path(tmp_path).unlink(missing_ok=True)
            except Exception: pass

    return app


def main(host: str = "127.0.0.1", port: int = 8007) -> None:
    try: import uvicorn
    except ImportError: print("pip install uvicorn"); sys.exit(1)
    app = create_app()
    print(f"M1 Document Parser: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
