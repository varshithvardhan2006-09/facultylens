"""Admin commands, run from backend/:

    python -m app.cli create-admin --email admin@college.edu --name "College Office"
    python -m app.cli backup ../facultylens-backup
    python -m app.cli restore ../facultylens-backup [--replace]

create-admin prints a temporary password once; the admin must change it at first sign-in.
backup writes every collection to JSON (sign-in sessions excepted) so the data can move to another
computer; restore loads it into the database in MONGODB_URI and checks every count."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from bson import json_util
from pydantic import TypeAdapter, ValidationError
from pydantic.networks import EmailStr

from app import db
from app.auth.security import generate_temp_password, hash_password
from app.services.audit import record
from app.utils import now


async def create_admin(email: str, name: str) -> int:
    try:
        email = TypeAdapter(EmailStr).validate_python(email).lower()
    except ValidationError:
        print(f"Not a valid email: {email}", file=sys.stderr)
        return 2
    if not await db.ping():
        print("MongoDB is not reachable at MONGODB_URI.", file=sys.stderr)
        return 1
    database = db.get_db()
    await db.ensure_indexes(database)
    if await database.users.find_one({"email": email}):
        print(f"A user with {email} already exists.", file=sys.stderr)
        return 1
    temp = generate_temp_password()
    doc = {
        "name": name.strip(),
        "role": "admin",
        "email": email,
        "password_hash": hash_password(temp),
        "must_change_pw": True,
        "is_active": True,
        "created_at": now(),
    }
    result = await database.users.insert_one(doc)
    await record(database, None, "user.create_admin_cli", str(result.inserted_id))
    print(f"Created admin {email}")
    print(f"Temporary password (shown once): {temp}")
    print("Sign in and change it straight away.")
    await db.close_client()
    return 0


# Sign-in sessions are tied to the browser that made them; everyone just signs in again.
SKIP = {"refresh_tokens"}
MANIFEST = "manifest.json"


def _holds_backup(folder: Path) -> bool:
    return folder.exists() and any(folder.glob("*.json"))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


async def backup(folder: str) -> int:
    out = Path(folder)
    if await asyncio.to_thread(_holds_backup, out):
        print(f"{out} already holds a backup; choose an empty folder.", file=sys.stderr)
        return 1
    if not await db.ping():
        print("MongoDB is not reachable at MONGODB_URI.", file=sys.stderr)
        return 1
    database = db.get_db()
    counts = {}
    for name in sorted(await database.list_collection_names()):
        if name in SKIP:
            continue
        docs = await database[name].find().to_list()
        text = json_util.dumps(docs, json_options=json_util.CANONICAL_JSON_OPTIONS)
        await asyncio.to_thread(_write, out / f"{name}.json", text)
        counts[name] = len(docs)
    manifest = {"database": database.name, "created_at": now().isoformat(), "counts": counts}
    await asyncio.to_thread(_write, out / MANIFEST, json.dumps(manifest, indent=2))
    print(f"Backed up {sum(counts.values())} documents in {len(counts)} collections to {out}")
    await db.close_client()
    return 0


async def restore(folder: str, replace: bool = False) -> int:
    src = Path(folder)
    manifest = await asyncio.to_thread(_read, src / MANIFEST)
    if manifest is None:
        print(f"No {MANIFEST} in {src}; is this a backup folder?", file=sys.stderr)
        return 2
    counts = json.loads(manifest)["counts"]
    if not await db.ping():
        print("MongoDB is not reachable at MONGODB_URI.", file=sys.stderr)
        return 1
    database = db.get_db()
    present = [n for n in await database.list_collection_names() if n not in SKIP]
    holding = [n for n in present if await database[n].estimated_document_count()]
    if holding and not replace:
        print(
            f"The database already has data ({', '.join(sorted(holding))}). "
            "Run again with --replace to overwrite it.",
            file=sys.stderr,
        )
        return 1
    # Read everything first: a missing or damaged file must not leave a half-emptied database.
    try:
        backup = {
            name: json_util.loads(await asyncio.to_thread(_read, src / f"{name}.json"))
            for name in counts
        }
    except (OSError, ValueError) as exc:
        print(f"The backup can't be read, so nothing was changed: {exc}", file=sys.stderr)
        return 1
    for name, docs in backup.items():
        await database[name].drop()
        if docs:
            await database[name].insert_many(docs, ordered=False)
    await db.ensure_indexes(database)
    wrong = [n for n, c in counts.items() if await database[n].count_documents({}) != c]
    if wrong:
        print(f"Counts differ after restore: {', '.join(wrong)}", file=sys.stderr)
        return 1
    print(f"Restored {sum(counts.values())} documents in {len(counts)} collections; counts match.")
    await db.close_client()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="create an Admin account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", default="Administrator")
    dump = sub.add_parser("backup", help="write every collection to JSON files in a new folder")
    dump.add_argument("folder")
    load = sub.add_parser("restore", help="load a backup folder into the database")
    load.add_argument("folder")
    load.add_argument("--replace", action="store_true", help="overwrite a database that has data")
    args = parser.parse_args()
    if args.command == "create-admin":
        sys.exit(asyncio.run(create_admin(args.email, args.name)))
    if args.command == "backup":
        sys.exit(asyncio.run(backup(args.folder)))
    if args.command == "restore":
        sys.exit(asyncio.run(restore(args.folder, args.replace)))


if __name__ == "__main__":
    main()
