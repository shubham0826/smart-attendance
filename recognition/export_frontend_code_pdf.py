"""Export the dashboard's embedded HTML, CSS, and JavaScript source to PDF."""

import argparse
import re
import textwrap
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
SOURCE = Path(__file__).resolve().with_name("attendance_dashboard.py")
DEFAULT_OUTPUT = PROJECT_DIR / "docs" / "smart_attendance_frontend_code.pdf"
PAGE_W, PAGE_H = 595, 842  # A4 points
LEFT, RIGHT = 42, 42
FONT_SIZE, LINE_STEP = 7.2, 9.2
CODE_WIDTH = 108


def extract_sections():
    source = SOURCE.read_text(encoding="utf-8")
    match = re.search(r"^HTML_TEMPLATE\s*=\s*r'''(.*?)'''", source, re.M | re.S)
    if not match:
        raise SystemExit(f"Could not find HTML_TEMPLATE in {SOURCE}")
    html = match.group(1)
    style = re.search(r"<style>(.*?)</style>", html, re.S)
    script = re.search(r"<script>(.*?)</script>", html, re.S)
    if not style or not script:
        raise SystemExit("Could not locate the dashboard CSS and JavaScript sections.")

    markup = html[: style.start()] + html[style.end() : script.start()] + html[script.end() :]
    return [
        ("HTML MARKUP", markup.strip("\n")),
        ("CSS STYLES", style.group(1).strip("\n")),
        ("JAVASCRIPT", script.group(1).strip("\n")),
    ]


def pdf_text(value):
    # Standard PDF Courier uses Windows-1252; replace the one arrow in the UI text.
    value = value.replace("→", "->").replace("—", "-")
    value = value.encode("cp1252", errors="replace").decode("cp1252")
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(sections, output):
    pages = []
    commands = []
    y = 790
    page_number = 1

    def draw(text, x, baseline, font="F1", size=8):
        return f"BT /{font} {size} Tf 1 0 0 1 {x} {baseline} Tm ({pdf_text(text)}) Tj ET"

    def start_page(first=False):
        nonlocal commands, y
        commands = []
        y = 790
        if first:
            commands.extend(["0.08 0.16 0.28 rg", draw("Smart Attendance - Frontend Code", LEFT, y, "F2", 19), "0 0 0 rg"])
            y -= 22
            commands.append(draw("HTML, CSS, and JavaScript from recognition/attendance_dashboard.py", LEFT, y, size=9))
            y -= 17
        else:
            commands.append(draw("Smart Attendance - Frontend Code", LEFT, y, "F2", 10))
            y -= 20

    def finish_page():
        commands.append(draw("Source: recognition/attendance_dashboard.py", LEFT, 27))
        commands.append(draw(f"Page {page_number}", PAGE_W - RIGHT - 55, 27))
        pages.append("\n".join(commands))

    start_page(first=True)
    for title, section in sections:
        if y < 65:
            finish_page()
            page_number += 1
            start_page()
        commands.append(draw(title, LEFT, y, "F2", 10))
        y -= 15
        for line_no, line in enumerate(section.splitlines(), start=1):
            wrapped = textwrap.wrap(
                line.expandtabs(2), width=CODE_WIDTH, replace_whitespace=False,
                drop_whitespace=False, break_long_words=True, break_on_hyphens=False,
            ) or [""]
            for wrap_no, part in enumerate(wrapped):
                if y < 43:
                    finish_page()
                    page_number += 1
                    start_page()
                    commands.append(draw(f"{title} - continued", LEFT, y, "F2", 8))
                    y -= 12
                prefix = f"{line_no:4} " if wrap_no == 0 else "     "
                commands.append(draw(prefix + part, LEFT, y, size=FONT_SIZE))
                y -= LINE_STEP
        y -= 8
    finish_page()

    objects = []
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{5 + i * 2} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    for i, content in enumerate(pages):
        page_obj = 5 + i * 2
        stream_obj = page_obj + 1
        stream = content.encode("cp1252", errors="replace")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {stream_obj} 0 R >>"
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n" + stream.decode("cp1252") + "\nendstream")

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(obj.encode("cp1252", errors="replace"))
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(pdf)
    return len(pages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="PDF output path")
    args = parser.parse_args()
    count = make_pdf(extract_sections(), args.output)
    print(f"Frontend code PDF created: {args.output}")
    print(f"Pages: {count}")


if __name__ == "__main__":
    main()
