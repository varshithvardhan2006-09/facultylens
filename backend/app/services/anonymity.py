"""Anonymous one-response-per-form check.

The stored code is HMAC-SHA256(STUDENT_HASH_SALT, "<student_id>:<form_id>"). It differs on
every form, so it blocks a second submission without letting anyone link one student's responses
across forms, and without the salt it can't be reversed to a student.
"""

import hashlib
import hmac

from app.config import get_settings


def student_form_hash(student_id: object, form_id: object) -> str:
    key = get_settings().student_hash_salt.encode()
    message = f"{student_id}:{form_id}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()
