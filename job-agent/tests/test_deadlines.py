from datetime import date

from matcher.dates import parse_deadline, days_left


def test_indian_numeric_format_is_day_first():
    assert parse_deadline("Last date: 05.08.2026 (4:30 PM)") == (date(2026, 8, 5), "date")


def test_wordy_dates():
    assert parse_deadline("Applications must reach on or before 25th August, 2026")[0] == date(2026, 8, 25)
    assert parse_deadline("Deadline: August 25, 2026")[0] == date(2026, 8, 25)


def test_prefers_date_after_last_date_phrase():
    d, _ = parse_deadline("Notice dated 18/08/2026. Last date of submission 25/08/2026. Interview on 05/09/2026")
    assert d == date(2026, 8, 25)


def test_without_hint_takes_latest_date():
    assert parse_deadline("Posted 01-10-2026, closes 20-10-2026")[0] == date(2026, 10, 20)


def test_rolling_and_unknown():
    assert parse_deadline("Applications reviewed on a rolling basis") == (None, "rolling")
    assert parse_deadline("Apply soon") == (None, "unknown")
    assert parse_deadline("") == (None, "unknown")


def test_invalid_date_ignored():
    assert parse_deadline("Last date 31.02.2026") == (None, "unknown")


def test_days_left():
    assert days_left("2026-11-06", date(2026, 11, 1)) == 5
    assert days_left("2026-10-31", date(2026, 11, 1)) == -1
