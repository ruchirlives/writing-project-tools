# Writing Project Tools

Reusable lightweight tooling for evidence-led writing projects.

This toolkit supports a workflow where source notes are held in Markdown, planning documents are generated into Word `.docx` files, and planned assertions are reviewed through a CSV plus checkbox interface.

## What To Copy Into A New Project

Copy these files and folders into the root of a new writing project:

- `pyproject.toml`
- `.gitignore`
- `src/`
- `tools/`
- `docx_sources.csv`
- `AGENTS.template.md`

Then rename `AGENTS.template.md` to `AGENTS.md` and edit it for the new project.

## Scaffold A New Article Folder

From inside a new empty article folder, run:

```powershell
python C:\path\to\writing-project-tools\scaffold_article.py --install
```

This creates the standard Markdown files, `AGENTS.md`, `assertions.csv`, `docx_sources.csv`, `README.md`, `.gitignore`, a `.venv`, and installs this toolkit with `uv`.

To scaffold a folder from elsewhere:

```powershell
python C:\path\to\writing-project-tools\scaffold_article.py C:\path\to\NewArticle --install
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

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Generate Word Documents

Edit `docx_sources.csv` to list the Markdown files you want converted to Word.

```powershell
create-writing-docs
```

Generated `.docx` files are written to `docs/` unless a different output path is set in `docx_sources.csv`.

## Assertions Review

Create an `assertions.csv` with these columns:

```csv
include,id,section,assertion,user_edit,status,evidence_or_check
```

Run:

```powershell
edit-assertions
```

The editor opens at:

```text
http://127.0.0.1:8765/
```

Tick or untick assertions, optionally add revised wording in `user_edit`, and click `Save CSV`.

## Notes

- The Word generator avoids visible labels such as `Generated from ...`.
- Document metadata is set from `docx_sources.csv`.
- The assertions editor preserves excluded assertions in the CSV for audit trail purposes.
