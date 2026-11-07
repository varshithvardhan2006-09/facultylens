"""MongoDB access through the PyMongo Async API, plus every index from SPEC §9."""

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient, IndexModel
from pymongo.asynchronous.database import AsyncDatabase

from app.config import get_settings

_client: AsyncMongoClient | None = None
_sync_client = None

# collection -> indexes (SPEC §9)
INDEXES: dict[str, list[IndexModel]] = {
    "users": [
        # Students may have no email, so uniqueness applies only where an email exists.
        IndexModel(
            [("email", ASCENDING)],
            unique=True,
            partialFilterExpression={"email": {"$type": "string"}},
            name="email_unique_partial",
        ),
        IndexModel([("roll_no", ASCENDING)], unique=True, sparse=True, name="roll_no_unique"),
        IndexModel([("role", ASCENDING), ("department_id", ASCENDING)], name="role_department"),
    ],
    "departments": [IndexModel([("code", ASCENDING)], unique=True, name="code_unique")],
    # A course offering: one code taught in one section of one semester of one academic year.
    "courses": [
        IndexModel(
            [
                ("code", ASCENDING),
                ("academic_year", ASCENDING),
                ("semester", ASCENDING),
                ("section", ASCENDING),
            ],
            unique=True,
            name="offering_unique",
        ),
        IndexModel([("faculty_ids", ASCENDING)], name="faculty_ids"),
        IndexModel([("student_ids", ASCENDING)], name="student_ids"),
    ],
    "refresh_tokens": [
        IndexModel([("jti_hash", ASCENDING)], unique=True, name="jti_hash_unique"),
        IndexModel([("user_id", ASCENDING)], name="user_id"),
        IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="expires_ttl"),
    ],
    "faculty_profiles": [IndexModel([("user_id", ASCENDING)], unique=True, name="user_id_unique")],
    "profile_versions": [
        IndexModel(
            [("user_id", ASCENDING), ("version", ASCENDING)], unique=True, name="user_version"
        )
    ],
    # One teaching form per offering x teacher and one curriculum form per offering, per cycle.
    "forms": [
        IndexModel(
            [
                ("cycle_id", ASCENDING),
                ("course_id", ASCENDING),
                ("faculty_id", ASCENDING),
                ("type", ASCENDING),
            ],
            unique=True,
            name="form_unique",
        ),
        IndexModel([("faculty_id", ASCENDING), ("cycle_id", ASCENDING)], name="faculty_cycle"),
    ],
    "feedback_cycles": [IndexModel([("status", ASCENDING)], name="status")],
    "responses": [
        IndexModel(
            [("form_id", ASCENDING), ("student_hash", ASCENDING)],
            unique=True,
            name="one_response_per_student",
        )
    ],
    "analyses": [
        IndexModel(
            [("response_id", ASCENDING), ("model_version", ASCENDING)],
            unique=True,
            name="response_model_version",
        )
    ],
    "aggregates": [
        IndexModel(
            [("faculty_id", ASCENDING), ("course_id", ASCENDING), ("cycle_id", ASCENDING)],
            unique=True,
            name="faculty_course_cycle",
        ),
        IndexModel([("form_id", ASCENDING), ("model_version", ASCENDING)], name="form_version"),
    ],
    "moderation_queue": [
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="status_created"),
        IndexModel(
            [("analysis_id", ASCENDING), ("field", ASCENDING)], unique=True, name="analysis_field"
        ),
    ],
    "summaries": [
        IndexModel([("form_id", ASCENDING)], unique=True, name="form_unique"),
        IndexModel([("faculty_id", ASCENDING), ("cycle_id", ASCENDING)], name="faculty_cycle"),
    ],
    "analysis_jobs": [IndexModel([("created_at", DESCENDING)], name="created_desc")],
    "action_taken": [
        IndexModel([("cycle_id", ASCENDING)], name="cycle_id"),
        IndexModel(
            [
                ("cycle_id", ASCENDING),
                ("department_id", ASCENDING),
                ("kind", ASCENDING),
                ("key", ASCENDING),
            ],
            unique=True,
            name="cycle_department_issue",
        ),
    ],
    # Phase 8 evaluation: items to label (public dataset or the app's own redacted comments),
    # one label per item per annotator, adjudicated gold, summary groups and the faculty survey.
    "eval_items": [
        IndexModel([("set", ASCENDING), ("order", ASCENDING)], name="set_order"),
        IndexModel([("source", ASCENDING), ("ref", ASCENDING)], unique=True, name="source_ref"),
    ],
    "labels": [
        IndexModel(
            [("item_id", ASCENDING), ("annotator_id", ASCENDING)],
            unique=True,
            name="item_annotator",
        ),
        IndexModel([("annotator_id", ASCENDING)], name="annotator"),
    ],
    "adjudications": [IndexModel([("item_id", ASCENDING)], unique=True, name="item_unique")],
    "eval_groups": [IndexModel([("order", ASCENDING)], name="order")],
    "survey_responses": [
        IndexModel([("faculty_id", ASCENDING)], unique=True, name="faculty_unique")
    ],
    "audit_log": [IndexModel([("at", DESCENDING)], name="at_desc")],
}


# Indexes replaced by later phases; dropped if an older database still has them.
OBSOLETE_INDEXES: dict[str, list[str]] = {
    "users": ["email_unique"],
    "courses": ["code_semester"],
    "moderation_queue": ["status"],
    "forms": ["cycle_course_faculty"],
    "labels": ["response_annotator"],
}


def get_sync_db():
    """Synchronous PyMongo database for the analysis worker thread (its own client)."""
    global _sync_client
    if _sync_client is None:
        from pymongo import MongoClient

        _sync_client = MongoClient(
            get_settings().mongodb_uri, serverSelectionTimeoutMS=3000, tz_aware=True
        )
    return _sync_client[get_settings().mongodb_db]


def close_sync_client() -> None:
    global _sync_client
    if _sync_client is not None:
        _sync_client.close()
        _sync_client = None


def get_client() -> AsyncMongoClient:
    """Create the client on first use. The connection itself is lazy, so this never blocks."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncMongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=3000,
            tz_aware=True,
        )
    return _client


def get_db() -> AsyncDatabase:
    """FastAPI dependency returning the application database."""
    return get_client()[get_settings().mongodb_db]


async def ping() -> bool:
    try:
        await get_client().admin.command("ping")
    except Exception:
        return False
    return True


async def ensure_indexes(db: AsyncDatabase | None = None) -> dict[str, list[str]]:
    """Create every index in INDEXES (idempotent). Returns created index names per collection."""
    db = db if db is not None else get_db()
    for name, old in OBSOLETE_INDEXES.items():
        existing = await db[name].index_information()
        for index_name in old:
            if index_name in existing:
                await db[name].drop_index(index_name)
    created: dict[str, list[str]] = {}
    for name, models in INDEXES.items():
        created[name] = await db[name].create_indexes(models)
    return created


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
