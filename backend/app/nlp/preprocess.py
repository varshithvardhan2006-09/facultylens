"""Text clean-up before analysis (SPEC §5 step 1).

Transformers get the normalised text (never stemmed or stop-word stripped); the contraction
expansion and lemmatising helpers exist only for the TF-IDF baseline and word clouds.
"""

import re
import unicodedata
from functools import lru_cache

from app.utils import CONTROL_CHARS

_SPACES = re.compile(r"[ \t ]+")
_NEWLINES = re.compile(r"\s*\n\s*")
_LONG_RUN = re.compile(r"([A-Za-z])\1{2,}")
# Links and emails keep every letter: "www." collapsed to "ww." would slip past PII redaction.
_LINK_OR_EMAIL = re.compile(
    r"(?:https?://|\bw{3,}\.)\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE
)
_PUNCT_RUN = re.compile(r"([!?])\1+|\.{4,}")
# Elongations that collapse to a doubled letter but mean a single-letter word.
_ELONGATED = {"soo": "so", "noo": "no", "yess": "yes", "okk": "ok", "hii": "hi", "verry": "very"}
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})

_CORE_STOPWORDS = (
    "a an the is are was were be been i you he she it we they this that and or but not to of "
    "in on for with at by from as very so too more most"
).split()


def _fix_elongation(match: re.Match) -> str:
    return match.group(1) * 2


def _collapse_long_runs(text: str) -> str:
    """'sooo' -> 'soo' everywhere except inside links and email addresses."""
    out, last = [], 0
    for match in _LINK_OR_EMAIL.finditer(text):
        out.append(_LONG_RUN.sub(_fix_elongation, text[last : match.start()]))
        out.append(match.group(0))
        last = match.end()
    out.append(_LONG_RUN.sub(_fix_elongation, text[last:]))
    return "".join(out)


def _keep_case(original: str, replacement: str) -> str:
    return replacement.capitalize() if original[:1].isupper() else replacement


def normalise(text: str | None) -> str:
    """NFKC, straight quotes, single spaces, kept newlines, 'sooo' -> 'so', '!!!' -> '!'."""
    if not text:
        return ""
    text = CONTROL_CHARS.sub("", unicodedata.normalize("NFKC", text)).translate(_QUOTES)
    text = _NEWLINES.sub("\n", text.strip())
    text = _SPACES.sub(" ", text)
    text = _collapse_long_runs(text)
    text = re.sub(
        r"\b(" + "|".join(_ELONGATED) + r")\b",
        lambda m: _keep_case(m.group(1), _ELONGATED[m.group(1).lower()]),
        text,
        flags=re.IGNORECASE,
    )
    return _PUNCT_RUN.sub(lambda m: m.group(1) or "...", text)


@lru_cache
def _stopwords() -> frozenset[str]:
    try:
        from nltk.corpus import stopwords

        return frozenset(stopwords.words("english"))
    except LookupError:  # data not downloaded; fall back to a small core list
        return frozenset(_CORE_STOPWORDS)


def detect_language(text: str) -> str:
    """'en', 'low_confidence' (mostly Latin letters but few English function words, e.g.
    romanised Telugu or Hindi) or 'non_english' (mostly non-Latin script). Code-mixed analysis
    is out of scope; the flag tells the admin which comments the English models may misread."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "en"
    non_latin = sum(1 for c in letters if not ("a" <= c.lower() <= "z")) / len(letters)
    if non_latin > 0.3:
        return "non_english"
    words = re.findall(r"[a-z']+", text.lower())
    if len(words) <= 3:
        return "en"
    stop_share = sum(1 for w in words if w in _stopwords()) / len(words)
    return "en" if stop_share >= 0.15 else "low_confidence"


_SENT_FALLBACK = re.compile(r"[^.!?\n]+[.!?]*")


def split_sentences(text: str) -> list[tuple[int, int]]:
    """(start, end) character spans of sentences in `text`, newlines also ending a sentence."""
    spans: list[tuple[int, int]] = []
    offset = 0
    for line in text.split("\n"):
        try:
            from nltk.tokenize import sent_tokenize

            parts = sent_tokenize(line)
        except LookupError:
            parts = [m.group(0).strip() for m in _SENT_FALLBACK.finditer(line)]
        cursor = 0
        for part in parts:
            part = part.strip()
            if not part:
                continue
            start = line.find(part, cursor)
            if start < 0:
                continue
            spans.append((offset + start, offset + start + len(part)))
            cursor = start + len(part)
        offset += len(line) + 1
    return spans
