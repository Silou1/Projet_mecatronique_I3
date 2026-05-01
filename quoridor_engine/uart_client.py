"""Client UART pour le protocole Plan 2 entre Raspberry Pi et ESP32.

Voir docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md
"""

import binascii
from dataclasses import dataclass
from typing import Optional


def compute_crc(data: bytes) -> int:
    """Calcule le CRC-16 CCITT-FALSE sur les octets fournis.

    Polynome 0x1021, valeur initiale 0xFFFF, sans reflexion, sans XOR final.
    Retourne un entier non signe sur 16 bits.
    """
    return binascii.crc_hqx(data, 0xFFFF)


@dataclass
class Frame:
    """Une trame protocolaire decodee ou en cours d'encodage.

    type    : nom de la trame en MAJUSCULES (MOVE_REQ, ACK, CMD, ...)
    args    : arguments serializes en chaine (vide si pas d'arg)
    seq     : numero de sequence de l'emetteur (0-255)
    ack     : seq de la requete a laquelle on repond (None sinon)
    version : numero de version, present uniquement sur HELLO
    """
    type: str
    args: str
    seq: int
    ack: Optional[int] = None
    version: Optional[int] = None

    def encode(self) -> bytes:
        """Serialize la trame au format <TYPE [args]|seq=N[|ack=M][|v=K]|crc=XXXX>\\n."""
        # Construit la zone CRC (entre '<' et '|crc=')
        body = self.type
        if self.args:
            body += " " + self.args
        body += f"|seq={self.seq}"
        if self.ack is not None:
            body += f"|ack={self.ack}"
        if self.version is not None:
            body += f"|v={self.version}"

        crc = compute_crc(body.encode("ascii"))
        crc_str = f"{crc:04X}"  # 4 chars hex MAJUSCULES, padde a gauche

        return f"<{body}|crc={crc_str}>\n".encode("ascii")


class UartError(Exception):
    """Base pour toutes les erreurs UART."""


class UartTimeoutError(UartError):
    """Levee apres 3 essais CMD sans DONE."""


class UartProtocolError(UartError):
    """Levee si le pic de trames mal formees depasse un seuil anormal."""


class UartVersionError(UartError):
    """Levee si HELLO v=K recu ne correspond pas a la version Python attendue."""


class UartHardwareError(UartError):
    """Levee a la reception d'un ERR non-recuperable de l'ESP32."""

    def __init__(self, code: str, message: str = ""):
        self.code = code
        full_msg = f"{code}" if not message else f"{code}: {message}"
        super().__init__(full_msg)
