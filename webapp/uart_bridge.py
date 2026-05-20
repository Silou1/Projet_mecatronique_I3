"""Wrapper texte brut autour de pyserial pour mirroir les coups au plateau.

Detection au boot : ouvre le port serie du DevKit ESP32 et fait un PING/PONG.
Si PONG recu dans le delai, le bridge est actif. Sinon, init() retourne None
et la webapp reste en mode autonome.

Erreur en cours de partie : log + desactivation locale (available=False).
Pas de tentative de reconnexion (cf. spec demo § 10.4).
"""
from __future__ import annotations

import glob
import logging
import platform
import time
from typing import Optional

import serial

log = logging.getLogger(__name__)

PING_TIMEOUT_S = 5.0
PING_RETRY_INTERVAL_S = 0.5


def _find_devkit_port() -> Optional[str]:
    """Cherche le port serie du DevKit ESP32.

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


def _open_and_handshake(port: str) -> Optional[serial.Serial]:
    """Ouvre le port et fait un PING/PONG. Retourne serial ouvert ou None."""
    try:
        s = serial.Serial(port, 115200, timeout=PING_RETRY_INTERVAL_S, write_timeout=1.0)
    except Exception as e:  # noqa: BLE001
        log.warning("UartBridge: ouverture port %s echouee : %s", port, e)
        return None

    deadline = time.monotonic() + PING_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            s.reset_input_buffer()
            s.write(b"PING\n")
            s.flush()
            line = s.readline()
            if b"PONG" in line:
                return s
        except Exception as e:  # noqa: BLE001
            log.warning("UartBridge: PING echoue (%s)", e)
            try:
                s.close()
            except Exception:  # noqa: BLE001
                pass
            return None

    log.info("UartBridge: aucun PONG recu sur %s apres %.1fs.", port, PING_TIMEOUT_S)
    try:
        s.close()
    except Exception:  # noqa: BLE001
        pass
    return None


def init() -> Optional["UartBridge"]:
    """Tente de detecter et d'ouvrir le port UART."""
    port = _find_devkit_port()
    if port is None:
        log.info("UartBridge: aucun port detecte, mode autonome.")
        return None
    s = _open_and_handshake(port)
    if s is None:
        return None
    log.info("UartBridge: connecte sur %s.", port)
    return UartBridge(s)


class UartBridge:
    """Mirror best-effort des coups vers le firmware ESP32 (texte brut).

    En cas d'erreur (timeout, port mort, etc.), `available` passe a False
    et les forwards suivants sont no-op silencieux.
    """

    def __init__(self, serial_obj: serial.Serial):
        self._serial = serial_obj
        self.available: bool = True

    def forward_move(self, move: tuple) -> None:
        """Envoie un coup au plateau. No-op si indisponible ou si deplacement de pion.

        En cas d'erreur, log et desactive `available`. Ne leve PAS.

        Args:
            move: tuple (move_type, payload) ou :
                  - move_type == 'deplacement' : no-op (pas de systeme pion physique)
                  - move_type == 'mur' : payload['orientation'], ['row'], ['col']
        """
        if not self.available:
            return
        move_type, payload = move
        try:
            if move_type == "mur":
                # Inversion H<->V : le plateau physique a une convention d'orientation
                # inverse de celle de l'engine Quoridor (mesure manuelle de la matrice).
                _SWAP = {"H": "V", "V": "H"}
                orientation = _SWAP[payload["orientation"].upper()]
                row = int(payload["row"])
                col = int(payload["col"])
                line = f"WALL {orientation} {row} {col}\n"
                self._serial.write(line.encode("ascii"))
                self._serial.flush()
            elif move_type == "deplacement":
                # No-op : pas de systeme physique de deplacement de pion pour ce demo.
                return
            else:
                log.warning("UartBridge: type de coup inconnu %r, ignore.", move_type)
        except Exception as e:  # noqa: BLE001
            log.warning("UartBridge: forward echoue (%s), desactivation mirroring.", e)
            self.available = False

    def send_home(self) -> None:
        """Envoie une commande HOME au plateau pour ré-homing au début d'une partie.

        No-op si indisponible. En cas d'erreur, désactive le bridge.
        """
        if not self.available:
            return
        try:
            self._serial.write(b"HOME\n")
            self._serial.flush()
        except Exception as e:  # noqa: BLE001
            log.warning("UartBridge: HOME echoue (%s), desactivation mirroring.", e)
            self.available = False

    def close(self) -> None:
        """Ferme proprement la connexion UART."""
        try:
            self._serial.close()
        except Exception:  # noqa: BLE001
            pass
