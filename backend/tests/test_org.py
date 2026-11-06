from tests.conftest import ROLL_NUMBERS, make_user


async def test_departments_create_list_and_duplicate(client, world):
    h = world["headers"]["admin"]
    r = await client.post("/api/departments", headers=h, json={"name": "Civil", "code": "civ"})
    assert r.status_code == 201 and r.json()["code"] == "CIV"
    r = await client.post("/api/departments", headers=h, json={"name": "Again", "code": "CSE"})
    assert r.status_code == 409
    r = await client.post("/api/departments", headers=h, json={"name": "Bad", "code": "C S"})
    assert r.status_code == 422
    codes = [d["code"] for d in (await client.get("/api/departments", headers=h)).json()]
    assert codes == ["CIV", "CSE", "ECE"]


OFFERING = {
    "code": "cs502",
    "name": "Computer Networks",
    "academic_year": "2026-27",
    "semester": 5,
    "section": "b",
}


async def test_course_offering_unique_per_section(client, world):
    h = world["headers"]["admin"]
    body = {**OFFERING, "department_id": str(world["cse"])}
    r = await client.post("/api/courses", headers=h, json=body)
    assert r.status_code == 201, r.text
    assert (r.json()["code"], r.json()["section"]) == ("CS502", "B")
    assert (await client.post("/api/courses", headers=h, json=body)).status_code == 409
    r = await client.post("/api/courses", headers=h, json={**body, "section": "C"})
    assert r.status_code == 201
    r = await client.post("/api/courses", headers=h, json={**body, "academic_year": "2026-28"})
    assert r.status_code == 422


async def test_course_visibility_by_role(client, world):
    h = world["headers"]
    other = await client.post(
        "/api/courses", headers=h["admin"], json={**OFFERING, "department_id": str(world["ece"])}
    )
    other_id = other.json()["id"]
    cid = str(world["course_id"])

    def ids(resp):
        return {c["id"] for c in resp.json()}

    assert ids(await client.get("/api/courses", headers=h["admin"])) == {cid, other_id}
    assert ids(await client.get("/api/courses", headers=h["hod"])) == {cid}
    assert ids(await client.get("/api/courses", headers=h["hod_ece"])) == {other_id}
    assert ids(await client.get("/api/courses", headers=h["faculty"])) == {cid}
    assert ids(await client.get("/api/courses", headers=h["student"])) == {cid}

    # Student lists only for admin and the department's HoD.
    admin_detail = (await client.get(f"/api/courses/{cid}", headers=h["admin"])).json()
    assert admin_detail["students"][0]["roll_no"] == ROLL_NUMBERS[0]
    assert (await client.get(f"/api/courses/{cid}", headers=h["hod"])).json()["students"]
    fac_detail = (await client.get(f"/api/courses/{cid}", headers=h["faculty"])).json()
    assert fac_detail["students"] is None and fac_detail["student_count"] == 1
    assert fac_detail["faculty"][0]["name"] == "Test Faculty"
    assert (await client.get(f"/api/courses/{other_id}", headers=h["student"])).status_code == 404


async def test_enrol_add_remove_and_unknown(client, world):
    h = world["headers"]["admin"]
    db = world["db"]
    second = await make_user(db, "student", department_id=world["cse"], roll_no=ROLL_NUMBERS[1])
    cid = str(world["course_id"])
    r = await client.post(
        f"/api/courses/{cid}/enrol",
        headers=h,
        json={"add_roll_numbers": [ROLL_NUMBERS[1].lower(), "2451-24-733-099", ROLL_NUMBERS[1]]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["unknown_roll_numbers"] == ["2451-24-733-099"]
    assert body["course"]["student_count"] == 2
    r = await client.post(
        f"/api/courses/{cid}/enrol", headers=h, json={"remove_roll_numbers": [ROLL_NUMBERS[0]]}
    )
    assert [s["id"] for s in r.json()["course"]["students"]] == [str(second["_id"])]

    # Assign teachers: only active faculty or HoDs.
    r = await client.post(
        f"/api/courses/{cid}/enrol",
        headers=h,
        json={"faculty_ids": [str(world["hod"]["_id"]), str(world["faculty"]["_id"])]},
    )
    assert len(r.json()["course"]["faculty"]) == 2
    r = await client.post(
        f"/api/courses/{cid}/enrol", headers=h, json={"faculty_ids": [str(second["_id"])]}
    )
    assert r.status_code == 422
    assert await db.audit_log.count_documents({"action": "course.enrol"}) == 3


async def test_health_index_migration_drops_old_indexes(mongo):
    from app import db

    await mongo.users.drop_index("email_unique_partial")
    await mongo.users.create_index("email", unique=True, name="email_unique")
    await db.ensure_indexes(mongo)
    names = set(await mongo.users.index_information())
    assert "email_unique" not in names and "email_unique_partial" in names
