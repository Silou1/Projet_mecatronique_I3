"""Fixtures pytest partagees pour les tests du projet Quoridor."""

import threading
from collections import deque

import pytest


class MockSerial:
    """Mock de serial.Serial pour tests sans hardware.

    Buffer bidirectionnel en memoire :
    - tx : ce que le code testant ecrit (lu via get_tx / peek_tx)
    - rx : ce que le code testant lit (rempli via inject_rx pour simuler des trames ESP32 entrantes)
    """

    def __init__(self):
        self._rx_buffer = bytearray()
        self._tx_buffer = bytearray()
        self._lock = threading.Lock()
        self.is_open = True
        self.timeout = 0.1

    def write(self, data: bytes) -> int:
        with self._lock:
            self._tx_buffer.extend(data)
        return len(data)

    def read(self, n: int = 1) -> bytes:
        with self._lock:
            if not self._rx_buffer:
                return b""
            chunk = bytes(self._rx_buffer[:n])
            del self._rx_buffer[:n]
            return chunk

    def readline(self) -> bytes:
        with self._lock:
            idx = self._rx_buffer.find(b"\n")
            if idx == -1:
                return b""
            line = bytes(self._rx_buffer[: idx + 1])
            del self._rx_buffer[: idx + 1]
            return line

    @property
    def in_waiting(self) -> int:
        return len(self._rx_buffer)

    def close(self):
        self.is_open = False

    # API helpers pour les tests
    def inject_rx(self, data: bytes) -> None:
        """Simule l'arrivee de bytes depuis l'ESP32."""
        with self._lock:
            self._rx_buffer.extend(data)

    def get_tx(self) -> bytes:
        """Recupere et vide le buffer TX (ce que le code a envoye a l'ESP32)."""
        with self._lock:
            data = bytes(self._tx_buffer)
            self._tx_buffer.clear()
            return data

    def peek_tx(self) -> bytes:
        """Lit le buffer TX sans le vider."""
        with self._lock:
            return bytes(self._tx_buffer)


class MockClock:
    """Horloge virtuelle pour tester les timeouts sans sleep reel."""

    def __init__(self, start: float = 0.0):
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def mock_serial():
    return MockSerial()


@pytest.fixture
def mock_clock():
    return MockClock()
