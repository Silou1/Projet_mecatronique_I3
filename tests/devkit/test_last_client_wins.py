"""Test devkit : la politique 'dernier client gagne' côté firmware."""
from __future__ import annotations

import time

import pytest

from webapp.transport import WiFiTransport


@pytest.mark.devkit_wifi
def test_last_client_wins(wifi_fixture):
    """Quand un 2e client se connecte, l'ESP32 doit dropper le 1er."""
    # Laisse l'ESP32 nettoyer d'eventuels clients fantomes d'un test precedent
    time.sleep(1.0)
    c1 = WiFiTransport()
    c1.open()
    c1.write_line("PING")
    assert c1.read_line(timeout=2.0) == "PONG"

    c2 = WiFiTransport()
    c2.open()
    time.sleep(0.5)  # laisse l'ESP32 traiter la nouvelle connexion
    c2.write_line("PING")
    assert c2.read_line(timeout=2.0) == "PONG"

    # c1 doit avoir été déconnecté côté ESP32
    # On envoie un PING : si l'ESP32 a stoppé c1, soit l'écriture échoue,
    # soit la lecture timeout (pas de PONG)
    c1_responded = False
    try:
        c1.write_line("PING")
        reply = c1.read_line(timeout=1.5)
        c1_responded = (reply == "PONG")
    except Exception:
        pass  # peut lever si socket fermé côté pair
    assert not c1_responded, "c1 ne devrait plus recevoir de PONG (politique dernier client gagne)"

    try:
        c1.close()
    except Exception:
        pass
    c2.close()
