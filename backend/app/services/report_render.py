# ruff: noqa: E501  (report prose reads better unwrapped)
"""Feedback report: the same content blocks rendered to PDF (fpdf2) and DOCX.

`blocks(data)` turns the report data into an ordered list of headings, paragraphs, tables
and charts; `render_pdf` and `render_docx` only draw those blocks, so the two files always
say the same thing. A draft preview carries a "DRAFT – not for submission" mark on every page.
"""

import io
import os
from datetime import datetime
from typing import Any

from app.feedback_spec import CURRICULUM_KEYS, CURRICULUM_LABELS

DRAFT_MARK = "DRAFT – not for submission"
Block = tuple


def _pct(v: float | None) -> str:
    return "–" if v is None else f"{v * 100:.0f}%"


def _signed(v: float | None) -> str:
    return "–" if v is None else f"{v:+.2f}"


def _date(v: Any) -> str:
    if isinstance(v, datetime):
        return f"{v.day} {v.strftime('%B %Y')}"
    return str(v or "")


def _share(sentiment: dict[str, float] | None, key: str) -> str:
    total = sum((sentiment or {}).values())
    return _pct(sentiment[key] / total) if total else "–"


# --------------------------------------------------------------------------- content


def blocks(data: dict[str, Any]) -> list[Block]:
    c, t = data["cycle"], data["totals"]
    out: list[Block] = [
        ("title", data["institution"]),
        ("subtitle", "Feedback Analysis and Action Taken Report"),
        ("p", "Student feedback summary"),
        (
            "kv",
            [
                ("Feedback cycle", c["name"]),
                ("Academic year", c.get("academic_year") or "–"),
                ("Collection window", f"{_date(c.get('opens_at'))} to {_date(c.get('closes_at'))}"),
                ("Report generated", _date(data["generated_at"])),
                ("Stakeholders covered", "Students (teaching and curriculum feedback)"),
            ],
        ),
        ("pagebreak",),
        # 1 ------------------------------------------------------------------------------
        ("h1", "1. Feedback collection"),
        (
            "p",
            f"In {c['name']}, students gave feedback on {t['offerings']} course offerings in "
            f"{t['departments']} departments: {t['responses']} responses out of {t['eligible']} "
            f"possible ({_pct(t['responses'] / t['eligible'] if t['eligible'] else None)}). Each "
            "offering had one teaching-feedback form per teacher and one curriculum form. This "
            "version collects feedback from students only; teachers, alumni, employers and parents "
            "are not yet surveyed through this system.",
        ),
        (
            "table",
            ["Department", "Offerings", "Responses", "Possible", "Response rate"],
            [
                [d["name"], d["offerings"], d["responses"], d["eligible"], _pct(d["response_rate"])]
                for d in data["departments"]
            ],
            [70, 25, 28, 25, 32],
        ),
    ]
    for d in data["departments"]:
        out += [
            ("h2", f"{d['name']}: teaching feedback by course"),
            (
                "table",
                ["Course", "Section", "Responses", "Possible", "Rate"],
                [
                    [
                        f"{x['code']} {x['name']}",
                        x["section"],
                        x["teaching_responses"],
                        x["teaching_eligible"],
                        _pct(x["teaching_rate"]),
                    ]
                    for x in d["courses"]
                ],
                [80, 20, 28, 25, 27],
            ),
        ]
    # 2 ----------------------------------------------------------------------------------
    teach = "; ".join(f"{label}" for label, _ in data["questionnaire"]["teaching"])
    curr = "; ".join(f"{label}" for label, _ in data["questionnaire"]["curriculum"])
    engines = (
        " and ".join(f"{e} ({n})" for e, n in data["summary_engines"].items()) or "nothing yet"
    )
    th = data["thresholds"]
    out += [
        ("pagebreak",),
        ("h1", "2. Methodology"),
        (
            "p",
            "Questionnaire. Students rate each teacher from 1 (Poor) to 5 (Excellent) on eight "
            f"aspects ({teach}) and may write what they liked, what should improve and any other "
            f"comments. A separate curriculum form rates {curr} and takes one comment.",
        ),
        (
            "p",
            "Anonymity. Students sign in only to prove they are enrolled. Their answers are stored "
            "without their name or roll number; a one-way code tied to each form only stops a "
            "second submission. Results for a course are shown only once at least "
            f"{data['minimum']} students have responded.",
        ),
        (
            "p",
            "Moderation and privacy. Before anyone reads a comment, names, phone numbers, e-mail "
            "addresses, roll numbers and links are replaced with placeholders such as [NAME] or "
            "[FACULTY]. An abuse check scores every sentence; answers scoring "
            f"{th['tox_hide']:.2f} or more are hidden until the administrator reviews them. "
            "All comments quoted in this report are moderated and redacted.",
        ),
        (
            "p",
            "Analysis. Each comment is scored for sentiment (positive, neutral, negative), linked "
            "to the teaching aspects it mentions with the tone for each, and checked for emotion "
            "and possible sarcasm; praise that reads as sarcastic counts half. Net sentiment is "
            "the share of positive answers minus the share of negative answers (from -1 to +1). "
            f"Course summaries were written by {engines}, each citing the comments that support it. "
            "All processing runs on the college's own computer; only summaries, when an AI model "
            "is configured, are written by an external service from already-redacted text.",
        ),
        ("table", ["Step", "Model"], [[m["task"], m["model"]] for m in data["models"]], [70, 110]),
    ]
    # 3 ----------------------------------------------------------------------------------
    out += [
        ("pagebreak",),
        ("h1", "3. Analysis of teaching feedback"),
        (
            "p",
            f"Across the institution, net sentiment was {_signed(t['net_score'])}: "
            f"{_share(t['sentiment'], 'positive')} of answers read as positive, "
            f"{_share(t['sentiment'], 'neutral')} as neutral and {_share(t['sentiment'], 'negative')} "
            "as negative. Figures are for departments as a whole; this published report does not "
            "show results for individual teachers.",
        ),
        ("image", "sentiment", "Share of positive, neutral and negative answers by department."),
    ]
    for d in data["departments"]:
        out += [
            ("h2", d["name"]),
            (
                "p",
                f"{d['forms_shown']} of {d['teaching_forms']} teaching forms had enough responses to "
                f"analyse. Net sentiment {_signed(d['net_score'])}.",
            ),
        ]
        if f"aspects:{d['code']}" in data.get("_charts", ()):
            out.append(
                ("image", f"aspects:{d['code']}", f"Mean rating by teaching aspect, {d['code']}.")
            )
        if d["strengths"]:
            out.append(("h3", "What students value most"))
            for s in d["strengths"]:
                out.append(
                    (
                        "bullet",
                        f"{s['label']}: praised in {s['courses']} course(s), {s['mentions']} positive mentions.",
                    )
                )
                out += [("quote", q) for q in s["samples"]]
        if d["gaps"]:
            out.append(("h3", "What students want improved"))
            for g in d["gaps"]:
                out.append(("bullet", g["issue"]))
                out += [("quote", q) for q in g["samples"]]
    # 4 ----------------------------------------------------------------------------------
    out += [("pagebreak",), ("h1", "4. Curriculum feedback")]
    for d in data["departments"]:
        cur = d["curriculum"]
        out.append(("h2", d["name"]))
        if not cur["forms_shown"]:
            out.append(("p", "Not enough curriculum responses to analyse yet."))
            continue
        means = [
            f"{CURRICULUM_LABELS[k]} {cur['means'][k]:.1f}"
            for k in CURRICULUM_KEYS
            if cur["means"].get(k) is not None
        ]
        out.append(
            (
                "p",
                f"{cur['forms_shown']} curriculum forms analysed. Mean ratings: {', '.join(means)}. "
                f"Syllabus comments: {_share(cur['sentiment'], 'positive')} positive, "
                f"{_share(cur['sentiment'], 'negative')} negative.",
            )
        )
        if f"curriculum:{d['code']}" in data.get("_charts", ()):
            out.append(
                ("image", f"curriculum:{d['code']}", f"Mean curriculum ratings, {d['code']}.")
            )
        if cur["samples"]:
            out.append(("h3", "Sample comments (moderated and redacted)"))
            out += [("quote", q) for q in cur["samples"]]
    # 5 ----------------------------------------------------------------------------------
    approved = sum(a["status"] == "approved" for a in data["actions"])
    out += [
        ("pagebreak",),
        ("h1", "5. Action Taken Report"),
        (
            "p",
            "Each issue below was raised in the feedback and is stated for a department as a "
            "whole. Actions were drafted from the feedback and then edited and approved by the "
            f"Head of Department or the administrator ({approved} of {len(data['actions'])} "
            "approved).",
        ),
    ]
    if not data["actions"]:
        out.append(("p", "No actions recorded yet."))
    for dept in dict.fromkeys(a["department"] for a in data["actions"]):
        rows = [a for a in data["actions"] if a["department"] == dept]
        out += [
            ("h2", dept),
            (
                "table",
                ["Issue", "Count", "Action", "Responsible", "Timeline", "Status"],
                [
                    [
                        a["issue"]
                        if a["topic"].lower() in a["issue"].lower()
                        else f"{a['topic']}: {a['issue']}",
                        f"{a['evidence_count']} ratings"
                        if a["kind"] == "curriculum" and a["topic"] != "Syllabus comments"
                        else (a["evidence_count"] or "–"),
                        a["action"],
                        a["responsible"],
                        a["timeline"],
                        a["status"].title(),
                    ]
                    for a in rows
                ],
                [54, 21, 52, 30, 24, 21],
            ),
        ]
    # 6 ----------------------------------------------------------------------------------
    out += [
        ("h1", "6. Statement for publication"),
        (
            "p",
            f"Feedback for {c['name']} was collected from students, analysed, and acted upon as "
            "described above. This feedback and the Action Taken Report are made available on "
            f"the website of {data['institution']}.",
        ),
        ("signatures", ["Administrator", "Principal"]),
    ]
    return out


# --------------------------------------------------------------------------- PDF


def _font_dir() -> str:
    import matplotlib

    return os.path.join(matplotlib.get_data_path(), "fonts", "ttf")


def render_pdf(data: dict[str, Any], charts: dict[str, bytes], draft: bool) -> bytes:
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    data = {**data, "_charts": charts}
    title = f"{data['institution']} · Feedback report · {data['cycle']['name']}"

    class Report(FPDF):
        def header(self):
            if draft:
                with self.local_context(fill_opacity=0.1, text_color=(180, 30, 30)):
                    self.set_font("DejaVu", "B", 44)
                    with self.rotation(35, x=self.w / 2, y=self.h / 2):
                        self.text(self.w / 2 - 95, self.h / 2, DRAFT_MARK)
            if self.page_no() > 1:
                self.set_font("DejaVu", "", 8)
                self.set_text_color(90, 96, 104)
                self.cell(0, 6, title, align="L")
                self.ln(10)
                self.set_text_color(14, 15, 17)

        def footer(self):
            self.set_y(-12)
            self.set_font("DejaVu", "", 8)
            self.set_text_color(90, 96, 104)
            mark = f"{DRAFT_MARK} · " if draft else ""
            self.cell(0, 6, f"{mark}Page {self.page_no()} of {{nb}}", align="C")

    pdf = Report(format="A4")
    pdf.set_auto_page_break(True, margin=18)
    fonts = _font_dir()
    pdf.add_font("DejaVu", "", os.path.join(fonts, "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", os.path.join(fonts, "DejaVuSans-Bold.ttf"))
    pdf.add_font("DejaVu", "I", os.path.join(fonts, "DejaVuSans-Oblique.ttf"))
    pdf.set_title(f"Feedback report, {data['cycle']['name']}")
    pdf.set_author(data["institution"])
    pdf.add_page()
    width = pdf.epw

    for block in blocks(data):
        kind = block[0]
        if kind == "pagebreak":
            pdf.add_page()
        elif kind == "title":
            pdf.ln(40)
            pdf.set_font("DejaVu", "B", 22)
            pdf.multi_cell(width, 11, block[1], new_x="LMARGIN", new_y="NEXT")
        elif kind == "subtitle":
            pdf.set_font("DejaVu", "", 16)
            pdf.multi_cell(width, 9, block[1], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif kind == "kv":
            pdf.ln(8)
            for k, v in block[1]:
                pdf.set_font("DejaVu", "B", 10)
                pdf.cell(55, 7, k)
                pdf.set_font("DejaVu", "", 10)
                pdf.multi_cell(width - 55, 7, str(v), new_x="LMARGIN", new_y="NEXT")
        elif kind in ("h1", "h2", "h3"):
            size = {"h1": 15, "h2": 12, "h3": 10.5}[kind]
            if pdf.get_y() > pdf.h - 40:  # never leave a heading alone at the foot of a page
                pdf.add_page()
            pdf.ln(4 if kind != "h1" else 2)
            pdf.set_font("DejaVu", "B", size)
            pdf.multi_cell(width, size * 0.55, block[1], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)
        elif kind == "p":
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(width, 5.2, block[1], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2.5)
        elif kind == "bullet":
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(width, 5.2, f"• {block[1]}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        elif kind == "quote":
            pdf.set_font("DejaVu", "I", 9.5)
            pdf.set_x(pdf.l_margin + 6)
            pdf.set_text_color(70, 75, 82)
            pdf.multi_cell(width - 6, 5, f"“{block[1]}”", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(14, 15, 17)
            pdf.ln(1)
        elif kind == "image":
            if block[1] in charts:
                pdf.image(io.BytesIO(charts[block[1]]), w=width)
                pdf.set_font("DejaVu", "", 8.5)
                pdf.set_text_color(90, 96, 104)
                pdf.multi_cell(width, 4.5, block[2], new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(14, 15, 17)
                pdf.ln(3)
        elif kind == "table":
            _, headers, rows, widths = block
            pdf.set_font("DejaVu", "", 8.5)
            scale = width / sum(widths)
            with pdf.table(
                col_widths=[w * scale for w in widths],
                width=width,
                headings_style=FontFace(emphasis="BOLD", fill_color=(242, 244, 247)),
                line_height=4.6,
                text_align="LEFT",
                padding=1.2,
            ) as table:
                head = table.row()
                for h in headers:
                    head.cell(h)
                for r in rows:
                    row = table.row()
                    for cell in r:
                        row.cell(str(cell))
            pdf.ln(4)
        elif kind == "signatures":
            pdf.ln(18)
            col = width / len(block[1])
            y = pdf.get_y()
            for i, who in enumerate(block[1]):
                x = pdf.l_margin + i * col
                pdf.line(x, y, x + col - 15, y)
                pdf.set_xy(x, y + 2)
                pdf.set_font("DejaVu", "", 10)
                pdf.cell(col - 15, 6, who)
    return bytes(pdf.output())


# --------------------------------------------------------------------------- DOCX


def render_docx(data: dict[str, Any], charts: dict[str, bytes], draft: bool) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt, RGBColor

    data = {**data, "_charts": charts}
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)
    section = doc.sections[0]
    section.left_margin = section.right_margin = Inches(0.8)
    head = section.header.paragraphs[0]
    head.text = (
        f"{DRAFT_MARK} · " if draft else ""
    ) + f"{data['institution']} · Feedback report · {data['cycle']['name']}"
    head.runs[0].font.size = Pt(8)
    head.runs[0].font.color.rgb = (
        RGBColor(0xB4, 0x1E, 0x1E) if draft else RGBColor(0x5A, 0x60, 0x68)
    )
    width = section.page_width - section.left_margin - section.right_margin

    for block in blocks(data):
        kind = block[0]
        if kind == "pagebreak":
            doc.add_page_break()
        elif kind == "title":
            doc.add_heading(block[1], level=0)
        elif kind == "subtitle":
            doc.add_paragraph(block[1]).runs[0].font.size = Pt(15)
        elif kind == "kv":
            table = doc.add_table(rows=0, cols=2)
            for k, v in block[1]:
                cells = table.add_row().cells
                cells[0].text, cells[1].text = k, str(v)
                cells[0].paragraphs[0].runs[0].bold = True
            if draft:
                p = doc.add_paragraph()
                run = p.add_run(DRAFT_MARK)
                run.bold = True
                run.font.color.rgb = RGBColor(0xB4, 0x1E, 0x1E)
        elif kind in ("h1", "h2", "h3"):
            doc.add_heading(block[1], level={"h1": 1, "h2": 2, "h3": 3}[kind])
        elif kind == "p":
            doc.add_paragraph(block[1])
        elif kind == "bullet":
            doc.add_paragraph(block[1], style="List Bullet")
        elif kind == "quote":
            p = doc.add_paragraph(f"“{block[1]}”", style="Quote")
            p.paragraph_format.left_indent = Inches(0.3)
        elif kind == "image":
            if block[1] in charts:
                doc.add_picture(io.BytesIO(charts[block[1]]), width=width)
                cap = doc.add_paragraph(block[2])
                cap.runs[0].font.size = Pt(8.5)
                cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
        elif kind == "table":
            _, headers, rows, _widths = block
            table = doc.add_table(rows=1, cols=len(headers))
            table.style = "Light Grid Accent 1"
            for cell, h in zip(table.rows[0].cells, headers, strict=True):
                cell.text = h
            for r in rows:
                cells = table.add_row().cells
                for cell, value in zip(cells, r, strict=True):
                    cell.text = str(value)
            doc.add_paragraph()
        elif kind == "signatures":
            doc.add_paragraph()
            table = doc.add_table(rows=2, cols=len(block[1]))
            for i, who in enumerate(block[1]):
                table.rows[0].cells[i].text = "\n\n______________________________"
                table.rows[1].cells[i].text = who
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


__all__ = ["DRAFT_MARK", "blocks", "render_docx", "render_pdf"]
