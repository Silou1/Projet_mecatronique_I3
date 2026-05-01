"""Client UART pour le protocole Plan 2 entre Raspberry Pi et ESP32.

Voir docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md
"""

import binascii


def compute_crc(data: bytes) -> int:
    """Calcule le CRC-16 CCITT-FALSE sur les octets fournis.

    Polynome 0x1021, valeur initiale 0xFFFF, sans reflexion, sans XOR final.
    Retourne un entier non signe sur 16 bits.
    """
    return binascii.crc_hqx(data, 0xFFFF)


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
