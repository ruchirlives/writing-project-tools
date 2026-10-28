# Writing Project Tools

Reusable lightweight tooling for evidence-led writing projects.

This toolkit supports a workflow where source notes are held in Markdown, planning documents are generated into Word `.docx` files, and planned assertions are reviewed through an Excel workbook plus checkbox interface.

## Install Once

Install this toolkit once from this repo:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e "E:\CODINGPROJECTS\Python\writing-project-tools"
```

For MCP support, install the optional MCP dependency:

```powershell
python -m pip install -e "E:\CODINGPROJECTS\Python\writing-project-tools[mcp]"
```

## Scaffold A New Article Folder
When asked to create a new article folder, create that folder if it doesn't already exist in M:\Desktop\Documents\ARTICLES
Then pwd into it.
From inside a new empty article folder, run:

```powershell
scaffold-writing-project
```

This creates `context.md`, `drafting-instructions.md`, and `considerations.md`, plus project-named plan and draft Markdown files, `docx_sources.csv`, `README.md`, a `sources/` folder for input files, a root-level `assertions.xlsx` workbook, and an `outputs/` folder for deliverables. The plan includes the proposed structure.

`drafting-instructions.md` starts with rules to spell out Scottish Wildlife Trust, support every assertion with evidence, and keep intended wording in `assertion` while using `precis` as a short navigation label.

To scaffold a folder from elsewhere:

```powershell
scaffold-writing-project C:\path\to\NewArticle
```

Use `--force` only when you intentionally want to overwrite scaffold files.

To upgrade an existing project through MCP, call `migrate_writing_project(project_dir)`. It consolidates legacy Markdown, moves `outputs/assertions.xlsx` to root-level `assertions.xlsx` without rewriting the workbook, or converts legacy assertions CSV files to that root-level workbook, moves root-level PDFs and exported emails and files in legacy `input/`, `inputs/`, or `source/` folders into `sources/`, moves existing deliverables from the project root or `docs/` into `outputs/`, updates legacy Word output paths, and removes the project `.gitignore`. Originals of changed source files are kept in `.writing-project-migration-backup/`. It also updates old assertions workbook paths in project README and instruction files. The migration checks for destination collisions before moving files and can be run again without duplicating content.

## Generate Word Documents

```powershell
create-writing-docs --project C:\path\to\ArticleProject
```

Edit `docx_sources.csv` to list the Markdown files you want converted to Word.
By default, new projects generate Word documents for the plan and draft.

```powershell
create-writing-docs --project C:\path\to\ArticleProject
```

Generated `.docx` files are written to `outputs/` unless a different output path is set in `docx_sources.csv`. Use `outputs/` for other deliverables too, such as reports, interactive HTML tables, and Excel workbooks.

## Project Editor

The `assertions.xlsx` workbook has these columns:

```text
include,id,section,precis,assertion,user_edit,status,evidence_or_check
```

Run:

```powershell
edit-assertions --workbook C:\path\to\ArticleProject\assertions.xlsx
```

The editor opens the assertions review page at:

```text
http://127.0.0.1:8765/
```

Tick or untick assertions, optionally add revised wording in `user_edit`, and click `Save workbook`.

The same server also includes a Markdown editor:

```text
http://127.0.0.1:8765/markdown
```

Use it to select, preview, edit and save project `.md` files without leaving the browser UI. The Markdown editor only serves and saves `.md` files inside the project folder.

## MCP Server

Run the MCP server from the central toolkit install:

```powershell
writing-project-mcp
```

The server exposes tools for working against any project folder by path:

- `scaffold_article_project`
- `migrate_writing_project`
- `generate_writing_docs`
- `get_writing_project_instructions`
- `get_project_instructions`
- `get_workflow_summary`
- `list_project_markdown`
- `list_project_sources`
- `read_writing_context`
- `read_selected_markdown`
- `read_project_markdown`
- `write_project_markdown`
- `prepare_draft_inputs`
- `build_paste_ready_llm_context`
- `export_paste_ready_llm_context`
- `read_docx_sources`
- `write_docx_sources`
- `read_project_assertions`
- `write_project_assertions`
- `start_project_editor`
- `get_project_editor_status`
- `stop_project_editor`

For manual LLM workflows, export a paste-ready context bundle:

```powershell
export-writing-llm-context --project C:\path\to\ArticleProject --task "Draft the article from the reviewed plan"
```

Example MCP server command:

```json
{
  "type": "local",
  "command": [
    "uv",
    "--directory",
    "E:/CODINGPROJECTS/Python/writing-project-tools",
    "run",
    "--extra",
    "mcp",
    "writing-project-mcp"
  ],
  "enabled": true
}
```

## Notes

- The Word generator avoids visible labels such as `Generated from ...`.
- Document metadata is set from `docx_sources.csv`.
- The assertions editor preserves excluded assertions in the workbook for audit trail purposes.
