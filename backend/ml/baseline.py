"""Classical sentiment baselines (SPEC §8.3): VADER, TF-IDF + Logistic Regression and
TF-IDF + Random Forest. Each exposes fit(texts, labels) and predict(texts) -> labels."""

from typing import Protocol

from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

SEED = 2026
VADER_THRESHOLD = 0.05  # VADER's authors' cut-off for the compound score


class Model(Protocol):
    def fit(self, texts: list[str], labels: list[str]) -> "Model": ...
    def predict(self, texts: list[str]) -> list[str]: ...


class Vader:
    """Lexicon-based, so fit() learns nothing."""

    def __init__(self):
        from nltk.sentiment import SentimentIntensityAnalyzer

        self.analyzer = SentimentIntensityAnalyzer()

    def fit(self, texts: list[str], labels: list[str]) -> "Vader":
        return self

    def predict(self, texts: list[str]) -> list[str]:
        out = []
        for text in texts:
            score = self.analyzer.polarity_scores(text)["compound"]
            if score >= VADER_THRESHOLD:
                out.append("positive")
            elif score <= -VADER_THRESHOLD:
                out.append("negative")
            else:
                out.append("neutral")
        return out


class _Sklearn:
    def __init__(self, classifier):
        self.pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
                ("clf", classifier),
            ]
        )

    def fit(self, texts: list[str], labels: list[str]) -> "_Sklearn":
        self.pipeline.fit(texts, labels)
        return self

    def predict(self, texts: list[str]) -> list[str]:
        return list(self.pipeline.predict(texts))


def tfidf_lr() -> _Sklearn:
    return _Sklearn(LogisticRegression(max_iter=2000, class_weight="balanced", random_state=SEED))


def tfidf_rf() -> _Sklearn:
    return _Sklearn(
        RandomForestClassifier(
            n_estimators=300, class_weight="balanced", random_state=SEED, n_jobs=-1
        )
    )


BASELINES = {
    "VADER": Vader,
    "TF-IDF + Logistic Regression": tfidf_lr,
    "TF-IDF + Random Forest": tfidf_rf,
}
