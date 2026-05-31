# Writing Project Tools

Reusable lightweight tooling for evidence-led writing projects.

This toolkit supports a workflow where source notes are held in Markdown, planning documents are generated into Word `.docx` files, and planned assertions are reviewed through a CSV plus checkbox interface.

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

From inside a new empty article folder, run:

```powershell
scaffold-writing-project
```

This creates the standard Markdown files, including `article-plan.md`, `article-outline.md`, `article-draft.md`, `assertions.csv`, `docx_sources.csv`, `README.md`, and `.gitignore`.

To scaffold a folder from elsewhere:

```powershell
scaffold-writing-project C:\path\to\NewArticle
```

Use `--force` only when you intentionally want to overwrite scaffold files.

## Work In Google Colab

Use the Colab template when you want to scaffold and work on a writing project in a Colab runtime instead of a local folder:

```text
colab/writing_project_tools_colab_template.ipynb
```

Upload that notebook to Google Colab, then run the cells in order. The notebook:

- clones this toolkit from GitHub
- installs it in editable mode
- optionally mounts Google Drive for persistent project files
- scaffolds a writing project folder
- generates Word `.docx` files from Markdown sources
- provides a Colab-compatible proxy link for the assertions editor

By default, Colab work is created under `/content/writing-project`, which is temporary. Set `USE_GOOGLE_DRIVE = True` in the notebook if you want the scaffolded project to persist in Google Drive.

## Generate Word Documents

```powershell
create-writing-docs --project C:\path\to\ArticleProject
```

Edit `docx_sources.csv` to list the Markdown files you want converted to Word.
By default, new projects generate Word documents for the article plan, outline, and draft.

```powershell
create-writing-docs --project C:\path\to\ArticleProject
```

Generated `.docx` files are written to `docs/` unless a different output path is set in `docx_sources.csv`.

## Project Editor

Create an `assertions.csv` with these columns:

```csv
include,id,section,assertion,user_edit,status,evidence_or_check
```

Run:

```powershell
edit-assertions --csv C:\path\to\ArticleProject\assertions.csv
```

The editor opens the assertions review page at:

```text
http://127.0.0.1:8765/
```

Tick or untick assertions, optionally add revised wording in `user_edit`, and click `Save CSV`.

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
- `generate_writing_docs`
- `get_writing_project_instructions`
- `get_project_instructions`
- `get_workflow_summary`
- `list_project_markdown`
- `read_writing_context`
- `read_selected_markdown`
- `read_project_markdown`
- `write_project_markdown`
- `prepare_draft_inputs`
- `read_docx_sources`
- `write_docx_sources`
- `read_project_assertions`
- `write_project_assertions`
- `start_project_editor`

Example MCP server command:

```json
{
  "command": "E:\\CODINGPROJECTS\\Python\\writing-project-tools\\.venv\\Scripts\\writing-project-mcp.exe"
}
```

## Notes

- The Word generator avoids visible labels such as `Generated from ...`.
- Document metadata is set from `docx_sources.csv`.
- The assertions editor preserves excluded assertions in the CSV for audit trail purposes.
