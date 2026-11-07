# ruff: noqa: E501  (fixture data reads better unwrapped)
"""Feedback report rendering: both files open, say the same things, and mark drafts."""

import io
from datetime import UTC, datetime

import pytest
from docx import Document
from pypdf import PdfReader

from app.services import report_charts, report_render


def sample_data(actions=None):
    sentiment = {"positive": 30.0, "neutral": 5.0, "negative": 15.0}
    dept = {
        "code": "CSE",
        "name": "Computer Science and Engineering",
        "offerings": 2,
        "teaching_forms": 2,
        "curriculum_forms": 2,
        "forms_shown": 2,
        "teaching_responses": 50,
        "teaching_eligible": 60,
        "responses": 95,
        "eligible": 120,
        "response_rate": 0.792,
        "courses": [
            {
                "code": "CS501",
                "name": "Compiler Design",
                "section": "A",
                "teaching_responses": 25,
                "teaching_eligible": 30,
                "teaching_rate": 0.833,
            },
        ],
        "net_score": 0.3,
        "sentiment": sentiment,
        "aspect_means": {"clarity": 4.2, "pace": 2.6},
        "strengths": [
            {
                "aspect": "clarity",
                "label": "Clarity of explanation",
                "courses": 2,
                "mentions": 18,
                "samples": ["Explains every topic clearly."],
            }
        ],
        "gaps": [
            {
                "aspect": "pace",
                "label": "Pace & syllabus coverage",
                "mentions": 9,
                "issue": "Pace & syllabus coverage was raised as an area to improve in 2 of 2 CSE courses (9 critical comments).",
                "samples": ["The pace is too fast to follow."],
            }
        ],
        "curriculum": {
            "forms_shown": 2,
            "means": {"lab_adequacy": 2.7, "syllabus_relevance": 3.9},
            "sentiment": sentiment,
            "samples": ["More lab hours would help."],
        },
    }
    return {
        "institution": "Demo Institute of Technology",
        "cycle": {
            "name": "2026-27 Odd Sem",
            "academic_year": "2026-27",
            "term": "odd",
            "opens_at": datetime(2026, 9, 29, tzinfo=UTC),
            "closes_at": datetime(2026, 11, 3, tzinfo=UTC),
            "status": "open",
        },
        "generated_at": datetime(2026, 10, 20, tzinfo=UTC),
        "minimum": 5,
        "totals": {
            "departments": 1,
            "offerings": 2,
            "responses": 95,
            "eligible": 120,
            "net_score": 0.3,
            "sentiment": sentiment,
        },
        "departments": [dept],
        "questionnaire": {
            "teaching": [("Clarity of explanation", "q")],
            "curriculum": [("Lab and practical work", "q")],
        },
        "models": [
            {
                "task": "3-class overall sentiment",
                "model": "cardiffnlp/twitter-roberta-base-sentiment-latest",
            }
        ],
        "summary_engines": {"built-in templates": 2},
        "thresholds": {"tox_hide": 0.7, "tox_review": 0.4, "sarc_flag": 0.95},
        "actions": actions
        if actions is not None
        else [
            {
                "department": "Computer Science and Engineering",
                "kind": "teaching",
                "topic": "Pace & syllabus coverage",
                "issue": "Raised in 2 of 2 CSE courses.",
                "evidence_count": 9,
                "action": "Share a weekly coverage plan.",
                "responsible": "HoD, CSE",
                "timeline": "Before the next cycle",
                "status": "approved",
            },
        ],
    }


@pytest.fixture(scope="module")
def charts():
    return report_charts.all_charts(sample_data())


def pdf_text(raw: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(raw)).pages)


def docx_text(raw: bytes) -> str:
    doc = Document(io.BytesIO(raw))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        parts += [cell.text for row in table.rows for cell in row.cells]
    parts += [p.text for s in doc.sections for p in s.header.paragraphs]
    return "\n".join(parts)


def test_charts_are_png(charts):
    assert set(charts) == {"sentiment", "aspects:CSE", "curriculum:CSE"}
    assert all(png.startswith(b"\x89PNG") for png in charts.values())


@pytest.mark.parametrize("draft", [True, False])
def test_pdf_and_docx_open_and_carry_every_section(charts, draft):
    data = sample_data()
    pdf = report_render.render_pdf(data, charts, draft=draft)
    docx = report_render.render_docx(data, charts, draft=draft)
    assert pdf.startswith(b"%PDF")
    texts = [pdf_text(pdf), docx_text(docx)]
    for text in texts:
        squashed = "".join(text.split())  # pypdf drops the space at a wrapped table line
        for needle in (
            "Feedback Analysis and Action Taken Report",
            "1. Feedback collection",
            "2. Methodology",
            "3. Analysis of teaching feedback",
            "4. Curriculum feedback",
            "5. Action Taken Report",
            "6. Statement for publication",
            "Share a weekly coverage plan.",
            "The pace is too fast to follow.",
            "Administrator",
        ):
            assert "".join(needle.split()) in squashed, needle
        assert ("DRAFT" in text) is draft
    assert len(Document(io.BytesIO(docx)).inline_shapes) == 3  # the three charts


def test_empty_action_table_still_renders(charts):
    pdf = report_render.render_pdf(sample_data(actions=[]), charts, draft=True)
    assert "No actions recorded yet." in " ".join(pdf_text(pdf).split())
