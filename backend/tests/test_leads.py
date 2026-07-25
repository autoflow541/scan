import json

import pytest

from app import leads as leads_module
from app.leads import InvalidEmailError, record_lead, validate_email


def test_valid_email_is_accepted():
    assert validate_email("  someone@example.com  ") == "someone@example.com"


@pytest.mark.parametrize("bad", ["", "not-an-email", "a@b", "@example.com", "a@example", "a b@example.com"])
def test_invalid_emails_are_rejected(bad):
    with pytest.raises(InvalidEmailError):
        validate_email(bad)


def test_overlong_email_is_rejected():
    with pytest.raises(InvalidEmailError):
        validate_email("a" * 250 + "@example.com")


def test_record_lead_writes_one_json_line(tmp_path, monkeypatch):
    monkeypatch.setattr(leads_module, "LEADS_DIR", tmp_path / "leads")
    monkeypatch.setattr(leads_module, "LEADS_FILE", tmp_path / "leads" / "leads.jsonl")

    record_lead(email="a@example.com", scanned_url="https://example.com", score=72, client_ip="1.2.3.4")

    lines = leads_module.LEADS_FILE.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["email"] == "a@example.com"
    assert entry["scanned_url"] == "https://example.com"
    assert entry["score"] == 72
    assert entry["ip"] == "1.2.3.4"
    assert "ts" in entry


def test_record_lead_creates_directory_if_missing(tmp_path, monkeypatch):
    leads_dir = tmp_path / "does" / "not" / "exist"
    monkeypatch.setattr(leads_module, "LEADS_DIR", leads_dir)
    monkeypatch.setattr(leads_module, "LEADS_FILE", leads_dir / "leads.jsonl")

    record_lead(email="a@example.com", scanned_url="https://example.com", score=None, client_ip="1.2.3.4")

    assert leads_dir.is_dir()


def test_record_lead_appends_multiple_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(leads_module, "LEADS_DIR", tmp_path)
    monkeypatch.setattr(leads_module, "LEADS_FILE", tmp_path / "leads.jsonl")

    record_lead(email="a@example.com", scanned_url="https://example.com", score=1, client_ip="1.1.1.1")
    record_lead(email="b@example.com", scanned_url="https://example.com", score=2, client_ip="2.2.2.2")

    lines = leads_module.LEADS_FILE.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
