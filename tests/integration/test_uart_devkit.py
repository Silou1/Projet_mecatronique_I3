"""Tests d'intégration P8.6 — protocole UART Plan 2 sur DevKit ESP32 réel.

Portage 1:1 des 8 scénarios de firmware/tests_devkit/run_p86_manual.py.
Marqueur @pytest.mark.devkit : skippé si aucun /dev/cu.usbserial-* présent.
"""

import re

import pytest

from _uart_helpers import crc16, make_frame, read_for, wait_for


@pytest.mark.devkit
def test_sc_1_handshake(raw_devkit):
    """Sc 1 — Handshake nominal : BOOT_START → HELLO → HELLO_ACK → state 3."""
    out = wait_for(raw_devkit, r"<HELLO\|seq=(\d+)\|v=1\|crc=", timeout=4.0)
    m = re.search(r"<HELLO\|seq=(\d+)\|v=1\|crc=", out)
    assert m, "aucun HELLO reçu"
    raw_devkit.write(make_frame("HELLO_ACK", seq=0, ack=int(m.group(1))))
    out2 = wait_for(raw_devkit, r"\[FSM\] -> state 3", timeout=2.0)
    assert "state 3" in out2, "pas de transition vers state 3 (CONNECTED)"
