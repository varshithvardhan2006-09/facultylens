"""Semantic Scholar Graph API: author search and paper import.

`tldr` isn't accepted by the author-papers endpoint, so TL;DRs come from POST /paper/batch and
are best-effort: without an S2_API_KEY the shared pool often answers 429, and the import then
continues without them.
"""

import re
from typing import Any

from app.config import get_settings
from app.services.http import ExternalServiceError, make_client, request_json
from app.services.profile_items import clean_text, normalise_doi, to_year

BASE = "https://api.semanticscholar.org/graph/v1"
SOURCE = "Semantic Scholar"
PAPER_FIELDS = "title,year,venue,citationCount,externalIds,authors,publicationTypes,journal"
MAX_PAPERS = 500
_AUTHOR_URL = re.compile(r"semanticscholar\.org/author/(?:[^/]+/)?(\d+)")

TYPES = {
    "JournalArticle": "journal",
    "Conference": "conference",
    "Book": "book",
    "BookSection": "chapter",
    "Dataset": "other",
    "Review": "journal",
}


def parse_author_id(value: str) -> str:
    value = (value or "").strip()
    if value.isdigit():
        return value
    match = _AUTHOR_URL.search(value)
    if match:
        return match.group(1)
    raise ValueError("Paste a Semantic Scholar author ID (digits) or the author page link.")


def _headers() -> dict[str, str]:
    key = get_settings().s2_api_key.strip()
    return {"x-api-key": key} if key else {}


def map_candidate(author: dict[str, Any]) -> dict[str, Any]:
    papers = sorted(author.get("papers") or [], key=lambda p: p.get("year") or 0, reverse=True)
    return {
        "author_id": author.get("authorId"),
        "name": author.get("name"),
        "affiliations": [a for a in author.get("affiliations") or [] if a][:3],
        "paper_count": author.get("paperCount") or 0,
        "h_index": author.get("hIndex"),
        "sample_titles": [p.get("title") for p in papers[:3] if p.get("title")],
    }


def map_paper(paper: dict[str, Any]) -> dict[str, Any]:
    ext = paper.get("externalIds") or {}
    doi = normalise_doi(ext.get("DOI"))
    types = paper.get("publicationTypes") or []
    kind = next((TYPES[t] for t in types if t in TYPES), None)
    venue = clean_text(paper.get("venue") or (paper.get("journal") or {}).get("name"), 300)
    if kind is None:
        kind = "preprint" if venue and "arxiv" in venue.lower() else "other"
    paper_id = paper.get("paperId")
    return {
        "title": clean_text(paper.get("title"), 500),
        "venue": venue,
        "year": to_year(paper.get("year")),
        "type": kind,
        "doi": doi,
        "authors": [clean_text(a.get("name"), 120) for a in paper.get("authors") or []][:50],
        "citations": paper.get("citationCount"),
        "tldr": None,
        "url": f"https://doi.org/{doi}"
        if doi
        else (f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None),
        "s2_paper_id": paper_id,
    }


async def search_authors(query: str, limit: int = 8) -> list[dict[str, Any]]:
    async with make_client(**_headers()) as client:
        data = await request_json(
            client,
            "GET",
            f"{BASE}/author/search",
            source=SOURCE,
            params={
                "query": query,
                "limit": limit,
                "fields": "name,affiliations,paperCount,hIndex,papers.title,papers.year",
            },
        )
    return [map_candidate(a) for a in data.get("data", [])]


async def fetch_papers(author_id: str) -> list[dict[str, Any]]:
    """Up to MAX_PAPERS papers for one author, with TL;DRs where S2 lets us have them."""
    papers: list[dict[str, Any]] = []
    async with make_client(**_headers()) as client:
        offset = 0
        while offset < MAX_PAPERS:
            page = await request_json(
                client,
                "GET",
                f"{BASE}/author/{author_id}/papers",
                source=SOURCE,
                params={"fields": PAPER_FIELDS, "limit": 100, "offset": offset},
            )
            papers.extend(page.get("data", []))
            if page.get("next") is None:
                break
            offset = page["next"]

        tldrs: dict[str, str] = {}
        ids = [p["paperId"] for p in papers if p.get("paperId")]
        for i in range(0, len(ids), 100):
            try:
                batch = await request_json(
                    client,
                    "POST",
                    f"{BASE}/paper/batch",
                    source=SOURCE,
                    params={"fields": "tldr"},
                    json={"ids": ids[i : i + 100]},
                )
            except ExternalServiceError:
                break  # TL;DRs are optional
            for entry in batch or []:
                text = ((entry or {}).get("tldr") or {}).get("text")
                if entry and text:
                    tldrs[entry["paperId"]] = clean_text(text, 600)

    items = []
    for paper in papers:
        item = map_paper(paper)
        if item["title"]:
            item["tldr"] = tldrs.get(paper.get("paperId"))
            items.append(item)
    return items
