from __future__ import annotations

import argparse
import csv
import html
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
FIELDNAMES = [
    "include",
    "id",
    "section",
    "assertion",
    "user_edit",
    "status",
    "evidence_or_check",
]


PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Assertions Review</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8f5;
      --panel: #ffffff;
      --ink: #1f2a24;
      --muted: #5d6a63;
      --line: #d9dfd8;
      --accent: #1f6f50;
      --accent-soft: #e4f1eb;
      --warn: #8a5b00;
    }
    body {
      margin: 0;
      font-family: Aptos, Segoe UI, Arial, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 18px 24px 14px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 24px;
      font-weight: 650;
    }
    .sub {
      color: var(--muted);
      margin: 0;
      max-width: 980px;
      line-height: 1.35;
    }
    .toolbar {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      margin-top: 14px;
    }
    button, select, input[type="search"] {
      font: inherit;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 6px;
      padding: 8px 10px;
    }
    button.primary {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }
    button:disabled {
      opacity: .55;
    }
    input[type="search"] {
      min-width: 260px;
      flex: 1 1 320px;
    }
    main {
      padding: 18px 24px 40px;
    }
    .table-wrap {
      overflow-x: auto;
      border: 1px solid var(--line);
      background: var(--panel);
    }
    .status {
      color: var(--muted);
      margin: 0 0 12px;
      min-height: 22px;
    }
    table {
      border-collapse: collapse;
      width: max(100%, 1500px);
      background: var(--panel);
      table-layout: fixed;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 9px 10px;
      vertical-align: top;
      text-align: left;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #eef3ef;
      font-size: 13px;
      color: #2d3932;
    }
    td.include, th.include {
      width: 70px;
      text-align: center;
    }
    td.id {
      width: 56px;
      font-variant-numeric: tabular-nums;
      color: var(--muted);
    }
    td.section {
      width: 150px;
      color: #34453b;
    }
    th.assertion-col,
    td.assertion-cell {
      width: 330px;
    }
    th.edit-col,
    td.edit-cell {
      width: 520px;
    }
    td.status-cell {
      width: 95px;
    }
    th.evidence-col,
    td.evidence-cell {
      width: 260px;
    }
    .pill {
      display: inline-block;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      background: var(--accent-soft);
      color: #1e5f45;
      white-space: nowrap;
    }
    .pill.verify {
      background: #fff2c7;
      color: var(--warn);
    }
    .evidence {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
    }
    .assertion {
      line-height: 1.35;
    }
    .user-edit {
      width: 100%;
      min-height: 56px;
      resize: vertical;
      font: inherit;
      line-height: 1.35;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 8px;
      box-sizing: border-box;
      background: #fff;
      color: var(--ink);
    }
    .user-edit:not(:placeholder-shown) {
      border-color: var(--accent);
      background: #fbfffd;
    }
    .edit-tools {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 6px;
    }
    .copy-to {
      font-size: 12px;
      padding: 4px 7px;
      border-radius: 5px;
      white-space: nowrap;
    }
    .edit-hint {
      color: var(--muted);
      font-size: 12px;
    }
    tr.excluded .assertion,
    tr.excluded .section,
    tr.excluded .evidence {
      color: #8a938d;
    }
    tr.excluded {
      background: #fafafa;
    }
  </style>
</head>
<body>
  <header>
    <h1>Assertions Review</h1>
    <p class="sub">Tick assertions to include. Unticked rows stay in the CSV as excluded, so the audit trail remains intact.</p>
    <div class="toolbar">
      <button class="primary" id="save">Save CSV</button>
      <button id="copyTsv">Copy visible TSV</button>
      <button id="includeAll">Include all visible</button>
      <button id="excludeAll">Exclude all visible</button>
      <select id="sectionFilter" aria-label="Filter by section"></select>
      <input id="search" type="search" placeholder="Search assertions, evidence or status">
    </div>
  </header>
  <main>
    <p class="status" id="status"></p>
    <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th class="include">Include</th>
          <th>ID</th>
          <th>Section</th>
          <th class="assertion-col">Assertion</th>
          <th class="edit-col">User edit</th>
          <th>Status</th>
          <th class="evidence-col">Evidence / check</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
    </div>
  </main>
  <script>
    let rows = [];
    let dirty = false;

    const statusEl = document.getElementById('status');
    const rowsEl = document.getElementById('rows');
    const searchEl = document.getElementById('search');
    const sectionFilterEl = document.getElementById('sectionFilter');

    function setStatus(message) {
      statusEl.textContent = message;
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[ch]));
    }

    function visibleRows() {
      const query = searchEl.value.trim().toLowerCase();
      const section = sectionFilterEl.value;
      return rows.filter(row => {
        const matchesSection = !section || row.section === section;
        const haystack = `${row.id} ${row.section} ${row.assertion} ${row.user_edit || ''} ${row.status} ${row.evidence_or_check}`.toLowerCase();
        return matchesSection && (!query || haystack.includes(query));
      });
    }

    function renderFilters() {
      const sections = [...new Set(rows.map(row => row.section))].sort();
      sectionFilterEl.innerHTML = '<option value="">All sections</option>' +
        sections.map(section => `<option value="${escapeHtml(section)}">${escapeHtml(section)}</option>`).join('');
    }

    function render() {
      const filtered = visibleRows();
      rowsEl.innerHTML = filtered.map(row => {
        const checked = row.include === 'TRUE' ? 'checked' : '';
        const excluded = row.include === 'TRUE' ? '' : ' class="excluded"';
        const statusClass = row.status === 'verify' ? 'pill verify' : 'pill';
        return `<tr${excluded}>
          <td class="include"><input type="checkbox" data-id="${escapeHtml(row.id)}" ${checked}></td>
          <td class="id">${escapeHtml(row.id)}</td>
          <td class="section">${escapeHtml(row.section)}</td>
          <td class="assertion assertion-cell">${escapeHtml(row.assertion)}</td>
          <td class="edit-cell">
            <div class="edit-tools">
              <button class="copy-to" type="button" data-copy-id="${escapeHtml(row.id)}">Copy to edit</button>
              <span class="edit-hint">${row.user_edit ? 'Edited wording' : 'Optional'}</span>
            </div>
            <textarea class="user-edit" data-edit-id="${escapeHtml(row.id)}" placeholder="Optional revised wording">${escapeHtml(row.user_edit || '')}</textarea>
          </td>
          <td class="status-cell"><span class="${statusClass}">${escapeHtml(row.status)}</span></td>
          <td class="evidence evidence-cell">${escapeHtml(row.evidence_or_check)}</td>
        </tr>`;
      }).join('');
      const included = rows.filter(row => row.include === 'TRUE').length;
      setStatus(`${included} of ${rows.length} included. Showing ${filtered.length}. ${dirty ? 'Unsaved changes.' : 'Saved.'}`);
    }

    function tsvCell(value) {
      return String(value ?? '').replace(/\r?\n/g, ' ').replace(/\t/g, ' ').trim();
    }

    function visibleRowsAsTsv() {
      const columns = ['include', 'id', 'section', 'assertion', 'user_edit', 'status', 'evidence_or_check'];
      const lines = [columns.join('\t')];
      for (const row of visibleRows()) {
        lines.push(columns.map(column => tsvCell(row[column])).join('\t'));
      }
      return lines.join('\n');
    }

    async function copyVisibleTsv() {
      const tsv = visibleRowsAsTsv();
      try {
        await navigator.clipboard.writeText(tsv);
        setStatus(`Copied ${visibleRows().length} visible rows as TSV.`);
      } catch (error) {
        const textArea = document.createElement('textarea');
        textArea.value = tsv;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        setStatus(`Copied ${visibleRows().length} visible rows as TSV.`);
      }
    }

    async function loadRows() {
      const response = await fetch('/api/assertions');
      if (!response.ok) throw new Error('Could not load assertions CSV');
      rows = await response.json();
      renderFilters();
      render();
    }

    async function saveRows() {
      document.getElementById('save').disabled = true;
      const response = await fetch('/api/assertions', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(rows)
      });
      document.getElementById('save').disabled = false;
      if (!response.ok) {
        setStatus('Save failed. Check the terminal for details.');
        return;
      }
      dirty = false;
      render();
    }

    rowsEl.addEventListener('change', event => {
      const checkbox = event.target.closest('input[type="checkbox"][data-id]');
      if (!checkbox) return;
      const row = rows.find(item => item.id === checkbox.dataset.id);
      if (!row) return;
      row.include = checkbox.checked ? 'TRUE' : 'FALSE';
      dirty = true;
      render();
    });

    rowsEl.addEventListener('input', event => {
      const textarea = event.target.closest('textarea[data-edit-id]');
      if (!textarea) return;
      const row = rows.find(item => item.id === textarea.dataset.editId);
      if (!row) return;
      row.user_edit = textarea.value;
      dirty = true;
      const included = rows.filter(row => row.include === 'TRUE').length;
      setStatus(`${included} of ${rows.length} included. Showing ${visibleRows().length}. Unsaved changes.`);
    });

    rowsEl.addEventListener('click', event => {
      const button = event.target.closest('button[data-copy-id]');
      if (!button) return;
      const row = rows.find(item => item.id === button.dataset.copyId);
      if (!row) return;
      row.user_edit = row.assertion;
      dirty = true;
      render();
    });

    document.getElementById('save').addEventListener('click', saveRows);
    document.getElementById('copyTsv').addEventListener('click', copyVisibleTsv);
    document.getElementById('includeAll').addEventListener('click', () => {
      const ids = new Set(visibleRows().map(row => row.id));
      rows.forEach(row => { if (ids.has(row.id)) row.include = 'TRUE'; });
      dirty = true;
      render();
    });
    document.getElementById('excludeAll').addEventListener('click', () => {
      const ids = new Set(visibleRows().map(row => row.id));
      rows.forEach(row => { if (ids.has(row.id)) row.include = 'FALSE'; });
      dirty = true;
      render();
    });
    searchEl.addEventListener('input', render);
    sectionFilterEl.addEventListener('change', render);

    window.addEventListener('beforeunload', event => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = '';
    });

    loadRows().catch(error => setStatus(error.message));
  </script>
</body>
</html>
"""


def read_assertions(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_assertions(csv_path: Path, rows: list[dict[str, str]]) -> None:
    cleaned_rows = []
    for row in rows:
        cleaned_rows.append({field: str(row.get(field, "")) for field in FIELDNAMES})

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(cleaned_rows)


def create_handler(csv_path: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self.respond(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/assertions":
                payload = json.dumps(read_assertions(csv_path)).encode("utf-8")
                self.respond(200, payload, "application/json; charset=utf-8")
            else:
                self.respond(404, b"Not found", "text/plain; charset=utf-8")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path != "/api/assertions":
                self.respond(404, b"Not found", "text/plain; charset=utf-8")
                return

            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length)
            try:
                rows = json.loads(payload.decode("utf-8"))
                if not isinstance(rows, list):
                    raise ValueError("Expected a list of rows")
                write_assertions(csv_path, rows)
            except Exception as exc:
                self.respond(400, html.escape(str(exc)).encode("utf-8"), "text/plain; charset=utf-8")
                return

            self.respond(200, b"Saved", "text/plain; charset=utf-8")

        def log_message(self, format: str, *args: object) -> None:
            return

        def respond(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Edit assertions.csv with a local checkbox UI.")
    parser.add_argument("--csv", default="assertions.csv", help="Path to the assertions CSV.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind.")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser automatically.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing {csv_path}")

    server = ThreadingHTTPServer((args.host, args.port), create_handler(csv_path))
    url = f"http://{args.host}:{args.port}/"
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    print(f"Assertions editor running at {url}")
    print(f"Editing {csv_path}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
