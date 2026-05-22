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
# 2026-05-22 : 2 -> 5. En Wi-Fi le HOME peut bloquer le loop() ESP32 ~5-15 s,
# les PING peuvent timeout transitoirement sans que le transport soit mort.
# Seuil plus large evite un transport_lost premature qui fermerait la socket
# pendant qu'une reponse longue est en transit.
FAILED_PINGS_LIMIT = 5


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
        reconnect_interval: float = HEARTBEAT_INTERVAL_DEFAULT * 2,
    ):
        self._transport = transport
        self._tx_lock = threading.Lock()
        self._heartbeat_interval = heartbeat_interval
        self._pong_timeout = pong_timeout
        self._reconnect_interval = reconnect_interval

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

        # Reconnect watcher
        self._reconnect_stop = threading.Event()
        self._reconnect_thread: Optional[threading.Thread] = None

        # Callbacks declenches apres une reconnexion reussie (LedRenderer, etc.)
        self._on_reconnect_callbacks: list = []

    @property
    def transport(self) -> Transport:
        return self._transport

    @property
    def available(self) -> bool:
        """True si transport ouvert ET pas marqué comme perdu."""
        return self._transport.is_alive and not self.transport_lost

    def add_on_reconnect_callback(self, callback) -> None:
        """Enregistre un callback a appeler quand la connexion est retablie."""
        self._on_reconnect_callbacks.append(callback)

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

    def send_command_await(
        self,
        cmd: str,
        accept_prefixes: tuple[str, ...],
        timeout: float = 10.0,
    ) -> Optional[str]:
        """Envoie une commande et lit les lignes jusqu'à un ACK matching un préfixe.

        Sert pour HOME, WALL, LED, PING : le firmware émet des logs verbeux
        (`GOTO ...`, `servo 0 deg`, `=== HOME ===`, etc.) puis termine par une
        ligne ACK. Cette méthode skip les verbeux (loggés en debug) et retourne
        la première ligne dont le préfixe matche.

        Acquiert le lock TX → toute commande concurrente attend.
        Tout match d'ACK déclenche `_mark_alive_unlocked()` : un round-trip
        réussi prouve que le canal est sain, donc reset des compteurs PING ratés
        et levée du flag transport_lost si actif.
        Retourne None si timeout total dépassé ou écriture échouée.
        """
        with self._tx_lock:
            try:
                self._transport.write_line(cmd)
            except TransportError as e:
                log.warning("send_command_await(%r) : write echoue : %s", cmd, e)
                return None
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    log.warning(
                        "send_command_await(%r) : timeout (aucun ACK match %r)",
                        cmd, accept_prefixes,
                    )
                    return None
                line = self._transport.read_line(timeout=min(0.5, remaining))
                if line is None:
                    continue  # rien lu cette tranche, on retente jusqu'à deadline
                if any(line.startswith(p) for p in accept_prefixes):
                    self._mark_alive()
                    return line
                log.debug("send_command_await(%r) : verbeux ignore %r", cmd, line)

    def _mark_alive(self) -> None:
        """Indique que le canal est sain après un round-trip réussi.

        Reset failed_pings, met à jour last_pong_at, et lève transport_lost si
        actif. Appelé après chaque ACK valide dans send_command_await.
        """
        was_lost = False
        with self._counters_lock:
            if self.transport_lost:
                was_lost = True
                self.transport_lost = False
            self.failed_pings = 0
            self.last_pong_at = time.monotonic()
        if was_lost:
            log.info("Reconnexion confirmee par round-trip, notification des abonnes")
            for cb in self._on_reconnect_callbacks:
                try:
                    cb()
                except Exception as e:  # noqa: BLE001
                    log.warning("Callback on_reconnect echoue (%s)", e)

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
        """Boucle : attend interval, envoie PING, mesure latence, met à jour compteurs.

        Skip le PING si une commande métier (WALL/HOME/LED) tient déjà le lock
        TX : le round-trip applicatif en cours sert lui-même de heartbeat (il
        appellera _mark_alive() en cas d'ACK). Évite les faux positifs où un
        WALL de 10 s ferait timeout 2 PING successifs.
        """
        while not self._stop_event.wait(self._heartbeat_interval):
            if not self._transport.is_alive:
                continue
            # Si une commande métier tient le lock, ne pas la perturber.
            # Elle appellera _mark_alive() à la fin et reset les compteurs.
            if self._tx_lock.locked():
                log.debug("heartbeat skip : commande metier en cours")
                continue
            t0 = time.monotonic()
            # send_command_await drain les eventuels verbeux residuels avant PONG.
            reply = self.send_command_await(
                "PING", accept_prefixes=("PONG",), timeout=self._pong_timeout,
            )
            if reply == "PONG":
                latency_ms = (time.monotonic() - t0) * 1000.0
                with self._counters_lock:
                    # _mark_alive() a déjà fait le reset des compteurs et levé
                    # transport_lost. Ici on ne touche qu'à la moyenne latence.
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

    def start_reconnect_watcher(self) -> None:
        """Lance le thread daemon qui retente transport.open() si transport_lost."""
        if self._reconnect_thread is not None and self._reconnect_thread.is_alive():
            return
        self._reconnect_stop.clear()
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop, daemon=True, name="plateau-reconnect"
        )
        self._reconnect_thread.start()

    def stop_reconnect_watcher(self) -> None:
        self._reconnect_stop.set()
        if self._reconnect_thread is not None:
            self._reconnect_thread.join(timeout=2.0)
            self._reconnect_thread = None

    def _reconnect_loop(self) -> None:
        """Boucle : attend interval, si transport_lost tente close()+open().

        Acquiert _tx_lock pendant close+open pour eviter qu'un PING heartbeat
        soit envoye pendant que le transport est temporairement ferme.
        """
        while not self._reconnect_stop.wait(self._reconnect_interval):
            if not self.transport_lost:
                continue
            log.info("Tentative de reconnexion %s ...", self._transport.description)
            with self._tx_lock:
                try:
                    self._transport.close()
                    self._transport.open()
                    log.info("Reconnexion reussie. Le heartbeat va valider via PING.")
                except TransportError as e:
                    log.info("Reconnexion echouee : %s", e)

    def status_dict(self) -> dict:
        """Snapshot des compteurs heartbeat, serialisable JSON."""
        import datetime as _dt
        with self._counters_lock:
            last_pong_iso = None
            last_pong_age = None
            if self.last_pong_at is not None:
                last_pong_age = max(0.0, time.monotonic() - self.last_pong_at)
                last_pong_iso = (
                    _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(seconds=last_pong_age)
                ).isoformat()
            return {
                "description": self._transport.description,
                "alive": self.available,
                "last_pong_at_iso": last_pong_iso,
                "last_pong_age_seconds": last_pong_age,
                "latency_avg_ms": self.latency_avg_ms,
                "transport_lost": self.transport_lost,
                "failed_pings": self.failed_pings,
            }

    def switch_transport(self, new_transport: Transport) -> None:
        """Bascule vers un nouveau transport en cours d'execution.

        Acquiert _tx_lock -> attend la fin d'une commande en cours.
        Ouvre le nouveau transport. Si l'open() echoue, l'ancien reste actif.
        Sinon, ferme l'ancien et bascule, puis reinitialise les compteurs heartbeat.
        """
        with self._tx_lock:
            new_transport.open()  # leve TransportError si echec -> l'ancien reste actif
            old = self._transport
            self._transport = new_transport
            try:
                old.close()
            except Exception:  # noqa: BLE001
                pass
            with self._counters_lock:
                self.last_pong_at = None
                self.failed_pings = 0
                self.latency_avg_ms = None
                self._latency_samples = []
                self.transport_lost = False
            log.info("Bascule transport : %s", new_transport.description)

    def close(self) -> None:
        """Ferme le transport sous-jacent et arrête les threads."""
        self.stop_heartbeat()
        self.stop_reconnect_watcher()
        self._transport.close()
