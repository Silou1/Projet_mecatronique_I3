"""Abstraction Transport : canal bidirectionnel ligne par ligne vers l'ESP32.

Deux implémentations : SerialTransport (USB-série) et WiFiTransport (TCP).
Plus NullTransport pour le mode autonome explicite.

Tous les transports parlent le même protocole texte ligne par ligne (UTF-8),
ce qui permet à la couche haute (PlateauBridge) de rester agnostique.
"""
from __future__ import annotations

import glob
import logging
import platform
import time
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class TransportError(Exception):
    """Erreur de transport (connexion impossible, coupure, encodage, etc.)."""


class Transport(ABC):
    """Canal bidirectionnel ligne par ligne vers l'ESP32."""

    @abstractmethod
    def open(self) -> None:
        """Établit la connexion. Lève TransportError si échec."""

    @abstractmethod
    def write_line(self, line: str) -> None:
        """Envoie une ligne (le \\n est ajouté automatiquement, UTF-8).

        Lève TransportError si l'écriture échoue.
        """

    @abstractmethod
    def read_line(self, timeout: float = 1.0) -> str | None:
        """Lit une ligne (sans \\n). Retourne None si timeout."""

    @abstractmethod
    def close(self) -> None:
        """Ferme proprement le canal. Idempotent."""

    @property
    @abstractmethod
    def is_alive(self) -> bool:
        """True si le canal est ouvert et présumé fonctionnel."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Description lisible pour le panneau Statut.

        Ex: 'wifi 192.168.4.1:3333' ou 'serial /dev/cu.usbserial-110'.
        """


class NullTransport(Transport):
    """Transport qui ne fait rien. Mode autonome explicite.

    Sert à éviter les Optional[Transport] partout dans le service.
    Toute tentative d'écriture lève TransportError.
    """

    def open(self) -> None:
        pass

    def write_line(self, line: str) -> None:
        raise TransportError("NullTransport : écriture impossible en mode autonome")

    def read_line(self, timeout: float = 1.0) -> str | None:
        return None

    def close(self) -> None:
        pass

    @property
    def is_alive(self) -> bool:
        return False

    @property
    def description(self) -> str:
        return "none (mode autonome)"


def _find_serial_ports() -> list[str]:
    """Cherche les ports série DevKit ESP32.

    Mac : /dev/cu.usbserial-*
    Linux : /dev/ttyUSB*, /dev/ttyAMA*
    """
    if platform.system() == "Darwin":
        return sorted(glob.glob("/dev/cu.usbserial-*"))
    ports = sorted(glob.glob("/dev/ttyUSB*"))
    if not ports:
        ports = sorted(glob.glob("/dev/ttyAMA*"))
    return ports


def _open_serial(port: str, baud: int):
    """Wrapper isolable (pour faciliter le mocking en tests)."""
    import serial
    return serial.Serial(port, baud, timeout=0.1, write_timeout=1.0)


class SerialTransport(Transport):
    """Transport USB-série via pyserial.

    Détection auto du port si non précisé (premier /dev/cu.usbserial-* sur Mac).
    """

    def __init__(self, port: str | None = None, baud: int = 115200):
        if port is None:
            ports = _find_serial_ports()
            self._port = ports[0] if ports else None
        else:
            self._port = port
        self._baud = baud
        self._serial = None
        self._rx_buffer = bytearray()

    def open(self) -> None:
        if self._port is None:
            raise TransportError("aucun port série DevKit ESP32 détecté")
        try:
            self._serial = _open_serial(self._port, self._baud)
        except Exception as e:
            raise TransportError(f"ouverture {self._port} échouée : {e}") from e

    def write_line(self, line: str) -> None:
        if self._serial is None:
            raise TransportError("SerialTransport non ouvert")
        try:
            self._serial.write((line + "\n").encode("utf-8"))
            self._serial.flush()
        except Exception as e:
            raise TransportError(f"écriture série échouée : {e}") from e

    def read_line(self, timeout: float = 1.0) -> str | None:
        if self._serial is None:
            return None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # Bloque jusqu'au prochain octet ou timeout pyserial (0.1s)
            chunk = self._serial.read(self._serial.in_waiting or 1)
            if chunk:
                self._rx_buffer.extend(chunk)
                if b"\n" in self._rx_buffer:
                    line, _, rest = self._rx_buffer.partition(b"\n")
                    self._rx_buffer = bytearray(rest)
                    return line.decode("utf-8", errors="replace").rstrip("\r")
        return None

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    @property
    def is_alive(self) -> bool:
        return self._serial is not None

    @property
    def description(self) -> str:
        return f"serial {self._port or 'aucun port détecté'}"
