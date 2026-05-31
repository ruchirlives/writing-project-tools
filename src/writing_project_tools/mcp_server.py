from __future__ import annotations

import socket
import subprocess
import sys
import csv
from importlib.resources import files
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from writing_project_tools.assertions_editor import (
    FIELDNAMES,
    markdown_files,
    read_assertions,
    resolve_markdown_path,
    write_assertions,
)
from writing_project_tools.create_docs import generate_docs
from writing_project_tools.llm_context import build_llm_context, export_llm_context
from writing_project_tools.scaffold import scaffold


mcp = FastMCP("writing-project-tools")
TOOLKIT_DIR = Path(__file__).resolve().parents[2]
AGENTS_TEMPLATE_PATH = TOOLKIT_DIR / "AGENTS.template.md"

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


def project_path(project_dir: str) -> Path:
    if not project_dir:
        raise ValueError("project_dir is required")
    return Path(project_dir).expanduser().resolve()


def free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def read_agents_template() -> str:
    if not AGENTS_TEMPLATE_PATH.exists():
        resource = files("writing_project_tools").joinpath("AGENTS.template.md")
        if not resource.is_file():
            raise FileNotFoundError(f"Missing {AGENTS_TEMPLATE_PATH}")
        return resource.read_text(encoding="utf-8")
    return AGENTS_TEMPLATE_PATH.read_text(encoding="utf-8")


@mcp.tool()
def get_writing_project_instructions() -> dict[str, Any]:
    """Read the default writing-project LLM instructions from AGENTS.template.md."""
    return {
        "source": str(AGENTS_TEMPLATE_PATH),
        "content": read_agents_template(),
    }


@mcp.tool()
def get_project_instructions(project_dir: str) -> dict[str, Any]:
    """Read toolkit instructions plus project-local AGENTS.md instructions when present."""
    root = project_path(project_dir)
    project_agents = root / "AGENTS.md"
    toolkit_content = read_agents_template()
    result = {
        "toolkit_source": str(AGENTS_TEMPLATE_PATH),
        "toolkit_instructions": toolkit_content,
        "project_source": str(project_agents),
        "project_instructions_present": project_agents.exists(),
        "project_instructions": "",
        "effective_guidance": (
            "Use toolkit_instructions as the base workflow and tool-use guidance. "
            "Apply project_instructions as project-specific audience, style, source, "
            "and constraint guidance when present. If they conflict, project-specific "
            "content guidance can override defaults, but do not override tool safety, "
            "path handling, or evidence-discipline rules."
        ),
    }
    if project_agents.exists():
        result["project_instructions"] = project_agents.read_text(encoding="utf-8")
    return result


@mcp.tool()
def get_workflow_summary() -> dict[str, Any]:
    """Return a concise structured summary of the writing-project workflow."""
    return {
        "standard_files": STANDARD_CONTEXT_FILES,
        "assertions_csv": {
            "required_columns": FIELDNAMES,
            "status_values": ["planned", "interpretation", "verify", "draft_phrase"],
            "guidance": (
                "Track content-related assertions only. Exclude setup, format instructions, "
                "authorial stance, workflow notes, and drafting-process guidance."
            ),
        },
        "workflow": [
            "Gather source notes and context.",
            "Identify audience, editorial format, and authorial stance.",
            "Create article-plan.md.",
            "Create article-outline.md.",
            "Extract planned assertions into assertions.csv.",
            "Review assertions through the editor.",
            "Revise plan and outline from reviewed assertions.",
            "Create article-draft.md from the reviewed outline.",
            "Generate Word documents from docx_sources.csv.",
            "Iterate based on feedback.",
        ],
        "markdown_style": [
            "Use #, ##, and ### headings only.",
            "Use - for bullet lists, not *.",
            "Use numbered lists as 1., 2., 3. when order matters.",
            "Keep paragraphs as plain text separated by blank lines.",
            "Prefer clear section headings over bold-only pseudo-headings.",
            "Avoid tables unless specifically requested.",
            "Avoid HTML, footnote syntax, embedded images, and complex Markdown extensions.",
        ],
        "word_conversion_guidance": [
            "Use a single # heading for the document title or top-level heading.",
            "Use ## and ### for sections and subsections.",
            "Use - bullet lists and 1., 2., 3. numbered lists.",
            "Do not include visible generator labels such as Generated from ...",
            "Do not include internal workflow notes, comments to the LLM, or prompt text.",
            "Ensure the document reads naturally as a working Word document before generating .docx.",
        ],
        "helpers": [
            "get_project_instructions",
            "read_writing_context",
            "write_project_assertions",
            "start_project_editor",
            "read_docx_sources",
            "write_docx_sources",
            "generate_writing_docs",
        ],
    }


@mcp.tool()
def scaffold_article_project(project_dir: str, force: bool = False) -> dict[str, Any]:
    """Create the standard writing-project files in project_dir."""
    return scaffold(project_path(project_dir), force=force, install=False)


@mcp.tool()
def generate_writing_docs(project_dir: str, config: str = "docx_sources.csv") -> dict[str, Any]:
    """Generate configured Word .docx files for a writing project."""
    outputs = generate_docs(project_path(project_dir), config)
    return {"outputs": [str(path) for path in outputs]}


@mcp.tool()
def list_project_markdown(project_dir: str) -> dict[str, Any]:
    """List editable Markdown files under a writing project folder."""
    root = project_path(project_dir)
    return {"files": markdown_files(root)}


def read_markdown_bundle(root: Path, paths: list[str]) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for requested_path in paths:
        markdown_path = resolve_markdown_path(root, requested_path)
        if not markdown_path.exists():
            continue
        files.append(
            {
                "path": markdown_path.relative_to(root).as_posix(),
                "content": markdown_path.read_text(encoding="utf-8"),
            }
        )
    return files


def resolve_project_file(root: Path, requested_path: str) -> Path:
    if not requested_path:
        raise ValueError("Missing path")
    path = (root / requested_path).resolve()
    if root != path and root not in path.parents:
        raise ValueError("Path is outside the project")
    return path


@mcp.tool()
def read_writing_context(project_dir: str) -> dict[str, Any]:
    """Read the standard writing-project Markdown files for assertion generation."""
    root = project_path(project_dir)
    files = read_markdown_bundle(root, STANDARD_CONTEXT_FILES)
    present = {file["path"] for file in files}
    return {
        "project_dir": str(root),
        "files": files,
        "missing_standard_files": [
            path for path in STANDARD_CONTEXT_FILES if path not in present
        ],
    }


@mcp.tool()
def read_selected_markdown(project_dir: str, paths: list[str]) -> dict[str, Any]:
    """Read selected Markdown files from a writing project folder."""
    root = project_path(project_dir)
    return {"project_dir": str(root), "files": read_markdown_bundle(root, paths)}


@mcp.tool()
def read_project_markdown(project_dir: str, path: str) -> dict[str, Any]:
    """Read a Markdown file from a writing project folder."""
    root = project_path(project_dir)
    markdown_path = resolve_markdown_path(root, path)
    return {
        "path": markdown_path.relative_to(root).as_posix(),
        "content": markdown_path.read_text(encoding="utf-8"),
    }


@mcp.tool()
def write_project_markdown(project_dir: str, path: str, content: str) -> dict[str, Any]:
    """Write a Markdown file inside a writing project folder."""
    root = project_path(project_dir)
    markdown_path = resolve_markdown_path(root, path)
    markdown_path.write_text(content, encoding="utf-8")
    return {"path": markdown_path.relative_to(root).as_posix(), "saved": True}


@mcp.tool()
def read_docx_sources(project_dir: str, csv_name: str = "docx_sources.csv") -> dict[str, Any]:
    """Read the Word document generation config CSV for a writing project."""
    root = project_path(project_dir)
    csv_path = resolve_project_file(root, csv_name)
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing {csv_path}")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            "fieldnames": reader.fieldnames or [],
            "rows": list(reader),
        }


def read_docx_sources_from_path(csv_path: Path) -> dict[str, Any]:
    if not csv_path.exists():
        return {"fieldnames": [], "rows": [], "missing": True}
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            "fieldnames": reader.fieldnames or [],
            "rows": list(reader),
            "missing": False,
        }


@mcp.tool()
def write_docx_sources(
    project_dir: str,
    rows: list[dict[str, Any]],
    csv_name: str = "docx_sources.csv",
) -> dict[str, Any]:
    """Write the Word document generation config CSV for a writing project."""
    root = project_path(project_dir)
    csv_path = resolve_project_file(root, csv_name)
    fieldnames = ["source", "title", "subject", "output", "author"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: str(row.get(field, "")) for field in fieldnames})
    return {"path": str(csv_path), "rows": len(rows), "saved": True}


@mcp.tool()
def prepare_draft_inputs(project_dir: str) -> dict[str, Any]:
    """Gather instructions, outline, context, assertions, and docx config for draft creation."""
    root = project_path(project_dir)
    instructions = get_project_instructions(str(root))
    context_files = read_markdown_bundle(root, STANDARD_CONTEXT_FILES)

    assertions_path = root / "assertions.csv"
    assertions = read_assertions(assertions_path) if assertions_path.exists() else []

    docx_sources = read_docx_sources_from_path(root / "docx_sources.csv")

    return {
        "project_dir": str(root),
        "instructions": instructions,
        "context_files": context_files,
        "assertions": {
            "fieldnames": FIELDNAMES,
            "rows": assertions,
            "missing": not assertions_path.exists(),
        },
        "docx_sources": docx_sources,
        "draft_target": "article-draft.md",
        "recommended_next_steps": [
            "Use article-outline.md as the drafting structure.",
            "Use source notes and context as the evidence base.",
            "Respect assertions.csv include flags and user_edit wording when present.",
            "Save the draft with write_project_markdown(project_dir, 'article-draft.md', content).",
            "Generate the Word version with generate_writing_docs(project_dir).",
        ],
    }


@mcp.tool()
def build_paste_ready_llm_context(
    project_dir: str,
    task: str = "draft",
    include_all_markdown: bool = False,
) -> dict[str, Any]:
    """Build paste-ready Markdown context for use with an external LLM."""
    root = project_path(project_dir)
    return {
        "project_dir": str(root),
        "content": build_llm_context(root, task=task, include_all_markdown=include_all_markdown),
    }


@mcp.tool()
def export_paste_ready_llm_context(
    project_dir: str,
    output: str = "llm-context.md",
    task: str = "draft",
    include_all_markdown: bool = False,
) -> dict[str, Any]:
    """Write paste-ready Markdown context for use with an external LLM."""
    root = project_path(project_dir)
    output_path = export_llm_context(
        root,
        output=output,
        task=task,
        include_all_markdown=include_all_markdown,
    )
    return {"path": str(output_path), "saved": True}


@mcp.tool()
def read_project_assertions(project_dir: str, csv_name: str = "assertions.csv") -> dict[str, Any]:
    """Read the assertions CSV for a writing project."""
    csv_path = project_path(project_dir) / csv_name
    return {"fieldnames": FIELDNAMES, "rows": read_assertions(csv_path)}


@mcp.tool()
def write_project_assertions(
    project_dir: str,
    rows: list[dict[str, Any]],
    csv_name: str = "assertions.csv",
) -> dict[str, Any]:
    """Write rows to the assertions CSV for a writing project."""
    csv_path = project_path(project_dir) / csv_name
    write_assertions(csv_path, rows)
    return {"path": str(csv_path), "rows": len(rows), "saved": True}


@mcp.tool()
def start_project_editor(
    project_dir: str,
    csv_name: str = "assertions.csv",
    host: str = "127.0.0.1",
    port: int = 0,
    open_browser: bool = False,
) -> dict[str, Any]:
    """Start the local assertions and Markdown editor for a writing project."""
    root = project_path(project_dir)
    csv_path = root / csv_name
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing {csv_path}")

    selected_port = port or free_port(host)
    command = [
        sys.executable,
        "-m",
        "writing_project_tools.assertions_editor",
        "--csv",
        str(csv_path),
        "--host",
        host,
        "--port",
        str(selected_port),
    ]
    if not open_browser:
        command.append("--no-open")

    process = subprocess.Popen(command, cwd=root)
    url = f"http://{host}:{selected_port}/"
    return {
        "pid": process.pid,
        "url": url,
        "markdown_url": f"{url}markdown",
        "csv": str(csv_path),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
