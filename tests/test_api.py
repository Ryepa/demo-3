"""API tests. Run with: pytest -q"""

import pytest
from fastapi.testclient import TestClient

from app import main

VALID = {"name": "Alex Morgan", "phone": "+1 555 123 4567", "service": "plumbing", "message": "Tap drips."}


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(main, "DEMO_MODE", True)
    monkeypatch.setattr(main, "limiter", main.RateLimiter(5, 600))
    yield


@pytest.fixture
def client():
    return TestClient(main.app)


def test_homepage_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Fixit Pro" in r.text and "Demo project" in r.text


def test_demo_mode_logs_and_succeeds(client, caplog):
    caplog.set_level("INFO")
    r = client.post("/api/lead", json=VALID)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "demo": True}
    assert "DEMO lead" in caplog.text and "Alex Morgan" in caplog.text


@pytest.mark.parametrize(
    "patch,field",
    [
        ({"name": "A"}, "name"),
        ({"name": "x" * 61}, "name"),
        ({"name": "R2D2"}, "name"),
        ({"phone": "12ab"}, "phone"),
        ({"phone": "123"}, "phone"),
        ({"phone": "+1 (555) 12-34-567-8901234"}, "phone"),
        ({"service": "roofing"}, "service"),
        ({"message": "x" * 1001}, "message"),
    ],
)
def test_validation_errors(client, patch, field):
    r = client.post("/api/lead", json={**VALID, **patch})
    assert r.status_code == 422
    body = r.json()
    assert body["ok"] is False and field in body["fields"]


def test_missing_fields(client):
    r = client.post("/api/lead", json={})
    assert r.status_code == 422
    assert {"name", "phone", "service"} <= set(r.json()["fields"])


def test_rate_limit_per_ip(client):
    for _ in range(5):
        assert client.post("/api/lead", json=VALID, headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    r = client.post("/api/lead", json=VALID, headers={"X-Forwarded-For": "1.1.1.1"})
    assert r.status_code == 429 and "Retry-After" in r.headers
    # A different IP is unaffected.
    assert client.post("/api/lead", json=VALID, headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200


def test_honeypot_is_silently_dropped(client, caplog):
    caplog.set_level("INFO")
    r = client.post("/api/lead", json={**VALID, "website": "http://spam"})
    assert r.status_code == 200
    assert "DEMO lead" not in caplog.text


def test_not_configured_returns_503(client, monkeypatch):
    monkeypatch.setattr(main, "DEMO_MODE", False)
    monkeypatch.setattr(main, "BOT_TOKEN", "")
    monkeypatch.setattr(main, "CHAT_ID", "")
    assert client.post("/api/lead", json=VALID).status_code == 503


def test_telegram_success_and_failure(client, monkeypatch):
    monkeypatch.setattr(main, "DEMO_MODE", False)
    monkeypatch.setattr(main, "BOT_TOKEN", "x")
    monkeypatch.setattr(main, "CHAT_ID", "1")
    sent = []

    async def ok(text):
        sent.append(text)

    monkeypatch.setattr(main, "send_telegram", ok)
    assert client.post("/api/lead", json=VALID).json() == {"ok": True}
    assert "<b>Service:</b> Plumbing" in sent[0]

    async def boom(text):
        raise RuntimeError("down")

    monkeypatch.setattr(main, "send_telegram", boom)
    assert client.post("/api/lead", json=VALID).status_code == 502


def test_message_html_is_escaped():
    lead = main.Lead(name="<b>Eve</b>", phone="5551234567", service="other", message="<script>")
    text = main.format_lead(lead)
    assert "&lt;script&gt;" in text and "<script>" not in text
