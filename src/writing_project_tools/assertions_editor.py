from __future__ import annotations

import argparse
import csv
import html
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
FIELDNAMES = [
    "include",
    "id",
    "section",
    "precis",
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
  <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
  <style>
    /* For custom variables or styles not easily done in Tailwind, like native dialog backdrop support and page font defaults */
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
      font-family: Aptos, Segoe UI, Arial, sans-serif;
    }
    /* Native dialog styling with clean transition */
    dialog {
      border: none;
      border-radius: 12px;
      padding: 0;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
      background: white;
      opacity: 0;
      transform: scale(0.95);
      transition: opacity 0.2s ease-in-out, transform 0.2s ease-in-out, overlay 0.2s allow-discrete, display 0.2s allow-discrete;
      max-width: 90vw;
      max-height: 90vh;
      width: 500px;
    }
    dialog[open] {
      opacity: 1;
      transform: scale(1);
    }
    @starting-style {
      dialog[open] {
        opacity: 0;
        transform: scale(0.95);
      }
    }
    dialog::backdrop {
      background-color: rgba(15, 23, 42, 0.3);
      backdrop-filter: blur(8px);
      opacity: 0;
      transition: opacity 0.2s ease-in-out, overlay 0.2s allow-discrete, display 0.2s allow-discrete;
    }
    dialog[open]::backdrop {
      opacity: 1;
    }
    @starting-style {
      dialog[open]::backdrop {
        opacity: 0;
      }
    }
  </style>
</head>
<body class="bg-[#f7f8f5] text-[#1f2a24] min-h-screen flex flex-col overflow-x-hidden">
  <header class="bg-white border-b border-[#d9dfd8] px-6 py-4.5 shadow-sm">
    <div class="max-w-[1600px] mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-[#1f2a24] tracking-tight">Assertions Review</h1>
        <p class="text-sm text-[#5d6a63] mt-1">Tick assertions to include. Unticked rows stay in the CSV as excluded, so the audit trail remains intact.</p>
      </div>
      <div class="flex flex-wrap gap-2.5 items-center">
        <button onclick="location.href='/markdown'" type="button" class="px-4.5 py-2.5 text-sm font-semibold border border-[#d9dfd8] bg-white rounded-lg hover:bg-gray-50 hover:border-gray-400 transition cursor-pointer">Markdown editor</button>
        <button id="addAssertionBtn" type="button" class="px-4.5 py-2.5 text-sm font-semibold border border-dashed border-[#1f6f50] text-[#1f6f50] bg-[#e4f1eb] rounded-lg hover:bg-[#d5ebd1] transition cursor-pointer">Add Assertion</button>
        <button class="px-4.5 py-2.5 text-sm font-semibold bg-[#1f6f50] text-white rounded-lg hover:bg-[#195a41] transition cursor-pointer" id="save">Save CSV</button>
      </div>
    </div>
    <div class="max-w-[1600px] mx-auto flex flex-wrap gap-3 items-center mt-4 border-t border-[#d9dfd8]/50 pt-4">
      <button id="copyTsv" class="px-3.5 py-2 text-xs font-semibold border border-[#d9dfd8] bg-white rounded-md hover:bg-gray-50 transition cursor-pointer">Copy visible TSV</button>
      <button id="includeAll" class="px-3.5 py-2 text-xs font-semibold border border-[#d9dfd8] bg-white rounded-md hover:bg-gray-50 transition cursor-pointer">Include all visible</button>
      <button id="excludeAll" class="px-3.5 py-2 text-xs font-semibold border border-[#d9dfd8] bg-white rounded-md hover:bg-gray-50 transition cursor-pointer">Exclude all visible</button>
      <select id="sectionFilter" aria-label="Filter by section" class="px-3.5 py-2 text-xs border border-[#d9dfd8] bg-white rounded-md focus:outline-none focus:border-[#1f6f50] cursor-pointer min-w-[180px]"></select>
      <input id="search" type="search" placeholder="Search précis, assertions, evidence or status" class="px-3.5 py-2 text-xs border border-[#d9dfd8] bg-white rounded-md focus:outline-none focus:border-[#1f6f50] flex-grow md:max-w-md">
    </div>
  </header>
  <main class="flex-grow px-6 py-5 max-w-[1600px] w-full mx-auto overflow-hidden">
    <p class="text-sm text-[#5d6a63] mb-3 min-h-[20px] font-medium" id="status"></p>
    <div class="w-full max-w-full overflow-x-auto border border-[#d9dfd8] bg-white rounded-xl shadow-md">
      <table class="w-full border-collapse table-fixed min-w-[1700px]">
        <thead>
          <tr class="bg-[#eef3ef] border-b border-[#d9dfd8]">
            <th class="w-[70px] text-center py-3.5 px-3 text-xs font-bold text-[#2d3932] uppercase tracking-wider sticky top-0 bg-[#eef3ef]">Include</th>
            <th class="w-[70px] text-left py-3.5 px-3 text-xs font-bold text-[#2d3932] uppercase tracking-wider sticky top-0 bg-[#eef3ef]">ID</th>
            <th class="w-[150px] text-left py-3.5 px-3 text-xs font-bold text-[#2d3932] uppercase tracking-wider sticky top-0 bg-[#eef3ef]">Section</th>
            <th class="w-[190px] text-left py-3.5 px-3 text-xs font-bold text-[#2d3932] uppercase tracking-wider sticky top-0 bg-[#eef3ef]">Précis</th>
            <th class="w-[330px] text-left py-3.5 px-3 text-xs font-bold text-[#2d3932] uppercase tracking-wider sticky top-0 bg-[#eef3ef]">Assertion</th>
            <th class="w-[500px] text-left py-3.5 px-3 text-xs font-bold text-[#2d3932] uppercase tracking-wider sticky top-0 bg-[#eef3ef]">User edit</th>
            <th class="w-[125px] text-left py-3.5 px-3 text-xs font-bold text-[#2d3932] uppercase tracking-wider sticky top-0 bg-[#eef3ef]">Status</th>
            <th class="w-[260px] text-left py-3.5 px-3 text-xs font-bold text-[#2d3932] uppercase tracking-wider sticky top-0 bg-[#eef3ef]">Evidence / check</th>
            <th class="w-[90px] text-center py-3.5 px-3 text-xs font-bold text-[#2d3932] uppercase tracking-wider sticky top-0 bg-[#eef3ef]">Actions</th>
          </tr>
        </thead>
        <tbody id="rows" class="divide-y divide-[#d9dfd8]"></tbody>
      </table>
    </div>
  </main>

  <!-- Add Assertion Modal Dialog -->
  <dialog id="addModal" class="w-full max-w-lg p-6 rounded-xl border border-[#d9dfd8]/80 backdrop:backdrop-blur-sm overflow-y-auto">
    <form method="dialog" id="addForm" class="space-y-4">
      <div class="flex items-center justify-between border-b border-[#d9dfd8]/50 pb-3">
        <h2 class="text-lg font-bold text-[#1f2a24]">Add New Assertion</h2>
        <button type="button" onclick="document.getElementById('addModal').close()" class="text-gray-400 hover:text-gray-600 text-xl font-semibold cursor-pointer">&times;</button>
      </div>
      <div class="grid grid-cols-3 gap-4">
        <div class="col-span-1">
          <label for="newId" class="block text-xs font-bold text-[#2d3932] uppercase mb-1">ID</label>
          <input type="text" id="newId" required class="w-full px-3 py-2 text-sm border border-[#d9dfd8] rounded-md focus:outline-none focus:border-[#1f6f50] bg-gray-50 font-mono">
        </div>
        <div class="col-span-2">
          <label for="newSection" class="block text-xs font-bold text-[#2d3932] uppercase mb-1">Section</label>
          <input type="text" id="newSection" list="sectionList" required placeholder="e.g. Intro" class="w-full px-3 py-2 text-sm border border-[#d9dfd8] rounded-md focus:outline-none focus:border-[#1f6f50]">
          <datalist id="sectionList"></datalist>
        </div>
      </div>
      <div>
        <label for="newPrecis" class="block text-xs font-bold text-[#2d3932] uppercase mb-1">Précis</label>
        <input type="text" id="newPrecis" placeholder="Short label for navigating the list" class="w-full px-3 py-2 text-sm border border-[#d9dfd8] rounded-md focus:outline-none focus:border-[#1f6f50]">
      </div>
      <div>
        <label for="newAssertion" class="block text-xs font-bold text-[#2d3932] uppercase mb-1">Assertion Wording</label>
        <textarea id="newAssertion" required placeholder="Describe the claim or assertion..." class="w-full px-3 py-2 text-sm border border-[#d9dfd8] rounded-md focus:outline-none focus:border-[#1f6f50] min-h-[80px]"></textarea>
      </div>
      <div>
        <label for="newEvidence" class="block text-xs font-bold text-[#2d3932] uppercase mb-1">Evidence / Check</label>
        <textarea id="newEvidence" placeholder="Optional evidence or validation method..." class="w-full px-3 py-2 text-sm border border-[#d9dfd8] rounded-md focus:outline-none focus:border-[#1f6f50] min-h-[60px]"></textarea>
      </div>
      <div>
        <label for="newStatus" class="block text-xs font-bold text-[#2d3932] uppercase mb-1">Status</label>
        <select id="newStatus" class="w-full px-3 py-2 text-sm border border-[#d9dfd8] bg-white rounded-md focus:outline-none focus:border-[#1f6f50]">
          <option value="planned">planned</option>
          <option value="interpretation">interpretation</option>
          <option value="verify" selected>verify</option>
          <option value="verified">verified</option>
          <option value="draft_phrase">draft_phrase</option>
          <option value="removed">removed</option>
        </select>
      </div>
      <div class="flex justify-end gap-2.5 pt-2 border-t border-[#d9dfd8]/50">
        <button type="button" onclick="document.getElementById('addModal').close()" class="px-4 py-2 text-sm font-semibold border border-[#d9dfd8] bg-white rounded-lg hover:bg-gray-50 transition cursor-pointer">Cancel</button>
        <button type="submit" class="px-4 py-2 text-sm font-semibold bg-[#1f6f50] text-white rounded-lg hover:bg-[#195a41] transition cursor-pointer">Add Assertion</button>
      </div>
    </form>
  </dialog>

  <script>
    let rows = [];
    let dirty = false;
    let newRowIds = new Set();

    const statusEl = document.getElementById('status');
    const rowsEl = document.getElementById('rows');
    const searchEl = document.getElementById('search');
    const sectionFilterEl = document.getElementById('sectionFilter');
    const projectKey = __ASSERTIONS_PROJECT_KEY__;
    const seenRowsKey = `assertions-editor-seen:${projectKey}`;

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
        const haystack = `${row.id} ${row.section} ${row.precis || ''} ${row.assertion} ${row.user_edit || ''} ${row.status} ${row.evidence_or_check}`.toLowerCase();
        return matchesSection && (!query || haystack.includes(query));
      });
    }

    function renderFilters() {
      const sections = [...new Set(rows.map(row => row.section))].filter(Boolean).sort();
      sectionFilterEl.innerHTML = '<option value="">All sections</option>' +
        sections.map(section => `<option value="${escapeHtml(section)}">${escapeHtml(section)}</option>`).join('');
      
      const datalist = document.getElementById('sectionList');
      datalist.innerHTML = sections.map(section => `<option value="${escapeHtml(section)}">`).join('');
    }

    function render() {
      const filtered = visibleRows();
      rowsEl.innerHTML = filtered.map(row => {
        const key = rowKey(row);
        const checked = row.include === 'TRUE' ? 'checked' : '';
        const rowClasses = [];
        if (row.include !== 'TRUE') rowClasses.push('bg-gray-50/70 text-[#8a938d]');
        if (newRowIds.has(key)) rowClasses.push('bg-blue-50/50 border-l-4 border-blue-500');
        const classAttr = rowClasses.length ? ` class="${rowClasses.join(' ')}"` : '';
        
        const newBadge = newRowIds.has(key) ? '<span class="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">New</span>' : '';
        
        let statusClass = 'text-xs rounded-full px-2.5 py-1 font-semibold border focus:outline-none cursor-pointer ';
        if (row.status === 'verify') {
          statusClass += 'bg-amber-100 text-[#8a5b00] border-amber-200';
        } else if (row.status === 'verified') {
          statusClass += 'bg-emerald-100 text-emerald-800 border-emerald-200';
        } else if (row.status === 'removed') {
          statusClass += 'bg-red-100 text-red-800 border-red-200';
        } else {
          statusClass += 'bg-gray-100 text-gray-800 border-gray-200';
        }
        
        const statusOptions = ['planned', 'interpretation', 'verify', 'verified', 'draft_phrase', 'removed'];
        const currentStatus = row.status || 'verify';
        const options = statusOptions.map(status =>
          `<option value="${escapeHtml(status)}" ${status === currentStatus ? 'selected' : ''}>${escapeHtml(status)}</option>`
        ).join('');
        
        return `<tr${classAttr}>
          <td class="py-3 px-3 text-center align-middle"><input type="checkbox" data-id="${escapeHtml(row.id)}" ${checked} class="w-4 h-4 text-[#1f6f50] border-[#d9dfd8] rounded focus:ring-[#1f6f50] cursor-pointer"></td>
          <td class="py-3 px-3 align-middle font-mono text-xs text-[#5d6a63] whitespace-nowrap">${escapeHtml(row.id)}${newBadge}</td>
          <td class="py-3 px-3 align-middle text-sm font-semibold">${escapeHtml(row.section)}</td>
          <td class="py-3 px-3"><input type="text" class="precis w-full text-sm border border-[#d9dfd8] rounded-md p-2 focus:outline-none focus:border-[#1f6f50]" data-precis-id="${escapeHtml(row.id)}" value="${escapeHtml(row.precis || '')}" placeholder="Short label"></td>
          <td class="py-3 px-3 text-sm leading-relaxed">${escapeHtml(row.assertion)}</td>
          <td class="py-3 px-3">
            <div class="flex items-center justify-between gap-2 mb-1.5">
              <button class="copy-to text-xs px-2 py-1 bg-gray-50 border border-[#d9dfd8] rounded hover:bg-gray-100 transition cursor-pointer" type="button" data-copy-id="${escapeHtml(row.id)}">Copy to edit</button>
              <span class="text-xs text-[#5d6a63] font-medium">${row.user_edit ? 'Edited wording' : 'Optional'}</span>
            </div>
            <textarea class="user-edit w-full min-h-[56px] text-sm border border-[#d9dfd8] rounded-md p-2 focus:outline-none focus:border-[#1f6f50] focus:bg-[#fbfffd] resize-y" data-edit-id="${escapeHtml(row.id)}" placeholder="Optional revised wording">${escapeHtml(row.user_edit || '')}</textarea>
          </td>
          <td class="py-3 px-3 align-middle"><select class="${statusClass}" data-status-id="${escapeHtml(row.id)}">${options}</select></td>
          <td class="py-3 px-3 text-sm text-[#5d6a63] leading-relaxed">${escapeHtml(row.evidence_or_check)}</td>
          <td class="py-3 px-3 align-middle text-center">
            <button class="remove-btn text-xs font-semibold text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 hover:border-red-300 rounded-lg px-2.5 py-1.5 transition cursor-pointer" type="button" data-remove-id="${escapeHtml(row.id)}">Delete</button>
          </td>
        </tr>`;
      }).join('');
      const included = rows.filter(row => row.include === 'TRUE').length;
      const newCount = newRowIds.size;
      const newText = newCount ? ` ${newCount} new since last refresh.` : '';
      setStatus(`${included} of ${rows.length} included. Showing ${filtered.length}.${newText} ${dirty ? 'Unsaved changes.' : 'Saved.'}`);
    }

    function rowKey(row) {
      return String(row.id || `${row.section}|${row.assertion}`);
    }

    function generateNextId() {
      let maxNum = 0;
      let prefix = 'A';
      for (const row of rows) {
        const match = String(row.id).match(/^([A-Za-z]+)?(\d+)$/);
        if (match) {
          if (match[1]) prefix = match[1];
          const num = parseInt(match[2], 10);
          if (num > maxNum) {
            maxNum = num;
          }
        }
      }
      return `${prefix}${maxNum + 1}`;
    }

    function updateNewRowState(loadedRows) {
      const currentKeys = loadedRows.map(rowKey);
      try {
        const previousKeys = JSON.parse(localStorage.getItem(seenRowsKey) || 'null');
        if (Array.isArray(previousKeys)) {
          const previous = new Set(previousKeys);
          newRowIds = new Set(currentKeys.filter(key => !previous.has(key)));
        } else {
          newRowIds = new Set();
        }
        localStorage.setItem(seenRowsKey, JSON.stringify(currentKeys));
      } catch (error) {
        newRowIds = new Set();
      }
    }

    function tsvCell(value) {
      return String(value ?? '').replace(/\r?\n/g, ' ').replace(/\t/g, ' ').trim();
    }

    function visibleRowsAsTsv() {
      const columns = ['include', 'id', 'section', 'precis', 'assertion', 'user_edit', 'status', 'evidence_or_check'];
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
      updateNewRowState(rows);
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
      const statusSelect = event.target.closest('select[data-status-id]');
      if (!checkbox && !statusSelect) return;
      const rowId = checkbox ? checkbox.dataset.id : statusSelect.dataset.statusId;
      const row = rows.find(item => item.id === rowId);
      if (!row) return;
      if (checkbox) {
        row.include = checkbox.checked ? 'TRUE' : 'FALSE';
      } else {
        row.status = statusSelect.value;
      }
      dirty = true;
      render();
    });

    rowsEl.addEventListener('input', event => {
      const precisInput = event.target.closest('input[data-precis-id]');
      if (precisInput) {
        const row = rows.find(item => item.id === precisInput.dataset.precisId);
        if (!row) return;
        row.precis = precisInput.value;
        dirty = true;
        setStatus('Unsaved changes.');
        return;
      }
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
      if (button) {
        const row = rows.find(item => item.id === button.dataset.copyId);
        if (!row) return;
        row.user_edit = row.assertion;
        dirty = true;
        render();
        return;
      }

      const removeBtn = event.target.closest('button[data-remove-id]');
      if (removeBtn) {
        const rowId = removeBtn.dataset.removeId;
        if (confirm(`Are you sure you want to delete assertion "${rowId}"?`)) {
          const index = rows.findIndex(item => item.id === rowId);
          if (index !== -1) {
            rows.splice(index, 1);
            dirty = true;
            renderFilters();
            render();
          }
        }
      }
    });

    document.getElementById('addAssertionBtn').addEventListener('click', () => {
      document.getElementById('newId').value = generateNextId();
      document.getElementById('newSection').value = '';
      document.getElementById('newPrecis').value = '';
      document.getElementById('newAssertion').value = '';
      document.getElementById('newEvidence').value = '';
      document.getElementById('newStatus').value = 'verify';
      document.getElementById('addModal').showModal();
    });

    document.getElementById('addForm').addEventListener('submit', event => {
      event.preventDefault();
      const newId = document.getElementById('newId').value.trim();
      const newSection = document.getElementById('newSection').value.trim();
      const newPrecis = document.getElementById('newPrecis').value.trim();
      const newAssertion = document.getElementById('newAssertion').value.trim();
      const newEvidence = document.getElementById('newEvidence').value.trim();
      const newStatus = document.getElementById('newStatus').value;

      if (!newId || !newSection || !newAssertion) return;

      if (rows.some(row => row.id === newId)) {
        alert(`An assertion with ID "${newId}" already exists.`);
        return;
      }

      const newRow = {
        include: 'TRUE',
        id: newId,
        section: newSection,
        precis: newPrecis,
        assertion: newAssertion,
        user_edit: '',
        status: newStatus,
        evidence_or_check: newEvidence
      };

      rows.push(newRow);
      newRowIds.add(rowKey(newRow));
      dirty = true;
      document.getElementById('addModal').close();
      renderFilters();
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


MARKDOWN_PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Markdown Editor</title>
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
      --code: #f0f3ef;
    }
    * {
      box-sizing: border-box;
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
    .toolbar,
    .formatbar {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      margin-top: 14px;
    }
    button,
    select {
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
    button.compact {
      min-width: 36px;
      padding: 7px 9px;
      font-weight: 650;
    }
    button[data-command="bold"] { font-weight: bold; }
    button[data-command="italic"] { font-style: italic; }
    select {
      min-width: 260px;
    }
    main {
      padding: 18px 24px 40px;
    }
    .status {
      color: var(--muted);
      margin: 0 auto 12px;
      max-width: 960px;
      min-height: 22px;
    }
    .editor-container {
      max-width: 960px;
      margin: 0 auto;
    }
    .pane {
      min-height: 600px;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    }
    #editor {
      width: 100%;
      min-height: 600px;
      padding: 30px 40px;
      outline: none;
      line-height: 1.6;
      font-size: 16px;
    }
    #editor h1 { font-size: 2em; margin-top: 0.67em; margin-bottom: 0.67em; font-weight: bold; }
    #editor h2 { font-size: 1.5em; margin-top: 0.83em; margin-bottom: 0.83em; font-weight: bold; }
    #editor h3 { font-size: 1.17em; margin-top: 1em; margin-bottom: 1em; font-weight: bold; }
    #editor p { margin-bottom: 1em; }
    #editor ul, #editor ol { margin-bottom: 1em; padding-left: 30px; }
    #editor li { margin-bottom: 0.25em; }
    #editor blockquote {
      border-left: 4px solid var(--accent);
      color: var(--muted);
      margin: 0 0 1em;
      padding: 4px 0 4px 15px;
      background: var(--bg);
    }
    #editor code {
      background: var(--code);
      border-radius: 4px;
      padding: 2px 4px;
      font-family: Consolas, monospace;
    }
    #editor pre {
      background: var(--code);
      border-radius: 6px;
      padding: 12px;
      overflow-x: auto;
    }
  </style>
</head>
<body>
  <header>
    <h1>Markdown Editor</h1>
    <p class="sub">Select a project Markdown file, edit it inline, and save it back to disk.</p>
    <div class="toolbar">
      <button onclick="location.href='/'" type="button">Assertions review</button>
      <select id="fileSelect" aria-label="Markdown file"></select>
      <button class="primary" id="save" type="button">Save Markdown</button>
    </div>
    <div class="formatbar">
      <button class="compact" data-command="bold" title="Bold" type="button">B</button>
      <button class="compact" data-command="italic" title="Italic" type="button">I</button>
      <button class="compact" data-command="formatBlock" data-value="h1" title="Heading 1" type="button">H1</button>
      <button class="compact" data-command="formatBlock" data-value="h2" title="Heading 2" type="button">H2</button>
      <button class="compact" data-command="formatBlock" data-value="h3" title="Heading 3" type="button">H3</button>
      <button class="compact" data-command="insertUnorderedList" title="Bullet list" type="button">-</button>
      <button class="compact" data-command="insertOrderedList" title="Numbered list" type="button">1.</button>
    </div>
  </header>
  <main>
    <p class="status" id="status"></p>
    <div class="editor-container">
      <div class="pane">
        <div id="editor" contenteditable="true" spellcheck="true"></div>
      </div>
    </div>
  </main>
  <script>
    const fileSelect = document.getElementById('fileSelect');
    const editor = document.getElementById('editor');
    const statusEl = document.getElementById('status');
    let currentFile = '';
    let dirty = false;

    function setStatus(message) {
      statusEl.textContent = message;
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[ch]));
    }

    function renderInline(value) {
      let text = escapeHtml(value);
      text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
      text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');
      text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
      return text;
    }

    function renderMarkdown(markdown) {
      const lines = markdown.replace(/\r\n/g, '\n').split('\n');
      const html = [];
      let paragraph = [];
      let listType = '';
      let inCode = false;
      let codeLines = [];

      function flushParagraph() {
        if (!paragraph.length) return;
        html.push(`<p>${renderInline(paragraph.join(' '))}</p>`);
        paragraph = [];
      }

      function flushList() {
        if (!listType) return;
        html.push(`</${listType}>`);
        listType = '';
      }

      for (const line of lines) {
        if (line.startsWith('```')) {
          if (inCode) {
            html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
            codeLines = [];
            inCode = false;
          } else {
            flushParagraph();
            flushList();
            inCode = true;
          }
          continue;
        }
        if (inCode) {
          codeLines.push(line);
          continue;
        }

        const trimmed = line.trim();
        if (!trimmed) {
          flushParagraph();
          flushList();
          continue;
        }
        if (trimmed.startsWith('# ')) {
          flushParagraph();
          flushList();
          html.push(`<h1>${renderInline(trimmed.slice(2))}</h1>`);
        } else if (trimmed.startsWith('## ')) {
          flushParagraph();
          flushList();
          html.push(`<h2>${renderInline(trimmed.slice(3))}</h2>`);
        } else if (trimmed.startsWith('### ')) {
          flushParagraph();
          flushList();
          html.push(`<h3>${renderInline(trimmed.slice(4))}</h3>`);
        } else if (trimmed.startsWith('> ')) {
          flushParagraph();
          flushList();
          html.push(`<blockquote>${renderInline(trimmed.slice(2))}</blockquote>`);
        } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          flushParagraph();
          if (listType !== 'ul') {
            flushList();
            html.push('<ul>');
            listType = 'ul';
          }
          html.push(`<li>${renderInline(trimmed.slice(2))}</li>`);
        } else if (/^\d+\. /.test(trimmed)) {
          flushParagraph();
          if (listType !== 'ol') {
            flushList();
            html.push('<ol>');
            listType = 'ol';
          }
          html.push(`<li>${renderInline(trimmed.replace(/^\d+\. /, ''))}</li>`);
        } else {
          flushList();
          paragraph.push(trimmed);
        }
      }

      flushParagraph();
      flushList();
      if (inCode) {
        html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
      }
      return html.join('\n') || '<p>Select a Markdown file to edit.</p>';
    }

    function domToMarkdown(node) {
      if (node.nodeType === Node.TEXT_NODE) {
        return node.nodeValue;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) {
        return '';
      }

      let childrenMarkdown = '';
      for (const child of node.childNodes) {
        childrenMarkdown += domToMarkdown(child);
      }

      const tag = node.tagName.toLowerCase();
      switch (tag) {
        case 'h1':
          return `\n\n# ${childrenMarkdown.trim()}\n\n`;
        case 'h2':
          return `\n\n## ${childrenMarkdown.trim()}\n\n`;
        case 'h3':
          return `\n\n### ${childrenMarkdown.trim()}\n\n`;
        case 'strong':
        case 'b':
          return `**${childrenMarkdown}**`;
        case 'em':
        case 'i':
          return `*${childrenMarkdown}*`;
        case 'p':
          return `\n\n${childrenMarkdown.trim()}\n\n`;
        case 'blockquote':
          return `\n\n> ${childrenMarkdown.trim()}\n\n`;
        case 'ul':
          return `\n\n${childrenMarkdown}\n\n`;
        case 'ol':
          return `\n\n${childrenMarkdown}\n\n`;
        case 'li': {
          const parent = node.parentNode;
          if (parent && parent.tagName.toLowerCase() === 'ol') {
            const index = Array.from(parent.children).indexOf(node) + 1;
            return `\n${index}. ${childrenMarkdown.trim()}`;
          }
          return `\n- ${childrenMarkdown.trim()}`;
        }
        case 'pre': {
          const codeElem = node.querySelector('code');
          const codeText = codeElem ? codeElem.textContent : node.textContent;
          return `\n\n\`\`\`\n${codeText.trim()}\n\`\`\`\n\n`;
        }
        case 'code':
          if (node.parentNode && node.parentNode.tagName.toLowerCase() === 'pre') {
            return childrenMarkdown;
          }
          return `\`${childrenMarkdown}\``;
        case 'a':
          return `[${childrenMarkdown}](${node.getAttribute('href') || ''})`;
        case 'br':
          return '\n';
        case 'div':
          return `\n${childrenMarkdown.trim()}\n`;
        default:
          return childrenMarkdown;
      }
    }

    function getMarkdownFromEditor() {
      let md = '';
      for (const child of editor.childNodes) {
        md += domToMarkdown(child);
      }
      return md.replace(/\r\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim() + '\n';
    }

    async function loadFiles() {
      const response = await fetch('/api/markdown/files');
      if (!response.ok) throw new Error('Could not list Markdown files');
      const files = await response.json();
      fileSelect.innerHTML = files.map(file => `<option value="${escapeHtml(file)}">${escapeHtml(file)}</option>`).join('');
      if (files.length) {
        await loadFile(files[0]);
      } else {
        setStatus('No Markdown files found in this project.');
      }
    }

    async function loadFile(path) {
      if (dirty && !confirm('Discard unsaved changes and load another file?')) {
        fileSelect.value = currentFile;
        return;
      }
      const response = await fetch(`/api/markdown/file?path=${encodeURIComponent(path)}`);
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      currentFile = data.path;
      fileSelect.value = currentFile;
      editor.innerHTML = renderMarkdown(data.content);
      dirty = false;
      setStatus(`Editing ${currentFile}. Saved.`);
    }

    async function saveFile() {
      if (!currentFile) return;
      document.getElementById('save').disabled = true;
      const response = await fetch('/api/markdown/file', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({path: currentFile, content: getMarkdownFromEditor()})
      });
      document.getElementById('save').disabled = false;
      if (!response.ok) {
        setStatus(`Save failed: ${await response.text()}`);
        return;
      }
      dirty = false;
      setStatus(`Saved ${currentFile}.`);
    }

    fileSelect.addEventListener('change', () => loadFile(fileSelect.value).catch(error => setStatus(error.message)));
    editor.addEventListener('input', () => {
      dirty = true;
      setStatus(`Editing ${currentFile}. Unsaved changes.`);
    });
    document.getElementById('save').addEventListener('click', saveFile);
    document.querySelector('.formatbar').addEventListener('click', event => {
      const button = event.target.closest('button');
      if (!button) return;
      const cmd = button.dataset.command;
      const val = button.dataset.value || null;
      if (cmd) {
        document.execCommand(cmd, false, val);
        editor.focus();
        dirty = true;
        setStatus(`Editing ${currentFile}. Unsaved changes.`);
      }
    });
    window.addEventListener('beforeunload', event => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = '';
    });

    loadFiles().catch(error => setStatus(error.message));
  </script>
</body>
</html>
"""


def read_assertions(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return [{field: row.get(field, "") or "" for field in FIELDNAMES} for row in csv.DictReader(handle)]


def write_assertions(csv_path: Path, rows: list[dict[str, str]]) -> None:
    cleaned_rows = []
    for row in rows:
        cleaned_rows.append({field: str(row.get(field, "")) for field in FIELDNAMES})

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(cleaned_rows)


def project_root_for(csv_path: Path) -> Path:
    return csv_path.parent.resolve()


def markdown_files(root: Path) -> list[str]:
    ignored_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
    files: list[str] = []
    for path in root.rglob("*.md"):
        if any(part in ignored_dirs or part.startswith(".") for part in path.relative_to(root).parts[:-1]):
            continue
        files.append(path.relative_to(root).as_posix())
    return sorted(files)


def resolve_markdown_path(root: Path, requested_path: str) -> Path:
    if not requested_path:
        raise ValueError("Missing Markdown path")
    path = (root / requested_path).resolve()
    if root != path and root not in path.parents:
        raise ValueError("Path is outside the project")
    if path.suffix.lower() != ".md":
        raise ValueError("Only .md files can be edited")
    return path


def create_handler(csv_path: Path) -> type[BaseHTTPRequestHandler]:
    root = project_root_for(csv_path)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            if path == "/":
                page = PAGE.replace("__ASSERTIONS_PROJECT_KEY__", json.dumps(str(csv_path.resolve())))
                self.respond(200, page.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/markdown":
                self.respond(200, MARKDOWN_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/assertions":
                payload = json.dumps(read_assertions(csv_path)).encode("utf-8")
                self.respond(200, payload, "application/json; charset=utf-8")
            elif path == "/api/markdown/files":
                payload = json.dumps(markdown_files(root)).encode("utf-8")
                self.respond(200, payload, "application/json; charset=utf-8")
            elif path == "/api/markdown/file":
                query = parse_qs(parsed_url.query)
                try:
                    markdown_path = resolve_markdown_path(root, query.get("path", [""])[0])
                    payload = json.dumps(
                        {
                            "path": markdown_path.relative_to(root).as_posix(),
                            "content": markdown_path.read_text(encoding="utf-8"),
                        }
                    ).encode("utf-8")
                except Exception as exc:
                    self.respond(400, html.escape(str(exc)).encode("utf-8"), "text/plain; charset=utf-8")
                    return
                self.respond(200, payload, "application/json; charset=utf-8")
            else:
                self.respond(404, b"Not found", "text/plain; charset=utf-8")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/assertions":
                self.save_assertions()
            elif path == "/api/markdown/file":
                self.save_markdown()
            else:
                self.respond(404, b"Not found", "text/plain; charset=utf-8")
            return

        def save_assertions(self) -> None:
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

        def save_markdown(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length)
            try:
                data = json.loads(payload.decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("Expected a file payload")
                markdown_path = resolve_markdown_path(root, str(data.get("path", "")))
                content = str(data.get("content", ""))
                markdown_path.write_text(content, encoding="utf-8")
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
    parser = argparse.ArgumentParser(description="Edit assertions.csv and project Markdown files with a local UI.")
    parser.add_argument("--csv", default="assertions.csv", help="Path to the assertions CSV.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind.")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser automatically.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"Starting writing project editor with CSV argument: {args.csv}", flush=True)
    csv_path = Path(args.csv).resolve()
    print(f"Resolved assertions CSV path: {csv_path}", flush=True)
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing {csv_path}")

    print(f"Binding editor server on {args.host}:{args.port}", flush=True)
    server = ThreadingHTTPServer((args.host, args.port), create_handler(csv_path))
    url = f"http://{args.host}:{args.port}/"
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    print(f"Writing project editor running at {url}")
    print(f"Markdown editor running at {url}markdown")
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
