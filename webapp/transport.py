"""Abstraction Transport : canal bidirectionnel ligne par ligne vers l'ESP32.

Deux implémentations : SerialTransport (USB-série) et WiFiTransport (TCP).
Plus NullTransport pour le mode autonome explicite.

Tous les transports parlent le même protocole texte ligne par ligne (UTF-8),
ce qui permet à la couche haute (PlateauBridge) de rester agnostique.
"""
from __future__ import annotations

import glob
import logging
import os
import platform
import socket
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


class WiFiTransport(Transport):
    """Transport TCP brut vers l'ESP32 en mode AP.

    Connexion à 192.168.4.1:3333 par défaut. Protocole ligne par ligne, UTF-8.
    Buffer interne pour gérer les chunks TCP coupés au milieu d'une ligne.
    """

    def __init__(
        self,
        host: str = "192.168.4.1",
        port: int = 3333,
        connect_timeout: float = 3.0,
    ):
        self._host = host
        self._port = port
        self._connect_timeout = connect_timeout
        self._sock: socket.socket | None = None
        self._rx_buffer = bytearray()

    def open(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._connect_timeout)
            sock.connect((self._host, self._port))
            # Désactive Nagle : la webapp envoie des commandes courtes et attend
            # la réponse, on veut zéro délai d'agrégation.
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            # Active TCP keep-alive pour détecter rapidement les coupures Wi-Fi.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.settimeout(0.1)  # lecture par défaut, ajustée par read_line
            self._sock = sock
        except (OSError, socket.timeout) as e:
            raise TransportError(
                f"connexion {self._host}:{self._port} échouée : {e}"
            ) from e

    def write_line(self, line: str) -> None:
        if self._sock is None:
            raise TransportError("WiFiTransport non ouvert")
        try:
            self._sock.sendall((line + "\n").encode("utf-8"))
        except OSError as e:
            raise TransportError(f"écriture TCP échouée : {e}") from e

    def read_line(self, timeout: float = 1.0) -> str | None:
        if self._sock is None:
            return None
        # Si une ligne complète est déjà dans le buffer, la retourner directement
        if b"\n" in self._rx_buffer:
            return self._pop_line()
        try:
            self._sock.settimeout(timeout)
            while b"\n" not in self._rx_buffer:
                chunk = self._sock.recv(256)
                if not chunk:  # connexion fermée par le pair
                    return None
                self._rx_buffer.extend(chunk)
        except socket.timeout:
            return None
        except OSError:
            return None
        return self._pop_line()

    def _pop_line(self) -> str:
        line, _, rest = self._rx_buffer.partition(b"\n")
        self._rx_buffer = bytearray(rest)
        return line.decode("utf-8", errors="replace").rstrip("\r")

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._rx_buffer.clear()

    @property
    def is_alive(self) -> bool:
        return self._sock is not None

    @property
    def description(self) -> str:
        return f"wifi {self._host}:{self._port}"


def make_transport() -> Transport:
    """Construit le Transport selon la variable d'env QUORIDOR_TRANSPORT.

    Valeurs acceptées (case-insensitive) : 'wifi', 'serial', 'none'.
    Défaut : 'wifi'.
    """
    kind = os.environ.get("QUORIDOR_TRANSPORT", "wifi").lower()
    if kind == "wifi":
        return WiFiTransport()
    if kind == "serial":
        return SerialTransport()
    if kind == "none":
        return NullTransport()
    raise ValueError(
        f"QUORIDOR_TRANSPORT invalide : {kind!r} (attendu : wifi|serial|none)"
    )
