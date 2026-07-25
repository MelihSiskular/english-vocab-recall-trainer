from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

EDGE_PUNCTUATION = " \t\n\r.,!?;:\"“”'‘’()[]{}"
UNKNOWN_ANSWERS = {
    "",
    "?",
    "bilmiyorum",
    "hatırlamıyorum",
    "hatirlamiyorum",
    "i don't know",
    "i dont know",
    "idk",
}


def clean_cell(value: str | None) -> str:
    """Clean CSV cells without changing their meaning."""
    if value is None:
        return ""
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_answer(value: str | None) -> str:
    """Normalize an answer for fair, case-insensitive comparison."""
    value = clean_cell(value)
    value = value.replace("’", "'").replace("‘", "'")
    value = value.casefold().strip(EDGE_PUNCTUATION)
    return re.sub(r"\s+", " ", value)


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_answer(left), normalize_answer(right)).ratio()


def levenshtein_distance(left: str, right: str) -> int:
    """Memory-efficient Levenshtein edit distance."""
    left = normalize_answer(left)
    right = normalize_answer(right)

    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    if len(left) < len(right):
        left, right = right, left

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def redact_target(example: str, target: str) -> str:
    """Hide the target word/phrase inside an example sentence."""
    if not example:
        return ""
    pattern = re.compile(re.escape(target.strip()), flags=re.IGNORECASE)
    replacement = "_" * max(4, len(target.strip()))
    return pattern.sub(replacement, example)


def classify_wrong_answer(
    answer: str,
    target: str,
    vocabulary_by_normalized_word: dict[str, str] | None = None,
) -> tuple[str, float, str | None]:
    """
    Return (error_type, similarity_score, confused_with_word).

    The result is intentionally conservative. Semantic reasons can be confirmed
    interactively when the automatic classifier cannot know the user's intent.
    """
    normalized_answer = normalize_answer(answer)
    normalized_target = normalize_answer(target)
    score = similarity(answer, target)

    if normalized_answer in UNKNOWN_ANSWERS:
        return "recall_failure", score, None

    if vocabulary_by_normalized_word:
        confused_word = vocabulary_by_normalized_word.get(normalized_answer)
        if confused_word and normalized_answer != normalized_target:
            return "confused_with_other_word", score, confused_word

    distance = levenshtein_distance(answer, target)
    typo_limit = 1 if len(normalized_target) <= 6 else max(2, round(len(normalized_target) * 0.20))
    if distance <= typo_limit or score >= 0.84:
        return "spelling_error", score, None

    answer_tokens = set(normalized_answer.split())
    target_tokens = set(normalized_target.split())
    if answer_tokens and target_tokens and answer_tokens < target_tokens:
        return "partial_answer", score, None

    return "unclassified_wrong_answer", score, None
