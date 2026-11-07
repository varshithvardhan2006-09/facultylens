"""PII redaction (SPEC §5 step 2). Runs before any other model sees the text.

Replaces people's names with [NAME] (the course teacher's own name with [FACULTY]), and phone
numbers, emails, roll numbers and links with [PHONE], [EMAIL], [ROLL], [URL]. Only the kinds
and counts of what was removed are kept, never the values.
"""

import re
from collections import Counter
from functools import lru_cache

from app.config import get_settings

TITLES = {"dr", "mr", "mrs", "ms", "prof", "sir", "madam", "maam", "ma'am", "miss"}

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_URL = re.compile(
    r"\b(?:https?://|w{3,}\.)\S+"
    # linkedin.com/in/someone. "In" and "Co" also start sentences ("well.In labs"), so those two
    # need one consistent case or a path; the other endings match in any case.
    r"|\b(?:[a-z0-9-]+\.)+(?:(?:com|org|net|edu|io)\b|(?-i:co|in|CO|IN)\b|(?:co|in)(?=/))(?:/\S*)?",
    re.IGNORECASE,
)
# Indian mobiles (+91 optional, 10 digits starting 6-9, spaced or not) and other 10-13 digit runs.
_PHONE = re.compile(
    r"(?<!\w)(?:\+?91[\s-]?)?[6-9]\d{4}[\s.-]?\d{5}(?!\w)|(?<!\w)\+?\d[\d\s-]{8,14}\d(?!\w)"
)
PRIORITY = {"EMAIL": 0, "URL": 1, "ROLL": 2, "PHONE": 3, "FACULTY": 4, "NAME": 5}


@lru_cache
def _roll_re(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


def _name_tokens(name: str | None) -> set[str]:
    words = re.findall(r"[a-z]+", (name or "").lower())
    return {w for w in words if w not in TITLES and len(w) >= 3}


def _uncovered(
    text: str, span: tuple[int, int, str], chosen: list[tuple[int, int, str]]
) -> list[tuple[int, int, str]]:
    """What is left of a name once stronger spans are cut out ("Ramesh 98765..." keeps "Ramesh")."""
    pieces, start = [], span[0]
    for c_start, c_end, _ in sorted(c for c in chosen if c[0] < span[1] and c[1] > span[0]):
        pieces.append((start, c_start))
        start = max(start, c_end)
    pieces.append((start, span[1]))
    out = []
    for a, b in pieces:
        piece = text[a:b] if a < b else ""
        if any(ch.isalpha() for ch in piece):
            lead = len(piece) - len(piece.lstrip())
            out.append((a + lead, a + len(piece.rstrip()), span[2]))
    return out


def find_spans(
    text: str, person_spans: list[tuple[int, int]], faculty_names: list[str]
) -> list[tuple[int, int, str]]:
    """All PII spans (start, end, kind), overlaps resolved by kind priority then length."""
    spans: list[tuple[int, int, str]] = []
    for kind, regex in (
        ("EMAIL", _EMAIL),
        ("URL", _URL),
        ("ROLL", _roll_re(get_settings().roll_no_regex)),
        ("PHONE", _PHONE),
    ):
        for m in regex.finditer(text):
            if kind == "URL":
                end = m.start() + len(m.group(0).rstrip(".,;:!?)"))
                spans.append((m.start(), end, kind))
                continue
            # A phone has at least 10 digits; this keeps year ranges like "2016 - 2020" out.
            if kind == "PHONE" and sum(c.isdigit() for c in m.group(0)) < 10:
                continue
            spans.append((m.start(), m.end(), kind))

    teacher = set().union(*(_name_tokens(n) for n in faculty_names)) if faculty_names else set()
    for start, end in person_spans:
        kind = "FACULTY" if _name_tokens(text[start:end]) & teacher else "NAME"
        spans.append((start, end, kind))
    # The teacher's name even where the NER model misses it ("Kavitha mam", "Reddy sir").
    for token in teacher:
        for m in re.finditer(rf"\b{re.escape(token)}\b", text, flags=re.IGNORECASE):
            spans.append((m.start(), m.end(), "FACULTY"))

    # Widen FACULTY/NAME spans to swallow a title right before them ("Dr. Kavitha").
    widened = []
    for start, end, kind in spans:
        if kind in ("FACULTY", "NAME"):
            before = re.search(r"(?:\b(?:dr|mr|mrs|ms|prof)\.?\s+)$", text[:start], re.IGNORECASE)
            if before:
                start = before.start()
        widened.append((start, end, kind))

    chosen: list[tuple[int, int, str]] = []
    for span in sorted(widened, key=lambda s: (PRIORITY[s[2]], -(s[1] - s[0]), s[0])):
        if all(span[1] <= c[0] or span[0] >= c[1] for c in chosen):
            chosen.append(span)
        elif span[2] in ("FACULTY", "NAME"):
            chosen.extend(_uncovered(text, span, chosen))
    # Merge adjacent FACULTY pieces ("Kavitha Reddy" found as two tokens) into one placeholder.
    chosen.sort()
    merged: list[tuple[int, int, str]] = []
    for span in chosen:
        if (
            merged
            and merged[-1][2] == span[2] == "FACULTY"
            and not text[merged[-1][1] : span[0]].strip()
        ):
            merged[-1] = (merged[-1][0], span[1], "FACULTY")
        else:
            merged.append(span)
    return merged


def redact(text: str, spans: list[tuple[int, int, str]]) -> tuple[str, dict[str, int]]:
    out = text
    for start, end, kind in sorted(spans, reverse=True):
        out = out[:start] + f"[{kind}]" + out[end:]
    counts = Counter(kind for _, _, kind in spans)
    return out, dict(counts)


def redact_batch(
    texts: list[str], faculty_names: list[list[str]]
) -> list[tuple[str, dict[str, int]]]:
    """Redact many texts with one spaCy pass."""
    from app.nlp import registry

    entities = registry.get("ner").entities(texts) if texts else []
    out = []
    for text, ents, names in zip(texts, entities, faculty_names, strict=True):
        persons = [(start, end) for _, label, start, end in ents if label == "PERSON"]
        out.append(redact(text, find_spans(text, persons, names)))
    return out
