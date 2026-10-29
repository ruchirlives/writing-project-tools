# Generator schema

Call `generate_editable_table(project_dir, title, columns, rows, sources, output, description, evidence_note, overwrite)` through MCP. Only `project_dir`, `title`, `columns` and `rows` are required. The default output is `outputs/editable-table.html`; the JSON shares its stem. The output and source paths must remain inside the project, including through symlinks.

## Columns

Each column has `key` (unique simple identifier), `label`, `type` (`text`, `select`, `number`, `date`), optional pixel `width` (100–800), string `default`, and optional `role` explaining the evidence basis. Select fields require unique string `options`; option order defines sorting. The first option is the default unless overridden. All cell values are strings, including numbers and ISO dates. A source-trace column is added automatically.

The columns can represent any subject; no field name, priority scale or organisational branding is hard-coded. Select columns receive filters; every field is searchable and sortable.

## Rows and sources

Rows use `id`, `values` keyed by column key, `sourceIds`, and optional `sourceNotes`. Missing values use column defaults. Original values are retained separately for traceability. Browser edits preserve row IDs, the original values and source snapshots.

Sources use unique `id`, `title`, optional `date`, `reference`, `excerpt`, and optional project-relative `path`. With `path`, optional `lineStart` and `lineEnd` extract the exact inclusive range from a UTF-8 file. Without a range, supply an exact `excerpt` when available; a path alone creates only a link. File links are relative to the HTML, so keep its position relative to source files when sharing. A named email reference is not proof the original email was inspected.

## Synthetic example

The following is fictional sample input, not project data. In a real project, read its own source and replace these fields and rows.

```json
{
  "project_dir": "C:/Writing/ExampleProject",
  "title": "Venue Review",
  "output": "outputs/venue-review.html",
  "description": "Agree practical improvements to the venue.",
  "evidence_note": "Current arrangements are sourced; next steps are proposals for agreement.",
  "columns": [
    {"key": "issue", "label": "Issue", "width": 180},
    {"key": "current", "label": "Current arrangement", "role": "Source summary"},
    {"key": "next", "label": "Next step", "role": "Proposed action"},
    {"key": "owner", "label": "Owner", "width": 160},
    {"key": "status", "label": "Status", "type": "select", "options": ["Not agreed", "Planned", "Complete"]}
  ],
  "sources": [{"id": "S1", "title": "Fictional venue note", "reference": "Synthetic example only", "excerpt": "The meeting room has no booking calendar."}],
  "rows": [{"id": "V1", "values": {"issue": "Room booking", "current": "No booking calendar.", "next": "Agree a shared booking process.", "owner": "To agree"}, "sourceIds": ["S1"]}]
}
```

For the CLI, place the specification in the target project, omit `project_dir` and `output` from the specification, and pass them with `--project` and `--output`. The generator returns absolute HTML/JSON paths, row and column counts and any timestamped backups. It generates a unique table identity. A saved JSON with a different identity or schema is rejected by the HTML to prevent loading the wrong project.

## Storage boundaries

The template is packaged with the toolkit; generated row data and JSON are never stored in the toolkit. Native browser file permissions are per user/session. Save compares the current connected file with the text originally loaded before writing. Changes detected elsewhere block the save and suggest reopening or saving a separate copy. This is a conflict check, not a transactional shared database. Recovery drafts are local to the browser and table identity. Clipboard copy includes the full table and source references, with a manual text fallback.
