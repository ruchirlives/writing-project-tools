from __future__ import annotations

import argparse
import csv
import re
import subprocess
from pathlib import Path


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
        "source-notes.md": "# Source Notes\n\nAdd rough notes, prompts and initial article thoughts here.\n",
        "context.md": "# Context\n\nAdd source material, evidence, interview notes, meeting notes or research here.\n",
        "considerations.md": "# Considerations\n\nAdd authorial stance, risks, constraints and things to avoid here.\n",
        "colleagues.md": "# Colleagues\n\nAdd likely reviewer lenses, stakeholder priorities or colleague feedback here.\n",
        "instructions_for_authors.md": "# Instructions For Authors\n\nAdd the editorial brief here.\n",
        f"{slug}-plan.md": f"# {folder_name} Plan For Comment\n\n## Working Title\n\n\n## Proposed Angle\n\n\n## Core Message\n\n\n## Proposed Content\n\n\n## Voice And Scope\n\n\n## Input Requested\n\n",
        f"{slug}-outline.md": f"# {folder_name} Outline\n\n## Brief\n\n\n## Core Thesis\n\n\n## Suggested Structure\n\n\n## Notes For Drafting\n\n",
        f"{slug}-draft.md": f"# {folder_name} Draft\n\nDraft from the approved outline after assertions have been reviewed.\n",
    }


def get_docx_sources_rows(folder_name: str) -> list[dict[str, str]]:
    """Get docx sources rows using folder name as prefix."""
    slug = folder_name_to_slug(folder_name)
    return [
        {
            "source": f"{slug}-plan.md",
            "title": f"{folder_name} Plan For Comment",
            "subject": f"{folder_name} plan",
            "output": f"docs/{slug}-plan.docx",
            "author": "Author Name",
        },
        {
            "source": f"{slug}-outline.md",
            "title": f"{folder_name} Outline",
            "subject": f"{folder_name} outline",
            "output": f"docs/{slug}-outline.docx",
            "author": "Author Name",
        },
        {
            "source": f"{slug}-draft.md",
            "title": f"{folder_name} Draft",
            "subject": f"{folder_name} draft",
            "output": f"docs/{slug}-draft.docx",
            "author": "Author Name",
        },
    ]


def get_standard_context_files(folder_name: str) -> list[str]:
    """Get standard context file names using folder name as prefix."""
    slug = folder_name_to_slug(folder_name)
    return [
        "instructions_for_authors.md",
        "source-notes.md",
        "context.md",
        "considerations.md",
        "colleagues.md",
        f"{slug}-plan.md",
        f"{slug}-outline.md",
        f"{slug}-draft.md",
    ]


ASSERTIONS_FIELDS = [
    "include",
    "id",
    "section",
    "assertion",
    "user_edit",
    "status",
    "evidence_or_check",
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
    target_dir.mkdir(parents=True, exist_ok=True)

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

    if write_csv(target_dir / "assertions.csv", ASSERTIONS_FIELDS, [], force):
        created.append("assertions.csv")
    else:
        skipped.append("assertions.csv")

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
        f"edit-assertions --csv \"{target_dir / 'assertions.csv'}\"\n"
        "```\n"
    )
    if write_text(target_dir / "README.md", readme, force):
        created.append("README.md")
    else:
        skipped.append("README.md")

    gitignore = ".venv/\n__pycache__/\n*.py[cod]\ndocs/*.docx\n~$*.docx\n"
    if write_text(target_dir / ".gitignore", gitignore, force):
        created.append(".gitignore")
    else:
        skipped.append(".gitignore")

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
