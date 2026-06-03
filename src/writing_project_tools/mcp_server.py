from __future__ import annotations

import socket
import subprocess
import sys
import csv
import json
import os
from importlib.resources import files
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlparse

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


def wait_for_http(url: str, timeout: float = 5.0) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        return False

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5) as sock:
                return True
        except Exception:
            time.sleep(0.2)
    return False


def wait_for_process_http(process: subprocess.Popen[bytes], url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        if wait_for_http(url, timeout=0.5):
            return True
        time.sleep(0.2)
    return False


def runtime_log_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME") or os.environ.get("TEMP")
    if base:
        path = Path(base) / "writing-project-tools"
    else:
        path = Path.home() / ".writing-project-tools"
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_log_path(root: Path, port: int) -> Path:
    safe_name = "".join(char if char.isalnum() else "-" for char in root.name).strip("-") or "project"
    return runtime_log_dir() / f"{safe_name}-editor-{port}.log"


def editor_environment() -> dict[str, str]:
    env = os.environ.copy()
    python_path_entries = [entry for entry in sys.path if entry]
    existing_python_path = env.get("PYTHONPATH")
    if existing_python_path:
        python_path_entries.append(existing_python_path)
    env["PYTHONPATH"] = os.pathsep.join(python_path_entries)
    return env


def editor_python() -> str:
    if os.name == "nt":
        base_executable = getattr(sys, "_base_executable", "")
        if base_executable and Path(base_executable).exists():
            return str(base_executable)
    return sys.executable


def editor_command(csv_path: Path, host: str, port: int, open_browser: bool) -> list[str]:
    command = [
        editor_python(),
        "-u",
        "-m",
        "writing_project_tools.assertions_editor",
        "--csv",
        str(csv_path),
        "--host",
        host,
        "--port",
        str(port),
    ]
    if not open_browser:
        command.append("--no-open")
    return command


def editor_creationflags() -> int:
    if os.name != "nt":
        return 0
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    flags |= getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    return flags


def find_editor_processes(csv_path: Path) -> list[dict[str, Any]]:
    csv_text = str(csv_path)
    ps_csv = "'" + csv_text.replace("'", "''") + "'"
    script = (
        "$pattern = 'writing_project_tools.assertions_editor'; "
        "$csv = " + ps_csv + "; "
        "$items = Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match '^python(\\.exe)?$' -and $_.CommandLine -and $_.CommandLine.Contains($pattern) -and $_.CommandLine.Contains($csv) } | "
        "ForEach-Object { "
        "$port = ''; "
        "if ($_.CommandLine -match '--port\\s+(\\d+)') { $port = $Matches[1] }; "
        "[pscustomobject]@{ pid = $_.ProcessId; command = $_.CommandLine; port = $port; url = $(if ($port) { 'http://127.0.0.1:' + $port + '/' } else { '' }) } "
        "}; "
        "$items | ConvertTo-Json -Depth 3"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return []
    text = result.stdout.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except Exception:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


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
            "path handling, evidence-discipline rules, or MCP helper usage. Do not "
            "create a project-local virtual environment, install this toolkit into the "
            "project folder, or search for copied toolkit scripts when MCP helpers are available."
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
        "tool_safety": [
            "Do not create a project-local .venv for this toolkit when MCP helpers are available.",
            "Do not install this toolkit into the writing project folder when using MCP.",
            "Do not search for copied toolkit scripts such as tools/assertions_editor.py when MCP helpers are available.",
            "If start_project_editor returns a URL, report it to the user and do not recreate the server manually.",
        ],
        "helpers": [
            "get_project_instructions",
            "read_writing_context",
            "write_project_assertions",
            "start_project_editor",
            "read_docx_sources",
            "write_docx_sources",
            "generate_writing_docs",
            "get_project_editor_status",
            "stop_project_editor",
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
    port: int = 8765,
    open_browser: bool = False,
    startup_timeout: float = 30.0,
) -> dict[str, Any]:
    """Start the local assertions and Markdown editor for a writing project."""
    root = project_path(project_dir)
    csv_path = root / csv_name
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing {csv_path}")

    selected_port = port
    url = f"http://{host}:{selected_port}/"
    if wait_for_http(url, timeout=1.0):
        return {
            "started": False,
            "reused": True,
            "url": url,
            "markdown_url": f"{url}markdown",
            "csv": str(csv_path),
            "message": (
                "A project editor is already responding at this URL. Open the returned URL; "
                "do not start a project-local Python script or create a .venv."
            ),
        }

    command = editor_command(csv_path, host, selected_port, open_browser)

    log_path = project_log_path(root, selected_port)
    with log_path.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=root,
            env=editor_environment(),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=editor_creationflags(),
        )

    if not wait_for_process_http(process, url, timeout=startup_timeout):
        return_code = process.poll()
        log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        if return_code is None:
            return {
                "started": True,
                "pid": process.pid,
                "reachable": False,
                "url": url,
                "markdown_url": f"{url}markdown",
                "csv": str(csv_path),
                "log": str(log_path),
                "log_excerpt": log_text[-4000:],
                "message": (
                    "Project editor process is running, but the readiness probe did not confirm the local URL. "
                    "Open the returned URL; if the browser cannot connect after a few seconds, report the log path."
                ),
            }
        return {
            "started": False,
            "url": url,
            "markdown_url": f"{url}markdown",
            "csv": str(csv_path),
            "log": str(log_path),
            "exit_code": return_code,
            "log_excerpt": log_text[-4000:],
            "message": (
                "Project editor did not become reachable before the startup timeout. "
                "Do not create a project-local .venv or search for tools/assertions_editor.py. "
                "Report this failure and the log path to the user."
            ),
        }

    return {
        "started": True,
        "pid": process.pid,
        "url": url,
        "markdown_url": f"{url}markdown",
        "csv": str(csv_path),
        "log": str(log_path),
        "message": (
            "Open the returned URL in your browser. Do not start a project-local "
            "Python script or create a .venv for this editor."
        ),
    }


@mcp.tool()
def get_project_editor_status(project_dir: str) -> dict[str, Any]:
    """Return likely editor processes for a writing project."""
    root = project_path(project_dir)
    csv_path = root / "assertions.csv"
    processes = find_editor_processes(csv_path)
    for process in processes:
        url = process.get("url", "")
        process["reachable"] = bool(url and wait_for_http(url, timeout=1.0))
    return {
        "running": bool(processes),
        "processes": processes,
        "message": "Found matching editor processes." if processes else "No matching editor processes found.",
    }


@mcp.tool()
def stop_project_editor(project_dir: str) -> dict[str, Any]:
    """Stop editor processes for a writing project by matching the assertions CSV path."""
    root = project_path(project_dir)
    csv_path = root / "assertions.csv"
    processes = find_editor_processes(csv_path)
    stopped: list[int] = []
    for process in processes:
        pid = int(process["pid"])
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            stopped.append(pid)
        except Exception:
            continue
    return {
        "stopped": bool(stopped),
        "stopped_pids": stopped,
        "matched_processes": processes,
        "message": "Stopped matching project editor processes." if stopped else "No matching project editor process was stopped.",
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
