"""Upgrade a writing project from the earlier scaffold without losing source files."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

from writing_project_tools.assertions_editor import FIELDNAMES
from writing_project_tools.scaffold import folder_name_to_slug, get_project_file_names


def migrate_project(project_dir: Path) -> dict[str, object]:
    root = project_dir.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Project folder does not exist: {root}")

    slug = folder_name_to_slug(root.name)
    defaults = get_project_file_names(root.name)
    sources = {
        "source-notes.md": "context.md",
        "instructions_for_authors.md": "drafting-instructions.md",
        "colleagues.md": "considerations.md",
        f"{slug}-outline.md": f"{slug}-plan.md",
    }
    present = {source: target for source, target in sources.items() if (root / source).is_file()}
    assertions_path = root / "assertions.csv"
    docx_path = root / "docx_sources.csv"

    assertion_rows = None
    assertions_need_update = False
    if assertions_path.is_file():
        with assertions_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError("assertions.csv has no header")
            required = [field for field in FIELDNAMES if field != "precis"]
            missing = [field for field in required if field not in reader.fieldnames]
            if missing:
                raise ValueError(f"assertions.csv is missing columns: {', '.join(missing)}")
            assertion_rows = list(reader)
            assertions_need_update = reader.fieldnames != FIELDNAMES

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
    if assertions_need_update:
        backed_up.append("assertions.csv")
    if docx_need_update:
        backed_up.append("docx_sources.csv")
    backup = root / ".writing-project-migration-backup"
    conflicts = [name for name in backed_up if (backup / name).exists()]
    if conflicts:
        raise FileExistsError(f"Migration backup already contains: {', '.join(conflicts)}")
    if backed_up:
        backup.mkdir(exist_ok=True)
        for name in backed_up:
            shutil.copy2(root / name, backup / name)

    updated: list[str] = []
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

    if assertions_need_update and assertion_rows is not None:
        with assertions_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows({field: row.get(field, "") or "" for field in FIELDNAMES} for row in assertion_rows)
        updated.append("assertions.csv")

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
    for name in ("context.md", "drafting-instructions.md", "considerations.md"):
        path = root / name
        if not path.exists():
            path.write_text(defaults[name], encoding="utf-8")
            created.append(name)
    (root / "outputs").mkdir(exist_ok=True)
    return {
        "project_dir": str(root),
        "updated": updated,
        "created": created,
        "archived_legacy_files": list(present),
        "backup_dir": str(backup) if backed_up else None,
        "assertions_migrated": assertions_need_update,
    }
