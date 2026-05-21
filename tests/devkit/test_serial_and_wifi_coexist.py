"""Test devkit : USB-série et Wi-Fi simultanément actifs côté firmware (régression)."""
from __future__ import annotations

import time

import pytest

from webapp.transport import SerialTransport, WiFiTransport


def _drain(t, duration: float = 1.0) -> None:
    """Vide les lignes inattendues (boot, [WiFi] Nouveau client, etc.)."""
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        line = t.read_line(timeout=0.1)
        if line is None:
            break


def _read_pong(t, timeout: float = 2.0) -> bool:
    """Lit jusqu'a trouver PONG ou timeout. Ignore les lignes debug [WiFi]/etc."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = t.read_line(timeout=0.2)
        if line is None:
            continue
        if line == "PONG":
            return True
        # Ignore les lignes de debug ou autres
    return False


@pytest.mark.devkit
def test_serial_and_wifi_coexist(wifi_fixture):
    """Les deux canaux répondent indépendamment.

    Note : on assume que le Mac est sur Quoridor-ESP32 (via wifi_fixture) ET
    que l'ESP32 reste branche en USB-C. Les deux canaux doivent coexister.
    """
    s = SerialTransport()
    s.open()
    w = WiFiTransport()
    w.open()
    time.sleep(0.5)  # laisse le firmware imprimer "[WiFi] Nouveau client" sur Serial
    _drain(s, 0.5)  # consomme ces messages debug avant de tester PING/PONG
    _drain(w, 0.2)
    try:
        for _ in range(5):
            s.write_line("PING")
            assert _read_pong(s, timeout=2.0), "Serial : pas de PONG recu"
            w.write_line("PING")
            assert _read_pong(w, timeout=2.0), "WiFi : pas de PONG recu"
    finally:
        s.close()
        w.close()
