"""Profile generation: keywords, the template, claim checking, and the draft → approve workflow."""

import pytest

from app.nlp import profile_gen

PROFILE = {
    "designation": "Associate Professor",
    "interests": ["Compiler optimisation", "Program analysis"],
    "qualifications": [
        {
            "id": "q1",
            "degree": "PhD",
            "specialisation": "Computer Science",
            "institution": "IIT Madras",
            "year": 2014,
        },
        {"id": "q2", "degree": "M.Tech", "institution": "JNTU Hyderabad", "year": 2008},
    ],
    "experience": [
        {
            "id": "e1",
            "role": "Associate Professor",
            "institution": "Demo College",
            "from_year": 2019,
        },
    ],
    "publications": [
        {
            "id": "p1",
            "title": "Register allocation for loop nests",
            "venue": "CGO",
            "year": 2023,
            "tldr": "Faster register allocation for nested loops.",
        },
        {
            "id": "p2",
            "title": "Static analysis of loop nests in compilers",
            "venue": "PLDI",
            "year": 2021,
        },
    ],
    "achievements": [
        {"id": "a1", "kind": "award", "title": "Best Teacher Award", "year": 2022},
    ],
}
USER = {"name": "Dr. Kavitha Reddy"}
DEPT = {"name": "Computer Science and Engineering", "code": "CSE"}
HIGHLIGHTS = [
    {"text": "Students praise clarity.", "aspect": "clarity", "evidence_ids": ["x:liked:0"]}
]


@pytest.fixture
def facts():
    return profile_gen.build_facts(USER, DEPT, PROFILE, HIGHLIGHTS)


def test_few_publications_give_interests_only(facts):
    assert profile_gen.keywords(facts) == ["Compiler optimisation", "Program analysis"]


def test_keywords_skip_generic_words_and_stitched_phrases():
    titles = [
        "Register allocation for loop nests",
        "An empirical evaluation of register allocation methods",
        "Loop tiling for cache locality",
        "Programming languages for resource-constrained systems",
    ]
    facts = profile_gen.build_facts(
        USER,
        DEPT,
        {
            "interests": ["Compilers"],
            "publications": [{"id": f"p{i}", "title": t} for i, t in enumerate(titles)],
        },
        [],
    )
    words = profile_gen.keywords(facts)
    assert words[0] == "Compilers" and "register allocation" in words and len(words) <= 8
    banned = {"evaluation", "methods", "empirical", "systems"}
    assert not any(set(w.split()) & banned for w in words)
    assert "languages resource" not in words and not any(w.isdigit() for w in words)


def test_keywords_skip_teaching_words():
    titles = [
        "Teaching machine learning through hands-on laboratory work",
        "A comparative study of machine learning techniques",
        "A comparative study of data mining techniques",
        "An empirical evaluation of data mining methods",
    ]
    facts = profile_gen.build_facts(
        USER,
        DEPT,
        {
            "interests": ["Machine learning", "Data mining"],
            "publications": [{"id": f"p{i}", "title": t} for i, t in enumerate(titles)],
        },
        [],
    )
    words = profile_gen.keywords(facts)
    assert words[:2] == ["Machine learning", "Data mining"]
    assert not {"hands", "laboratory", "teaching"} & set(words)


def test_template_is_factual(facts):
    fields = profile_gen.template(facts, profile_gen.keywords(facts))
    assert fields["headline"] == "Associate Professor, Computer Science and Engineering"
    assert fields["bio_short"].startswith(
        "Dr. Kavitha Reddy is an Associate Professor in the Department of Computer Science"
    )
    assert "PhD in Computer Science from IIT Madras (2014)" in fields["bio_short"]
    assert "Best Teacher Award (2022)" in fields["key_achievements"]
    assert fields["teaching_highlights"] == [
        {"text": "Students praise clarity.", "evidence_ids": ["x:liked:0"]}
    ]
    assert "q1" in fields["sources"]["bio_short"]
    # every number in the template is a fact
    out = profile_gen._Profile.model_validate(fields)
    assert profile_gen.problems(out, facts) == []


def draft(**over):
    base = {
        "headline": "Associate Professor working on compilers",
        "bio_short": "Dr. Kavitha Reddy teaches and researches compiler optimisation and "
        "program analysis, with a PhD from IIT Madras.",
        "bio_long": "Dr. Kavitha Reddy is an Associate Professor whose work on register "
        "allocation appeared at CGO in 2023. Research covers program analysis.",
        "research_areas": ["Compiler optimisation", "Quantum gravity"],
        "key_achievements": ["Best Teacher Award (2022)"],
        "teaching_highlights": [
            {"text": "Clear explanations.", "evidence_ids": ["x:liked:0", "fake:id:9"]},
            {"text": "Invented.", "evidence_ids": ["fake:id:1"]},
        ],
        "sources": {"bio_long": ["p1", "made-up"]},
    }
    return profile_gen._Profile.model_validate({**base, **over})


def test_problems_catch_invented_numbers_venues_and_awards(facts):
    assert profile_gen.problems(draft(), facts) == []
    bad = draft(
        bio_long="Dr. Kavitha Reddy has 45 papers and won the Turing Award at NeurIPS Conference.",
        key_achievements=["Fellow of the Royal Society"],
    )
    found = " | ".join(profile_gen.problems(bad, facts))
    assert "45" in found and "Turing Award" in found and "Royal Society" in found


def test_lead_in_words_do_not_make_a_real_award_look_invented(facts):
    for sentence in (
        "Dr. Kavitha Reddy was Awarded the Best Teacher Award by the college.",
        "Dr. Kavitha Reddy studied at IIT Madras. Awarded the Best Teacher Award by the college.",
        "Dr. Kavitha Reddy received the Best Teacher Award in the college.",
    ):
        assert profile_gen.problems(draft(bio_long=sentence), facts) == []
    bad = draft(bio_long="Dr. Kavitha Reddy was Awarded the Turing Award by the college.")
    assert "Turing Award" in " | ".join(profile_gen.problems(bad, facts))


def test_problems_catch_invented_duties_and_reputation(facts):
    bad = draft(
        bio_long="Dr. Kavitha Reddy has been contributing to curriculum development and student "
        "mentorship, and is internationally renowned."
    )
    found = " | ".join(profile_gen.problems(bad, facts))
    assert "curriculum development" in found
    assert "mentorship" in found
    assert "internationally" in found and "renowned" in found


def test_duties_stated_in_the_facts_are_allowed(facts):
    supported = {
        **facts,
        "experience": [
            *facts["experience"],
            {"id": "e9", "role": "Mentoring coordinator", "institution": "MVSR"},
        ],
    }
    ok = draft(bio_long="Dr. Kavitha Reddy mentors students and coordinates the mentoring cell.")
    assert profile_gen.problems(ok, supported) == []
    assert profile_gen.problems(ok, facts) != []


def test_clean_drops_unsupported_areas_highlights_and_sources(facts):
    fields = profile_gen._clean(draft(), facts)
    assert fields["research_areas"] == ["Compiler optimisation"]
    assert fields["teaching_highlights"] == [
        {"text": "Clear explanations.", "evidence_ids": ["x:liked:0"]}
    ]
    assert fields["sources"] == {"bio_long": ["p1"]}


def test_generate_retries_once_then_uses_template(facts, monkeypatch):
    calls = []

    def fake(system, user, schema):
        calls.append(user)
        return draft(bio_long="Dr. Kavitha Reddy published 99 papers in total, a lot."), {
            "engine": "groq:m"
        }

    monkeypatch.setattr(profile_gen.llm, "complete_json", fake)
    fields, meta = profile_gen.generate(facts)
    assert len(calls) == 2 and "99" in calls[1]  # the retry lists the problem
    assert meta["engine"] == "template" and meta["rejected"]
    assert fields["headline"].startswith("Associate Professor")


def test_generate_accepts_a_clean_llm_draft(facts, monkeypatch):
    monkeypatch.setattr(
        profile_gen.llm, "complete_json", lambda s, u, schema: (draft(), {"engine": "groq:m"})
    )
    fields, meta = profile_gen.generate(facts)
    assert meta["engine"] == "groq:m" and fields["headline"].startswith("Associate Professor")


def test_generate_without_llm_is_the_template(facts):
    fields, meta = profile_gen.generate(facts)  # no GROQ_API_KEY in tests
    assert meta["engine"] == "template" and "rejected" not in meta


# --------------------------------------------------------------------------- API workflow


async def test_draft_edit_approve_workflow(client, world):
    db, h, fac = world["db"], world["headers"], world["faculty"]
    await db.faculty_profiles.insert_one({"user_id": fac["_id"], **PROFILE})
    base = f"/api/faculty/{fac['_id']}"

    empty = (await client.get(f"{base}/profile", headers=h["hod_ece"])).json()
    assert empty["status"] == "none" and empty["fields"] is None

    r = await client.post(f"{base}/profile/generate", headers=h["faculty"])
    assert r.status_code == 201, r.text
    v1 = r.json()
    assert v1["version"] == 1 and v1["status"] == "draft" and v1["engine"] == "template"
    assert (await client.post(f"{base}/profile/generate", headers=h["admin"])).json()[
        "version"
    ] == 2

    edited = {**v1["fields"], "headline": "Compiler researcher and teacher"}
    r = await client.put(f"{base}/profile/versions/1", headers=h["faculty"], json=edited)
    assert r.status_code == 200 and r.json()["edited"] is True

    # Only the owner approves; the HoD can read but not write.
    assert (
        await client.post(f"{base}/profile/versions/1/approve", headers=h["admin"])
    ).status_code == 403
    assert (
        await client.put(f"{base}/profile/versions/1", headers=h["hod"], json=edited)
    ).status_code == 403
    assert (await client.get(f"{base}/profile/versions", headers=h["hod"])).status_code == 200
    assert (await client.get(f"{base}/profile/versions", headers=h["hod_ece"])).status_code == 403

    assert (await client.post(f"{base}/profile/versions/1/approve", headers=h["faculty"])).json()[
        "status"
    ] == "approved"
    r = await client.post(f"{base}/profile/versions/2/approve", headers=h["faculty"])
    assert r.json()["status"] == "approved"
    versions = {
        v["version"]: v["status"]
        for v in (await client.get(f"{base}/profile/versions", headers=h["faculty"])).json()
    }
    assert versions == {1: "superseded", 2: "approved"}
    assert (
        await client.put(f"{base}/profile/versions/2", headers=h["faculty"], json=edited)
    ).status_code == 409

    public = (await client.get(f"{base}/profile", headers=h["hod_ece"])).json()
    assert public["status"] == "approved" and public["version"] == 2
    assert public["publications"][0]["title"] == "Register allocation for loop nests"
    assert all("evidence_ids" not in t for t in public["fields"]["teaching_highlights"])
    assert (await client.get(f"{base}/profile", headers=h["student"])).status_code == 403
    assert await db.audit_log.count_documents({"action": "profile.approve"}) == 2
