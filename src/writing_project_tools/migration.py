"""Upgrade a writing project from the earlier scaffold without losing source files."""

from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path

from writing_project_tools.assertions_store import FIELDNAMES, write_assertions
from writing_project_tools.scaffold import folder_name_to_slug, get_project_file_names


def migrate_project(project_dir: Path) -> dict[str, object]:
    root = project_dir.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Project folder does not exist: {root}")

    slug = folder_name_to_slug(root.name)
    defaults = get_project_file_names(root.name)
    sources = {
        "source-notes.md": "sources/context.md",
        "instructions_for_authors.md": "drafting-instructions.md",
        "colleagues.md": "sources/considerations.md",
        f"{slug}-outline.md": f"{slug}-plan.md",
    }
    present = {source: target for source, target in sources.items() if (root / source).is_file()}
    legacy_assertions_path = root / "assertions.csv"
    output_csv_path = root / "outputs" / "assertions.csv"
    output_workbook_path = root / "outputs" / "assertions.xlsx"
    assertions_path = root / "assertions.xlsx"
    candidates = [path for path in (assertions_path, output_workbook_path, legacy_assertions_path, output_csv_path) if path.exists()]
    if len(candidates) > 1:
        raise FileExistsError("Multiple assertions files exist; resolve the conflict before migration: " + ", ".join(str(path) for path in candidates))
    source_assertions_path = next((path for path in (output_workbook_path, legacy_assertions_path, output_csv_path) if path.is_file()), output_csv_path)
    docx_path = root / "docx_sources.csv"
    gitignore_path = root / ".gitignore"
    instruction_updates = {}
    for name in ("README.md", "AGENTS.md", "drafting-instructions.md"):
        path = root / name
        if path.is_file():
            current = path.read_text(encoding="utf-8")
            revised = current.replace("outputs/assertions.xlsx", "assertions.xlsx").replace("outputs\\assertions.xlsx", "assertions.xlsx")
            for filename in ("context.md", "considerations.md"):
                revised = re.sub(rf"(?<![\w/\\-]){re.escape(filename)}", f"sources/{filename}", revised)
            if revised != current:
                instruction_updates[name] = revised

    assertion_rows = None
    assertions_need_update = False
    if source_assertions_path.is_file() and source_assertions_path.suffix == ".csv":
        with source_assertions_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError("assertions.csv has no header")
            required = [field for field in FIELDNAMES if field != "precis"]
            missing = [field for field in required if field not in reader.fieldnames]
            if missing:
                raise ValueError(f"assertions.csv is missing columns: {', '.join(missing)}")
            assertion_rows = list(reader)
            assertions_need_update = True
    elif source_assertions_path.is_file():
        assertions_need_update = True

    docx_rows = None
    docx_fields = None
    docx_need_update = False
    if docx_path.is_file():
        with docx_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            docx_fields = reader.fieldnames
            docx_rows = list(reader)
        if docx_fields and "source" in docx_fields:
            docx_need_update = any(
                row.get("source", "") == f"{slug}-outline.md"
                or row.get("output", "").replace("\\", "/").startswith("docs/")
                for row in docx_rows
            )

    backed_up = list(present)
    root_source_files = [name for name in ("context.md", "considerations.md") if (root / name).is_file()]
    backed_up.extend(root_source_files)
    backed_up.extend(instruction_updates)
    if gitignore_path.is_file():
        backed_up.append(".gitignore")
    if source_assertions_path.is_file():
        backed_up.append(source_assertions_path.relative_to(root).as_posix())
    if docx_need_update:
        backed_up.append("docx_sources.csv")
    backup = root / ".writing-project-migration-backup"
    input_suffixes = {".pdf", ".eml", ".msg", ".mbox", ".emlx", ".txt", ".rtf"}
    input_files = [path for path in root.iterdir() if path.is_file() and path.suffix.lower() in input_suffixes]
    legacy_input_dirs = [root / name for name in ("source", "inputs", "input") if (root / name).is_dir()]
    for directory in legacy_input_dirs:
        input_files.extend(path for path in directory.rglob("*") if path.is_file())
    input_destinations = [
        root / "sources" / (path.relative_to(path.parent if path.parent == root else next(directory for directory in legacy_input_dirs if directory in path.parents)))
        for path in input_files
    ]
    deliverable_suffixes = {".csv", ".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx", ".html", ".htm", ".odt", ".ods", ".odp"}
    deliverables = [
        path for path in root.iterdir()
        if path.is_file()
        and path.suffix.lower() in deliverable_suffixes
        and path.name not in {"assertions.xlsx", "assertions.csv", "docx_sources.csv"}
        and not path.name.startswith("~$")
    ]
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        deliverables.extend(path for path in docs_dir.rglob("*") if path.is_file())
    destinations = [root / "outputs" / (path.relative_to(docs_dir) if docs_dir in path.parents else path.name) for path in deliverables]
    conflicts = [name for name in backed_up if (backup / name).exists()]
    conflicts.extend(str(destination.relative_to(root)) for destination in destinations + input_destinations if destination.exists())
    if len(destinations) != len(set(destinations)):
        conflicts.append("multiple deliverables have the same destination")
    if len(input_destinations) != len(set(input_destinations)):
        conflicts.append("multiple source files have the same destination")
    if conflicts:
        raise FileExistsError(f"Migration backup already contains: {', '.join(conflicts)}")
    if backed_up:
        backup.mkdir(exist_ok=True)
        for name in backed_up:
            (backup / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, backup / name)

    updated: list[str] = []
    for name, content in instruction_updates.items():
        (root / name).write_text(content, encoding="utf-8")
        updated.append(name)
    (root / "sources").mkdir(exist_ok=True)
    for name in root_source_files:
        destination = root / "sources" / name
        original = root / name
        if destination.exists():
            content = destination.read_text(encoding="utf-8").rstrip()
            content += f"\n\n## Imported from root {name}\n\n" + original.read_text(encoding="utf-8").strip() + "\n"
            destination.write_text(content, encoding="utf-8")
            original.unlink()
        else:
            shutil.move(str(original), str(destination))
        updated.append(f"sources/{name}")
    for source, target in present.items():
        target_path = root / target
        if target_path.is_file():
            current = target_path.read_text(encoding="utf-8")
            if current == defaults.get(target):
                current = f"# {target.removesuffix('.md').replace('-', ' ').title()}\n"
        else:
            current = defaults[target]
        legacy = (root / source).read_text(encoding="utf-8").strip()
        if legacy:
            current = current.rstrip() + f"\n\n## Imported from {source}\n\n" + legacy + "\n"
            target_path.write_text(current, encoding="utf-8")
            if target not in updated:
                updated.append(target)
        (root / source).unlink()

    if gitignore_path.is_file():
        gitignore_path.unlink()

    if source_assertions_path.is_file():
        if assertion_rows is not None:
            write_assertions(assertions_path, assertion_rows)
        else:
            shutil.copy2(source_assertions_path, assertions_path)
        source_assertions_path.unlink()
        updated.append("assertions.xlsx")

    if docx_need_update and docx_rows is not None and docx_fields:
        revised = []
        for row in docx_rows:
            if row.get("source") == f"{slug}-outline.md":
                continue
            output = row.get("output", "")
            if output.replace("\\", "/").startswith("docs/"):
                row["output"] = "outputs/" + output.replace("\\", "/")[5:]
            revised.append(row)
        with docx_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=docx_fields)
            writer.writeheader()
            writer.writerows(revised)
        updated.append("docx_sources.csv")

    created: list[str] = []
    for name in ("sources/context.md", "drafting-instructions.md", "sources/considerations.md"):
        path = root / name
        if not path.exists():
            path.write_text(defaults[name], encoding="utf-8")
            created.append(name)
    (root / "outputs").mkdir(exist_ok=True)
    (root / "sources").mkdir(exist_ok=True)
    moved_sources: list[str] = []
    for source, destination in zip(input_files, input_destinations):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        moved_sources.append(destination.relative_to(root).as_posix())
    for input_dir in legacy_input_dirs:
        for directory in sorted((path for path in input_dir.rglob("*") if path.is_dir()), key=lambda path: len(path.parts), reverse=True):
            directory.rmdir()
        input_dir.rmdir()
    moved_deliverables: list[str] = []
    for source, destination in zip(deliverables, destinations):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        moved_deliverables.append(destination.relative_to(root).as_posix())
    if docs_dir.is_dir():
        for directory in sorted((path for path in docs_dir.rglob("*") if path.is_dir()), key=lambda path: len(path.parts), reverse=True):
            directory.rmdir()
        docs_dir.rmdir()
    return {
        "project_dir": str(root),
        "updated": updated,
        "created": created,
        "archived_legacy_files": [name for name in backed_up if name in present or name == ".gitignore"],
        "backup_dir": str(backup) if backed_up else None,
        "assertions_migrated": assertions_need_update,
        "moved_deliverables": moved_deliverables,
        "moved_sources": moved_sources,
    }
