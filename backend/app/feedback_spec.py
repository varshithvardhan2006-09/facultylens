"""The feedback questionnaire (SPEC §4) in one place: forms, validation, seed data and the Phase 4
aspect lexicon all read from here, so the question text and the analysis can never drift apart."""

from typing import Final

# key, label, the Likert question students see, seed phrases (also the aspect lexicon)
TEACHING_ASPECTS: Final = [
    (
        "knowledge",
        "Subject knowledge",
        "The teacher knows the subject well and explains concepts in depth.",
        ["knows the subject", "expert", "deep knowledge", "concepts"],
    ),
    (
        "clarity",
        "Clarity of explanation",
        "Explanations are clear and easy to follow.",
        ["explains clearly", "easy to understand", "confusing", "fast explanation"],
    ),
    (
        "punctuality",
        "Punctuality & regularity",
        "Classes start on time and are held regularly.",
        ["on time", "late", "cancels class", "regular"],
    ),
    (
        "interaction",
        "Interaction & doubt clearing",
        "The teacher answers questions and clears doubts, in and after class.",
        ["clears doubts", "approachable after class", "answers questions", "interactive"],
    ),
    (
        "practical",
        "Examples & practical relevance",
        "Classes use real-world examples and practical applications.",
        ["real-world examples", "practical", "industry", "lab", "applications"],
    ),
    (
        "assessment",
        "Assessment & feedback fairness",
        "Marking is fair and tests come back with useful feedback.",
        ["fair marking", "internals", "assignments", "evaluation", "feedback on tests"],
    ),
    (
        "behaviour",
        "Behaviour & approachability",
        "The teacher is respectful, approachable and motivating.",
        ["polite", "rude", "friendly", "strict", "respectful", "motivating"],
    ),
    (
        "pace",
        "Pace & syllabus coverage",
        "The pace is right and the syllabus is covered in time.",
        ["completes syllabus", "too fast", "rushed", "slow", "covers portions"],
    ),
]

TEACHING_TEXTS: Final = [
    ("liked", "What did you like most about this course and teacher?"),
    ("improve", "What should the teacher improve?"),
    ("other", "Any other comments?"),
]

CURRICULUM_ITEMS: Final = [
    ("syllabus_relevance", "Syllabus relevance", "The syllabus is relevant and up to date."),
    ("outcomes_clarity", "Course outcomes", "The course outcomes were stated clearly."),
    ("lab_adequacy", "Lab and practical work", "Lab and practical sessions were adequate."),
    ("reference_material", "Reference material", "Textbooks and reference material were adequate."),
]

CURRICULUM_TEXTS: Final = [("comment", "Any comments on the syllabus or curriculum?")]

LIKERT_LABELS: Final = {1: "Poor", 2: "Fair", 3: "Good", 4: "Very good", 5: "Excellent"}
MAX_TEXT: Final = 2000

ASPECT_KEYS: Final = [a[0] for a in TEACHING_ASPECTS]
ASPECT_LABELS: Final = {a[0]: a[1] for a in TEACHING_ASPECTS}
ASPECT_LEXICON: Final = {a[0]: a[3] for a in TEACHING_ASPECTS}

# Templated next steps for the no-LLM summary (and the NAAC action-taken draft later).
SUGGESTED_ACTIONS: Final = {
    "knowledge": "Link each topic to the core concepts and share further reading for depth.",
    "clarity": "Break explanations into smaller steps and recap the key point before moving on.",
    "punctuality": "Start on time and announce any rescheduled class in advance.",
    "interaction": "Set aside a few minutes each class, or an office hour, for doubts.",
    "practical": "Add one real-world example or short demonstration per topic.",
    "assessment": "Share the marking scheme and return tests with written feedback.",
    "behaviour": "Keep the tone encouraging and invite questions without judgement.",
    "pace": "Check understanding before moving on and share a weekly coverage plan.",
}
CURRICULUM_KEYS: Final = [c[0] for c in CURRICULUM_ITEMS]


def questions(form_type: str) -> list[dict]:
    """The question snapshot stored on each form at publish time."""
    if form_type == "teaching":
        likert = [
            {"key": k, "label": label, "text": q, "kind": "likert"}
            for k, label, q, _ in TEACHING_ASPECTS
        ]
        texts = [{"key": k, "label": q, "text": q, "kind": "text"} for k, q in TEACHING_TEXTS]
    else:
        likert = [
            {"key": k, "label": label, "text": q, "kind": "likert"}
            for k, label, q in CURRICULUM_ITEMS
        ]
        texts = [{"key": k, "label": q, "text": q, "kind": "text"} for k, q in CURRICULUM_TEXTS]
    return likert + texts


def likert_keys(form_type: str) -> list[str]:
    return ASPECT_KEYS if form_type == "teaching" else CURRICULUM_KEYS


def text_keys(form_type: str) -> list[str]:
    return [k for k, _ in (TEACHING_TEXTS if form_type == "teaching" else CURRICULUM_TEXTS)]


# Gendered-language lexicons for the bias panel (SPEC §11.7). "Ability" words are used more
# for men and "warmth" words more for women in published studies of student evaluations; the
# panel counts answers that use them, by the teacher's recorded gender, at department level.
ABILITY_WORDS: Final = ["brilliant", "genius", "smart", "intelligent", "gifted", "expert"]
WARMTH_WORDS: Final = [
    "helpful",
    "caring",
    "kind",
    "patient",
    "supportive",
    "organised",
    "organized",
    "friendly",
]

# Templated next steps for curriculum issues in the NAAC Action Taken Report (no-LLM path).
CURRICULUM_ACTIONS: Final = {
    "syllabus_relevance": "Review the syllabus with the Board of Studies and add current topics.",
    "outcomes_clarity": "State the course outcomes in the first class and map each unit to them.",
    "lab_adequacy": "Add lab hours or experiments and check equipment before the semester.",
    "reference_material": "Update the reference list and add recent editions to the library.",
    "comments": "Discuss the recurring syllabus comments in the next Board of Studies meeting.",
}
CURRICULUM_LABELS: Final = {c[0]: c[1] for c in CURRICULUM_ITEMS}
