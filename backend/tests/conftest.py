import os

import pytest

# Tests use their own database so they never touch demo data, and cheap bcrypt rounds.
os.environ["MONGODB_DB"] = "facultylens_test"
# Tests drop their database, so they never follow a cloud address in .env.
os.environ["MONGODB_URI"] = os.environ.get("TEST_MONGODB_URI", "mongodb://127.0.0.1:27017")
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ["JWT_SECRET"] = "test-only-jwt-secret-long-enough-to-sign-with"
os.environ["STUDENT_HASH_SALT"] = "test-only-student-hash-salt-long-enough"
os.environ["ANALYSIS_ON_SUBMIT"] = "false"  # no background model runs during tests
# Never call a live API or spend a real quota from tests, whatever keys .env holds; tests that
# need an LLM answer mock llm.complete_json.
os.environ["GROQ_API_KEY"] = ""
os.environ["S2_API_KEY"] = ""

from httpx import ASGITransport, AsyncClient

from app import db
from app.auth.security import hash_password
from app.config import get_settings
from app.limiter import limiter
from app.main import create_app
from app.routers.auth import reset_login_failures
from app.utils import now

PASSWORD = "correct-horse-battery"
ROLL_NUMBERS = ["2451-24-733-001", "2451-24-733-002", "2451-24-733-003", "2451-24-733-004"]


@pytest.fixture(autouse=True)
def _fresh_settings():
    get_settings.cache_clear()
    reset_login_failures()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def mongo():
    """Live local MongoDB test database, emptied before and after; skipped if not running."""
    await db.close_client()
    if not await db.ping():
        message = "MongoDB not reachable on MONGODB_URI"
        # On a laptop a skip is friendly; in CI it would hide most of the suite.
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)
    database = db.get_db()
    await db.get_client().drop_database(database.name)
    await db.ensure_indexes(database)
    yield database
    await db.get_client().drop_database(database.name)
    await db.close_client()


@pytest.fixture
async def client(mongo):
    """HTTP client on the same event loop as the database client."""
    limiter.reset()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def make_user(database, role, name=None, department_id=None, must_change_pw=False, **extra):
    doc = {
        "name": name or f"Test {role.title()}",
        "role": role,
        "password_hash": hash_password(PASSWORD),
        "must_change_pw": must_change_pw,
        "is_active": True,
        "created_at": now(),
        **extra,
    }
    if department_id:
        doc["department_id"] = department_id
    result = await database.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def login(client, username, password=PASSWORD):
    r = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def world(mongo, client):
    """Two departments, one user per role, and one CSE offering with a teacher and a student."""
    cse = await mongo.departments.insert_one({"name": "Computer Science", "code": "CSE"})
    cse = cse.inserted_id
    ece = (await mongo.departments.insert_one({"name": "Electronics", "code": "ECE"})).inserted_id
    admin = await make_user(mongo, "admin", email="admin@test.edu")
    hod = await make_user(mongo, "hod", department_id=cse, email="hod@test.edu", gender="female")
    hod_ece = await make_user(mongo, "hod", department_id=ece, email="hod.ece@test.edu")
    faculty = await make_user(
        mongo, "faculty", department_id=cse, email="fac@test.edu", gender="male"
    )
    student = await make_user(mongo, "student", department_id=cse, roll_no=ROLL_NUMBERS[0])
    course = await mongo.courses.insert_one(
        {
            "code": "CS501",
            "name": "Compiler Design",
            "department_id": cse,
            "academic_year": "2026-27",
            "semester": 5,
            "section": "A",
            "faculty_ids": [faculty["_id"]],
            "student_ids": [student["_id"]],
            "created_at": now(),
        }
    )
    headers = {
        "admin": await login(client, "admin@test.edu"),
        "hod": await login(client, "hod@test.edu"),
        "hod_ece": await login(client, "hod.ece@test.edu"),
        "faculty": await login(client, "fac@test.edu"),
        "student": await login(client, ROLL_NUMBERS[0]),
        "anon": {},
    }
    limiter.reset()  # the logins above count against the per-IP login limit
    return {
        "db": mongo,
        "cse": cse,
        "ece": ece,
        "admin": admin,
        "hod": hod,
        "hod_ece": hod_ece,
        "faculty": faculty,
        "student": student,
        "course_id": course.inserted_id,
        "headers": headers,
    }
