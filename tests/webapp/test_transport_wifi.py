"""Tests de WiFiTransport contre un faux serveur socket local."""
from __future__ import annotations

import socket
import threading
import time

import pytest

from webapp.transport import WiFiTransport, TransportError


@pytest.fixture
def fake_server():
    """Faux serveur TCP local. Accepte 1 client, expose les bytes reçus et permet d'en envoyer."""

    class FakeServer:
        def __init__(self):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("127.0.0.1", 0))  # port aléatoire
            self.port = self.sock.getsockname()[1]
            self.sock.listen(1)
            self.client_sock = None
            self.received = bytearray()
            self.stop = False
            self.thread = threading.Thread(target=self._accept, daemon=True)
            self.thread.start()

        def _accept(self):
            try:
                self.client_sock, _ = self.sock.accept()
                self.client_sock.settimeout(0.05)
                while not self.stop:
                    try:
                        chunk = self.client_sock.recv(256)
                        if not chunk:
                            break
                        self.received.extend(chunk)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
            except OSError:
                pass

        def send(self, data: bytes):
            if self.client_sock:
                self.client_sock.sendall(data)

        def shutdown(self):
            self.stop = True
            try:
                if self.client_sock:
                    self.client_sock.close()
                self.sock.close()
            except OSError:
                pass

    fs = FakeServer()
    yield fs
    fs.shutdown()


def test_wifi_transport_description_before_open():
    t = WiFiTransport(host="192.168.4.1", port=3333)
    assert "wifi" in t.description.lower()
    assert "192.168.4.1:3333" in t.description


def test_wifi_transport_open_and_write(fake_server):
    t = WiFiTransport(host="127.0.0.1", port=fake_server.port)
    t.open()
    t.write_line("PING")
    time.sleep(0.1)  # laisse le serveur recevoir
    assert fake_server.received == b"PING\n"
    t.close()


def test_wifi_transport_read_line(fake_server):
    t = WiFiTransport(host="127.0.0.1", port=fake_server.port)
    t.open()
    time.sleep(0.05)  # laisse le serveur accept()
    fake_server.send(b"PONG\n")
    assert t.read_line(timeout=1.0) == "PONG"
    t.close()


def test_wifi_transport_read_line_partial_chunks(fake_server):
    """Le buffer interne doit gérer les chunks coupés au milieu d'une ligne."""
    t = WiFiTransport(host="127.0.0.1", port=fake_server.port)
    t.open()
    time.sleep(0.05)
    fake_server.send(b"PO")
    time.sleep(0.01)
    fake_server.send(b"NG\n")
    assert t.read_line(timeout=1.0) == "PONG"
    t.close()


def test_wifi_transport_read_line_multiple_lines_one_chunk(fake_server):
    """Si deux lignes arrivent dans le même chunk, on les lit une à une."""
    t = WiFiTransport(host="127.0.0.1", port=fake_server.port)
    t.open()
    time.sleep(0.05)
    fake_server.send(b"PONG\nOK\n")
    assert t.read_line(timeout=1.0) == "PONG"
    assert t.read_line(timeout=1.0) == "OK"
    t.close()


def test_wifi_transport_read_line_timeout(fake_server):
    t = WiFiTransport(host="127.0.0.1", port=fake_server.port)
    t.open()
    assert t.read_line(timeout=0.1) is None
    t.close()


def test_wifi_transport_is_alive(fake_server):
    t = WiFiTransport(host="127.0.0.1", port=fake_server.port)
    assert t.is_alive is False
    t.open()
    assert t.is_alive is True
    t.close()
    assert t.is_alive is False


def test_wifi_transport_open_unreachable():
    """Ouverture sur un host injoignable doit lever TransportError dans le timeout configuré."""
    t = WiFiTransport(host="127.0.0.1", port=1, connect_timeout=0.5)
    with pytest.raises(TransportError):
        t.open()


def test_wifi_transport_write_after_close_raises(fake_server):
    t = WiFiTransport(host="127.0.0.1", port=fake_server.port)
    t.open()
    t.close()
    with pytest.raises(TransportError):
        t.write_line("PING")


def test_wifi_transport_close_idempotent(fake_server):
    t = WiFiTransport(host="127.0.0.1", port=fake_server.port)
    t.open()
    t.close()
    t.close()
