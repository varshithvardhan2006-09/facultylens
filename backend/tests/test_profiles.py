import json
from pathlib import Path

import pytest

from app.services import orcid as orcid_service
from app.services import semantic_scholar as s2_service
from app.services.http import ExternalServiceError

FIXTURES = Path(__file__).parent / "fixtures"
CARBERRY = "0000-0002-1825-0097"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def carberry_items():
    return {
        "publication": orcid_service.map_works(
            load("orcid_carberry_works.json"), load("orcid_carberry_works_bulk.json")
        ),
        "experience": orcid_service.map_employments(load("orcid_carberry_employments.json")),
        "qualification": orcid_service.map_educations(load("orcid_bengio_educations.json")),
        "interest": [
            {"tag": t} for t in orcid_service.map_keywords(load("orcid_carberry_keywords.json"))
        ],
    }


@pytest.fixture
def stub_sources(monkeypatch):
    """No network in unit tests: ORCID returns the saved Carberry record, S2 two papers."""

    async def fake_orcid(orcid):
        if orcid != CARBERRY:
            raise ExternalServiceError("ORCID has no record for that ID.", status=404)
        return carberry_items()

    s2_papers = [
        # same DOI as a Carberry work: should enrich, not duplicate
        {
            "title": "A Methodology for the Emulation of Architecture",
            "venue": "Journal of Psychoceramics",
            "year": 2012,
            "type": "journal",
            "doi": "10.5555/12345680",
            "authors": ["Josiah Carberry"],
            "citations": 7,
            "tldr": "Emulating architecture, methodically.",
            "url": None,
            "s2_paper_id": "abc",
        },
        {
            "title": "A brand new paper",
            "venue": "arXiv",
            "year": 2025,
            "type": "preprint",
            "doi": None,
            "authors": [],
            "citations": 0,
            "tldr": None,
            "url": None,
            "s2_paper_id": "def",
        },
    ]

    async def fake_papers(author_id):
        return s2_papers

    async def fake_search(q):
        return [
            {
                "author_id": "42",
                "name": "J. Carberry",
                "affiliations": [],
                "paper_count": 2,
                "h_index": 1,
                "sample_titles": ["A brand new paper"],
            }
        ]

    monkeypatch.setattr(orcid_service, "fetch_orcid", fake_orcid)
    monkeypatch.setattr(s2_service, "fetch_papers", fake_papers)
    monkeypatch.setattr(s2_service, "search_authors", fake_search)


def url(world, who="faculty", path="profile-data"):
    return f"/api/faculty/{world[who]['_id']}/{path}"


async def test_empty_profile_has_defaults_and_courses(client, world):
    r = await client.get(url(world), headers=world["headers"]["faculty"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["publications"] == [] and body["pending_imports"] == []
    assert body["user"]["department_code"] == "CSE"
    assert [c["code"] for c in body["courses_taught"]] == ["CS501"]
    assert body["can_edit"] is True
    hod_view = (await client.get(url(world), headers=world["headers"]["hod"])).json()
    assert hod_view["can_edit"] is False


async def test_put_assigns_ids_and_validates(client, world):
    h = world["headers"]["faculty"]
    body = {
        "designation": "Assistant Professor",
        "photo_url": "https://example.org/me.jpg",
        "interests": ["NLP", "nlp", "  Machine   learning "],
        "qualifications": [{"degree": "M.Tech", "institution": "JNTU Hyderabad", "year": 2015}],
        "experience": [
            {"role": "Assistant Professor", "institution": "Demo College", "from_year": 2016}
        ],
        "publications": [{"title": "Sentiment in feedback", "year": 2024, "type": "journal"}],
        "achievements": [{"kind": "fdp", "title": "FDP on Deep Learning", "year": 2023}],
    }
    r = await client.put(url(world), headers=h, json=body)
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["interests"] == ["NLP", "Machine learning"]
    ids = [
        saved[s][0]["id"] for s in ("qualifications", "experience", "publications", "achievements")
    ]
    assert all(ids) and len(set(ids)) == 4
    # ids survive a round trip
    again = await client.put(
        url(world), headers=h, json=saved | {"designation": "Associate Professor"}
    )
    assert again.json()["publications"][0]["id"] == saved["publications"][0]["id"]

    bad = await client.put(url(world), headers=h, json={"photo_url": "http://insecure/x.png"})
    assert bad.status_code == 422
    bad = await client.put(
        url(world),
        headers=h,
        json={
            "experience": [{"role": "X", "institution": "Y", "from_year": 2020, "to_year": 2010}]
        },
    )
    assert bad.status_code == 422 and "before the start" in bad.text


async def test_orcid_import_review_and_reimport(client, world, stub_sources):
    h = world["headers"]["faculty"]
    r = await client.post(
        url(world, path="import/orcid"), headers=h, json={"orcid": f"https://orcid.org/{CARBERRY}"}
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["added"] == {"publication": 6, "experience": 2, "qualification": 2, "interest": 2}
    profile = result["profile"]
    assert profile["orcid"] == CARBERRY and profile["import_log"]["orcid"]["added"] == 12
    pending = profile["pending_imports"]
    assert len(pending) == 12 and profile["publications"] == []

    pubs = [p for p in pending if p["kind"] == "publication"]
    interest = next(p for p in pending if p["kind"] == "interest")
    job = next(p for p in pending if p["kind"] == "experience")
    # accept one paper with an edit, reject another, accept an interest
    r = await client.post(
        url(world, path=f"imports/{pubs[0]['id']}/accept"),
        headers=h,
        json={"data": {"venue": "J. Psychoceramics"}},
    )
    assert r.status_code == 200
    accepted = r.json()["publications"][0]
    assert accepted["venue"] == "J. Psychoceramics" and accepted["source"] == "orcid"
    assert accepted["id"] == pubs[0]["id"]
    assert (
        await client.post(url(world, path=f"imports/{pubs[1]['id']}/reject"), headers=h)
    ).status_code == 200
    r = await client.post(
        url(world, path="imports/bulk"),
        headers=h,
        json={"accept": [interest["id"], job["id"]], "reject": []},
    )
    after = r.json()
    assert after["interests"] == [interest["data"]["tag"]]
    assert after["experience"][0]["institution"] == "Wesleyan University"
    assert len(after["pending_imports"]) == 8

    # Re-import: nothing already accepted, pending or rejected comes back.
    again = (
        await client.post(url(world, path="import/orcid"), headers=h, json={"orcid": CARBERRY})
    ).json()
    assert again["added"] == {} and again["skipped"] == 12
    assert len(again["profile"]["pending_imports"]) == 8

    gone = await client.post(url(world, path=f"imports/{pubs[1]['id']}/accept"), headers=h)
    assert gone.status_code == 404


async def test_s2_import_enriches_pending_orcid_paper(client, world, stub_sources):
    h = world["headers"]["faculty"]
    await client.post(url(world, path="import/orcid"), headers=h, json={"orcid": CARBERRY})
    r = await client.post(
        url(world, path="import/semantic-scholar"),
        headers=h,
        json={"author": "https://www.semanticscholar.org/author/Josiah-Carberry/42"},
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["added"] == {"publication": 1} and result["enriched"] == 1
    twin = next(
        p
        for p in result["profile"]["pending_imports"]
        if p["data"].get("doi") == "10.5555/12345680"
    )
    assert twin["source"] == "orcid" and twin["data"]["citations"] == 7
    assert twin["data"]["tldr"] == "Emulating architecture, methodically."
    assert result["profile"]["s2_author_id"] == "42"

    s = await client.get(url(world, path="semantic-scholar/search") + "?q=Carberry", headers=h)
    assert s.status_code == 200 and s.json()[0]["author_id"] == "42"


async def test_import_errors_are_plain(client, world, stub_sources):
    h = world["headers"]["faculty"]
    r = await client.post(
        url(world, path="import/orcid"), headers=h, json={"orcid": "0000-0002-1825-0098"}
    )
    assert r.status_code == 422 and "typo" in r.json()["detail"]
    r = await client.post(
        url(world, path="import/orcid"), headers=h, json={"orcid": "0000-0002-9322-3515"}
    )
    assert r.status_code == 404 and "No public ORCID record" in r.json()["detail"]
    r = await client.post(
        url(world, path="import/semantic-scholar"), headers=h, json={"author": "Josiah"}
    )
    assert r.status_code == 422


async def test_upstream_rate_limit_passes_through(client, world, monkeypatch):
    async def limited(orcid):
        raise ExternalServiceError("ORCID is limiting requests right now.", status=429)

    monkeypatch.setattr(orcid_service, "fetch_orcid", limited)
    r = await client.post(
        url(world, path="import/orcid"),
        headers=world["headers"]["faculty"],
        json={"orcid": CARBERRY},
    )
    assert r.status_code == 429 and "limiting" in r.json()["detail"]


async def test_access_rules(client, world):
    h = world["headers"]
    # HoD of another department, faculty looking at someone else, a student id, students.
    assert (await client.get(url(world), headers=h["hod_ece"])).status_code == 403
    assert (await client.get(url(world, who="hod"), headers=h["faculty"])).status_code == 403
    assert (await client.get(url(world, who="student"), headers=h["admin"])).status_code == 404
    assert (await client.put(url(world), headers=h["hod"], json={})).status_code == 403
    assert (await client.get(url(world), headers=h["student"])).status_code == 403
    # admin can edit anyone's profile
    assert (
        await client.put(url(world), headers=h["admin"], json={"designation": "Prof"})
    ).status_code == 200
    assert await world["db"].audit_log.count_documents({"action": "profile.update"}) == 1
