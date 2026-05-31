from __future__ import annotations

import argparse
import csv
from importlib.resources import files
from pathlib import Path

from writing_project_tools.assertions_editor import FIELDNAMES, markdown_files, read_assertions


STANDARD_CONTEXT_FILES = [
    "instructions_for_authors.md",
    "source-notes.md",
    "context.md",
    "considerations.md",
    "colleagues.md",
    "article-plan.md",
    "article-outline.md",
    "article-draft.md",
]


def project_path(project_dir: str | Path) -> Path:
    return Path(project_dir).expanduser().resolve()


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def read_toolkit_instructions() -> str:
    repo_template = Path(__file__).resolve().parents[2] / "AGENTS.template.md"
    if repo_template.exists():
        return repo_template.read_text(encoding="utf-8")
    resource = files("writing_project_tools").joinpath("AGENTS.template.md")
    if resource.is_file():
        return resource.read_text(encoding="utf-8")
    return ""


def read_docx_sources(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_table(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    if not rows:
        return "_No rows._"
    lines = [",".join(fieldnames)]
    for row in rows:
        values = []
        for field in fieldnames:
            value = str(row.get(field, "")).replace('"', '""')
            if any(char in value for char in [",", "\n", '"']):
                value = f'"{value}"'
            values.append(value)
        lines.append(",".join(values))
    return "\n".join(lines)


def build_llm_context(
    project_dir: Path,
    task: str = "draft",
    include_all_markdown: bool = False,
) -> str:
    root = project_dir.resolve()
    agents_path = root / "AGENTS.md"

    if include_all_markdown:
        context_paths = markdown_files(root)
    else:
        context_paths = STANDARD_CONTEXT_FILES

    parts = [
        "# LLM Writing Project Context",
        "",
        "## Task",
        "",
        task,
        "",
        "## How To Use This Context",
        "",
        "- Follow the toolkit instructions as the base workflow.",
        "- If project instructions are present, apply them as project-specific guidance.",
        "- Treat source notes and context as the evidence base.",
        "- Do not treat the article plan or outline as original evidence.",
        "- Use simple Word-output-friendly Markdown: `#`, `##`, `###`, `-` bullets, and `1.`, `2.`, `3.` numbered lists.",
        "",
        "## Toolkit Instructions",
        "",
        read_toolkit_instructions() or "_Toolkit instructions were not found._",
        "",
        "## Project Instructions",
        "",
        read_text_if_exists(agents_path) or "_No project-local AGENTS.md was found._",
        "",
        "## Project Files",
        "",
    ]

    for relative_path in context_paths:
        path = root / relative_path
        if not path.exists() or path.suffix.lower() != ".md":
            continue
        parts.extend(
            [
                f"### {relative_path}",
                "",
                "```md",
                path.read_text(encoding="utf-8"),
                "```",
                "",
            ]
        )

    assertions = read_assertions(root / "assertions.csv") if (root / "assertions.csv").exists() else []
    parts.extend(
        [
            "## Assertions CSV",
            "",
            "```csv",
            csv_table(assertions, FIELDNAMES),
            "```",
            "",
        ]
    )

    docx_rows = read_docx_sources(root / "docx_sources.csv")
    parts.extend(
        [
            "## Word Output Config",
            "",
            "```csv",
            csv_table(docx_rows, ["source", "title", "subject", "output", "author"]),
            "```",
            "",
            "## Expected Response",
            "",
            "Return only the requested project artifact or edits, in clean Markdown or CSV as appropriate.",
        ]
    )

    return "\n".join(parts).rstrip() + "\n"


def export_llm_context(
    project_dir: Path,
    output: str = "llm-context.md",
    task: str = "draft",
    include_all_markdown: bool = False,
) -> Path:
    root = project_dir.resolve()
    output_path = (root / output).resolve()
    if root != output_path and root not in output_path.parents:
        raise ValueError("Output path is outside the project")
    output_path.write_text(
        build_llm_context(root, task=task, include_all_markdown=include_all_markdown),
        encoding="utf-8",
    )
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a paste-ready LLM context Markdown file.")
    parser.add_argument("--project", default=".", help="Project folder to read.")
    parser.add_argument("--output", default="llm-context.md", help="Output Markdown path relative to the project.")
    parser.add_argument("--task", default="draft", help="Task description to include in the context.")
    parser.add_argument(
        "--all-markdown",
        action="store_true",
        help="Include all project Markdown files instead of the standard writing-project files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = export_llm_context(
        project_path(args.project),
        output=args.output,
        task=args.task,
        include_all_markdown=args.all_markdown,
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
