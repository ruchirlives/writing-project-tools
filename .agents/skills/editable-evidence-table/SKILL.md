---
name: editable-evidence-table
description: Create a standalone editable HTML table with a companion project-owned JSON file, configurable columns, and traceable source extracts. Use for locally saved review tables, action registers and evidence matrices.
---

# Editable evidence table

Use the writing-project-tools template and generator for local HTML tables that can be edited and saved without a server. This is a repository skill and code template, not a Template Gallery artifact.

## Create a table

- Read the user's source files and any existing table first. Preserve original table wording when requested. Keep proposals, interpretations and unknowns distinct from sourced facts. Do not infer missing priorities or completion states.
- Use `generate_editable_table` through writing-project-tools MCP with the explicit `project_dir`. Read [references/schema.md](references/schema.md) for the configurable fields, source links and example arguments. The packaged template is `src/writing_project_tools/templates/editable_table.html`; do not copy a previous project's HTML as the implementation.
- Choose meaningful column keys, labels, types, options and widths. Priority is an ordinary optional select column, not a fixed requirement. Column `role` explains the evidence basis in the trace view. Keep row IDs stable.
- Supply source IDs with exact extracts or project-relative file paths and one-based line ranges. Path/range sources are extracted by the generator. Use `reference` for named correspondence unavailable as a file; do not invent links or claim the originals were checked. Source extracts remain snapshots.
- Write the HTML and JSON pair to the target project's `outputs/`, with a project-appropriate filename. Project rows, source extracts and saved JSON belong to that project, never the toolkit repository or this skill. Use synthetic material for toolkit examples and tests.
- The generator refuses existing outputs by default. Before explicit regeneration, read the project's saved JSON and preserve edits. `overwrite=True` backs up both existing files but does not merge their data or migrate schemas. Rebuilding creates a new table identity; use a new output stem for a changed schema.

If the MCP tool has not been loaded after an update, restart the MCP connection. An installed CLI fallback is `generate-editable-table --project <folder> --spec <project-owned-spec.json> --output outputs/review.html`. Do not install the toolkit or create a virtual environment in the writing project.

## Verify and hand over

Check generated fields, row counts, source ranges, and that the HTML embeds the same starting data as the JSON. Check editing, select filters, undo/redo, source trace, copy fallback and save/reopen behavior when browser access permits. Distinguish logic tests using mocked file handles from native permission and browser checks.

Tell the user to open the HTML in Chrome or Edge, then use **Open JSON** to connect the companion file and **Save** to write changes. The HTML's starting snapshot does not update when JSON is saved. Other browsers may download a copy instead; that is not a save to the original file. Browser recovery storage is a convenience, not the saved project file. The app detects changes to a connected file before saving, but cloud sync does not provide simultaneous editing or eliminate races.

Keep Word documents and other deliverables unchanged unless the user asks to regenerate them. A standalone table does not synchronise them automatically.
