"""Wrapper optionnel autour de UartClient pour mirrorer les coups sur le plateau.

Detection au boot : si un port est trouvé et le handshake passe, le bridge est
actif. Sinon, init() retourne None et la web app reste 100 % autonome.

Erreur en cours de partie : log + désactivation locale (available=False). Pas
de tentative de reconnexion (cf. spec §10.4).
"""
from __future__ import annotations

import glob
import logging
import platform
from typing import Optional

log = logging.getLogger(__name__)


def _find_devkit_port() -> Optional[str]:
    """Cherche le port série du DevKit/PCB ESP32.

    Mac : /dev/cu.usbserial-*
    Linux/RPi : /dev/ttyUSB* puis /dev/ttyAMA*
    """
    system = platform.system()
    if system == "Darwin":
        ports = sorted(glob.glob("/dev/cu.usbserial-*"))
    else:
        ports = sorted(glob.glob("/dev/ttyUSB*"))
        if not ports:
            ports = sorted(glob.glob("/dev/ttyAMA*"))
    return ports[0] if ports else None


def _open_client(port: str):
    """Ouvre un UartClient et fait le handshake. Lève une exception si KO."""
    from quoridor_engine import UartClient
    client = UartClient(port)
    client.connect()
    return client


def init() -> Optional["UartBridge"]:
    """Tente de détecter et d'ouvrir le port UART.

    Returns:
        UartBridge si succès, None sinon.
    """
    port = _find_devkit_port()
    if port is None:
        log.info("UartBridge: aucun port detecte, mode autonome.")
        return None
    try:
        client = _open_client(port)
    except Exception as e:  # noqa: BLE001
        log.warning("UartBridge: handshake echoue sur %s (%s), mode autonome.", port, e)
        return None
    log.info("UartBridge: connecte sur %s.", port)
    return UartBridge(client)


class UartBridge:
    """Mirror best-effort des coups vers le firmware ESP32.

    En cas d'erreur (timeout, port mort, etc.), `available` passe à False
    et les forwards suivants sont no-op silencieux.
    """

    def __init__(self, client):
        self._client = client
        self.available: bool = True

    def forward_move(self, move: tuple) -> None:
        """Envoie un coup au plateau. No-op si indisponible.

        En cas d'erreur, log et désactive `available`. Ne lève PAS.

        Args:
            move: tuple (move_type, payload) où :
                  - move_type == 'deplacement' : payload['target'] = [row, col]
                  - move_type == 'mur' : payload['orientation'], ['row'], ['col']
        """
        if not self.available:
            return
        move_type, payload = move
        try:
            if move_type == "deplacement":
                r, c = payload["target"]
                self._client.send_cmd("PAWN", f"{r} {c}")
            elif move_type == "mur":
                self._client.send_cmd(
                    "WALL",
                    f"{payload['orientation']} {payload['row']} {payload['col']}",
                )
            else:
                log.warning("UartBridge: type de coup inconnu %r, ignore.", move_type)
                return
        except Exception as e:  # noqa: BLE001
            log.warning("UartBridge: forward echoue (%s), desactivation mirroring.", e)
            self.available = False

    def close(self) -> None:
        """Ferme proprement la connexion UART."""
        try:
            if hasattr(self._client, "close"):
                self._client.close()
        except Exception:  # noqa: BLE001
            pass
