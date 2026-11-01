"""Export markdown CV to PDF with reportlab. Returns the page count."""
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _inline(s):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


def md_to_pdf(md, out_path):
    st = getSampleStyleSheet()
    body = st["BodyText"]
    body.fontSize, body.leading = 9.5, 12
    flow = []
    for line in md.splitlines():
        if line.startswith("# "):
            flow.append(Paragraph(_inline(line[2:]), st["Title"]))
        elif line.startswith("## "):
            flow += [Spacer(1, 4), Paragraph(_inline(line[3:]), st["Heading3"])]
        elif line.startswith("- "):
            flow.append(Paragraph("• " + _inline(line[2:]), body))
        elif line.strip():
            flow.append(Paragraph(_inline(line), body))
    pages = {"n": 0}

    def count(canvas, doc):
        pages["n"] = doc.page

    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title="CV")
    doc.build(flow, onFirstPage=count, onLaterPages=count)
    return pages["n"]
