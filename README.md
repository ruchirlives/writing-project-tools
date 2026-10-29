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

This creates `sources/context.md` and `sources/considerations.md` alongside other input files in `sources/`, plus `drafting-instructions.md`, project-named plan and draft Markdown files, `docx_sources.csv`, `README.md`, a root-level `assertions.xlsx` workbook, and an `outputs/` folder for deliverables. The plan includes the proposed structure.

`drafting-instructions.md` starts with rules to spell out Scottish Wildlife Trust, support every assertion with evidence, and keep intended wording in `assertion` while using `precis` as a short navigation label.

To scaffold a folder from elsewhere:

```powershell
scaffold-writing-project C:\path\to\NewArticle
```

Use `--force` only when you intentionally want to overwrite scaffold files.

To upgrade an existing project through MCP, call `migrate_writing_project(project_dir)`. It consolidates legacy Markdown, moves root-level `context.md` and `considerations.md` into `sources/`, moves `outputs/assertions.xlsx` to root-level `assertions.xlsx` without rewriting the workbook, or converts legacy assertions CSV files to that root-level workbook, moves root-level PDFs and exported emails and files in legacy `input/`, `inputs/`, or `source/` folders into `sources/`, moves existing deliverables from the project root or `docs/` into `outputs/`, updates legacy Word output paths, and removes the project `.gitignore`. Originals of changed source files are kept in `.writing-project-migration-backup/`. It also updates old assertions and source Markdown paths in project README and instruction files. The migration checks for destination collisions before moving files and can be run again without duplicating content.

To archive a completed project through MCP, call `archive_writing_project(project_dir)`. It creates and validates `sources.zip`, removes the original `sources/` folder and root-level working Markdown and `docx_sources.csv`, and keeps `assertions.xlsx` and `outputs/`. Any unrelated files are left in place and listed in the result. If `sources.zip` already exists while `sources/` is present, the action stops before changing files.

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

## Editable Evidence Tables

Create a standalone editable HTML table and companion JSON through the
`generate_editable_table` MCP helper. Set the title, columns, row values and
source references for each project. Supported field types are text, select,
number and date; priority is an optional configurable select field.

The reusable template is
`src/writing_project_tools/templates/editable_table.html`. The repository skill
is [.agents/skills/editable-evidence-table/SKILL.md](.agents/skills/editable-evidence-table/SKILL.md);
its [schema reference](.agents/skills/editable-evidence-table/references/schema.md)
contains a synthetic example and field definitions.

Pass the target project folder explicitly. Generated HTML, JSON, source extracts
and real row data belong in that project's `outputs/`, not this toolkit repository.
Sources can be exact excerpts or project-relative paths with inclusive one-based
line ranges. The HTML retains original row wording and a source trace alongside
editable fields. Source snapshots are not independent verification.

Open the generated HTML locally in Chrome or Edge, use **Open JSON** to connect
the companion file, then edit and **Save**. No server is required. The HTML's
embedded starting copy does not update after a JSON save. File changes detected
elsewhere block a normal save; **Save as** keeps a separate copy. This is not
simultaneous collaborative editing. Unsupported browsers download JSON copies;
browser recovery drafts and Word exports remain separate.

Existing output files are refused unless `overwrite=True`; explicit regeneration
backs up both files but does not merge saved browser edits. A rebuild creates a
new table identity. Preserve saved JSON before regenerating; use a new output
stem when changing the schema.

Installed CLI fallback:

```powershell
generate-editable-table --project C:\Writing\Example --spec C:\Writing\Example\table-spec.json --output outputs/review.html
```

After updating the toolkit, restart the MCP connection to discover the new helper.

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

Tick or untick assertions, optionally add revised wording in `user_edit`, or use **Verify** on a row, then click `Save workbook`. New rows start with `draft_phrase` status.

The MCP server also provides `update_project_assertions(project_dir, rows)` to upsert by stable `id`. It preserves verified rows exactly and marks new rows `draft_phrase`. Use `reset_project_assertions(project_dir)` to clear all assertion rows while keeping a blank workbook.

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
- `archive_writing_project`
- `generate_writing_docs`
- `generate_editable_table`
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
- `update_project_assertions`
- `reset_project_assertions`
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
