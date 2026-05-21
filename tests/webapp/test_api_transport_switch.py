"""Tests de POST /api/transport/switch."""
from __future__ import annotations

from fastapi.testclient import TestClient

from webapp.server import create_app
from webapp.transport import NullTransport, TransportError


def test_transport_switch_success(monkeypatch):
    """On simule un switch vers un transport qui s'ouvre OK."""
    from tests.webapp.test_plateau_bridge import FakeTransport
    t = NullTransport()
    t.open()
    app = create_app(transport=t)

    fake_serial = FakeTransport()

    def fake_make(kind):
        if kind == "serial":
            return fake_serial
        raise ValueError(kind)

    monkeypatch.setattr("webapp.server._make_transport_by_kind", fake_make)

    client = TestClient(app)
    resp = client.post("/api/transport/switch", json={"kind": "serial"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "fake" in body["description"]


def test_transport_switch_open_failure(monkeypatch):
    """Si le nouveau transport échoue à open(), success=False et on garde l'ancien."""
    from tests.webapp.test_plateau_bridge import FakeTransport
    t = FakeTransport()
    t.open()
    app = create_app(transport=t)

    class Failing:
        is_alive = False
        description = "wifi 192.168.4.1:3333"
        def open(self): raise TransportError("Wi-Fi injoignable")
        def write_line(self, l): pass
        def read_line(self, timeout=1.0): return None
        def close(self): pass

    monkeypatch.setattr("webapp.server._make_transport_by_kind", lambda k: Failing())

    client = TestClient(app)
    resp = client.post("/api/transport/switch", json={"kind": "wifi"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "injoignable" in body["error"].lower()


def test_transport_switch_invalid_kind():
    t = NullTransport()
    t.open()
    app = create_app(transport=t)
    client = TestClient(app)
    resp = client.post("/api/transport/switch", json={"kind": "bluetooth"})
    assert resp.status_code == 422  # validation Pydantic
