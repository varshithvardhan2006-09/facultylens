"""ORCID / Semantic Scholar mapping on saved real responses, plus retry and failure handling.

Fixtures in tests/fixtures are real public API responses (ORCID's test record for Josiah Carberry,
Yoshua Bengio's ORCID educations, and Semantic Scholar search/papers), saved on 2026-10-20.
"""

import json
from pathlib import Path

import httpx
import pytest

from app.services import http as http_service
from app.services import orcid, semantic_scholar
from app.services.http import ExternalServiceError, request_json
from app.services.profile_items import existing_keys, item_key, normalise_doi

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(http_service.asyncio, "sleep", instant)


# ---------------------------------------------------------------- ORCID iD parsing


@pytest.mark.parametrize(
    "raw",
    [
        "0000-0002-1825-0097",
        "0000000218250097",
        "https://orcid.org/0000-0002-1825-0097",
        " orcid.org/0000-0002-1825-0097 ",
    ],
)
def test_parse_orcid_accepts_common_forms(raw):
    assert orcid.parse_orcid(raw) == "0000-0002-1825-0097"


def test_parse_orcid_checksum_and_x():
    assert orcid.parse_orcid("0000-0002-9322-3515") == "0000-0002-9322-3515"
    assert orcid.parse_orcid("0000-0002-1694-233x") == "0000-0002-1694-233X"
    with pytest.raises(ValueError, match="typo"):
        orcid.parse_orcid("0000-0002-1825-0098")
    with pytest.raises(ValueError, match="isn't an ORCID"):
        orcid.parse_orcid("hello")


# ---------------------------------------------------------------- ORCID mapping


def test_map_carberry_works_with_details():
    items = orcid.map_works(
        load("orcid_carberry_works.json"), load("orcid_carberry_works_bulk.json")
    )
    assert len(items) == 6
    first = next(i for i in items if i["doi"] == "10.5555/12345680")
    assert first["title"] == "A Methodology for the Emulation of Architecture"
    assert first["year"] == 2012
    assert first["type"] == "journal"
    assert first["url"]
    assert all(i["title"] and isinstance(i["authors"], list) for i in items)


def test_map_works_without_bulk_still_imports():
    items = orcid.map_works(load("orcid_carberry_works.json"))
    assert len(items) == 6 and all(i["authors"] == [] for i in items)


def test_map_employments_educations_keywords():
    jobs = orcid.map_employments(load("orcid_carberry_employments.json"))
    assert jobs[0]["role"] == "Professor"
    assert jobs[0]["institution"] == "Wesleyan University"
    assert jobs[0]["department"] == "Psychoceramics"
    assert jobs[0]["from_year"] == 1930 and jobs[0]["to_year"] is None
    assert orcid.map_educations(load("orcid_carberry_educations.json")) == []
    degrees = orcid.map_educations(load("orcid_bengio_educations.json"))
    assert {(d["degree"], d["institution"], d["year"]) for d in degrees} == {
        ("PhD", "McGill University", 1991),
        ("MSc", "McGill University", 1988),
    }
    assert orcid.map_keywords(load("orcid_carberry_keywords.json")) == [
        "psychoceramics",
        "ionian philology",
    ]


def test_map_keywords_splits_and_dedupes():
    payload = {"keyword": [{"content": "NLP; Machine Learning"}, {"content": "nlp"}]}
    assert orcid.map_keywords(payload) == ["NLP", "Machine Learning"]


# ---------------------------------------------------------------- Semantic Scholar mapping


def test_s2_candidates_and_papers():
    candidates = [semantic_scholar.map_candidate(a) for a in load("s2_author_search.json")["data"]]
    assert candidates[0]["author_id"] and candidates[0]["paper_count"] >= 1
    assert len(candidates[0]["sample_titles"]) <= 3
    papers = [semantic_scholar.map_paper(p) for p in load("s2_author_papers.json")["data"]]
    first = papers[0]
    assert first["doi"] == "10.1353/jod.2023.a907692"
    assert first["type"] == "journal" and first["citations"] == 34
    assert first["url"] == "https://doi.org/10.1353/jod.2023.a907692"


def test_parse_author_id():
    assert semantic_scholar.parse_author_id("1751762") == "1751762"
    assert (
        semantic_scholar.parse_author_id(
            "https://www.semanticscholar.org/author/Yoshua-Bengio/1751762"
        )
        == "1751762"
    )
    with pytest.raises(ValueError):
        semantic_scholar.parse_author_id("Yoshua Bengio")


# ---------------------------------------------------------------- keys and dedup


def test_item_keys():
    a = {"doi": "https://doi.org/10.1/ABC", "title": "X"}
    b = {"doi": "10.1/abc", "title": "Different title"}
    assert item_key("publication", a) == item_key("publication", b)
    no_doi = {"title": "Deep  Learning!", "year": 2015}
    assert item_key("publication", no_doi) == item_key(
        "publication", {"title": "deep learning", "year": 2015}
    )
    assert item_key("interest", {"tag": "NLP"}) == item_key("interest", {"tag": "nlp "})
    assert normalise_doi("doi: 10.5/X") == "10.5/x"


def test_existing_keys_cover_accepted_pending_rejected():
    profile = {
        "publications": [{"title": "A", "year": 2020, "doi": None}],
        "interests": ["NLP"],
        "pending_imports": [{"key": "pub:doi:10.1/x"}],
        "rejected_keys": ["exp:professor:wesleyan university"],
    }
    keys = existing_keys(profile)
    assert {"pub:title:a:2020", "int:nlp", "pub:doi:10.1/x"} <= keys
    assert "exp:professor:wesleyan university" in keys


# ---------------------------------------------------------------- HTTP behaviour


def client_for(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_retries_on_429_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "1"})
        return httpx.Response(200, json={"ok": True})

    async with client_for(handler) as client:
        assert await request_json(client, "GET", "https://x.test/a", source="S") == {"ok": True}
    assert calls["n"] == 2


async def test_persistent_429_and_404_and_timeout():
    async with client_for(lambda r: httpx.Response(429)) as client:
        with pytest.raises(ExternalServiceError) as err:
            await request_json(client, "GET", "https://x.test/a", source="S")
        assert err.value.status == 429 and "Wait a minute" in err.value.message

    async with client_for(lambda r: httpx.Response(404)) as client:
        with pytest.raises(ExternalServiceError) as err:
            await request_json(client, "GET", "https://x.test/a", source="ORCID")
        assert err.value.status == 404

    def boom(request):
        raise httpx.ConnectTimeout("slow", request=request)

    async with client_for(boom) as client:
        with pytest.raises(ExternalServiceError) as err:
            await request_json(client, "GET", "https://x.test/a", source="ORCID")
        assert err.value.status == 502 and "didn't answer" in err.value.message


async def test_fetch_orcid_end_to_end_with_mock(monkeypatch):
    routes = {
        "/works": load("orcid_carberry_works.json"),
        "/employments": load("orcid_carberry_employments.json"),
        "/educations": load("orcid_carberry_educations.json"),
        "/keywords": load("orcid_carberry_keywords.json"),
    }

    def handler(request):
        path = request.url.path
        if "/works/" in path:
            return httpx.Response(200, json=load("orcid_carberry_works_bulk.json"))
        for suffix, body in routes.items():
            if path.endswith(suffix):
                return httpx.Response(200, json=body)
        return httpx.Response(404)

    monkeypatch.setattr(
        orcid, "make_client", lambda **h: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    result = await orcid.fetch_orcid("0000-0002-1825-0097")
    assert len(result["publication"]) == 6
    assert result["experience"][0]["institution"] == "Wesleyan University"
    assert [i["tag"] for i in result["interest"]] == ["psychoceramics", "ionian philology"]


async def test_fetch_s2_papers_survives_tldr_429(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/paper/batch"):
            return httpx.Response(429)
        return httpx.Response(200, json=load("s2_author_papers.json") | {"next": None})

    monkeypatch.setattr(
        semantic_scholar,
        "make_client",
        lambda **h: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    papers = await semantic_scholar.fetch_papers("1751762")
    assert len(papers) == 3 and all(p["tldr"] is None for p in papers)


@pytest.mark.network
async def test_real_orcid_imports():
    """The SPEC 'done when' proof: real public ORCID records import (needs internet)."""
    carberry = await orcid.fetch_orcid("0000-0002-1825-0097")
    assert len(carberry["publication"]) >= 6
    assert carberry["experience"][0]["institution"] == "Wesleyan University"
    bengio = await orcid.fetch_orcid("0000-0002-9322-3515")
    assert len(bengio["publication"]) >= 10  # 20 work groups on 2026-10-20
    assert any(q["institution"] == "McGill University" for q in bengio["qualification"])
    assert all(p["title"] for p in bengio["publication"])
