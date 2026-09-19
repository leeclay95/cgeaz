"""Unit tests for the POA&M history tool. No Azure: only its pure helpers are exercised."""

import datetime
import importlib.util
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "poam_history.py"
spec = importlib.util.spec_from_file_location("poam_history", SRC)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def at(minute):
    return datetime.datetime(2026, 9, 19, 0, minute, 1, tzinfo=datetime.timezone.utc)


def test_summarise_counts_items_by_severity():
    report = {"runId": "r1", "collectedAt": "t", "items": [{"severity": "High"}, {"severity": "Low"}, {"severity": "Low"}]}
    assert tool.summarise(report) == {"runId": "r1", "collectedAt": "t", "items": 3, "high": 1, "medium": 0, "low": 2}


def test_an_empty_report_summarises_to_zero():
    assert tool.summarise({})["items"] == 0


def test_a_timer_run_created_at_the_timer_minute_is_timer():
    assert tool.shape(at(10), "timer") == "timer"


def test_a_ledger_timer_run_reported_at_another_minute_is_not_called_scheduled():
    assert tool.shape(at(43), "timer") == "manual"


def test_a_manual_run_is_manual_and_a_missing_ledger_entry_says_so():
    assert tool.shape(at(10), "manual") == "manual"
    assert tool.shape(at(10), None) == "no ledger entry"
