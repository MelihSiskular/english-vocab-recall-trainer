# Architecture

## Goal

The application separates the learning rules from terminal input/output and
from SQLite persistence. This keeps the first version simple while making a
future Streamlit, desktop, or web interface possible without rewriting the
quiz engine.

## Modules

- `text.py`: normalization, similarity, typo detection, and hint redaction.
- `database.py`: SQLite schema and transaction boundary.
- `importer.py`: CSV validation, cleanup, and idempotent upsert.
- `quiz.py`: session queue, retry spacing, answer recording, and terminal flow.
- `mastery.py`: transparent state calculation.
- `analytics.py`: summaries, hardest words, session history, and CSV export.
- `cli.py`: command-line adapter.

## Data model

### words
The current vocabulary and current mastery state.

### sessions
One study run. A session is completed only when every selected word is answered
correctly once. Quitting early keeps the attempts but marks the session aborted.

### attempts
Every submitted answer. This is the immutable analytics event table. It stores:

- the exact answer,
- correctness,
- retry number,
- response time,
- hint usage,
- similarity,
- error classification,
- prompt snapshot.

### word_state_history
Every change between `new`, `learning`, `known`, and `mastered`.

### data_quality_issues
CSV import warnings such as whitespace cleanup, missing fields, duplicates, and
unbalanced quotes.

## Retry rule

A wrong word is inserted three positions later in the queue. A correct word is
removed for the rest of that session. The session therefore ends only after all
selected words have been recalled correctly.

## Mastery rule

- `new`: no completed session.
- `learning`: studied but not stable.
- `known`: correct without hint on the first attempt in the last two completed
  sessions.
- `mastered`: correct without hint on the first attempt in the last four
  completed sessions, spanning at least seven days.

The rule is deliberately visible and editable. It should not be replaced by a
black-box score until enough real attempt data exists.
