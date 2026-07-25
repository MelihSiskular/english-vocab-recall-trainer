from vocab_trainer.text import (
    classify_wrong_answer,
    levenshtein_distance,
    normalize_answer,
    redact_target,
)


def test_normalize_answer_is_case_and_whitespace_insensitive():
    assert normalize_answer("  At   Times  ") == "at times"


def test_normalize_answer_ignores_edge_punctuation():
    assert normalize_answer('"Appeal!"') == "appeal"


def test_levenshtein_distance_detects_typo():
    assert levenshtein_distance("transmision", "transmission") == 1


def test_classifier_marks_blank_as_recall_failure():
    error_type, _, _ = classify_wrong_answer("", "appeal")
    assert error_type == "recall_failure"


def test_classifier_marks_close_answer_as_spelling_error():
    error_type, _, _ = classify_wrong_answer("ap peal", "appeal")
    assert error_type == "spelling_error"


def test_classifier_detects_another_vocabulary_word():
    vocabulary = {"appeal": "Appeal", "grant": "Grant"}
    error_type, _, confused = classify_wrong_answer("grant", "appeal", vocabulary)
    assert error_type == "confused_with_other_word"
    assert confused == "Grant"


def test_redact_target_hides_word_case_insensitively():
    assert "appeal" not in redact_target("Their Appeal was accepted.", "appeal").casefold()
