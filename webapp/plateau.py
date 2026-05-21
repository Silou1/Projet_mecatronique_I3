"""Couche haute au-dessus de Transport : heartbeat, lock TX, switch.

PlateauBridge remplace l'ancien UartBridge. Elle :
- détient un Transport (Serial/WiFi/Null)
- sérialise toutes les commandes via _tx_lock (un seul write+read à la fois)
- maintient les compteurs heartbeat (last_pong_at, latency_avg, failed_pings)
- gère le switch_transport sans redémarrer la webapp

La gestion du heartbeat thread et de la reconnexion auto vient en Task C2 et C3.
Le switch_transport vient en Task C4.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from webapp.transport import Transport, TransportError

log = logging.getLogger(__name__)


class PlateauBridge:
    """Couche haute pour parler à l'ESP32 via un Transport.

    Sérialise les commandes (write_line puis read_line) via un lock thread-safe.
    """

    def __init__(self, transport: Transport):
        self._transport = transport
        self._tx_lock = threading.Lock()

    @property
    def transport(self) -> Transport:
        return self._transport

    @property
    def available(self) -> bool:
        """True si le transport est ouvert et présumé fonctionnel."""
        return self._transport.is_alive

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

    def close(self) -> None:
        """Ferme le transport sous-jacent."""
        self._transport.close()
