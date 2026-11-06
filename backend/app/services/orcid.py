"""ORCID Public API v3.0 import (no key needed for public data).

Fetching and mapping are separate: `map_*` functions turn ORCID JSON into FacultyLens items and
are unit-tested on saved real responses; `fetch_orcid` does the HTTP.
"""

import re
from typing import Any

from app.services.http import ExternalServiceError, make_client, request_json
from app.services.profile_items import PUBLICATION_TYPES, clean_text, normalise_doi, to_year

BASE = "https://pub.orcid.org/v3.0"
SOURCE = "ORCID"
_ID = re.compile(r"(\d{4})-?(\d{4})-?(\d{4})-?(\d{3}[\dX])", re.IGNORECASE)

WORK_TYPES = {
    "journal-article": "journal",
    "conference-paper": "conference",
    "conference-abstract": "conference",
    "conference-poster": "conference",
    "book": "book",
    "edited-book": "book",
    "book-chapter": "chapter",
    "preprint": "preprint",
    "working-paper": "preprint",
    "dissertation-thesis": "thesis",
    "dissertation": "thesis",
}


def parse_orcid(value: str) -> str:
    """Accept '0000-0002-1825-0097', '0000000218250097' or an orcid.org URL; verify the checksum."""
    match = _ID.search((value or "").strip())
    if not match:
        raise ValueError("That isn't an ORCID iD. It looks like 0000-0002-1825-0097.")
    orcid = "-".join(match.groups()).upper()
    digits = orcid.replace("-", "")
    total = 0
    for ch in digits[:-1]:
        total = (total + int(ch)) * 2
    check = (12 - total % 11) % 11
    expected = "X" if check == 10 else str(check)
    if digits[-1] != expected:
        raise ValueError("That ORCID iD has a typo: its last character doesn't match.")
    return orcid


def _value(node: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _doi(external_ids: Any) -> str | None:
    for ext in _value(external_ids, "external-id") or []:
        if (ext.get("external-id-type") or "").lower() == "doi" and ext.get(
            "external-id-relationship", "self"
        ) in ("self", None):
            return normalise_doi(ext.get("external-id-value"))
    return None


def map_work(summary: dict[str, Any], detail: dict[str, Any] | None = None) -> dict[str, Any]:
    source = detail or summary
    doi = _doi(source.get("external-ids"))
    authors = [
        clean_text(_value(c, "credit-name", "value"), 120)
        for c in _value(detail, "contributors", "contributor") or []
    ]
    url = _value(source, "url", "value") or (f"https://doi.org/{doi}" if doi else None)
    kind = WORK_TYPES.get(source.get("type") or "", "other")
    return {
        "title": clean_text(_value(source, "title", "title", "value"), 500),
        "venue": clean_text(_value(source, "journal-title", "value"), 300),
        "year": to_year(_value(source, "publication-date", "year", "value")),
        "type": kind if kind in PUBLICATION_TYPES else "other",
        "doi": doi,
        "authors": [a for a in authors if a][:50],
        "citations": None,
        "tldr": None,
        "url": clean_text(url, 500),
        "s2_paper_id": None,
    }


def map_works(works: dict[str, Any], bulk: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """One item per ORCID work group (the group already merges the same work from many sources)."""
    details = {}
    for entry in (bulk or {}).get("bulk", []):
        work = entry.get("work")
        if work:
            details[work.get("put-code")] = work
    items = []
    for group in works.get("group", []):
        summaries = group.get("work-summary") or []
        if not summaries:
            continue
        summary = summaries[0]
        item = map_work(summary, details.get(summary.get("put-code")))
        if item["title"]:
            items.append(item)
    return items


def _affiliations(payload: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    out = []
    for group in payload.get("affiliation-group", []):
        for summary in group.get("summaries", []):
            node = summary.get(f"{kind}-summary")
            if node:
                out.append(node)
    return out


def map_employments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for node in _affiliations(payload, "employment"):
        institution = clean_text(_value(node, "organization", "name"), 200)
        if not institution:
            continue
        items.append(
            {
                "role": clean_text(node.get("role-title"), 160) or "Staff",
                "institution": institution,
                "department": clean_text(node.get("department-name"), 160),
                "from_year": to_year(_value(node, "start-date", "year", "value")),
                "to_year": to_year(_value(node, "end-date", "year", "value")),
            }
        )
    return items


def map_educations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for node in _affiliations(payload, "education"):
        institution = clean_text(_value(node, "organization", "name"), 200)
        degree = clean_text(node.get("role-title"), 120)
        if not institution or not degree:
            continue
        items.append(
            {
                "degree": degree,
                "specialisation": clean_text(node.get("department-name"), 160),
                "institution": institution,
                "year": to_year(_value(node, "end-date", "year", "value")),
            }
        )
    return items


def map_keywords(payload: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for kw in payload.get("keyword", []):
        for part in re.split(r"[;,]", kw.get("content") or ""):
            tag = clean_text(part, 60)
            if tag and tag.lower() not in {t.lower() for t in tags}:
                tags.append(tag)
    return tags


async def fetch_orcid(orcid: str) -> dict[str, list]:
    """Fetch and map everything importable from a public ORCID record."""
    async with make_client(Accept="application/json") as client:
        base = f"{BASE}/{orcid}"
        works = await request_json(client, "GET", f"{base}/works", source=SOURCE)
        put_codes = [
            g["work-summary"][0]["put-code"]
            for g in works.get("group", [])
            if g.get("work-summary")
        ]
        bulk: dict[str, Any] = {"bulk": []}
        for i in range(0, len(put_codes), 100):
            chunk = ",".join(str(p) for p in put_codes[i : i + 100])
            try:
                part = await request_json(client, "GET", f"{base}/works/{chunk}", source=SOURCE)
                bulk["bulk"].extend(part.get("bulk", []))
            except ExternalServiceError:
                break  # author names are a nice-to-have; the summaries still import
        employments = await request_json(client, "GET", f"{base}/employments", source=SOURCE)
        educations = await request_json(client, "GET", f"{base}/educations", source=SOURCE)
        keywords = await request_json(client, "GET", f"{base}/keywords", source=SOURCE)
    return {
        "publication": map_works(works, bulk),
        "experience": map_employments(employments),
        "qualification": map_educations(educations),
        "interest": [{"tag": t} for t in map_keywords(keywords)],
    }
