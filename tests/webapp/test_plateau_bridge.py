"""Tests de PlateauBridge (couche haute au-dessus de Transport)."""
from __future__ import annotations

import threading
import time

import pytest

from webapp.transport import NullTransport, TransportError
from webapp.plateau import PlateauBridge


class FakeTransport:
    """Transport en mémoire pour tests : on contrôle ce qu'il lit, on capture ce qu'il écrit."""

    def __init__(self):
        self.written: list[str] = []
        self.to_read: list[str] = []  # queue de lignes que read_line va retourner
        self.opened = False
        self._read_lock = threading.Lock()

    def open(self) -> None:
        self.opened = True

    def write_line(self, line: str) -> None:
        if not self.opened:
            raise TransportError("not open")
        self.written.append(line)

    def read_line(self, timeout: float = 1.0) -> str | None:
        with self._read_lock:
            if self.to_read:
                return self.to_read.pop(0)
        time.sleep(min(timeout, 0.01))
        return None

    def close(self) -> None:
        self.opened = False

    @property
    def is_alive(self) -> bool:
        return self.opened

    @property
    def description(self) -> str:
        return "fake"


def test_plateau_bridge_init_with_transport():
    t = FakeTransport()
    t.open()
    b = PlateauBridge(transport=t)
    assert b.transport is t
    assert b.available is True


def test_plateau_bridge_init_with_null_transport():
    t = NullTransport()
    t.open()
    b = PlateauBridge(transport=t)
    assert b.available is False  # NullTransport.is_alive = False


def test_plateau_bridge_send_command_serializes_write_then_read():
    """Une commande envoie une ligne puis lit la réponse, dans le lock."""
    t = FakeTransport()
    t.open()
    t.to_read.append("PONG")
    b = PlateauBridge(transport=t)
    reply = b.send_command("PING", timeout=1.0)
    assert reply == "PONG"
    assert t.written == ["PING"]


def test_plateau_bridge_send_command_concurrent_serialized():
    """Deux send_command depuis 2 threads ne doivent pas s'entrelacer."""
    t = FakeTransport()
    t.open()
    t.to_read.extend(["PONG", "OK"])
    b = PlateauBridge(transport=t)
    results = []

    def call(cmd):
        results.append(b.send_command(cmd, timeout=1.0))

    threads = [threading.Thread(target=call, args=(c,)) for c in ["PING", "WALL"]]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    # Les écritures ne se sont pas entrelacées : ce sont des lignes entières
    assert set(t.written) == {"PING", "WALL"}
    assert set(results) == {"PONG", "OK"}


def test_plateau_bridge_send_command_timeout_returns_none():
    t = FakeTransport()
    t.open()
    # rien dans to_read
    b = PlateauBridge(transport=t)
    reply = b.send_command("PING", timeout=0.05)
    assert reply is None


def test_plateau_bridge_close():
    t = FakeTransport()
    t.open()
    b = PlateauBridge(transport=t)
    b.close()
    assert t.opened is False


def test_plateau_bridge_starts_heartbeat_thread():
    t = FakeTransport()
    t.open()
    t.to_read.extend(["PONG"] * 100)  # toujours répond
    b = PlateauBridge(transport=t, heartbeat_interval=0.1)
    b.start_heartbeat()
    time.sleep(0.35)  # 3 cycles environ
    b.stop_heartbeat()
    # Au moins 2 PING envoyés
    pings = [w for w in t.written if w == "PING"]
    assert len(pings) >= 2
    assert b.last_pong_at is not None
    assert b.failed_pings == 0


def test_plateau_bridge_heartbeat_detects_lost_after_2_failures():
    t = FakeTransport()
    t.open()
    # rien dans to_read → PONG manqué
    b = PlateauBridge(transport=t, heartbeat_interval=0.05, pong_timeout=0.05)
    b.start_heartbeat()
    time.sleep(0.5)  # 5+ cycles de 0.05+0.05
    b.stop_heartbeat()
    assert b.failed_pings >= 2
    assert b.transport_lost is True


def test_plateau_bridge_latency_avg_updated_on_pong():
    t = FakeTransport()
    t.open()
    t.to_read.extend(["PONG"] * 100)
    b = PlateauBridge(transport=t, heartbeat_interval=0.05)
    b.start_heartbeat()
    time.sleep(0.25)
    b.stop_heartbeat()
    assert b.latency_avg_ms is not None
    assert b.latency_avg_ms >= 0
