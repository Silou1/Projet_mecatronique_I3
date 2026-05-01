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

    @staticmethod
    def decode(raw: bytes) -> "Frame":
        """Decode une trame brute en Frame. Leve UartProtocolError si malformee.

        raw : octets de la trame, avec ou sans \\n final, avec les delimiteurs <>.
        """
        # Strip eventuel \n final et \r
        if raw.endswith(b"\n"):
            raw = raw[:-1]
        if raw.endswith(b"\r"):
            raw = raw[:-1]

        # Verifie longueur max
        if len(raw) > 80:
            raise UartProtocolError(f"trame trop longue ({len(raw)} > 80 octets)")

        # Verifie delimiteurs
        if not raw.startswith(b"<") or not raw.endswith(b">"):
            raise UartProtocolError("delimiteurs <> manquants ou mal places")

        # Retire <>
        inner = raw[1:-1].decode("ascii", errors="strict")

        # Split sur '|'
        parts = inner.split("|")
        if len(parts) < 2:
            raise UartProtocolError("trame sans champs metadata")

        # Premier champ : TYPE [args]
        head = parts[0]
        if " " in head:
            type_str, args_str = head.split(" ", 1)
        else:
            type_str = head
            args_str = ""

        # Verifie que TYPE est en majuscules valides
        if not type_str or not all(c.isupper() or c.isdigit() or c == "_" for c in type_str):
            raise UartProtocolError(f"TYPE invalide : {type_str!r}")

        # Le dernier champ doit etre crc=XXXX
        crc_field = parts[-1]
        if not crc_field.startswith("crc="):
            raise UartProtocolError("champ crc= manquant en fin")
        crc_value = crc_field[4:]
        if len(crc_value) != 4 or crc_value != crc_value.upper():
            raise UartProtocolError(f"format crc invalide : {crc_value!r}")
        try:
            crc_int = int(crc_value, 16)
        except ValueError:
            raise UartProtocolError(f"crc non hexadecimal : {crc_value!r}")

        # Champs intermediaires : seq= obligatoire, ack= et v= optionnels
        seq = None
        ack = None
        version = None
        for field in parts[1:-1]:
            if field.startswith("seq="):
                try:
                    seq = int(field[4:])
                except ValueError:
                    raise UartProtocolError(f"seq non numerique : {field!r}")
                if not (0 <= seq <= 255):
                    raise UartProtocolError(f"seq hors plage : {seq}")
            elif field.startswith("ack="):
                try:
                    ack = int(field[4:])
                except ValueError:
                    raise UartProtocolError(f"ack non numerique : {field!r}")
                if not (0 <= ack <= 255):
                    raise UartProtocolError(f"ack hors plage : {ack}")
            elif field.startswith("v="):
                try:
                    version = int(field[2:])
                except ValueError:
                    raise UartProtocolError(f"v non numerique : {field!r}")
            else:
                raise UartProtocolError(f"champ inconnu : {field!r}")

        if seq is None:
            raise UartProtocolError("champ seq= manquant")

        # Verifie le CRC sur la zone (TYPE [args]|seq=N[|ack=M][|v=K])
        crc_zone = inner.rsplit("|crc=", 1)[0]
        computed = compute_crc(crc_zone.encode("ascii"))
        if computed != crc_int:
            raise UartProtocolError(
                f"CRC invalide : recu 0x{crc_int:04X}, calcule 0x{computed:04X}"
            )

        return Frame(type=type_str, args=args_str, seq=seq, ack=ack, version=version)


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
