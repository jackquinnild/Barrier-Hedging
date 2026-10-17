"""Render paper/paper.md to paper/paper.pdf (needs the `markdown` package and Google Chrome).

    python scripts/build_paper.py
"""

import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page { size: Letter; margin: 0.9in 0.95in 0.9in 0.95in; }
body { font-family: "Charter", "Georgia", serif; font-size: 10.6pt; line-height: 1.5; color: #1f1f1d; }
h1 { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 21pt; line-height: 1.2; margin: 0 0 4pt; }
h3 { font-family: "Helvetica Neue", Arial, sans-serif; font-weight: normal; font-size: 12pt; color: #52514e; margin: 0 0 10pt; }
h2 { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 13.5pt; margin: 20pt 0 6pt; break-after: avoid; }
h3.section { color: #1f1f1d; font-weight: bold; font-size: 11pt; margin: 14pt 0 4pt; }
p { margin: 0 0 8pt; text-align: left; }
hr { border: none; border-top: 0.6pt solid #d8d7d2; margin: 14pt 0; }
table { border-collapse: collapse; margin: 6pt 0 12pt; font-family: "Helvetica Neue", Arial, sans-serif; font-size: 8.8pt;
        break-inside: avoid; }
th { text-align: left; border-bottom: 0.8pt solid #1f1f1d; padding: 3pt 10pt 3pt 0; font-weight: bold; }
td { border-bottom: 0.4pt solid #e6e5e1; padding: 3pt 10pt 3pt 0; vertical-align: top; }
h2, h3 { break-after: avoid; }
img { width: 90%; margin: 6pt 0 2pt; break-inside: avoid; }
img[src*="fig6_"] { width: 66%; }
img[src*="fig1_"], img[src*="fig4_"], img[src*="fig5_"], img[src*="fig8_"], img[src*="fig9_"] { width: 80%; }
p:has(img) { break-inside: avoid; break-after: avoid; margin-bottom: 0; }
em { color: #52514e; }
p > em:only-child { font-size: 9.2pt; display: block; margin-bottom: 6pt; }
ul, ol { margin: 0 0 8pt; padding-left: 18pt; }
li { margin-bottom: 3pt; }
code { font-size: 9pt; }
"""


def main():
    source = (ROOT / "paper" / "paper.md").read_text()
    body = markdown.markdown(source, extensions=["tables"])
    # Subsection headings inside the results are h3 in the markdown; give them their own style.
    body = body.replace("<h3>4.", '<h3 class="section">4.').replace("<h3>The", '<h3 class="section">The')
    body = body.replace("<h3>Who", '<h3 class="section">Who').replace("<h3>Index", '<h3 class="section">Index')
    # Keep course numbers such as 21-370 from splitting across lines at the hyphen.
    for course in ("21-270", "21-370"):
        body = body.replace(course, f'<span style="white-space: nowrap">{course}</span>')
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    html_path = ROOT / "paper" / "paper.html"
    html_path.write_text(html)
    pdf = ROOT / "paper" / "paper.pdf"
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}",
                    html_path.as_uri()], check=True, capture_output=True)
    html_path.unlink()
    print("wrote", pdf)


if __name__ == "__main__":
    sys.exit(main())
