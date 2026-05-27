# AGENTS.md

## Purpose Of This Workspace

Describe the writing project here: audience, intended publication, desired format, and the type of evidence being used.

## Source Files

Use Markdown files for source material and planning.

Recommended pattern:

- `source-notes.md` for rough notes and prompts.
- `context.md` for larger evidence, transcripts, research notes or stakeholder input.
- `considerations.md` for authorial stance, risks, constraints and things to avoid.
- `colleagues.md` for likely reviewer lenses or stakeholder priorities.
- `instructions_for_authors.md` for the editorial brief.
- `article-plan.md` for the short shareable plan.
- `article-outline.md` for the fuller drafting outline.

Always check source files before changing the plan, outline or draft. Do not treat the plan or outline as the original evidence base.

## Planning Method

Recommended workflow:

1. Gather source notes and context.
2. Identify audience, editorial format and authorial stance.
3. Create a concise shareable plan.
4. Create a fuller outline for drafting.
5. Extract planned assertions into `assertions.csv`.
6. Review assertions through the checkbox UI.
7. Generate Word documents for sharing and comments.
8. Iterate based on feedback.

## Assertions Audit

Use `assertions.csv` to track claims before drafting.

Track content-related assertions only. Do not include article setup, format instructions, authorial stance, workflow notes, or drafting-process guidance.

Required columns:

```csv
include,id,section,assertion,user_edit,status,evidence_or_check
```

Use `assertion` for the original planned claim and `user_edit` for optional revised wording. This preserves the audit trail while allowing edits.

Suggested status values:

- `planned`
- `interpretation`
- `verify`
- `draft_phrase`

Run the local editor with:

```powershell
edit-assertions
```

## Word Document Generation

Configure generated Word documents in:

- `docx_sources.csv`

Generate Word documents with:

```powershell
create-writing-docs
```

Before sharing, check that documents do not contain visible generator labels and that they read like natural working documents.

## Evidence Discipline

Distinguish clearly between:

- Directly sourced claims.
- Reasonable interpretations.
- Draft phrases.
- Claims requiring verification.

If a point is not directly supported by the source material, label it as interpretation or mark it for verification.
