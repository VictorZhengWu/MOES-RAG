# -*- coding: utf-8 -*-
"""
M3 standalone search server — FastAPI + search page for testing retrieval.
Start: python -m m3_retrieval.standalone.search_server
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from fastapi import FastAPI, Form
    from fastapi.responses import HTMLResponse
except ImportError:
    FastAPI = None

_SEARCH_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>M3 Retrieval Engine — Search</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 1000px; margin: 30px auto; padding: 20px; background: #f5f5f5; color: #333; }
  h1 { font-size: 1.4em; margin-bottom: 4px; }
  .subtitle { color: #666; margin-bottom: 20px; font-size: 0.9em; }
  .search-bar { display: flex; gap: 8px; margin-bottom: 16px; }
  .search-bar input { flex: 1; padding: 10px 14px; border: 1px solid #ccc; border-radius: 6px;
                      font-size: 1em; }
  .search-bar input:focus { outline: none; border-color: #4a90d9; }
  .search-bar button { padding: 10px 24px; background: #4a90d9; color: #fff; border: none;
                       border-radius: 6px; cursor: pointer; font-size: 1em; }
  .search-bar button:hover { background: #357abd; }
  .search-bar button:disabled { background: #bbb; cursor: not-allowed; }
  .options { display: flex; gap: 16px; margin-bottom: 16px; align-items: center; font-size: 0.9em; }
  .options label { display: flex; align-items: center; gap: 4px; cursor: pointer; }
  .card { background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 12px; border: 1px solid #e0e0e0; }
  .card h3 { font-size: 0.95em; margin-bottom: 8px; color: #555; }
  .analysis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 16px; font-size: 0.88em; }
  .analysis-grid .label { color: #888; }
  .analysis-grid .value { font-weight: 500; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 0.85em;
         font-weight: 500; margin: 2px; }
  .tag.keyword { background: #e8f0fe; color: #2563eb; }
  .tag.path { background: #e6f4ea; color: #137333; }
  .result-item { padding: 10px 0; border-bottom: 1px solid #eee; }
  .result-item:last-child { border-bottom: none; }
  .result-score { font-weight: 600; color: #4a90d9; font-size: 0.85em; }
  .result-source { font-size: 0.8em; color: #888; }
  .result-citation { font-size: 0.82em; color: #666; margin-top: 2px; }
  .result-text { font-size: 0.88em; line-height: 1.5; margin-top: 4px; color: #333; }
  .empty { color: #888; font-style: italic; }
  .error { color: #c00; background: #fee; padding: 10px; border-radius: 4px; }
</style>
</head>
<body>
<h1>M3 Retrieval Engine</h1>
<p class="subtitle">Marine &amp; Offshore Expert System — Hybrid Search</p>

<div class="search-bar">
  <input type="text" id="queryInput" placeholder='Try: "DNV Pt.4 Ch.3 EH36 预热温度要求"'
         onkeydown="if(event.key==='Enter') doSearch()">
  <button id="searchBtn" onclick="doSearch()">Search</button>
</div>

<div class="options">
  <label><input type="checkbox" id="showAnalysis" checked> Show query analysis</label>
  <label><input type="checkbox" id="showPipeline" checked> Show pipeline details</label>
  <label>Top K: <input type="text" id="topK" value="10" style="width:50px;text-align:center"></label>
</div>

<div id="analysisArea"></div>
<div id="pipelineArea"></div>
<div id="resultsArea"></div>

<script>
async function doSearch() {
  const q = document.getElementById('queryInput').value.trim();
  if (!q) return;
  const btn = document.getElementById('searchBtn');
  btn.disabled = true; btn.textContent = 'Searching...';
  document.getElementById('resultsArea').innerHTML = '';
  document.getElementById('analysisArea').innerHTML = '';
  document.getElementById('pipelineArea').innerHTML = '';

  const fd = new FormData();
  fd.append('query', q);
  fd.append('top_k', document.getElementById('topK').value || '10');

  try {
    const resp = await fetch('/search', { method: 'POST', body: fd });
    const data = await resp.json();

    // Query analysis
    if (document.getElementById('showAnalysis').checked && data.analysis) {
      const a = data.analysis;
      document.getElementById('analysisArea').innerHTML =
        '<div class="card"><h3>Query Analysis</h3>' +
        '<div class="analysis-grid">' +
        row('Classification', a.classification_society) +
        row('Chapter', a.chapter_section) +
        row('Year', a.version_year) +
        row('Keywords', (a.keywords||[]).map(k => '<span class="tag keyword">'+esc(k)+'</span>').join(' ')) +
        row('Semantic Query', a.semantic_query) +
        '</div></div>';
    }

    // Pipeline info
    if (document.getElementById('showPipeline').checked) {
      document.getElementById('pipelineArea').innerHTML =
        '<div class="card"><h3>Pipeline</h3>' +
        '<span class="tag path">' + esc(data.path) + '</span> ' +
        esc(data.path_desc || '') +
        ' | ' + (data.total_found||0) + ' found | ' + (data.latency_ms||'?') + 'ms' +
        '</div>';
    }

    // Results
    const chunks = data.chunks || [];
    if (chunks.length === 0) {
      document.getElementById('resultsArea').innerHTML =
        '<div class="card"><p class="empty">No results. Try a different query.</p></div>';
    } else {
      let html = '<div class="card"><h3>Results</h3>';
      for (const c of chunks) {
        html += '<div class="result-item">' +
          '<span class="result-score">' + (c.score||0).toFixed(4) + '</span> ' +
          '<span class="result-source">[' + esc(c.source) + ']</span>' +
          '<div class="result-citation">' + esc(c.citation||'') + '</div>' +
          '<div class="result-text">' + esc((c.text||'').substring(0, 300)) + '</div>' +
          '</div>';
      }
      html += '</div>';
      document.getElementById('resultsArea').innerHTML = html;
    }
  } catch (err) {
    document.getElementById('resultsArea').innerHTML =
      '<div class="error">' + esc(err.message) + '</div>';
  }
  btn.disabled = false; btn.textContent = 'Search';
}

function row(label, value) {
  if (!value) return '';
  return '<div><span class="label">'+esc(label)+'</span></div><div class="value">'+esc(String(value))+'</div>';
}

function esc(s) { const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }
</script>
</body>
</html>"""


def create_app() -> "FastAPI":
    if FastAPI is None:
        raise ImportError("FastAPI not installed. pip install fastapi uvicorn")

    app = FastAPI(title="M3 Retrieval Engine", version="0.1.0")

    @app.get("/")
    async def root():
        return HTMLResponse(content=_SEARCH_PAGE)

    @app.post("/search")
    async def search(query: str = Form(""), top_k: str = Form("10")):
        """Execute retrieval pipeline and return results."""
        try:
            k = int(top_k) if top_k.isdigit() else 10
        except Exception:
            k = 10

        # Analyse query
        from m3_retrieval.stages.query_analyzer import (
            analyze_query, _is_exact_match, _is_keyword_query,
        )

        qa = analyze_query(query)

        # Determine pipeline path
        if _is_exact_match(query):
            path = "fast (BM25 only)"
            path_desc = "Exact match query"
        elif _is_keyword_query(query):
            path = "medium (hybrid, no rerank)"
            path_desc = "Keyword query"
        else:
            path = "full (7-stage pipeline)"
            path_desc = "Full natural language query"

        # For demo mode (no M2 connected): show analysis without actual retrieval
        analysis = {
            "classification_society": qa.classification_society,
            "chapter_section": qa.chapter_section,
            "version_year": qa.version_year,
            "keywords": qa.keywords,
            "semantic_query": qa.semantic_query,
        }

        return {
            "analysis": analysis,
            "path": path,
            "path_desc": path_desc,
            "chunks": [],  # Demo mode — no M2 backend connected
            "total_found": 0,
            "latency_ms": 0,
            "note": "Demo mode: query analysis only. Connect M2 StorageManager for full retrieval.",
        }

    return app


def main(host: str = "127.0.0.1", port: int = 8008) -> None:
    try:
        import uvicorn
    except ImportError:
        print("pip install uvicorn"); sys.exit(1)
    app = create_app()
    print(f"M3 Retrieval Search: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
