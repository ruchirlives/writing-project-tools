from __future__ import annotations

import re
import csv
import argparse
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from docx.shared import Pt


DEFAULT_AUTHOR = "Author"


def is_separator_line(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    if "|" not in line or "-" not in line:
        return False
    return all(c in "| -:" for c in line)


def parse_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def add_runs_to_paragraph(paragraph, text: str) -> None:
    font_name = "Calibri"

    pattern = re.compile(r"(\*\*.*?\*\*|__.*?__)")
    parts = pattern.split(text)
    for part in parts:
        if not part:
            continue
        if (part.startswith("**") and part.endswith("**")) or (part.startswith("__") and part.endswith("__")):
            content = part[2:-2]
            run = paragraph.add_run(content)
            run.bold = True
        else:
            run = paragraph.add_run(part)
        run.font.name = font_name


def add_markdown_to_document(document: Document, markdown: str) -> None:
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line = raw_line.strip()

        if not line:
            i += 1
            continue

        # Check if this line starts a table
        is_table = False
        if "|" in line and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if is_separator_line(next_line):
                is_table = True

        if is_table:
            table_lines = []
            while i < len(lines):
                curr_line = lines[i].strip()
                if "|" not in curr_line:
                    break
                table_lines.append(curr_line)
                i += 1

            if len(table_lines) >= 2:
                header_cells = parse_table_row(table_lines[0])
                # Skip the separator line table_lines[1]
                body_rows = [parse_table_row(l) for l in table_lines[2:]]

                num_cols = len(header_cells)
                if num_cols > 0:
                    table = document.add_table(rows=1, cols=num_cols)
                    table.style = "Table Grid"

                    hdr_cells = table.rows[0].cells
                    for col_idx, cell_text in enumerate(header_cells):
                        p = hdr_cells[col_idx].paragraphs[0]
                        add_runs_to_paragraph(p, cell_text)
                        for run in p.runs:
                            run.bold = True

                    for row_cells in body_rows:
                        row = table.add_row()
                        cells = row.cells
                        for col_idx in range(num_cols):
                            cell_text = row_cells[col_idx] if col_idx < len(row_cells) else ""
                            p = cells[col_idx].paragraphs[0]
                            add_runs_to_paragraph(p, cell_text)
            continue

        if line.startswith("# "):
            heading = document.add_heading("", level=1)
            add_runs_to_paragraph(heading, line.removeprefix("# "))
        elif line.startswith("## "):
            heading = document.add_heading("", level=2)
            add_runs_to_paragraph(heading, line.removeprefix("## "))
        elif line.startswith("### "):
            heading = document.add_heading("", level=3)
            add_runs_to_paragraph(heading, line.removeprefix("### "))
        elif line.startswith(("- ", "* ")):
            p = document.add_paragraph(style="List Bullet")
            add_runs_to_paragraph(p, line[2:])
        elif ". " in line[:5] and line.split(". ", 1)[0].isdigit():
            p = document.add_paragraph(style="List Number")
            add_runs_to_paragraph(p, line.split(". ", 1)[1])
        else:
            p = document.add_paragraph()
            add_runs_to_paragraph(p, line)

        i += 1



def style_document(document: Document) -> None:
    styles = document.styles
    styles["Normal"].font.name = "Calibri"
    styles["Normal"].font.size = Pt(11)

    for style_name in ("Heading 1", "Heading 2", "Heading 3"):
        if style_name in styles:
            styles[style_name].font.name = "Calibri"

    for style_name in ("List Bullet", "List Number"):
        if style_name in styles:
            styles[style_name].font.name = "Calibri"


def set_document_properties(
    document: Document,
    title: str,
    subject: str,
    author: str,
) -> None:
    timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
    properties = document.core_properties
    properties.author = author
    properties.last_modified_by = author
    properties.title = title
    properties.subject = subject
    properties.keywords = ""
    properties.comments = ""
    properties.category = ""
    properties.content_status = ""
    properties.created = timestamp
    properties.modified = timestamp
    properties.revision = 1


def patch_extended_properties(docx_path: Path) -> None:
    with TemporaryDirectory(dir=docx_path.parent) as temp_dir:
        temp_path = Path(temp_dir) / docx_path.name

        with ZipFile(docx_path, "r") as source_zip, ZipFile(
            temp_path, "w", ZIP_DEFLATED
        ) as target_zip:
            for item in source_zip.infolist():
                data = source_zip.read(item.filename)

                if item.filename == "docProps/app.xml":
                    text = data.decode("utf-8")
                    text = text.replace(
                        "<Application>Microsoft Macintosh Word</Application>",
                        "<Application>Microsoft Word</Application>",
                    )
                    text = text.replace(
                        "<AppVersion>14.0000</AppVersion>",
                        "<AppVersion>16.0000</AppVersion>",
                    )
                    data = text.encode("utf-8")

                target_zip.writestr(item, data)

        temp_path.replace(docx_path)


def build_docx(
    source_path: Path,
    title: str,
    subject: str,
    output_path: Path,
    author: str,
) -> None:
    document = Document()
    style_document(document)
    set_document_properties(document, title, subject, author)

    add_markdown_to_document(document, source_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
    patch_extended_properties(output_path)


def read_config(config_path: Path) -> list[dict[str, str]]:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Missing {config_path}. Create it with columns: "
            "source,title,subject,output,author"
        )

    with config_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def generate_docs(project_dir: Path, config: str = "docx_sources.csv") -> list[Path]:
    root = project_dir.resolve()
    config_path = (root / config).resolve()
    outputs: list[Path] = []

    for row in read_config(config_path):
        source = row.get("source", "").strip()
        if not source:
            continue

        source_path = root / source
        if not source_path.exists():
            raise FileNotFoundError(f"Missing source file: {source_path}")

        title = row.get("title", "").strip() or source_path.stem.replace("-", " ").title()
        subject = row.get("subject", "").strip() or title
        output = row.get("output", "").strip() or f"outputs/{source_path.with_suffix('.docx').name}"
        author = row.get("author", "").strip() or DEFAULT_AUTHOR
        output_path = root / output

        build_docx(source_path, title, subject, output_path, author)
        outputs.append(output_path)

    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Word .docx files from project Markdown sources.")
    parser.add_argument(
        "--project",
        default=".",
        help="Project folder containing docx_sources.csv. Defaults to the current folder.",
    )
    parser.add_argument(
        "--config",
        default="docx_sources.csv",
        help="Config CSV path relative to the project folder.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = generate_docs(Path(args.project), args.config)
    for output in outputs:
        print(f"Wrote {output}")


if __name__ == "__main__":
    main()
