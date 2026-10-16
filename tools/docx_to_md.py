import sys
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

src, dst = sys.argv[1], sys.argv[2]
doc = Document(src)
out = []


def runs_md(para):
    s = ""
    for r in para.runs:
        t = r.text
        if not t:
            continue
        if r.bold:
            t = f"**{t.strip()}**" + (" " if t.endswith(" ") else "")
        s += t
    return s.strip()


body = doc.element.body
first_para = True
for child in body.iterchildren():
    tag = child.tag.split("}")[-1]
    if tag == "p":
        para = Paragraph(child, doc)
        style = para.style.name
        text = runs_md(para)
        if not text:
            continue
        if first_para:
            out.append(f"# {text}")
            first_para = False
        elif style.startswith("Heading 1"):
            out.append(f"\n## {text}")
        elif style.startswith("Heading 2"):
            out.append(f"\n### {text}")
        elif style.startswith("List"):
            out.append(f"- {text}")
        else:
            out.append(f"\n{text}")
    elif tag == "tbl":
        t = Table(child, doc)
        rows = [[c.text.strip().replace("\n", " ") for c in r.cells] for r in t.rows]
        out.append("")
        out.append("| " + " | ".join(rows[0]) + " |")
        out.append("|" + "---|" * len(rows[0]))
        for r in rows[1:]:
            out.append("| " + " | ".join(r) + " |")
        out.append("")

open(dst, "w", encoding="utf-8").write("\n".join(out) + "\n")
print("wrote", dst)
