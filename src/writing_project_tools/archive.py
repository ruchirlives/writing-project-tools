"""Archive a completed writing project while retaining its final deliverables."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def archive_project(project_dir: Path) -> dict[str, object]:
    root = project_dir.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Project folder does not exist: {root}")

    sources = root / "sources"
    archive = root / "sources.zip"
    if sources.is_symlink() or (sources.exists() and not sources.is_dir()):
        raise ValueError(f"Expected a sources folder: {sources}")
    if sources.is_dir() and archive.exists():
        raise FileExistsError(f"Archive already exists: {archive}")

    # Build and validate the archive before removing any project material.
    archived_files: list[str] = []
    if sources.is_dir():
        members = sorted(sources.rglob("*"))
        if any(path.is_symlink() for path in members):
            raise ValueError("sources/ contains a symlink; resolve it before archiving")
        fd, temporary_name = tempfile.mkstemp(prefix=".sources-", suffix=".zip", dir=root)
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as zipped:
                zipped.writestr("sources/", "")
                for path in members:
                    name = path.relative_to(root).as_posix()
                    if path.is_dir():
                        zipped.writestr(name + "/", "")
                    elif path.is_file():
                        zipped.write(path, name)
                        archived_files.append(name)
            with ZipFile(temporary) as zipped:
                if zipped.testzip() is not None:
                    raise OSError("Source archive failed validation")
                if sorted(name for name in zipped.namelist() if not name.endswith("/")) != sorted(archived_files):
                    raise OSError("Source archive does not match source files")
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)

    intermediate = sorted(
        path for path in root.iterdir()
        if path.is_file() and (path.suffix.lower() == ".md" or path.name == "docx_sources.csv")
    )
    deleted = []
    for path in intermediate:
        path.unlink()
        deleted.append(path.name)
    if sources.is_dir():
        for path in sorted(sources.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.is_dir():
                path.rmdir()
            else:
                path.unlink()
        sources.rmdir()

    kept_other = sorted(
        path.name for path in root.iterdir()
        if path.name not in {"assertions.xlsx", "outputs", "sources.zip"}
    )
    return {
        "project_dir": str(root),
        "sources_archive": str(archive) if archive.exists() else None,
        "archived_source_files": archived_files,
        "deleted_intermediate_files": deleted,
        "kept_other_entries": kept_other,
        "assertions_workbook": str(root / "assertions.xlsx") if (root / "assertions.xlsx").exists() else None,
        "outputs_dir": str(root / "outputs") if (root / "outputs").is_dir() else None,
    }
