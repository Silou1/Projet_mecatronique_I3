"""Tests de SerialTransport avec MockSerial."""
from __future__ import annotations

import pytest

from webapp.transport import SerialTransport, TransportError


def test_serial_transport_description_before_open():
    t = SerialTransport(port="/dev/cu.usbserial-110")
    assert "serial" in t.description.lower()
    assert "/dev/cu.usbserial-110" in t.description


def test_serial_transport_auto_detect_port(monkeypatch):
    """SerialTransport sans port explicite cherche le premier /dev/cu.usbserial-*."""
    fake_ports = ["/dev/cu.usbserial-110", "/dev/cu.usbserial-220"]
    monkeypatch.setattr("webapp.transport._find_serial_ports", lambda: fake_ports)
    t = SerialTransport()
    assert t._port == "/dev/cu.usbserial-110"


def test_serial_transport_auto_detect_no_port(monkeypatch):
    """SerialTransport sans port et sans /dev/cu.usbserial-* lève TransportError à l'open."""
    monkeypatch.setattr("webapp.transport._find_serial_ports", lambda: [])
    t = SerialTransport()
    with pytest.raises(TransportError, match="aucun port"):
        t.open()


def test_serial_transport_open_and_write(mock_serial, monkeypatch):
    """SerialTransport.write_line envoie 'line\\n' encodé UTF-8."""
    monkeypatch.setattr("webapp.transport._open_serial", lambda port, baud: mock_serial)
    t = SerialTransport(port="/dev/cu.usbserial-110")
    t.open()
    t.write_line("PING")
    assert mock_serial.get_tx() == b"PING\n"


def test_serial_transport_read_line(mock_serial, monkeypatch):
    """SerialTransport.read_line lit jusqu'à \\n et retourne sans \\n."""
    monkeypatch.setattr("webapp.transport._open_serial", lambda port, baud: mock_serial)
    t = SerialTransport(port="/dev/cu.usbserial-110")
    t.open()
    mock_serial.inject_rx(b"PONG\n")
    assert t.read_line(timeout=1.0) == "PONG"


def test_serial_transport_read_line_timeout(mock_serial, monkeypatch):
    """read_line retourne None si rien n'arrive."""
    monkeypatch.setattr("webapp.transport._open_serial", lambda port, baud: mock_serial)
    t = SerialTransport(port="/dev/cu.usbserial-110")
    t.open()
    # rien injecté
    assert t.read_line(timeout=0.01) is None


def test_serial_transport_is_alive(mock_serial, monkeypatch):
    monkeypatch.setattr("webapp.transport._open_serial", lambda port, baud: mock_serial)
    t = SerialTransport(port="/dev/cu.usbserial-110")
    assert t.is_alive is False
    t.open()
    assert t.is_alive is True
    t.close()
    assert t.is_alive is False


def test_serial_transport_close_idempotent(mock_serial, monkeypatch):
    monkeypatch.setattr("webapp.transport._open_serial", lambda port, baud: mock_serial)
    t = SerialTransport(port="/dev/cu.usbserial-110")
    t.open()
    t.close()
    t.close()  # ne doit pas lever


def test_serial_transport_open_failure(monkeypatch):
    """Si l'ouverture du port lève, on convertit en TransportError."""
    def raise_oserror(port, baud):
        raise OSError("port introuvable")
    monkeypatch.setattr("webapp.transport._open_serial", raise_oserror)
    t = SerialTransport(port="/dev/cu.usbserial-110")
    with pytest.raises(TransportError):
        t.open()
