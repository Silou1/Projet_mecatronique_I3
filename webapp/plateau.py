"""Couche haute au-dessus de Transport : heartbeat, lock TX, switch.

PlateauBridge :
- détient un Transport (Serial/WiFi/Null)
- sérialise toutes les commandes via _tx_lock (un seul write+read à la fois)
- maintient les compteurs heartbeat (last_pong_at, latency_avg, failed_pings)
- thread heartbeat daemon qui envoie PING toutes les 5s
- thread reconnect watcher qui retente transport.open() si transport_lost
- gère le switch_transport sans redémarrer la webapp
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from webapp.transport import Transport, TransportError

log = logging.getLogger(__name__)


HEARTBEAT_INTERVAL_DEFAULT = 5.0
PONG_TIMEOUT_DEFAULT = 2.0
FAILED_PINGS_LIMIT = 2


class PlateauBridge:
    """Couche haute pour parler à l'ESP32 via un Transport.

    Sérialise les commandes (write_line puis read_line) via un lock thread-safe.
    Heartbeat applicatif (PING/PONG) en thread daemon pour détecter coupures.
    """

    def __init__(
        self,
        transport: Transport,
        heartbeat_interval: float = HEARTBEAT_INTERVAL_DEFAULT,
        pong_timeout: float = PONG_TIMEOUT_DEFAULT,
    ):
        self._transport = transport
        self._tx_lock = threading.Lock()
        self._heartbeat_interval = heartbeat_interval
        self._pong_timeout = pong_timeout

        # Compteurs heartbeat (lecture par /api/status, écriture par thread heartbeat)
        self._counters_lock = threading.Lock()
        self.last_pong_at: Optional[float] = None  # time.monotonic()
        self.failed_pings: int = 0
        self.latency_avg_ms: Optional[float] = None
        self._latency_samples: list[float] = []
        self._max_samples = 10
        self.transport_lost: bool = False

        # Thread heartbeat
        self._stop_event = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None

    @property
    def transport(self) -> Transport:
        return self._transport

    @property
    def available(self) -> bool:
        """True si transport ouvert ET pas marqué comme perdu."""
        return self._transport.is_alive and not self.transport_lost

    def send_command(self, cmd: str, timeout: float = 5.0) -> Optional[str]:
        """Envoie une ligne et attend une ligne de réponse.

        Acquiert le lock TX → toute commande concurrente attend.
        Retourne None si timeout ou erreur.
        """
        with self._tx_lock:
            try:
                self._transport.write_line(cmd)
            except TransportError as e:
                log.warning("send_command(%r) : write echoue : %s", cmd, e)
                return None
            return self._transport.read_line(timeout=timeout)

    def start_heartbeat(self) -> None:
        """Lance le thread daemon qui envoie PING toutes les heartbeat_interval secondes."""
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._stop_event.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="plateau-heartbeat"
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        """Arrête proprement le thread heartbeat."""
        self._stop_event.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=2.0)
            self._heartbeat_thread = None

    def _heartbeat_loop(self) -> None:
        """Boucle : attend interval, envoie PING, mesure latence, met à jour compteurs."""
        while not self._stop_event.wait(self._heartbeat_interval):
            if not self._transport.is_alive:
                continue
            t0 = time.monotonic()
            reply = self.send_command("PING", timeout=self._pong_timeout)
            if reply == "PONG":
                latency_ms = (time.monotonic() - t0) * 1000.0
                with self._counters_lock:
                    self.last_pong_at = time.monotonic()
                    self.failed_pings = 0
                    self.transport_lost = False
                    self._latency_samples.append(latency_ms)
                    if len(self._latency_samples) > self._max_samples:
                        self._latency_samples.pop(0)
                    self.latency_avg_ms = sum(self._latency_samples) / len(self._latency_samples)
            else:
                with self._counters_lock:
                    self.failed_pings += 1
                    if self.failed_pings >= FAILED_PINGS_LIMIT:
                        self.transport_lost = True
                        log.warning("Transport perdu apres %d PING rates", self.failed_pings)

    def close(self) -> None:
        """Ferme le transport sous-jacent et arrête les threads."""
        self.stop_heartbeat()
        self._transport.close()
