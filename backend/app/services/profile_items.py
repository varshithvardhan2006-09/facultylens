"""Profile item helpers shared by manual editing and imports: ids, normalisation, dedup keys."""

import re
import unicodedata
from typing import Any

from bson import ObjectId

PUBLICATION_TYPES = ("journal", "conference", "book", "chapter", "preprint", "thesis", "other")


def new_id() -> str:
    return str(ObjectId())


def _plain(text: str | None) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalise_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = doi.strip().lower()
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", doi)
    return doi or None


def item_key(kind: str, data: dict[str, Any]) -> str:
    """Stable identity used to skip duplicates across manual entries, imports and rejections."""
    if kind == "publication":
        doi = normalise_doi(data.get("doi"))
        if doi:
            return f"pub:doi:{doi}"
        return f"pub:title:{_plain(data.get('title'))}:{data.get('year') or ''}"
    if kind == "experience":
        return f"exp:{_plain(data.get('role'))}:{_plain(data.get('institution'))}"
    if kind == "qualification":
        return f"qual:{_plain(data.get('degree'))}:{_plain(data.get('institution'))}"
    if kind == "interest":
        return f"int:{_plain(data.get('tag'))}"
    raise ValueError(f"Unknown item kind {kind}")


SECTION_FOR_KIND = {
    "publication": "publications",
    "experience": "experience",
    "qualification": "qualifications",
    "interest": "interests",
}


def existing_keys(profile: dict[str, Any]) -> set[str]:
    """Keys of everything already accepted, pending or rejected on a profile."""
    keys = set(profile.get("rejected_keys", []))
    keys.update(p["key"] for p in profile.get("pending_imports", []))
    for kind, section in SECTION_FOR_KIND.items():
        for item in profile.get(section, []):
            data = {"tag": item} if kind == "interest" else item
            keys.add(item_key(kind, data))
    return keys


def clean_text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:limit] or None


def to_year(value: Any) -> int | None:
    try:
        year = int(str(value)[:4])
    except (TypeError, ValueError):
        return None
    return year if 1900 <= year <= 2100 else None
