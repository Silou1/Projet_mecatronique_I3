"""Client UART pour le protocole Plan 2 entre Raspberry Pi et ESP32.

Voir docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md
"""

import binascii
import queue
import threading
import time as _time
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


class UartClient:
    """Client UART Plan 2 cote Raspberry Pi (Python).

    Voir docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md
    """

    PROTOCOL_VERSION = 1
    MAX_DEBUG_LINES = 200  # buffer circulaire pour les logs ESP32

    def __init__(
        self,
        serial_port,
        clock=None,
        expected_version: int = PROTOCOL_VERSION,
    ):
        """
        serial_port : objet compatible serial.Serial (avec write/read/readline/in_waiting/close)
        clock : callable retournant un float monotone (default time.monotonic)
        expected_version : version protocole attendue (default = PROTOCOL_VERSION)
        """
        self._serial = serial_port
        self._clock = clock or _time.monotonic
        self._expected_version = expected_version

        self._tx_seq = 0
        self._tx_seq_lock = threading.Lock()
        self._last_request_seq: Optional[int] = None
        self._last_err_received: Optional[str] = None

        self._rx_queue: "queue.Queue[Frame]" = queue.Queue()
        self._debug_lines: list = []  # logs ESP32 (lignes ne commencant pas par '<')
        self._read_buffer = bytearray()

        self._reader_thread: Optional[threading.Thread] = None
        self._stop_reader = threading.Event()

        self.is_connected = False

    def _next_tx_seq(self) -> int:
        """Retourne le seq courant et incremente (modulo 256)."""
        with self._tx_seq_lock:
            seq = self._tx_seq
            self._tx_seq = (self._tx_seq + 1) & 0xFF
            return seq

    def _start_reader_thread(self) -> None:
        """Demarre le thread de lecture du port serie. Idempotent."""
        if self._reader_thread is not None and self._reader_thread.is_alive():
            return
        self._stop_reader.clear()
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True, name="UartReader"
        )
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        """Boucle de lecture. Decoupe en lignes, classe trame protocole / debug."""
        while not self._stop_reader.is_set():
            try:
                chunk = self._serial.read(64)
            except Exception:
                break
            if chunk:
                self._read_buffer.extend(chunk)
            else:
                # Pas de donnee : petit sleep pour ne pas spinner a fond
                _time.sleep(0.01)
            # Decoupe en lignes
            while True:
                idx = self._read_buffer.find(b"\n")
                if idx == -1:
                    # Protection : si buffer > 80 octets sans \n, jeter
                    if len(self._read_buffer) > 80:
                        self._read_buffer.clear()
                    break
                raw_line = bytes(self._read_buffer[: idx + 1])
                del self._read_buffer[: idx + 1]
                self._dispatch_line(raw_line)

    def _dispatch_line(self, raw_line: bytes) -> None:
        """Classe une ligne recue : trame protocole ou log debug."""
        # Strip \r\n
        stripped = raw_line.rstrip(b"\r\n")
        if not stripped:
            return
        # Test sur le PREMIER caractere uniquement
        if stripped[0:1] == b"<":
            try:
                frame = Frame.decode(stripped)
                self._rx_queue.put(frame)
            except UartProtocolError:
                # Rejet silencieux (cf. §3.6 spec)
                pass
        else:
            # Ligne de debug ESP32
            try:
                line_str = stripped.decode("ascii", errors="replace")
            except Exception:
                return
            self._debug_lines.append(line_str)
            # Rotation simple
            if len(self._debug_lines) > self.MAX_DEBUG_LINES:
                self._debug_lines = self._debug_lines[-self.MAX_DEBUG_LINES:]

    def close(self) -> None:
        """Arrete le thread de lecture et ferme le port serie."""
        self._stop_reader.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2)
        try:
            self._serial.close()
        except Exception:
            pass
        self.is_connected = False

    def connect(self, timeout: float = 3.0) -> None:
        """Realise le handshake HELLO/HELLO_ACK et verifie la version.

        Bloque jusqu'a reception d'un HELLO valide ou timeout.
        Leve UartTimeoutError si pas de HELLO recu, UartVersionError si version incompatible.
        """
        self._start_reader_thread()

        deadline = self._clock() + timeout
        while self._clock() < deadline:
            try:
                frame = self._rx_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            if frame.type == "HELLO":
                # Verifie version
                if frame.version != self._expected_version:
                    raise UartVersionError(
                        f"version protocole incompatible : "
                        f"recu v={frame.version}, attendu v={self._expected_version}"
                    )
                # Repond HELLO_ACK avec ack=seq du HELLO
                self._send_response(type="HELLO_ACK", args="", ack=frame.seq)
                self.is_connected = True
                return

        raise UartTimeoutError(f"aucun HELLO recu apres {timeout}s")

    def _send_frame(self, frame: "Frame") -> None:
        """Envoie une frame deja construite sur le port serie."""
        self._serial.write(frame.encode())

    def _send_response(self, type: str, args: str, ack: int) -> None:
        """Construit et envoie une reponse (avec ack=)."""
        seq = self._next_tx_seq()
        frame = Frame(type=type, args=args, seq=seq, ack=ack)
        self._send_frame(frame)

    def _send_request(self, type: str, args: str, version: Optional[int] = None) -> int:
        """Construit et envoie une requete. Retourne le seq utilise."""
        seq = self._next_tx_seq()
        frame = Frame(type=type, args=args, seq=seq, version=version)
        self._send_frame(frame)
        return seq

    def send_keepalive(self) -> None:
        """Envoie une trame KEEPALIVE. A appeler periodiquement (1 s) depuis le main loop.

        No-op si pas connecte.
        """
        if not self.is_connected:
            return
        self._send_request(type="KEEPALIVE", args="")
