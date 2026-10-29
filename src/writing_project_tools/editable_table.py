"""Generate portable, editable HTML tables and project-owned JSON data files."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from datetime import date
from importlib.resources import files
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any
from uuid import uuid4
from urllib.parse import quote

FORMAT = "writing-project-editable-table"
KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def valid_cell(col: dict[str, Any], value: Any) -> bool:
    if not isinstance(value, str):
        return False
    kind = col["type"]
    if kind == "select":
        return value in col["options"]
    if not value:
        return True
    if kind == "number":
        return bool(re.fullmatch(r"-?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?", value)) and math.isfinite(float(value))
    if kind == "date":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
    return True


def inside(root: Path, name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or not name or ".." in path.parts:
        raise ValueError("Use a project-relative path without '..'.")
    result = (root / path).resolve()
    if not result.is_relative_to(root):
        raise ValueError("Path must stay inside project_dir.")
    return result


def build_table_data(
    root: Path, output: Path, title: str, columns: list[dict[str, Any]],
    rows: list[dict[str, Any]], sources: list[dict[str, Any]],
    description: str = "", evidence_note: str = "",
) -> dict[str, Any]:
    if not title.strip() or not columns:
        raise ValueError("A title and at least one column are required.")
    cols = deepcopy(columns)
    keys: set[str] = set()
    for col in cols:
        key = col.get("key", "")
        if not isinstance(key, str) or not KEY.fullmatch(key) or key in keys:
            raise ValueError("Column keys must be unique simple identifiers.")
        keys.add(key)
        if not isinstance(col.get("label"), str) or not col["label"].strip():
            raise ValueError("Each column needs a label.")
        col.setdefault("type", "text")
        if col["type"] not in {"text", "select", "number", "date"}:
            raise ValueError("Column type must be text, select, number or date.")
        col.setdefault("width", 240 if col["type"] == "text" else 150)
        if not isinstance(col["width"], int) or not 100 <= col["width"] <= 800:
            raise ValueError("Column width must be 100–800 pixels.")
        if col["type"] == "select":
            options = col.get("options")
            if not isinstance(options, list) or not options or not all(isinstance(v, str) for v in options) or len(set(options)) != len(options):
                raise ValueError("Select columns need unique string options.")
            col.setdefault("default", options[0])
        else:
            col.setdefault("default", "")
        if not valid_cell(col, col["default"]):
            raise ValueError("Column defaults must be strings and valid select choices.")
        col.setdefault("role", "")
        if not isinstance(col["role"], str):
            raise ValueError("Column role must be a string describing its evidence basis.")
    refs = []
    source_ids: set[str] = set()
    for supplied in sources:
        source = deepcopy(supplied)
        sid = source.get("id")
        if not isinstance(sid, str) or not sid or sid in source_ids:
            raise ValueError("Source IDs must be non-empty and unique.")
        source_ids.add(sid)
        for field in ("title", "date", "reference", "excerpt"):
            source.setdefault(field, "")
            if not isinstance(source[field], str):
                raise ValueError(f"Source {field} must be text.")
        source.pop("href", None)  # Derive links from checked project-relative source paths.
        if source.get("path"):
            src = inside(root, source["path"])
            if not src.is_file():
                raise FileNotFoundError(src)
            source["href"] = quote(Path(os.path.relpath(src, output.parent)).as_posix(), safe="/")
            start, end = source.get("lineStart"), source.get("lineEnd")
            if start is not None or end is not None:
                lines = src.read_text(encoding="utf-8-sig").splitlines()
                if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
                    raise ValueError("Source line ranges must be valid, inclusive and one-based.")
                source["excerpt"] = "\n".join(lines[start - 1:end])
        refs.append(source)
    records = []
    row_ids: set[str] = set()
    for supplied in rows:
        row = deepcopy(supplied)
        rid = row.get("id", f"ROW-{len(records) + 1:03}")
        if not isinstance(rid, str) or not rid or rid in row_ids:
            raise ValueError("Row IDs must be non-empty and unique.")
        row_ids.add(rid)
        values = row.get("values", {})
        if not isinstance(values, dict) or set(values) - keys:
            raise ValueError("Row values must use declared column keys.")
        values = {col["key"]: values.get(col["key"], col["default"]) for col in cols}
        for col in cols:
            value = values[col["key"]]
            if not valid_cell(col, value):
                raise ValueError("Cell values must match their text, select, number or ISO date type.")
        linked = row.get("sourceIds", [])
        if not isinstance(linked, list) or not all(isinstance(s, str) and s in source_ids for s in linked):
            raise ValueError("Row sourceIds must reference supplied source IDs.")
        if not isinstance(row.get("sourceNotes", ""), str):
            raise ValueError("Source notes must be text.")
        records.append({"id": rid, "values": values, "sourceIds": linked,
                        "sourceNotes": row.get("sourceNotes", ""), "original": deepcopy(values), "updatedAt": None})
    return {"format": FORMAT, "schemaVersion": 1, "tableId": str(uuid4()), "title": title,
            "description": description, "evidenceNote": evidence_note,
            "updatedAt": None, "columns": cols, "rows": records, "sources": refs}


def generate_table(
    project_dir: str | Path, title: str, columns: list[dict[str, Any]],
    rows: list[dict[str, Any]], sources: list[dict[str, Any]] | None = None,
    output: str = "outputs/editable-table.html", description: str = "",
    evidence_note: str = "", overwrite: bool = False,
) -> dict[str, Any]:
    if not str(project_dir).strip():
        raise ValueError("project_dir is required.")
    root = Path(project_dir).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    html_path = inside(root, output)
    if html_path.suffix.lower() != ".html":
        raise ValueError("output must end in .html; the JSON is saved beside it.")
    json_path = html_path.with_suffix(".json")
    targets = (html_path, json_path)
    for target in targets:
        if not target.resolve().is_relative_to(root):
            raise ValueError("Output links must stay inside project_dir.")
        if target.exists() and not target.is_file():
            raise ValueError(f"Output is not a file: {target}")
        if target.exists() and not overwrite:
            raise FileExistsError(f"Refusing to replace {target}; use overwrite=True after preserving edits.")
    data = build_table_data(root, html_path, title, columns, rows, sources or [], description, evidence_note)
    source_paths = {inside(root, s["path"]) for s in sources or [] if s.get("path")}
    if source_paths.intersection(targets):
        raise ValueError("An output would overwrite a source file.")
    template = files("writing_project_tools").joinpath("templates/editable_table.html").read_text(encoding="utf-8")
    embedded = json.dumps(data, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    html = template.replace("__TABLE_DATA__", embedded)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    backups = []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for target in targets:
        if target.exists():
            backup = target.with_name(f"{target.stem}.backup-{stamp}{target.suffix}")
            shutil.copy2(target, backup)
            backups.append(str(backup))
    # Stage both complete files before replacing either. Backups retain any earlier pair.
    staged = []
    try:
        for target, text in ((html_path, html), (json_path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")):
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as f:
                f.write(text)
                staged.append((Path(f.name), target))
        for temp, target in staged:
            os.replace(temp, target)
    finally:
        for temp, _ in staged:
            temp.unlink(missing_ok=True)
    return {"html": str(html_path), "json": str(json_path), "rows": len(data["rows"]),
            "columns": len(columns), "backups": backups,
            "message": "Open the HTML locally, then Open JSON to connect the saved project data. No server is required."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--spec", required=True, help="Project-owned JSON specification, not toolkit data.")
    parser.add_argument("--output", default="outputs/editable-table.html")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8-sig"))
    print(json.dumps(generate_table(args.project, spec["title"], spec["columns"], spec.get("rows", []),
        spec.get("sources", []), args.output, spec.get("description", ""), spec.get("evidence_note", ""), args.overwrite), indent=2))


if __name__ == "__main__":
    main()
