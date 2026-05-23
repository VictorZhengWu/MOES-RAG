# -*- coding: utf-8 -*-
"""
Standalone FastAPI web server for M1 document parsing engine.

Endpoints:
  GET  /             -- upload page (HTML UI)
  POST /parse        -- upload + parse one document
  POST /parse-batch  -- upload + parse multiple documents sequentially
  GET  /status       -- component availability check
"""

from __future__ import annotations

import logging
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, File, Form, UploadFile
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError:
    FastAPI = None

# ===========================================================================
# Component availability detection
# ===========================================================================

def _check_import(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False

def _check_tesseract_cli() -> bool:
    import subprocess
    try:
        subprocess.run(["tesseract", "--version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False

def get_component_status() -> dict:
    return {
        "backends": {
            "docling": {"available": _check_import("docling"), "label": "Docling (IBM)", "install": "pip install docling>=2.94.0"},
            "marker":  {"available": False, "label": "Marker (PDF specialist)", "install": "pip install marker-pdf", "note": "Skeleton stub — not yet implemented"},
            "mineru":  {"available": False, "label": "MinerU (Chinese docs)", "install": "pip install magic-pdf", "note": "Skeleton stub — not yet implemented"},
        },
        "ocr": {
            "easyocr":    {"available": _check_import("easyocr"), "label": "EasyOCR", "install": "pip install easyocr"},
            "paddleocr":  {"available": _check_import("paddleocr"), "label": "PaddleOCR (best Chinese)", "install": "pip install paddlepaddle paddleocr"},
            "tesseract":  {"available": _check_tesseract_cli(), "label": "Tesseract", "install": "Download from https://github.com/UB-Mannheim/tesseract/wiki then pip install pytesseract"},
            "suryaocr":   {"available": _check_import("docling_surya"), "label": "SuryaOCR (best tables)", "install": "pip install docling-surya"},
        },
        "web_framework": {
            "fastapi": {"available": FastAPI is not None, "label": "FastAPI", "install": "pip install fastapi uvicorn python-multipart"},
        },
    }

# ===========================================================================
# Backend/OCR descriptions
# ===========================================================================

_BACKEND_INFO = {
    "docling": "IBM Research 开源，MIT 许可证。综合引擎处理 PDF/DOCX/XLSX/PPTX/HTML/图片全部格式。Standard Pipeline 速度最快。图片需指定 Output Directory 保存。",
    "marker":  "PDF/图片专项。基于 Surya 深度学习模型做版面检测和 OCR。GPL 许可证。当前为骨架实现——需 pip install marker-pdf。",
    "mineru":  "上海 AI Lab 开源，Apache 2.0。中文科技文档 PDF 解析效果最佳。当前为骨架实现——需 pip install magic-pdf。",
}

_OCR_INFO = {
    "easyocr":   "开箱即用，80+ 语言，GPU 加速。速度快但复杂表格精度不如 PaddleOCR。当前已安装。",
    "paddleocr": "百度开源，中文识别率最高（97%+）。PP-OCRv4 在 ICDAR 持续领先。船级社中文规范首选。{status}",
    "tesseract": "Google 维护，100+ 语言，纯 CPU 可用。适合纯英文老规范。{status}",
    "suryaocr":  "Transformer 架构，90+ 语言。版面分析+表格识别最强。GPL 许可证（商用注意）。{status}",
}

# ===========================================================================
# HTML page
# ===========================================================================

def _build_page(components: dict) -> str:
    """Generate the upload page HTML with component status embedded."""
    import json
    comp_json = json.dumps(components, ensure_ascii=False)
    backend_info_json = json.dumps(_BACKEND_INFO, ensure_ascii=False)
    ocr_info_json = json.dumps(_OCR_INFO, ensure_ascii=False)

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
  .subtitle {{ color: #666; margin-bottom: 16px; font-size: 0.9em; }}

  /* Component status panel */
  .status-panel {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; }}
  .status-panel summary {{ cursor: pointer; font-weight: 600; font-size: 0.92em; margin-bottom: 8px; }}
  .status-panel summary:hover {{ color: #4a90d9; }}
  .status-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px 24px; font-size: 0.82em; }}
  .status-item {{ display: flex; align-items: center; gap: 6px; }}
  .status-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
  .status-dot.ok {{ background: #4caf50; }}
  .status-dot.warn {{ background: #ff9800; }}
  .status-dot.off {{ background: #ccc; }}
  .status-item .install-cmd {{ color: #888; font-size: 0.9em; }}

  /* Upload area */
  .drop-zone {{
    border: 2px dashed #bbb; border-radius: 8px; padding: 30px; text-align: center;
    background: #fff; margin-bottom: 12px; transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
    cursor: pointer;
  }}
  .drop-zone:hover {{ border-color: #4a90d9; background: #f0f6ff; box-shadow: 0 0 0 4px rgba(74,144,217,0.1); }}
  .drop-zone.drag-over {{ border-color: #2563eb; border-style: solid; background: #e0eeff; }}
  .drop-zone p {{ color: #888; font-size: 0.92em; }}
  .drop-zone .formats {{ font-size: 0.8em; color: #aaa; margin-top: 4px; }}

  /* File list */
  .file-list {{ margin-bottom: 12px; }}
  .file-item {{ display: flex; align-items: center; gap: 8px; padding: 6px 10px;
                background: #fff; border: 1px solid #eee; border-radius: 4px; margin-bottom: 4px; font-size: 0.9em; }}
  .file-item .name {{ flex: 1; }}
  .file-item .size {{ color: #888; font-size: 0.85em; }}
  .file-item .remove {{ cursor: pointer; color: #c00; font-weight: bold; font-size: 1.1em;
                        border: none; background: none; padding: 2px 6px; }}
  .file-item .remove:hover {{ background: #fee; border-radius: 3px; }}

  /* Controls */
  select, button, input[type=text] {{ padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 0.9em; background: #fff; }}
  select:focus, input[type=text]:focus {{ outline: none; border-color: #4a90d9; }}
  button {{ background: #4a90d9; color: #fff; border: none; cursor: pointer; padding: 9px 20px; font-size: 0.92em; }}
  button:hover:not(:disabled) {{ background: #357abd; }}
  button:disabled {{ background: #bbb; cursor: not-allowed; }}
  .options {{ display: flex; gap: 10px; align-items: flex-end; margin-bottom: 8px; flex-wrap: wrap; }}
  .opt-group {{ display: flex; flex-direction: column; gap: 2px; }}
  .opt-group label {{ font-size: 0.78em; color: #777; font-weight: 500; }}

  .info-box {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 10px 14px;
               margin-bottom: 12px; font-size: 0.85em; color: #555; line-height: 1.5; min-height: 36px; }}
  .info-box strong {{ color: #333; }}

  /* Results */
  .result {{ background: #fff; border-radius: 8px; padding: 16px; margin-top: 12px; display: none; }}
  .result h3 {{ margin-bottom: 10px; font-size: 1em; }}
  .result pre {{ background: #f8f8f8; padding: 14px; border-radius: 4px; font-size: 0.85em;
                 line-height: 1.5; max-height: 400px; overflow: auto; white-space: pre-wrap; }}
  .result .meta {{ font-size: 0.82em; color: #888; margin-top: 6px; }}
  .error {{ color: #c00; background: #fee; padding: 10px; border-radius: 4px; font-size: 0.9em; }}
  .success-ok {{ color: #2a0; }}
  .progress-bar {{ height: 6px; background: #e0e0e0; border-radius: 3px; margin: 8px 0; }}
  .progress-bar .fill {{ height: 100%; background: #4a90d9; border-radius: 3px; transition: width 0.3s; width: 0%; }}
  .btn-sm {{ padding: 4px 10px; font-size: 0.8em; border-radius: 3px; border: 1px solid #ccc; background: #f8f8f8; cursor: pointer; }}
  .btn-sm:hover {{ background: #e8e8e8; }}
  .meta-line {{ display: flex; gap: 6px; align-items: center; flex-wrap: wrap; font-size: 0.82em; color: #666; margin-bottom: 4px; }}
  .meta-tag {{ background: #e8f0fe; color: #2563eb; padding: 1px 6px; border-radius: 3px; font-weight: 500; }}
  .meta-stats {{ color: #888; }}
  .meta-time {{ color: #4caf50; font-weight: 500; margin-left: auto; }}
  .html-preview {{ background: #fafafa; padding: 12px; border: 1px solid #eee; border-radius: 4px; font-size: 0.9em; line-height: 1.5; }}
</style>
</head>
<body>
<h1>M1 Document Parser</h1>
<p class="subtitle">Marine &amp; Offshore Expert System &mdash; Standalone Document Parsing</p>

<!-- Component Status -->
<details class="status-panel">
  <summary>Component Status</summary>
  <div class="status-grid">
    <div><strong>Backends:</strong></div><div></div>
    <div id="status-marker"></div><div id="status-mineru"></div>
    <div><strong>OCR Engines:</strong></div><div></div>
    <div id="status-easyocr"></div><div id="status-paddleocr"></div>
    <div id="status-tesseract"></div><div id="status-suryaocr"></div>
  </div>
</details>

<!-- Drop Zone -->
<div class="drop-zone" id="dropZone">
  <p>Drop files here, or click to browse</p>
  <p class="formats">PDF &middot; DOCX &middot; XLSX &middot; PPTX &middot; HTML &middot; JPG &middot; PNG &middot; TIFF &middot; BMP</p>
  <input type="file" id="fileInput" style="display:none" multiple
    accept=".pdf,.docx,.xlsx,.pptx,.html,.htm,.jpg,.jpeg,.png,.tiff,.tif,.bmp">
</div>

<!-- File list -->
<div class="file-list" id="fileList"></div>

<!-- Options -->
<div class="options">
  <div class="opt-group">
    <label for="backend">Backend</label>
    <select id="backend"></select>
  </div>
  <div class="opt-group">
    <label for="ocr">OCR Engine</label>
    <select id="ocr"></select>
  </div>
  <div class="opt-group">
    <label for="format">Format</label>
    <select id="format">
      <option value="md">Markdown</option>
      <option value="html">HTML</option>
      <option value="json">JSON</option>
    </select>
  </div>
  <div class="opt-group">
    <label for="vlm">VLM (PDF only)</label>
    <select id="vlm">
      <option value="">Standard Pipeline</option>
      <option value="granite_docling">GraniteDocling (lightweight)</option>
      <option value="deepseek_ocr">DeepSeek-OCR 2 (efficient)</option>
      <option value="paddleocr_vl">PaddleOCR-VL 1.5 (best Chinese)</option>
    </select>
  </div>
  <div class="opt-group">
    <label for="pages">Pages <span style="font-weight:400;color:#aaa">(optional)</span></label>
    <input type="text" id="pages" placeholder="all" style="width:70px">
  </div>
  <div class="opt-group">
    <label for="outdir">Output Dir</label>
    <input type="text" id="outdir" placeholder="./output" style="width:140px">
  </div>
  <div style="display:flex;gap:14px;align-items:center">
    <label style="font-size:0.88em;display:flex;align-items:center;gap:4px;cursor:pointer">
      <input type="checkbox" id="picDesc"> Picture Desc
    </label>
    <label style="font-size:0.88em;display:flex;align-items:center;gap:4px;cursor:pointer">
      <input type="checkbox" id="exportTbls"> Export Tables (CSV)
    </label>
  </div>
  <button id="parseBtn" disabled>Parse All</button>
  <button id="clearBtn" style="background:#888" disabled>Clear All</button>
</div>

<div class="info-box" id="infoBox">Select backend and OCR engine to see details.</div>

<div id="resultsArea"></div>

<script>
const COMPONENTS = {comp_json};
const BACKEND_INFO = {backend_info_json};
const OCR_INFO = {ocr_info_json};

let selectedFiles = [];
let isParsing = false;

// --- Build component status panel ---
function buildStatus() {{
  const cs = COMPONENTS;
  const mkStatus = (id, info) => {{
    const el = document.getElementById(id);
    if (!el) return;
    const avail = info.available;
    const dot = avail ? 'ok' : (info.note ? 'off' : 'warn');
    let label = info.label;
    if (!avail && !info.note) label += ' (not installed)';
    if (info.note) label += ' (not implemented)';
    const cmd = !avail && info.install ? ' <span class="install-cmd">[' + info.install + ']</span>' : '';
    el.innerHTML = '<span class="status-dot ' + dot + '"></span> ' + label + cmd;
  }};
  mkStatus('status-marker', cs.backends.marker);
  mkStatus('status-mineru', cs.backends.mineru);
  mkStatus('status-easyocr', cs.ocr.easyocr);
  mkStatus('status-paddleocr', cs.ocr.paddleocr);
  mkStatus('status-tesseract', cs.ocr.tesseract);
  mkStatus('status-suryaocr', cs.ocr.suryaocr);
}}
buildStatus();

// --- Dropdowns ---
const selBackend = document.getElementById('backend');
const selOcr = document.getElementById('ocr');
[['docling', 'Docling (available)'], ['marker', 'Marker (unavailable)'], ['mineru', 'MinerU (unavailable)']]
  .forEach(([k, v]) => {{
    const o = document.createElement('option'); o.value = k; o.textContent = v;
    if (k !== 'docling') o.disabled = true;
    selBackend.appendChild(o);
  }});
[['easyocr', 'EasyOCR' + (COMPONENTS.ocr.easyocr.available ? ' (available)' : '')],
 ['paddleocr', 'PaddleOCR' + (COMPONENTS.ocr.paddleocr.available ? ' (available)' : ' (not installed)')],
 ['tesseract', 'Tesseract' + (COMPONENTS.ocr.tesseract.available ? ' (available)' : ' (not installed)')],
 ['suryaocr', 'SuryaOCR' + (COMPONENTS.ocr.suryaocr.available ? ' (available)' : ' (not installed)')]]
  .forEach(([k, v]) => {{
    const o = document.createElement('option'); o.value = k; o.textContent = v;
    if (!COMPONENTS.ocr[k] || !COMPONENTS.ocr[k].available) o.style.color = '#999';
    selOcr.appendChild(o);
  }});

function updateInfo() {{
  const b = selBackend.value; const o = selOcr.value;
  const ocrAvail = COMPONENTS.ocr[o] && COMPONENTS.ocr[o].available;
  const ocrStatus = ocrAvail ? 'Available.' : 'NOT installed — will fall back to EasyOCR. Install: ' + (COMPONENTS.ocr[o] ? COMPONENTS.ocr[o].install : '');
  document.getElementById('infoBox').innerHTML =
    '<strong>' + selBackend.selectedOptions[0].textContent + '</strong>: ' + (BACKEND_INFO[b] || '') +
    '<br><strong>' + selOcr.selectedOptions[0].textContent + '</strong>: ' +
    (OCR_INFO[o] || '').replace('{{status}}', ocrStatus);
}}
selBackend.addEventListener('change', updateInfo);
selOcr.addEventListener('change', updateInfo);
updateInfo();

// --- File handling ---
const dz = document.getElementById('dropZone');
const fi = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const btn = document.getElementById('parseBtn');
const clearBtn = document.getElementById('clearBtn');
const resultsArea = document.getElementById('resultsArea');

function updateUI() {{
  btn.disabled = selectedFiles.length === 0 || isParsing;
  clearBtn.disabled = selectedFiles.length === 0 || isParsing;
  dz.querySelector('p:first-child').textContent = selectedFiles.length === 0
    ? 'Drop files here, or click to browse'
    : 'Click to add more files (' + selectedFiles.length + ' selected)';
  renderFileList();
}}

function addFiles(newFiles) {{
  for (const f of newFiles) {{
    if (!selectedFiles.find(sf => sf.name === f.name && sf.size === f.size)) {{
      selectedFiles.push(f);
    }}
  }}
  updateUI();
}}

function removeFile(idx) {{
  selectedFiles.splice(idx, 1);
  updateUI();
}}

function clearAll() {{
  selectedFiles = [];
  resultsArea.innerHTML = '';
  updateUI();
}}

function renderFileList() {{
  fileList.innerHTML = selectedFiles.map((f, i) =>
    '<div class="file-item">' +
      '<span class="name">' + escapeHtml(f.name) + '</span>' +
      '<span class="size">' + formatSize(f.size) + '</span>' +
      '<button class="remove" onclick="removeFile(' + i + ')" title="Remove">&times;</button>' +
    '</div>'
  ).join('');
}}

dz.addEventListener('click', () => fi.click());
fi.addEventListener('change', () => {{ if (fi.files.length > 0) addFiles(fi.files); fi.value = ''; }});
dz.addEventListener('dragover', e => {{ e.preventDefault(); dz.classList.add('drag-over'); }});
dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
dz.addEventListener('drop', e => {{
  e.preventDefault(); dz.classList.remove('drag-over');
  if (e.dataTransfer.files.length > 0) addFiles(e.dataTransfer.files);
}});
clearBtn.addEventListener('click', clearAll);

function formatSize(bytes) {{
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes/1024).toFixed(1) + ' KB';
  return (bytes/1048576).toFixed(1) + ' MB';
}}

// --- Batch parsing ---
btn.addEventListener('click', async () => {{
  if (selectedFiles.length === 0 || isParsing) return;
  isParsing = true;
  updateUI();
  btn.textContent = 'Parsing...';
  resultsArea.innerHTML = '';

  const backend = selBackend.value;
  const ocr = selOcr.value;
  const fmt = document.getElementById('format').value;
  const outDir = document.getElementById('outdir').value;

  // Progress bar
  const progressDiv = document.createElement('div');
  progressDiv.innerHTML = '<div class="progress-bar"><div class="fill" id="progressFill"></div></div>' +
    '<p style="font-size:0.85em;color:#888" id="progressText">0 / ' + selectedFiles.length + '</p>';
  resultsArea.appendChild(progressDiv);
  const fill = document.getElementById('progressFill');
  const progText = document.getElementById('progressText');

  for (let i = 0; i < selectedFiles.length; i++) {{
    const f = selectedFiles[i];
    progText.textContent = (i + 1) + ' / ' + selectedFiles.length + ': ' + f.name;

    const fd = new FormData();
    fd.append('file', f);
    fd.append('backend', backend);
    fd.append('ocr', ocr);
    fd.append('format', fmt);
    fd.append('output_dir', outDir);
    fd.append('vlm_preset', document.getElementById('vlm').value);
    fd.append('max_pages', document.getElementById('pages').value);
    fd.append('picture_description', document.getElementById('picDesc').checked ? '1' : '0');
    fd.append('export_tables', document.getElementById('exportTbls').checked ? '1' : '0');

    try {{
      const resp = await fetch('/parse', {{ method: 'POST', body: fd }});
      const data = await resp.json();
      const resultDiv = document.createElement('div');
      resultDiv.className = 'result';
      resultDiv.style.display = 'block';
      resultDiv.style.marginBottom = '8px';

      if (data.success) {{
        // Determine display content based on format
        let display, displayClass;
        if (fmt === 'json') {{
          display = JSON.stringify(data.result, null, 2); displayClass = '';
        }} else if (fmt === 'html') {{
          display = data.html || data.markdown || ''; displayClass = 'html-preview';
        }} else {{
          display = data.markdown || ''; displayClass = '';
        }}

        // Build metadata line
        let metaLine = '<div class="meta-line">';
        if (data.metadata && data.metadata.classification_society) {{
          metaLine += '<span class="meta-tag">' + escapeHtml(data.metadata.classification_society) + '</span> ';
        }}
        if (data.metadata && data.metadata.version_year) {{
          metaLine += '<span class="meta-tag">' + data.metadata.version_year + '</span> ';
        }}
        if (data.metadata && data.metadata.chapter_section) {{
          metaLine += '<span class="meta-tag">' + escapeHtml(data.metadata.chapter_section) + '</span> ';
        }}
        if (data.metadata && data.metadata.language) {{
          metaLine += '<span class="meta-tag">' + data.metadata.language + '</span> ';
        }}
        metaLine += '<span class="meta-stats">' + data.page_count + ' pages, ' + data.figure_count + ' figures, ' + data.table_count + ' tables';
        if (data.output_dir) metaLine += ', saved: ' + escapeHtml(data.output_dir);
        metaLine += '</span>';
        metaLine += '<span class="meta-time">' + (data.parse_time_sec || '?') + 's</span></div>';
          if (data.tables_csv) {{
            const csvId = 'csv_' + i + '_' + Math.random().toString(36).substr(2,6);
            metaLine += '<div style="margin-top:4px"><button class="btn-sm" onclick="copyResult('' + csvId + '')">Copy Tables CSV</button></div>';
            metaLine += '<textarea id="' + csvId + '" style="display:none">' + escapeHtml(data.tables_csv) + '</textarea>';
          }}

        const truncated = display.length > 3000;
        const preview = truncated ? display.substring(0, 3000) + '\n\n... (truncated, ' + display.length + ' chars total)' : display;
        const displayId = 'disp_' + i + '_' + Math.random().toString(36).substr(2,6);

        resultDiv.innerHTML =
          '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">' +
            '<strong class="success-ok">OK</strong> ' + escapeHtml(f.name) +
            '<span>' +
              '<button class="btn-sm" onclick="copyResult(\'' + displayId + '\')" title="Copy to clipboard">Copy</button>' +
            '</span>' +
          '</div>' +
          metaLine +
          '<div id="' + displayId + '" style="max-height:300px;overflow:auto;margin-top:6px">' +
            (fmt === 'html'
              ? '<div style="background:#fafafa;padding:12px;border:1px solid #eee;border-radius:4px">' + preview + '</div>'
              : '<pre style="font-size:0.85em;line-height:1.4">' + escapeHtml(preview) + '</pre>') +
          '</div>';
        if (truncated) {{
          resultDiv.innerHTML += '<p style="font-size:0.8em;color:#888;margin-top:4px">Showing first 3000 of ' + display.length + ' characters.</p>';
        }}
      }} else {{
        resultDiv.innerHTML =
          '<strong class="error">FAIL</strong> ' + escapeHtml(f.name) +
          '<div class="error" style="margin-top:4px">' + escapeHtml(data.error || 'Unknown error') + '</div>' +
          '<button class="btn-sm" style="margin-top:6px" onclick="retryFile(' + i + ')">Retry</button>';
      }}
      resultsArea.appendChild(resultDiv);
    }} catch (err) {{
      const errDiv = document.createElement('div');
      errDiv.className = 'result'; errDiv.style.display = 'block';
      errDiv.innerHTML = '<strong class="error">ERROR</strong> ' + escapeHtml(f.name) +
        '<div class="error">Network: ' + escapeHtml(err.message) + '</div>' +
        '<button class="btn-sm" style="margin-top:6px" onclick="retryFile(' + i + ')">Retry</button>';
      resultsArea.appendChild(errDiv);
    }}

    fill.style.width = ((i + 1) / selectedFiles.length * 100) + '%';
  }}

  progText.textContent = 'Done. ' + selectedFiles.length + ' file(s) processed.';
  isParsing = false;
  btn.textContent = 'Parse All';
  updateUI();
}});

// Copy result to clipboard
function copyResult(elId) {{
  const el = document.getElementById(elId);
  if (!el) return;
  const text = el.textContent || el.innerText;
  navigator.clipboard.writeText(text).then(() => {{
    // Brief visual feedback
    const btn = event.target;
    const orig = btn.textContent;
    btn.textContent = 'Copied!';
    btn.style.background = '#4caf50';
    setTimeout(() => {{ btn.textContent = orig; btn.style.background = '#4a90d9'; }}, 1500);
  }});
}}

// Retry a single failed file
async function retryFile(idx) {{
  if (isParsing) return;
  const f = selectedFiles[idx];
  if (!f) return;
  isParsing = true;
  updateUI();

  // Build a temporary progress indicator
  const results = document.getElementById('resultsArea');
  const tmpDiv = document.createElement('div');
  tmpDiv.textContent = 'Retrying: ' + f.name + '...';
  results.appendChild(tmpDiv);

  const fd = new FormData();
  fd.append('file', f);
  fd.append('backend', selBackend.value);
  fd.append('ocr', selOcr.value);
  fd.append('format', document.getElementById('format').value);
  fd.append('output_dir', document.getElementById('outdir').value);
  fd.append('vlm_preset', document.getElementById('vlm').value);
  fd.append('max_pages', document.getElementById('pages').value);
  fd.append('picture_description', document.getElementById('picDesc').checked ? '1' : '0');
  fd.append('export_tables', document.getElementById('exportTbls').checked ? '1' : '0');

  try {{
    const resp = await fetch('/parse', {{ method: 'POST', body: fd }});
    const data = await resp.json();
    tmpDiv.remove();
    const resultDiv = document.createElement('div');
    resultDiv.className = 'result'; resultDiv.style.display = 'block';
    if (data.success) {{
      resultDiv.innerHTML = '<strong class="success-ok">RETRY OK</strong> ' + escapeHtml(f.name) +
        '<pre>' + escapeHtml((data.markdown || '').substring(0, 2000)) + '</pre>';
    }} else {{
      resultDiv.innerHTML = '<strong class="error">RETRY FAILED</strong> ' + escapeHtml(f.name) +
        '<div class="error">' + escapeHtml(data.error || '') + '</div>';
    }}
    results.appendChild(resultDiv);
  }} catch (err) {{
    tmpDiv.innerHTML = '<span class="error">Retry network error: ' + escapeHtml(err.message) + '</span>';
  }}
  isParsing = false;
  updateUI();
}}

function escapeHtml(text) {{
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}}
</script>
</body>
</html>"""

# ===========================================================================
# App factory
# ===========================================================================

def create_app() -> "FastAPI":
    if FastAPI is None:
        raise ImportError("FastAPI not installed. pip install fastapi uvicorn python-multipart")

    app = FastAPI(title="M1 Document Parsing Engine", version="0.1.0")
    components = get_component_status()

    @app.get("/")
    async def root():
        return HTMLResponse(content=_build_page(components))

    @app.get("/status")
    async def status():
        return components

    @app.post("/parse")
    async def parse_document(
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
        """Upload + parse a single document."""
        suffix = Path(file.filename or "upload").suffix or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            from m1_parser.core.converter import convert, ParseOptions

            options = ParseOptions(
                backend=backend,
                ocr_engine=ocr,
                vlm_preset=vlm_preset or None,
                output_dir=output_dir or None,
                output_formats=[format],
                max_pages=int(max_pages) if max_pages.strip() else None,
                picture_description=picture_description == "1",
                export_tables=export_tables == "1",
            )
            result = convert(tmp_path, options)

            if result.success:
                return {
                    "success": True,
                    "doc_id": result.doc_id,
                    "markdown": result.markdown,
                    "html": result.html,
                    "result": result.json_dict,
                    "page_count": result.page_count,
                    "figure_count": result.figure_count,
                    "table_count": result.table_count,
                    "output_dir": result.output_dir,
                    "metadata": result.metadata,
                    "parse_time_sec": result.parse_time_sec,
                    "tables_csv": result.tables_csv,
                }
            else:
                return {"success": False, "error": result.error or "Unknown error"}
        except Exception as e:
            logger.exception("Parse failed: %s", file.filename)
            return {"success": False, "error": str(e)}
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

    return app


# ===========================================================================
# Entry point
# ===========================================================================

_start_time: datetime | None = None


def main(host: str = "127.0.0.1", port: int = 8004) -> None:
    global _start_time
    _start_time = datetime.now(timezone.utc)

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    app = create_app()
    print("=" * 60)
    print("  M1 Document Parsing Engine -- Web Server")
    print(f"  http://{host}:{port}")
    print(f"  API docs: http://{host}:{port}/docs")
    print(f"  Status:    http://{host}:{port}/status")
    print("=" * 60)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
