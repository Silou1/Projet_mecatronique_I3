"""Test devkit : le parser WALL répond ERR sur une position invalide (sans plateau)."""
from __future__ import annotations

import time

import pytest

from webapp.transport import SerialTransport


def _drain(t: SerialTransport, duration: float = 1.0) -> None:
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        if t.read_line(timeout=0.2) is None:
            break


@pytest.mark.devkit_serial
def test_wall_parser_invalid_orientation_returns_err():
    """WALL avec une orientation hors {H,V} doit renvoyer ERR."""
    t = SerialTransport()
    t.open()
    try:
        _drain(t)
        t.write_line("WALL Z 0 0")
        reply = t.read_line(timeout=3.0)
        assert reply is not None
        # Le firmware repond "WALL ERR orientation : H ou V attendu"
        assert "ERR" in reply.upper(), f"Attendu ERR, recu {reply!r}"
    finally:
        t.close()


@pytest.mark.devkit_serial
def test_wall_parser_out_of_bounds_returns_err():
    """WALL hors grille (row/col > 4) doit renvoyer ERR."""
    t = SerialTransport()
    t.open()
    try:
        _drain(t)
        t.write_line("WALL H 99 99")
        reply = t.read_line(timeout=3.0)
        assert reply is not None
        assert "ERR" in reply.upper(), f"Attendu ERR, recu {reply!r}"
    finally:
        t.close()
