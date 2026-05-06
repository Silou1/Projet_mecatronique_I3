"""Fixtures pour les tests d'intégration nécessitant le DevKit ESP32 branché.

Skippe automatiquement les tests si aucun port /dev/cu.usbserial-* n'est détecté.
"""

import re
import sys
from pathlib import Path

import pytest
import serial

# Permet l'import de _uart_helpers depuis firmware/tests_devkit/
# (ce dossier n'est pas un package Python, c'est volontaire — script direct).
_TESTS_DEVKIT = Path(__file__).resolve().parents[2] / "firmware" / "tests_devkit"
sys.path.insert(0, str(_TESTS_DEVKIT))

from _uart_helpers import (  # noqa: E402
    BAUD,
    find_devkit_port,
    make_frame,
    reset_esp,
    wait_for,
)


@pytest.fixture(scope="session")
def serial_port():
    """Ouvre le port DevKit pour toute la session pytest. Skip si non détecté."""
    port = find_devkit_port()
    if port is None:
        pytest.skip("DevKit ESP32 non détecté (aucun /dev/cu.usbserial-*)")
    s = serial.Serial(port, BAUD, timeout=0.1)
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def raw_devkit(serial_port):
    """Reset hardware uniquement. Pour sc 1 qui teste le handshake lui-même."""
    reset_esp(serial_port)
    return serial_port


@pytest.fixture
def connected_devkit(serial_port):
    """Reset + handshake complet. Pour sc 2-8 qui partent de l'état CONNECTED."""
    reset_esp(serial_port)
    out = wait_for(serial_port, r"<HELLO\|seq=(\d+)\|v=1\|crc=", timeout=4.0)
    m = re.search(r"<HELLO\|seq=(\d+)\|v=1\|crc=", out)
    assert m, "fixture connected_devkit : pas de HELLO reçu après reset"
    serial_port.write(make_frame("HELLO_ACK", seq=0, ack=int(m.group(1))))
    out2 = wait_for(serial_port, r"\[FSM\] -> state 3", timeout=2.0)
    assert "state 3" in out2, "fixture connected_devkit : pas de transition CONNECTED"
    return serial_port
