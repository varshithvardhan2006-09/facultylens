from app.schemas.users import normalise_roll_no
from tests.conftest import ROLL_NUMBERS


def test_roll_numbers_typed_with_spaces_become_the_college_format():
    assert normalise_roll_no(" 2451 24 751 999 ") == "2451-24-751-999"
    assert normalise_roll_no("2451 - 24 - 751 - 999") == "2451-24-751-999"
    assert normalise_roll_no("2451-24-751-999") == "2451-24-751-999"
    assert normalise_roll_no("ravi kumar") == "RAVI KUMAR"  # left alone, rejected later
    assert normalise_roll_no("   ") is None


async def test_create_user_returns_working_one_time_password(client, world):
    h = world["headers"]["admin"]
    r = await client.post(
        "/api/users",
        headers=h,
        json={
            "name": "Anita Rao",
            "role": "faculty",
            "email": "Anita@Test.edu",
            "department_id": str(world["cse"]),
            "gender": "female",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == "anita@test.edu"
    assert body["user"]["must_change_pw"] is True
    assert body["user"]["gender"] == "female"
    doc = await world["db"].users.find_one({"email": "anita@test.edu"})
    assert doc["password_hash"].startswith("$2b$") and body["temp_password"] not in str(doc)
    r = await client.post(
        "/api/auth/login",
        json={"username": "anita@test.edu", "password": body["temp_password"]},
    )
    assert r.status_code == 200 and r.json()["user"]["must_change_pw"] is True
    assert await world["db"].audit_log.count_documents({"action": "user.create"}) == 1


async def test_create_user_validation_and_duplicates(client, world):
    h = world["headers"]["admin"]
    student = {"name": "Ravi", "role": "student", "department_id": str(world["cse"])}
    r = await client.post("/api/users", headers=h, json=student)
    assert r.status_code == 422 and "roll number" in r.text
    r = await client.post("/api/users", headers=h, json={**student, "roll_no": "12345"})
    assert r.status_code == 422 and "ROLL_NO_REGEX" in r.text
    r = await client.post("/api/users", headers=h, json={**student, "roll_no": ROLL_NUMBERS[0]})
    assert r.status_code == 409 and "roll number" in r.json()["detail"]
    r = await client.post(
        "/api/users", headers=h, json={"name": "Dup", "role": "admin", "email": "fac@test.edu"}
    )
    assert r.status_code == 409
    r = await client.post(
        "/api/users",
        headers=h,
        json={**student, "roll_no": ROLL_NUMBERS[2], "gender": "male"},
    )
    assert r.status_code == 422 and "Gender" in r.text


async def test_students_without_email_do_not_clash(client, world):
    h = world["headers"]["admin"]
    for roll in ROLL_NUMBERS[1:3]:
        r = await client.post(
            "/api/users",
            headers=h,
            json={
                "name": "Student Without Email",
                "role": "student",
                "roll_no": roll,
                "department_id": str(world["cse"]),
            },
        )
        assert r.status_code == 201, r.text


async def test_gender_is_visible_to_admin_only(client, world):
    admin = (await client.get("/api/users?role=faculty", headers=world["headers"]["admin"])).json()
    assert admin["items"][0]["gender"] == "male"
    hod = (await client.get("/api/users", headers=world["headers"]["hod"])).json()
    assert all("gender" not in u for u in hod["items"])
    # A HoD only sees their own department, even when asking for another one.
    ece = str(world["ece"])
    hod = (
        await client.get(f"/api/users?department_id={ece}", headers=world["headers"]["hod"])
    ).json()
    assert {u["department_id"] for u in hod["items"]} == {str(world["cse"])}


async def test_search_and_pagination(client, world):
    h = world["headers"]["admin"]
    r = (await client.get("/api/users?q=fac@&page_size=1", headers=h)).json()
    assert r["total"] == 1 and r["items"][0]["email"] == "fac@test.edu"
    r = (await client.get("/api/users?q=.*", headers=h)).json()  # regex is escaped
    assert r["total"] == 0


async def test_bulk_json_creates_all_and_returns_credentials(client, world):
    h = world["headers"]["admin"]
    users = [
        {"name": "S One", "role": "student", "roll_no": ROLL_NUMBERS[1], "department_code": "cse"},
        {"name": "S Two", "role": "student", "roll_no": ROLL_NUMBERS[2], "department_code": "CSE"},
        {"name": "F One", "role": "faculty", "email": "f1@test.edu", "department_code": "ECE"},
    ]
    dry = await client.post("/api/users/bulk?dry_run=true", headers=h, json={"users": users})
    assert dry.status_code == 200 and dry.json() == {"dry_run": True, "valid_rows": 3}
    assert await world["db"].users.count_documents({}) == 5
    r = await client.post("/api/users/bulk", headers=h, json={"users": users})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 3 and len(body["credentials"]) == 3
    login = await client.post(
        "/api/auth/login",
        json={"username": ROLL_NUMBERS[2], "password": body["credentials"][1]["temp_password"]},
    )
    assert login.status_code == 200


async def test_bulk_with_any_bad_row_inserts_nothing(client, world):
    h = world["headers"]["admin"]
    users = [
        {"name": "Fine", "role": "student", "roll_no": ROLL_NUMBERS[1], "department_code": "CSE"},
        {"name": "Twin", "role": "student", "roll_no": ROLL_NUMBERS[1], "department_code": "CSE"},
        {"name": "Nowhere", "role": "faculty", "email": "n@test.edu", "department_code": "XYZ"},
        {"name": "Taken", "role": "faculty", "email": "fac@test.edu", "department_code": "CSE"},
        {"role": "student"},
        {"name": "Two Faults", "role": "student", "roll_no": "bad", "department_code": "XYZ"},
    ]
    r = await client.post("/api/users/bulk", headers=h, json={"users": users})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "bulk_invalid"
    rows = {e["row"]: " ".join(e["errors"]) for e in detail["errors"]}
    assert set(rows) == {2, 3, 4, 5, 6}
    assert "Same roll number as row 1" in rows[2]
    assert "No department with code XYZ" in rows[3]
    assert "already exists" in rows[4]
    assert "name:" in rows[5]
    assert "ROLL_NO_REGEX" in rows[6] and "No department with code XYZ" in rows[6]
    assert await world["db"].users.count_documents({}) == 5


async def test_bulk_csv_upload(client, world):
    csv_text = (
        "name,email,role,department_code,roll_no,gender\n"
        f"Meena,,student,CSE,{ROLL_NUMBERS[3]},\n"
        "Prakash,prakash@test.edu,faculty,CSE,,male\n"
    )
    r = await client.post(
        "/api/users/bulk",
        headers=world["headers"]["admin"],
        files={"file": ("users.csv", csv_text.encode(), "text/csv")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 2
    prakash = await world["db"].users.find_one({"email": "prakash@test.edu"})
    assert prakash["gender"] == "male" and prakash["must_change_pw"] is True

    bad = "name,role\nOnly Name,student\n"
    r = await client.post(
        "/api/users/bulk",
        headers=world["headers"]["admin"],
        files={"file": ("u.csv", bad.encode(), "text/csv")},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["errors"][0]["row"] == 2  # CSV line numbers (header is line 1)


async def test_update_deactivate_and_reset(client, world):
    h = world["headers"]["admin"]
    fac = str(world["faculty"]["_id"])
    r = await client.patch(f"/api/users/{fac}", headers=h, json={"role": "student"})
    assert r.status_code == 422  # a student needs a roll number
    r = await client.patch(f"/api/users/{fac}", headers=h, json={"role": "hod"})
    assert r.status_code == 200 and r.json()["role"] == "hod" and r.json()["gender"] == "male"
    me = str(world["admin"]["_id"])
    assert (await client.delete(f"/api/users/{me}", headers=h)).status_code == 400
    assert (
        await client.patch(f"/api/users/{me}", headers=h, json={"role": "hod"})
    ).status_code == 400

    r = await client.post(f"/api/users/{fac}/reset-password", headers=h)
    temp = r.json()["temp_password"]
    login = await client.post(
        "/api/auth/login", json={"username": "fac@test.edu", "password": temp}
    )
    assert login.status_code == 200 and login.json()["user"]["must_change_pw"] is True

    r = await client.delete(f"/api/users/{fac}", headers=h)
    assert r.status_code == 200 and r.json()["is_active"] is False
    login = await client.post(
        "/api/auth/login", json={"username": "fac@test.edu", "password": temp}
    )
    assert login.status_code == 401
    listed = (await client.get("/api/users", headers=h)).json()["items"]
    assert fac not in {u["id"] for u in listed}
    listed = (await client.get("/api/users?include_inactive=true", headers=h)).json()["items"]
    assert fac in {u["id"] for u in listed}


async def test_unknown_user_id_is_404(client, world):
    h = world["headers"]["admin"]
    assert (await client.patch("/api/users/nope", headers=h, json={})).status_code == 404
    missing = "0123456789abcdef01234567"
    assert (await client.delete(f"/api/users/{missing}", headers=h)).status_code == 404
