# Roadmap

## Version 0.1 — Reliable learning core

- CSV import and validation
- SQLite attempt history
- Session retry queue
- Error classification
- Hint tracking
- Mastery states
- CLI analytics and CSV export
- Automated tests and CI

## Version 0.2 — Evidence-based review scheduling

- `next_review_at` for each word
- due-word study mode
- configurable intervals after successful recall
- lapse handling when a known word is missed
- daily review summary

## Version 0.3 — Analytics dashboard

Add pandas and a small Streamlit dashboard only after enough attempt data exists.

Planned views:

- first-try accuracy by date
- newly known words by week
- error-type distribution
- response-time trend
- hardest words
- words frequently confused with each other
- hint dependence
- mastery-state transitions

## Version 0.4 — Data quality tools

- optional correction dictionary
- suspicious English spelling report
- missing example suggestions
- duplicate meaning detection
- CSV round-trip export

## Version 1.0 — Portfolio release

- screenshots and demo GIF
- anonymized sample dataset
- documented architecture decisions
- tagged release
