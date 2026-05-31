# Writing Project Tools Instructions

These instructions are intended for an LLM using the `writing-project-tools` MCP server. They describe how to work with evidence-led writing projects whose source files live in an external project folder.

Always operate on the user-specified project folder. Pass that folder explicitly as `project_dir` when using MCP helpers. Do not assume the MCP server working directory is the writing project.

## Core Operating Rules

- Treat source material as the evidence base. Do not treat the article plan or outline as the original evidence.
- Check relevant source files before changing `article-plan.md`, `article-outline.md`, or `article-draft.md`.
- Preserve existing files unless the user explicitly asks to overwrite or replace them.
- Keep claims traceable to source material, interpretation, draft phrasing, or verification needs.
- Use Markdown files for planning and drafting, `assertions.csv` for claim review, and `docx_sources.csv` for Word document outputs.

## MCP Helpers

Use these `writing-project-tools` MCP helpers when available:

- `get_project_instructions(project_dir)` reads these toolkit instructions and also includes project-local `AGENTS.md` as an overlay when present.
- `get_writing_project_instructions()` reads these default toolkit instructions.
- `get_workflow_summary()` returns a concise structured summary of files, assertion rules, workflow steps, and core helpers.
- `scaffold_article_project(project_dir, force=False)` creates missing standard project files without overwriting by default.
- `list_project_markdown(project_dir)` lists Markdown files in the project folder.
- `read_writing_context(project_dir)` reads the standard writing-project Markdown files that exist.
- `read_selected_markdown(project_dir, paths)` reads selected Markdown files.
- `read_project_markdown(project_dir, path)` reads one project Markdown file.
- `write_project_markdown(project_dir, path, content)` writes one project Markdown file.
- `prepare_draft_inputs(project_dir)` gathers instructions, outline, context, assertions, and Word config for draft creation.
- `build_paste_ready_llm_context(project_dir, task="draft")` returns a Markdown context bundle for pasting into an external LLM.
- `export_paste_ready_llm_context(project_dir, output="llm-context.md", task="draft")` writes that context bundle into the project folder.
- `read_project_assertions(project_dir, csv_name="assertions.csv")` reads assertions.
- `write_project_assertions(project_dir, rows, csv_name="assertions.csv")` writes assertions.
- `read_docx_sources(project_dir, csv_name="docx_sources.csv")` reads Word generation config.
- `write_docx_sources(project_dir, rows, csv_name="docx_sources.csv")` writes Word generation config.
- `generate_writing_docs(project_dir, config="docx_sources.csv")` generates Word documents.
- `start_project_editor(project_dir, csv_name="assertions.csv")` starts the browser-based assertions and Markdown editor.

If MCP is unavailable, use the installed console commands:

```powershell
scaffold-writing-project "C:\path\to\project"
create-writing-docs --project "C:\path\to\project"
edit-assertions --csv "C:\path\to\project\assertions.csv"
```

## Standard Project Files

Recommended files:

- `source-notes.md` for rough notes and prompts.
- `context.md` for larger evidence, transcripts, research notes, or stakeholder input.
- `considerations.md` for authorial stance, risks, constraints, and things to avoid.
- `colleagues.md` for likely reviewer lenses or stakeholder priorities.
- `instructions_for_authors.md` for the editorial brief.
- `article-plan.md` for the short shareable plan.
- `article-outline.md` for the fuller drafting outline.
- `article-draft.md` for the draft created from the reviewed outline.

Existing folders may have only some of these files. Work with the files that exist unless the user asks you to scaffold missing files.

## Markdown Style

Use simple, Word-output-friendly Markdown.

- Use `#`, `##`, and `###` headings only.
- Use `-` for bullet lists, not `*`.
- Use numbered lists as `1.`, `2.`, `3.` when order matters.
- Keep paragraphs as plain text separated by blank lines.
- Prefer clear section headings over bold-only pseudo-headings.
- Avoid tables unless the user specifically asks for them.
- Avoid HTML, footnote syntax, embedded images, and complex Markdown extensions.
- Avoid decorative separators unless needed for readability.
- Keep Markdown readable in plain text; do not rely on styling that only works in a preview renderer.

## Planning Workflow

Use this workflow when the user asks for article planning or drafting:

1. Read instructions with `get_project_instructions(project_dir)`. Use toolkit instructions as the base workflow, and project-local `AGENTS.md` as project-specific overlay guidance when present.
2. Read source material with `read_writing_context(project_dir)` or `read_selected_markdown(project_dir, paths)`.
3. Identify audience, editorial format, authorial stance, and evidence constraints.
4. Create or revise `article-plan.md`.
5. Create or revise `article-outline.md`.
6. Extract planned content assertions into `assertions.csv`.
7. Ask the user to review assertions, or start the editor with `start_project_editor(project_dir)`.
8. Revise the plan and outline from reviewed assertions.
9. Create or revise `article-draft.md` from the reviewed outline. Use `prepare_draft_inputs(project_dir)` before drafting when available.
10. Generate Word documents with `generate_writing_docs(project_dir)` when requested.

## Assertions Audit

Use `assertions.csv` to track claims before drafting.

Track content-related assertions only. Do not include article setup, format instructions, authorial stance, workflow notes, or drafting-process guidance.

Required columns:

```csv
include,id,section,assertion,user_edit,status,evidence_or_check
```

Column guidance:

- `include`: use `TRUE` for claims to keep and `FALSE` for claims excluded from the draft.
- `id`: stable row identifier.
- `section`: article section or planning area.
- `assertion`: original planned claim.
- `user_edit`: optional revised wording; leave blank when not needed.
- `status`: one of `planned`, `interpretation`, `verify`, or `draft_phrase`.
- `evidence_or_check`: short evidence pointer, source note, or verification task.

Use `read_writing_context(project_dir)` before generating assertions. Save generated rows with `write_project_assertions(project_dir, rows)`.

## Evidence Discipline

Distinguish clearly between:

- Directly sourced claims.
- Reasonable interpretations.
- Draft phrases.
- Claims requiring verification.

If a point is not directly supported by source material, label it as `interpretation` or mark it as `verify`.

## Word Document Generation

Use `docx_sources.csv` to configure generated Word documents.

Required columns:

```csv
source,title,subject,output,author
```

Before changing document outputs, read current config with `read_docx_sources(project_dir)`. Write updates with `write_docx_sources(project_dir, rows)`. Generate files with `generate_writing_docs(project_dir)`.

When preparing Markdown for Word conversion:

- Use a single `#` heading for the document title or top-level document heading.
- Use `##` and `###` for sections and subsections.
- Use `-` bullet lists and `1.`, `2.`, `3.` numbered lists.
- Keep each paragraph on its own line or wrapped naturally as plain text.
- Do not include visible generator labels such as `Generated from ...`.
- Do not include internal workflow notes, comments to the LLM, or prompt text in shareable documents.
- Ensure the document reads naturally as a working Word document before generating `.docx`.

Before sharing generated documents, check that they do not contain visible generator labels and that they read like natural working documents.
