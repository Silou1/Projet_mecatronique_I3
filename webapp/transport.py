"""Abstraction Transport : canal bidirectionnel ligne par ligne vers l'ESP32.

Deux implémentations : SerialTransport (USB-série) et WiFiTransport (TCP).
Plus NullTransport pour le mode autonome explicite.

Tous les transports parlent le même protocole texte ligne par ligne (UTF-8),
ce qui permet à la couche haute (PlateauBridge) de rester agnostique.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


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
