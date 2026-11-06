import pytest

from app import seed as seed_module
from app.feedback_spec import ASPECT_KEYS
from app.services.anonymity import student_form_hash
from tests.conftest import make_user


async def test_seed_shape_is_synthetic_and_repeatable(mongo):
    first = await seed_module.seed(mongo)
    assert first["students"] == 144 and first["offerings"] == 11
    assert first["departments"] == 8 and await mongo.departments.count_documents({}) == 8
    assert first["sample_logins"]["student"] == "2451-24-733-001"
    assert 280 <= first["teaching_responses"] <= 370
    for name in seed_module.COLLECTIONS:
        assert await mongo[name].count_documents({"is_synthetic": {"$ne": True}}) == 0
    # Women and men among teaching staff: the bias panel needs at least 3 per group.
    genders = [u["gender"] async for u in mongo.users.find({"role": {"$in": ["faculty", "hod"]}})]
    assert genders.count("female") >= 3 and genders.count("male") >= 3
    # Per department: CSE can show the comparison (3 and 3); ECE shows "too small" (2 and 3).
    for code, women, men in (("CSE", 3, 3), ("ECE", 2, 3)):
        dept = await mongo.departments.find_one({"code": code})
        staff = [
            u["gender"]
            async for u in mongo.users.find(
                {"role": {"$in": ["faculty", "hod"]}, "department_id": dept["_id"]}
            )
        ]
        assert (staff.count("female"), staff.count("male")) == (women, men)

    again = await seed_module.seed(mongo)  # replaces the synthetic data, same random seed
    assert again["teaching_responses"] == first["teaching_responses"]
    assert await mongo.users.count_documents({}) == 156


async def test_seeded_responses_follow_the_privacy_rules(mongo):
    await seed_module.seed(mongo)
    response = await mongo.responses.find_one({"type": "teaching"})
    assert set(response["likert"]) == set(ASPECT_KEYS)
    assert (response["submitted_on"].hour, response["submitted_on"].minute) == (0, 0)
    assert "student_id" not in response
    # The seeded student's per-form code matches, so they see the form as submitted.
    student = await mongo.users.find_one({"roll_no": "2451-24-733-001"})
    course = await mongo.courses.find_one({"student_ids": student["_id"]})
    form = await mongo.forms.find_one({"course_id": course["_id"], "type": "teaching"})
    # Every seeded response carries the code of exactly one enrolled student.
    codes = {student_form_hash(s, form["_id"]) for s in course["student_ids"]}
    stored = [r["student_hash"] async for r in mongo.responses.find({"form_id": form["_id"]})]
    assert stored and set(stored) <= codes and len(stored) == len(set(stored))


async def test_seed_refuses_real_data_and_reset_keeps_it(mongo):
    real = await make_user(mongo, "admin", email="real@college.edu")
    with pytest.raises(SystemExit):
        await seed_module.seed(mongo)
    await seed_module.seed(mongo, force=True)
    removed = await seed_module.reset(mongo)
    assert removed["users"] == 156
    assert await mongo.users.count_documents({}) == 1
    assert await mongo.users.find_one({"_id": real["_id"]})
