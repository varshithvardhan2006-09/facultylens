"""Every API operation has a request in the Postman collection (CLAUDE.md rule 12)."""

import json
import re
from pathlib import Path

from app.main import create_app

COLLECTION = Path(__file__).resolve().parents[2] / "postman" / "FacultyLens.postman_collection.json"


def _requests(items):
    for item in items:
        if "item" in item:
            yield from _requests(item["item"])
        else:
            url = item["request"]["url"]
            raw = url["raw"] if isinstance(url, dict) else url
            yield item["request"]["method"], raw.split("{{baseUrl}}")[-1].split("?")[0]


def _shape(path: str) -> str:
    """'/api/users/{user_id}' and '/users/{{userId}}' both become '/users/X'."""
    return re.sub(r"\{\{?[^}]+\}?\}", "X", path.removeprefix("/api")).rstrip("/")


def test_collection_covers_every_operation():
    spec = create_app().openapi()
    operations = {(m.upper(), _shape(p)) for p, ops in spec["paths"].items() for m in ops}
    collection = json.loads(COLLECTION.read_text(encoding="utf-8"))
    covered = {(m, _shape(p)) for m, p in _requests(collection["item"])}
    assert operations - covered == set()
