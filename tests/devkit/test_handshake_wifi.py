"""Test devkit Wi-Fi : PING/PONG via TCP avec ESP32 en mode AP."""
from __future__ import annotations

import pytest

from webapp.transport import WiFiTransport


@pytest.mark.devkit_wifi
def test_ping_pong_wifi(wifi_fixture):
    """Envoie PING via TCP 192.168.4.1:3333, attend PONG."""
    t = WiFiTransport()
    t.open()
    try:
        t.write_line("PING")
        reply = t.read_line(timeout=3.0)
        assert reply == "PONG", f"Attendu 'PONG', reçu {reply!r}"
    finally:
        t.close()
