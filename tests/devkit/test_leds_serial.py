"""Tests devkit USB des commandes LED.

Necessite un ESP32 branche en USB-C avec le firmware
bringup_l298n_complet.cpp flashe (incluant les commandes LED).

Marker : devkit_serial (filtre via pytest -m devkit_serial).

Convention du repo (cf. test_handshake_serial.py, test_wall_parser.py) :
on instancie SerialTransport() directement dans chaque test plutot que
de passer par une fixture pyserial — il n'existe pas de fixture
`serial_conn` ni equivalent dans conftest.py.
"""
from __future__ import annotations

import time

import pytest

from webapp.transport import SerialTransport

pytestmark = pytest.mark.devkit_serial


def _drain_boot_messages(t: SerialTransport, duration: float = 2.0) -> None:
    """Vide les messages de boot que l'ESP32 imprime au reset."""
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        if t.read_line(timeout=0.2) is None:
            break


def _send(t: SerialTransport, line: str, timeout: float = 1.0) -> str:
    """Envoie une ligne et retourne la premiere reponse (strippee)."""
    t.write_line(line)
    reply = t.read_line(timeout=timeout)
    return reply if reply is not None else ""


def test_led_set_pixel_valide():
    """LED <idx> <r> <g> <b> avec valeurs valides retourne OK."""
    t = SerialTransport()
    t.open()
    try:
        _drain_boot_messages(t)
        resp = _send(t, "LED 0 0 0 255")
        assert resp == "OK", f"Reponse inattendue : {resp!r}"
    finally:
        t.close()


def test_led_show_apres_set():
    """LEDSHOW pousse le buffer sans erreur."""
    t = SerialTransport()
    t.open()
    try:
        _drain_boot_messages(t)
        _send(t, "LED 0 0 0 255")
        resp = _send(t, "LEDSHOW")
        assert resp == "OK"
    finally:
        t.close()


def test_led_clear():
    """LEDCLEAR eteint toutes les LEDs et push."""
    t = SerialTransport()
    t.open()
    try:
        _drain_boot_messages(t)
        _send(t, "LED 5 255 0 0")
        _send(t, "LEDSHOW")
        resp = _send(t, "LEDCLEAR")
        assert resp == "OK"
    finally:
        t.close()


def test_led_idx_hors_bornes():
    """LED 99 ... retourne une erreur explicite."""
    t = SerialTransport()
    t.open()
    try:
        _drain_boot_messages(t)
        resp = _send(t, "LED 99 0 0 0")
        assert resp.startswith("ERR"), f"Erreur attendue, recu : {resp!r}"
        assert "idx=99" in resp or "borne" in resp.lower()
    finally:
        t.close()


def test_led_composante_hors_bornes():
    """LED 0 999 0 0 retourne une erreur explicite."""
    t = SerialTransport()
    t.open()
    try:
        _drain_boot_messages(t)
        resp = _send(t, "LED 0 999 0 0")
        assert resp.startswith("ERR"), f"Erreur attendue, recu : {resp!r}"
    finally:
        t.close()


def test_led_syntaxe_incomplete():
    """LED 0 0 (args manquants) retourne une erreur explicite."""
    t = SerialTransport()
    t.open()
    try:
        _drain_boot_messages(t)
        resp = _send(t, "LED 0 0")
        assert resp.startswith("ERR"), f"Erreur attendue, recu : {resp!r}"
    finally:
        t.close()


def test_led_bright_valide():
    """LEDBRIGHT 128 retourne OK."""
    t = SerialTransport()
    t.open()
    try:
        _drain_boot_messages(t)
        resp = _send(t, "LEDBRIGHT 128")
        assert resp == "OK"
        _send(t, "LEDBRIGHT 102")  # restaure le defaut
    finally:
        t.close()


def test_led_bright_hors_bornes():
    """LEDBRIGHT 999 retourne une erreur."""
    t = SerialTransport()
    t.open()
    try:
        _drain_boot_messages(t)
        resp = _send(t, "LEDBRIGHT 999")
        assert resp.startswith("ERR")
    finally:
        t.close()


def test_led_cleanup_en_fin():
    """Nettoie l'etat des LEDs en fin de batch de tests."""
    t = SerialTransport()
    t.open()
    try:
        _drain_boot_messages(t)
        resp = _send(t, "LEDCLEAR")
        assert resp == "OK"
    finally:
        t.close()
