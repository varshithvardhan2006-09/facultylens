# ruff: noqa: E501  (sentence banks and fixture rows read better unwrapped)
"""Synthetic demo data: `python -m app.seed [--reset] [--force]`.

Everything created here carries `is_synthetic: true` and is excluded from evaluation (SPEC §8).
The institution, its 8 departments and the course codes and names are MVSR Engineering
College's (mvsrec.in and its R21 scheme). Every person is fictional, so no synthetic feedback
sits under a real teacher's name.

Shape: 8 departments (only CSE and ECE populated), 1 IQAC admin, 2 HoDs, 9 faculty, 144 students in two sections per
department, 11 odd-semester offerings for 2026-27, one open cycle, and roughly 330 teaching
responses plus curriculum responses, all from a fixed random seed. Counting HoDs, CSE has three
women and three men teaching (enough for the bias panel to compare groups) and ECE two women and
three men (so it shows the "groups too small" state).

The comments are hand-written sentence banks, not real student feedback. They deliberately
include negation, sarcasm, a few abusive lines and a few personal details (a phone number, a roll
number, the teacher's name) so the Phase 4 moderation and redaction steps have something to catch.
Gendered words ("brilliant", "caring" ...) are drawn independently of the teacher's gender, so the
bias panel shows no gap that the seed put there.

All demo accounts share the password in DEMO_PASSWORD (default in .env.example).
"""

import argparse
import asyncio
import random
import sys
from datetime import timedelta
from typing import Any

from app import db
from app.auth.security import hash_password
from app.config import get_settings
from app.feedback_spec import ASPECT_KEYS, CURRICULUM_KEYS, questions
from app.services.anonymity import student_form_hash
from app.services.profile_items import new_id
from app.utils import now

RNG_SEED = 2026
ACADEMIC_YEAR = "2026-27"
SECTION_SIZE = 36
PARTICIPATION = 0.82
COLLECTIONS = [
    "users",
    "departments",
    "courses",
    "faculty_profiles",
    "feedback_cycles",
    "forms",
    "responses",
]

# MVSR Engineering College's academic units (mvsrec.in/departments.php). Only CSE and ECE get
# demo staff, students and feedback; the rest exist so pickers and reports list the real units.
DEPARTMENTS = [
    ("CIVIL", "Civil Engineering"),
    ("CSE", "Computer Science Engineering & Allied Branches"),
    ("IT", "Information Technology"),
    ("ECE", "Electronics & Communication Engineering"),
    ("EEE", "Electrical & Electronics Engineering"),
    ("MECH", "Mechanical Engineering"),
    ("MBA", "Master of Business Administration"),
    ("ASH", "Applied Science & Humanities"),
]
# Roll numbers follow the college's Osmania University format, e.g. 2451-24-733-001:
# college code, year of admission, branch code, serial. 751 (CSIT) was confirmed by a student;
# 733 (CSE) and 735 (ECE) are the usual OU branch codes and still need confirming.
COLLEGE_CODE = "2451"
ADMISSION_YEAR = "24"  # semester 5 in 2026-27 means the 2024 intake
BRANCH_CODES = {"CSE": "733", "ECE": "735"}

# name, gender, department, role, designation, strong aspects, weak aspects, interests
FACULTY = [
    (
        "Dr. Padma Rao",
        "female",
        "CSE",
        "hod",
        "Professor & Head",
        ["knowledge", "practical"],
        ["pace"],
        ["Machine learning", "Data mining"],
    ),
    (
        "Dr. Kavitha Reddy",
        "female",
        "CSE",
        "faculty",
        "Associate Professor",
        ["clarity", "interaction"],
        ["pace", "assessment"],
        ["Compilers", "Programming languages"],
    ),
    (
        "Mr. Arvind Sharma",
        "male",
        "CSE",
        "faculty",
        "Assistant Professor",
        ["practical", "behaviour"],
        ["clarity", "punctuality"],
        ["Compilers", "Software engineering"],
    ),
    (
        "Dr. Lakshmi Narayanan",
        "female",
        "CSE",
        "faculty",
        "Associate Professor",
        ["knowledge", "assessment"],
        ["interaction"],
        ["Computer networks", "Network security"],
    ),
    (
        "Mr. Rahul Verma",
        "male",
        "CSE",
        "faculty",
        "Assistant Professor",
        ["behaviour", "interaction"],
        ["knowledge", "pace"],
        ["Wireless networks", "IoT"],
    ),
    (
        "Dr. Venkat Rao",
        "male",
        "ECE",
        "hod",
        "Professor & Head",
        ["knowledge", "clarity"],
        ["interaction"],
        ["Microwave engineering", "Antennas"],
    ),
    (
        "Dr. Sneha Patil",
        "female",
        "ECE",
        "faculty",
        "Associate Professor",
        ["clarity", "pace"],
        ["practical"],
        ["VLSI design", "Low-power circuits"],
    ),
    (
        "Mr. Imran Khan",
        "male",
        "ECE",
        "faculty",
        "Assistant Professor",
        ["interaction", "practical"],
        ["assessment", "punctuality"],
        ["VLSI design", "FPGA systems"],
    ),
    (
        "Dr. Deepa Menon",
        "female",
        "ECE",
        "faculty",
        "Associate Professor",
        ["assessment", "punctuality"],
        ["clarity"],
        ["Signal processing", "Speech processing"],
    ),
    (
        "Mr. Farhan Siddiqui",
        "male",
        "ECE",
        "faculty",
        "Assistant Professor",
        ["punctuality", "behaviour"],
        ["practical", "knowledge"],
        ["Digital signal processing", "Embedded systems"],
    ),
    (
        "Mr. Naveen Kumar",
        "male",
        "CSE",
        "faculty",
        "Assistant Professor",
        ["practical", "punctuality"],
        ["clarity"],
        ["Operating systems", "Distributed systems"],
    ),
]

# code, name, department, section, teacher name (all semester 5 of 2026-27). Course codes and
# names are from MVSR's R21 B.E. scheme; the teachers are fictional.
OFFERINGS = [
    ("U21PCN05CS", "Automata Languages and Computation", "CSE", "A", "Dr. Kavitha Reddy"),
    ("U21PCN05CS", "Automata Languages and Computation", "CSE", "B", "Mr. Arvind Sharma"),
    ("U21PC501CS", "Web Programming", "CSE", "A", "Dr. Lakshmi Narayanan"),
    ("U21PC501CS", "Web Programming", "CSE", "B", "Mr. Rahul Verma"),
    ("U21PE513CS", "Image Processing", "CSE", "A", "Dr. Padma Rao"),
    ("U21PC501EC", "Linear Integrated Circuits and Applications", "ECE", "A", "Dr. Sneha Patil"),
    ("U21PC501EC", "Linear Integrated Circuits and Applications", "ECE", "B", "Mr. Imran Khan"),
    ("U21PC502EC", "Digital Signal Processing", "ECE", "A", "Dr. Deepa Menon"),
    ("U21PC502EC", "Digital Signal Processing", "ECE", "B", "Mr. Farhan Siddiqui"),
    ("U21PC506EC", "Antennas and Wave Propagation", "ECE", "A", "Dr. Venkat Rao"),
    # Added in Phase 6 (last, so earlier offerings draw the same random numbers): with him
    # CSE has three women and three men, enough for the bias panel to show its comparison.
    ("U21PCN04CS", "Operating Systems", "CSE", "A", "Mr. Naveen Kumar"),
]

FIRST = [
    "Aarav",
    "Aditi",
    "Akhil",
    "Ananya",
    "Arjun",
    "Bhavana",
    "Charan",
    "Deepika",
    "Divya",
    "Ganesh",
    "Harika",
    "Harsha",
    "Ishaan",
    "Jahnavi",
    "Karthik",
    "Keerthi",
    "Kiran",
    "Lavanya",
    "Manoj",
    "Meghana",
    "Mohan",
    "Nandini",
    "Nikhil",
    "Pooja",
    "Pranav",
    "Priya",
    "Rahul",
    "Ramya",
    "Ravi",
    "Sahithi",
    "Sai",
    "Sandeep",
    "Shreya",
    "Siddharth",
    "Sneha",
    "Srinivas",
    "Swathi",
    "Tarun",
    "Teja",
    "Varun",
    "Vishnu",
    "Yamini",
]
LAST = [
    "Reddy",
    "Rao",
    "Sharma",
    "Naidu",
    "Varma",
    "Kumar",
    "Goud",
    "Chowdary",
    "Patel",
    "Iyer",
    "Menon",
    "Nair",
    "Khan",
    "Singh",
    "Das",
    "Pillai",
    "Gupta",
    "Joshi",
]

POSITIVE = {
    "knowledge": [
        "Sir has deep knowledge of the subject.",
        "Madam knows the subject very well and connects concepts nicely.",
        "Excellent command over the concepts.",
        "Very knowledgeable, answers even tricky questions.",
    ],
    "clarity": [
        "Explains every topic clearly, easy to understand.",
        "The explanations are very clear and step by step.",
        "Even difficult derivations were easy to follow.",
        "Clear teaching with good board work.",
    ],
    "punctuality": [
        "Always comes on time and never cancels class.",
        "Classes are very regular and start on time.",
        "Punctual and completes the period fully.",
    ],
    "interaction": [
        "Clears all our doubts patiently, even after class.",
        "Very approachable after class for doubts.",
        "Class is interactive, we are encouraged to ask questions.",
        "Answers questions without making us feel stupid.",
    ],
    "practical": [
        "Gives real-world examples from industry.",
        "Lab sessions were very practical and useful.",
        "Connects theory to real applications, which made it interesting.",
        "The mini project helped us understand the practical side.",
    ],
    "assessment": [
        "Internal marks are fair and transparent.",
        "Gives useful feedback on assignments.",
        "Evaluation is fair, mistakes are explained after the test.",
    ],
    "behaviour": [
        "Very friendly and respectful towards students.",
        "Motivating teacher, always encourages us.",
        "Polite and caring, we feel comfortable in class.",
        "Strict but fair, and genuinely helpful.",
    ],
    "pace": [
        "Completed the syllabus on time with revision classes.",
        "The pace was comfortable for everyone.",
        "Covered all portions well before the exams.",
    ],
}
NEGATIVE = {
    "knowledge": [
        "Sometimes seems unsure about the advanced topics.",
        "Reads from slides and cannot explain beyond them.",
        "Concepts are not explained in depth.",
    ],
    "clarity": [
        "Explanations are confusing at times.",
        "Too fast while explaining, hard to follow the derivations.",
        "Please explain step by step, many of us got lost.",
        "Board work is not clear and hard to read.",
    ],
    "punctuality": [
        "Often comes late to class.",
        "Cancels classes without informing us.",
        "Classes are irregular, we lost many periods.",
    ],
    "interaction": [
        "Does not clear doubts properly.",
        "Not approachable after class.",
        "Hardly any interaction, it is a one-way lecture.",
    ],
    "practical": [
        "No real-world examples, only theory.",
        "Lab sessions were not useful.",
        "Please include more practical applications.",
    ],
    "assessment": [
        "Internal marks are not fair.",
        "Assignments are corrected late and without feedback.",
        "Evaluation of internals is too strict and unclear.",
    ],
    "behaviour": [
        "Sometimes rude when we ask questions.",
        "Too strict, students are afraid to speak.",
        "Could be more respectful towards students.",
    ],
    "pace": [
        "The pace is too fast, the last units were rushed.",
        "Syllabus was not completed, last unit was skipped.",
        "Very slow in the beginning and rushed at the end.",
    ],
}
GENERAL = [
    "Overall a good course.",
    "Thank you for the semester.",
    "Nothing much to add.",
    "The subject was interesting.",
    "Good teacher overall.",
]
NEGATION = [
    "Not engaging but informative.",
    "The class is not boring, but the pace could be better.",
    "Not very interactive, though the notes are excellent.",
]
SARCASM = [
    "Wow, another class of reading slides aloud. Very helpful.",
    "Great, the syllabus magically finished in the last week.",
    "Sure, cancelling class twice a week really helps us learn.",
]
ABUSIVE = [
    "This teacher is useless and a total waste of time.",
    "Worst teacher ever, absolutely pathetic classes.",
]
WORDS_A = ["Brilliant teacher.", "A genius in the subject."]  # "ability" words
WORDS_B = ["Very helpful and caring.", "Organised and supportive."]  # "warmth" words
CURRICULUM = [
    "Syllabus should include more recent topics.",
    "More lab hours would help.",
    "Reference books are outdated, please suggest newer ones.",
    "Course outcomes were clear.",
    "Good balance of theory and lab.",
    None,
    None,
    None,
]


def _rating(rng: random.Random, mu: float) -> int:
    return max(1, min(5, round(rng.gauss(mu, 0.75))))


DEMO_INSTITUTION = "MVSR Engineering College"
UNIVERSITIES = ["JNTU Hyderabad", "Osmania University", "NIT Warangal", "Andhra University"]
TITLE_PATTERNS = [
    "A comparative study of {topic} techniques",
    "{topic} for resource-constrained systems",
    "Teaching {topic} through hands-on laboratory work",
    "An empirical evaluation of {topic} methods",
]


def _demo_facts(name: str, designation: str, interests: list[str]) -> dict[str, list]:
    """A few synthetic profile facts so generated profiles have something to say.

    A separate RNG per teacher keeps the feedback responses identical to earlier seeds.
    Venues and awards carry "(demo)" so nothing here can pass for a real record.
    """
    rng = random.Random(f"facts:{name}")
    doctor = name.startswith("Dr.")
    phd_year = rng.randint(2008, 2018)
    quals = [
        {
            "id": new_id(),
            "source": "manual",
            "degree": "M.Tech",
            "specialisation": interests[0],
            "institution": rng.choice(UNIVERSITIES),
            "year": phd_year - rng.randint(4, 6),
        }
    ]
    if doctor:
        quals.insert(
            0,
            {
                "id": new_id(),
                "source": "manual",
                "degree": "PhD",
                "specialisation": interests[0],
                "institution": rng.choice(UNIVERSITIES),
                "year": phd_year,
            },
        )
    joined = phd_year + rng.randint(1, 4) if doctor else rng.randint(2014, 2020)
    experience = [
        {
            "id": new_id(),
            "source": "manual",
            "role": designation,
            "institution": DEMO_INSTITUTION,
            "from_year": joined,
            "to_year": None,
        }
    ]
    pubs = []
    for i in range(rng.randint(2, 4)):
        topic = interests[i % len(interests)]
        pubs.append(
            {
                "id": new_id(),
                "source": "manual",
                "title": rng.choice(TITLE_PATTERNS).format(topic=topic.lower()).capitalize(),
                "venue": rng.choice(
                    [
                        "Journal of Engineering Education (demo)",
                        "National Computing Conference (demo)",
                    ]
                ),
                "year": rng.randint(joined, 2026),
                "type": "journal" if i % 2 == 0 else "conference",
                "authors": [name],
            }
        )
    achievements = []
    if rng.random() < 0.6:
        achievements.append(
            {
                "id": new_id(),
                "source": "manual",
                "kind": "award",
                "title": "Best Teacher Award (demo)",
                "year": rng.randint(joined + 1, 2026),
            }
        )
    return {
        "qualifications": quals,
        "experience": experience,
        "publications": pubs,
        "achievements": achievements,
    }


def _profile(strong: list[str], weak: list[str]) -> dict[str, float]:
    return {a: 4.4 if a in strong else 2.3 if a in weak else 3.6 for a in ASPECT_KEYS}


def _teaching_response(rng, teacher, mu, student):
    likert = {a: _rating(rng, mu[a]) for a in ASPECT_KEYS}
    best = sorted(ASPECT_KEYS, key=lambda a: -likert[a])[:2]
    worst = [a for a in sorted(ASPECT_KEYS, key=lambda a: likert[a])[:2] if likert[a] <= 3]
    liked = " ".join(rng.choice(POSITIVE[a]) for a in rng.sample(best, k=rng.choice([1, 1, 2])))
    if rng.random() < 0.15:
        liked = f"{liked} {rng.choice(WORDS_A + WORDS_B)}"
    improve = (
        " ".join(rng.choice(NEGATIVE[a]) for a in worst) if worst and rng.random() < 0.8 else None
    )
    other = None
    roll = rng.random()
    if roll < 0.06:
        other = rng.choice(SARCASM)
    elif roll < 0.09:
        other = rng.choice(NEGATION)
    elif roll < 0.11:
        other = rng.choice(ABUSIVE)
    elif roll < 0.13:
        phone = f"98{rng.randint(100, 999)} {rng.randint(10000, 99999)}"
        other = f"{teacher}, please share the notes on WhatsApp, my number is {phone}."
    elif roll < 0.15:
        other = f"I am {student['roll_no']}, please recheck my internal marks."
    elif roll < 0.35:
        other = rng.choice(GENERAL)
    return likert, {"liked": liked or None, "improve": improve, "other": other}


async def _refuse_if_real(database, force: bool) -> None:
    real_users = await database.users.count_documents({"is_synthetic": {"$ne": True}})
    codes = [d[0] for d in DEPARTMENTS]
    real_depts = await database.departments.count_documents(
        {"code": {"$in": codes}, "is_synthetic": {"$ne": True}}
    )
    if (real_users or real_depts) and not force:
        print(
            f"This database has {real_users} real users and {real_depts} real departments with "
            "the demo codes. Seeding would mix demo data with real data. Use an empty database, "
            "or pass --force if you really mean it.",
            file=sys.stderr,
        )
        raise SystemExit(2)


async def reset(database) -> dict[str, int]:
    """Delete synthetic data only, plus sessions and responses that belong to it."""
    removed = {}
    synthetic_users = [
        u["_id"] async for u in database.users.find({"is_synthetic": True}, {"_id": 1})
    ]
    await database.refresh_tokens.delete_many({"user_id": {"$in": synthetic_users}})
    for name in COLLECTIONS:
        result = await database[name].delete_many({"is_synthetic": True})
        removed[name] = result.deleted_count
    return removed


async def seed(database, force: bool = False) -> dict[str, Any]:
    await _refuse_if_real(database, force)
    await reset(database)
    await db.ensure_indexes(database)
    rng = random.Random(RNG_SEED)
    settings = get_settings()
    password_hash = hash_password(settings.demo_password)  # one hash, reused: same password
    stamp = now()
    common = {"is_synthetic": True, "created_at": stamp}

    dept_ids = {}
    for code, name in DEPARTMENTS:
        dept_ids[code] = (
            await database.departments.insert_one({"code": code, "name": name, **common})
        ).inserted_id

    def user(name, role, **extra):
        return {
            "name": name,
            "role": role,
            "password_hash": password_hash,
            "must_change_pw": False,
            "is_active": True,
            **common,
            **extra,
        }

    await database.users.insert_one(
        user("IQAC Coordinator (demo)", "admin", email="iqac@demo.facultylens.in")
    )
    teachers: dict[str, dict] = {}
    for name, gender, dept, role, designation, strong, weak, interests in FACULTY:
        local = name.split(" ", 1)[1].lower().replace(" ", ".")
        doc = user(
            name,
            role,
            email=f"{local}@demo.facultylens.in",
            department_id=dept_ids[dept],
            gender=gender,
        )
        doc["_id"] = (await database.users.insert_one(doc)).inserted_id
        teachers[name] = {"doc": doc, "mu": _profile(strong, weak)}
        await database.faculty_profiles.insert_one(
            {
                "user_id": doc["_id"],
                "designation": designation,
                "interests": interests,
                **_demo_facts(name, designation, interests),
                "pending_imports": [],
                "rejected_keys": [],
                **common,
            }
        )

    students: dict[tuple[str, str], list[dict]] = {}
    used_names = set()
    for code, branch in BRANCH_CODES.items():
        for s_index, section in enumerate(["A", "B"]):
            batch = []
            for i in range(SECTION_SIZE):
                while True:
                    name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
                    if name not in used_names:
                        used_names.add(name)
                        break
                serial = s_index * SECTION_SIZE + i + 1
                roll = f"{COLLEGE_CODE}-{ADMISSION_YEAR}-{branch}-{serial:03d}"
                doc = user(name, "student", roll_no=roll, department_id=dept_ids[code])
                batch.append(doc)
            result = await database.users.insert_many(batch)
            for doc, _id in zip(batch, result.inserted_ids, strict=True):
                doc["_id"] = _id
            students[(code, section)] = batch

    cycle = {
        "name": f"{ACADEMIC_YEAR} Odd Sem",
        "academic_year": ACADEMIC_YEAR,
        "term": "odd",
        "opens_at": stamp - timedelta(days=21),
        "closes_at": stamp + timedelta(days=14),
        "status": "open",
        "published_at": stamp - timedelta(days=21),
        **common,
    }
    cycle["_id"] = (await database.feedback_cycles.insert_one(cycle)).inserted_id

    counts = {"teaching": 0, "curriculum": 0}
    for code, name, dept, section, teacher_name in OFFERINGS:
        teacher = teachers[teacher_name]
        enrolled = students[(dept, section)]
        course = {
            "code": code,
            "name": name,
            "department_id": dept_ids[dept],
            "academic_year": ACADEMIC_YEAR,
            "semester": 5,
            "section": section,
            "faculty_ids": [teacher["doc"]["_id"]],
            "student_ids": [s["_id"] for s in enrolled],
            **common,
        }
        course["_id"] = (await database.courses.insert_one(course)).inserted_id
        forms = {}
        for form_type in ("teaching", "curriculum"):
            form = {
                "cycle_id": cycle["_id"],
                "course_id": course["_id"],
                "faculty_id": teacher["doc"]["_id"] if form_type == "teaching" else None,
                "type": form_type,
                "questions": questions(form_type),
                **common,
            }
            forms[form_type] = (await database.forms.insert_one(form)).inserted_id

        responses = []
        for student in enrolled:
            if rng.random() > PARTICIPATION:
                continue
            day = (stamp - timedelta(days=rng.randint(0, 20))).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            likert, texts = _teaching_response(rng, teacher_name, teacher["mu"], student)
            responses.append(
                {
                    "form_id": forms["teaching"],
                    "type": "teaching",
                    "likert": likert,
                    "texts": texts,
                    "submitted_on": day,
                    "student_hash": student_form_hash(student["_id"], forms["teaching"]),
                    "is_synthetic": True,
                }
            )
            if rng.random() < 0.9:
                responses.append(
                    {
                        "form_id": forms["curriculum"],
                        "type": "curriculum",
                        "likert": {k: _rating(rng, 3.6) for k in CURRICULUM_KEYS},
                        "texts": {"comment": rng.choice(CURRICULUM)},
                        "submitted_on": day,
                        "student_hash": student_form_hash(student["_id"], forms["curriculum"]),
                        "is_synthetic": True,
                    }
                )
        if responses:
            await database.responses.insert_many(responses)
        counts["teaching"] += sum(r["type"] == "teaching" for r in responses)
        counts["curriculum"] += sum(r["type"] == "curriculum" for r in responses)

    return {
        "departments": len(DEPARTMENTS),
        "faculty": len(FACULTY),
        "students": sum(len(v) for v in students.values()),
        "offerings": len(OFFERINGS),
        "teaching_responses": counts["teaching"],
        "curriculum_responses": counts["curriculum"],
        "cycle_id": str(cycle["_id"]),
        "sample_logins": {
            "admin": "iqac@demo.facultylens.in",
            "hod": "padma.rao@demo.facultylens.in",
            "faculty": "kavitha.reddy@demo.facultylens.in",
            "student": students[("CSE", "A")][0]["roll_no"],
        },
    }


async def main_async(args) -> int:
    database = db.get_db()
    if not await db.ping():
        print("MongoDB is not reachable at MONGODB_URI.", file=sys.stderr)
        return 1
    if args.reset_only:
        print("Removed synthetic data:", await reset(database))
        return 0
    summary = await seed(database, force=args.force)
    print("Seeded synthetic demo data (is_synthetic=true, excluded from evaluation):")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("All demo accounts use the password in DEMO_PASSWORD (see backend/.env.example).")
    await db.close_client()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.seed")
    parser.add_argument(
        "--reset",
        dest="reset_only",
        action="store_true",
        help="only delete synthetic data, then stop",
    )
    parser.add_argument(
        "--force", action="store_true", help="seed even though the database has real users"
    )
    sys.exit(asyncio.run(main_async(parser.parse_args())))


if __name__ == "__main__":
    main()
