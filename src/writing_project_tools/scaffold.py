from __future__ import annotations

import argparse
import csv
import re
import subprocess
from pathlib import Path

from writing_project_tools.assertions_store import write_assertions


TOOLKIT_DIR = Path(__file__).resolve().parents[2]


def folder_name_to_slug(folder_name: str) -> str:
    """Convert folder name to a slug for file naming (e.g., 'Peatland Action' -> 'peatland-action')."""
    slug = folder_name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug or 'article'


def get_project_file_names(folder_name: str) -> dict[str, str]:
    """Get project file names using folder name as prefix."""
    slug = folder_name_to_slug(folder_name)
    return {
        "sources/context.md": "# Context\n\nAdd source material, evidence, notes, interviews, meetings, research and initial ideas here.\n",
        "drafting-instructions.md": (
            "# Drafting Instructions\n\n"
            "Add the editorial brief, audience, format, tone and other drafting requirements here.\n\n"
            "- Always write Scottish Wildlife Trust in full. Never use SWT as shorthand.\n"
            "- Back every assertion with evidence. Record the source or verification needed in assertions.xlsx.\n"
            "- When extracting assertions, preserve the actual phrasing to be used in assertion. Put a short navigation summary in precis.\n"
        ),
        "sources/considerations.md": "# Considerations\n\nAdd authorial stance, risks, constraints and things to avoid here.\n",
        f"{slug}-plan.md": f"# {folder_name} Plan For Comment\n\n## Working Title\n\n\n## Proposed Angle\n\n\n## Core Message\n\n\n## Proposed Structure\n\n- Introduction: \n- Main points: \n- Conclusion: \n\n## Voice And Scope\n\n\n## Input Requested\n\n",
        f"{slug}-draft.md": f"# {folder_name} Draft\n\nDraft from the reviewed plan after assertions have been reviewed.\n",
    }


def get_docx_sources_rows(folder_name: str) -> list[dict[str, str]]:
    """Get docx sources rows using folder name as prefix."""
    slug = folder_name_to_slug(folder_name)
    return [
        {
            "source": f"{slug}-plan.md",
            "title": f"{folder_name} Plan For Comment",
            "subject": f"{folder_name} plan",
            "output": f"outputs/{slug}-plan.docx",
            "author": "Author Name",
        },
        {
            "source": f"{slug}-draft.md",
            "title": f"{folder_name} Draft",
            "subject": f"{folder_name} draft",
            "output": f"outputs/{slug}-draft.docx",
            "author": "Author Name",
        },
    ]


def get_standard_context_files(folder_name: str) -> list[str]:
    """Get standard context file names using folder name as prefix."""
    slug = folder_name_to_slug(folder_name)
    return [
        "sources/context.md",
        "drafting-instructions.md",
        "sources/considerations.md",
        f"{slug}-plan.md",
        f"{slug}-draft.md",
    ]


def write_text(path: Path, content: str, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]], force: bool) -> bool:
    if path.exists() and not force:
        return False
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return True


def run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def scaffold(target_dir: Path, force: bool = False, install: bool = False, use_uv: bool = True) -> dict[str, object]:
    target_dir = target_dir.resolve()
    legacy_assertions = [
        path for path in (target_dir / "outputs" / "assertions.xlsx", target_dir / "outputs" / "assertions.csv", target_dir / "assertions.csv")
        if path.exists()
    ]
    if legacy_assertions:
        raise FileExistsError("Legacy assertions files exist; run migrate_writing_project before scaffolding: " + ", ".join(str(path) for path in legacy_assertions))
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "outputs").mkdir(exist_ok=True)
    (target_dir / "sources").mkdir(exist_ok=True)

    folder_name = target_dir.name
    default_files = get_project_file_names(folder_name)
    docx_sources_rows = get_docx_sources_rows(folder_name)

    created: list[str] = []
    skipped: list[str] = []

    for filename, content in default_files.items():
        if write_text(target_dir / filename, content, force):
            created.append(filename)
        else:
            skipped.append(filename)

    assertions_path = target_dir / "assertions.xlsx"
    if force or not assertions_path.exists():
        write_assertions(assertions_path, [])
        created.append("assertions.xlsx")
    else:
        skipped.append("assertions.xlsx")

    if write_csv(
        target_dir / "docx_sources.csv",
        ["source", "title", "subject", "output", "author"],
        docx_sources_rows,
        force,
    ):
        created.append("docx_sources.csv")
    else:
        skipped.append("docx_sources.csv")

    readme = (
        "# Writing Project\n\n"
        "## Generate Word Documents\n\n"
        "```powershell\n"
        f"create-writing-docs --project \"{target_dir}\"\n"
        "```\n\n"
        "## Assertions Editor\n\n"
        "```powershell\n"
        f"edit-assertions --workbook \"{target_dir / 'assertions.xlsx'}\"\n"
        "```\n"
    )
    if write_text(target_dir / "README.md", readme, force):
        created.append("README.md")
    else:
        skipped.append("README.md")

    if install:
        if use_uv:
            run(["uv", "venv"], target_dir)
            run(["uv", "pip", "install", "-e", str(TOOLKIT_DIR)], target_dir)
        else:
            run(["python", "-m", "venv", ".venv"], target_dir)
            python_path = target_dir / ".venv" / "Scripts" / "python.exe"
            run([str(python_path), "-m", "pip", "install", "-e", str(TOOLKIT_DIR)], target_dir)

    return {"project": str(target_dir), "created": created, "skipped": skipped}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaffold a writing project folder.")
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Folder to scaffold. Defaults to the current folder.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing scaffold files.")
    parser.add_argument(
        "--install",
        action="store_true",
        help="Create a virtual environment and install the toolkit.",
    )
    parser.add_argument(
        "--no-uv",
        action="store_true",
        help="Use python/pip instead of uv when --install is set.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = scaffold(Path(args.target), args.force, args.install, not args.no_uv)
    print(f"Scaffolded writing project at {result['project']}")
    if result["created"]:
        print("Created/updated:")
        for item in result["created"]:
            print(f"  - {item}")
    if result["skipped"]:
        print("Skipped existing files:")
        for item in result["skipped"]:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
