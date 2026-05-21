"""Tests de l'endpoint GET /api/status."""
from __future__ import annotations

from fastapi.testclient import TestClient

from webapp.server import create_app
from webapp.transport import NullTransport


def test_get_status_with_null_transport():
    t = NullTransport()
    t.open()
    app = create_app(transport=t, startup_error="Wi-Fi indisponible : timeout")
    client = TestClient(app)
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["transport"]["kind"] == "none"
    assert body["transport"]["alive"] is False
    assert body["transport"]["startup_error"] == "Wi-Fi indisponible : timeout"
    assert body["transport"]["description"] == "none (mode autonome)"


def test_get_status_with_fake_alive_transport():
    """Avec un transport ouvert mais sans heartbeat lancé, alive=True, last_pong=None."""
    from tests.webapp.test_plateau_bridge import FakeTransport
    t = FakeTransport()
    t.open()
    app = create_app(transport=t)
    client = TestClient(app)
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    # FakeTransport.description = "fake", on tombera donc sur kind=none par defaut
    # mais alive doit etre True
    assert body["transport"]["alive"] is True


def test_get_status_polling_fields_present():
    t = NullTransport()
    t.open()
    app = create_app(transport=t)
    client = TestClient(app)
    body = client.get("/api/status").json()
    assert "client" in body
    assert body["client"]["polling_active"] is True
    assert body["client"]["polling_interval_ms"] == 500
    assert "plateau" in body
