from app import cli, db
from app.auth.security import verify_password


async def _keep_client():
    return None  # the test's own client must stay open for the fixture's cleanup


async def test_create_admin_prints_a_one_time_password(mongo, monkeypatch, capsys):
    monkeypatch.setattr(db, "close_client", _keep_client)
    assert await cli.create_admin("IQAC@College.edu", " IQAC Office ") == 0
    out = capsys.readouterr().out
    temp = out.split("(shown once): ")[1].splitlines()[0]
    user = await mongo.users.find_one({"email": "iqac@college.edu"})
    assert user["role"] == "admin" and user["must_change_pw"] and user["name"] == "IQAC Office"
    assert verify_password(temp, user["password_hash"])
    assert await mongo.audit_log.find_one({"action": "user.create_admin_cli"})

    assert await cli.create_admin("iqac@college.edu", "Again") == 1  # no duplicates
    assert "already exists" in capsys.readouterr().err
    assert await cli.create_admin("not-an-email", "X") == 2
    assert await mongo.users.count_documents({}) == 1


async def test_backup_and_restore_round_trip(mongo, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(db, "close_client", _keep_client)
    await mongo.users.insert_many([{"email": "a@x.in", "role": "faculty"}, {"email": "b@x.in"}])
    await mongo.responses.insert_one({"form_id": "f1", "likert": {"clarity": 4}})
    await mongo.refresh_tokens.insert_one({"token": "secret-session"})
    folder = tmp_path / "backup"

    assert await cli.backup(str(folder)) == 0
    manifest = (folder / "manifest.json").read_text(encoding="utf-8")
    assert '"users": 2' in manifest and '"responses": 1' in manifest
    assert not (folder / "refresh_tokens.json").exists()  # sessions never leave the machine
    assert await cli.backup(str(folder)) == 1  # never writes over an existing backup

    # A database that already holds data is left alone unless --replace is given.
    assert await cli.restore(str(folder)) == 1
    assert "--replace" in capsys.readouterr().err
    await mongo.users.delete_many({})
    await mongo.users.insert_one({"email": "stray@x.in"})
    assert await cli.restore(str(folder), replace=True) == 0
    assert await mongo.users.count_documents({}) == 2
    assert await mongo.users.find_one({"email": "stray@x.in"}) is None
    assert await cli.restore(str(tmp_path / "nothing-here")) == 2
