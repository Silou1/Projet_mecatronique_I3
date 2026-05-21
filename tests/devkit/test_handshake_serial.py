"""Test devkit USB : PING/PONG via USB-série avec ESP32 branché."""
from __future__ import annotations

import time

import pytest

from webapp.transport import SerialTransport


def _drain_boot_messages(t: SerialTransport, duration: float = 2.0) -> None:
    """Vide les messages de boot que l'ESP32 imprime au reset."""
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        if t.read_line(timeout=0.2) is None:
            break


@pytest.mark.devkit_serial
def test_ping_pong_serial():
    """Envoie PING via USB, attend PONG."""
    t = SerialTransport()  # détection auto /dev/cu.usbserial-*
    t.open()
    try:
        _drain_boot_messages(t)
        t.write_line("PING")
        reply = t.read_line(timeout=3.0)
        assert reply == "PONG", f"Attendu 'PONG', reçu {reply!r}"
    finally:
        t.close()


@pytest.mark.devkit_serial
def test_unknown_command_returns_err_serial():
    """Une commande inconnue doit renvoyer une ligne commençant par ERR."""
    t = SerialTransport()
    t.open()
    try:
        _drain_boot_messages(t)
        t.write_line("FOOBAR")
        reply = t.read_line(timeout=3.0)
        assert reply is not None
        assert reply.startswith("ERR"), f"Attendu 'ERR ...', reçu {reply!r}"
    finally:
        t.close()
