"""Tests d'intégration P8.6 — protocole UART Plan 2 sur DevKit ESP32 réel.

Portage 1:1 des 8 scénarios de firmware/tests_devkit/run_p86_manual.py.
Marqueur @pytest.mark.devkit : skippé si aucun /dev/cu.usbserial-* présent.
"""

import re

import pytest

from _uart_helpers import crc16, make_frame, read_for, wait_for


@pytest.mark.devkit
def test_smoke_fixture_connected(connected_devkit):
    """Smoke test : la fixture connected_devkit doit fournir un port en état CONNECTED."""
    assert connected_devkit.is_open, "port doit être ouvert"
