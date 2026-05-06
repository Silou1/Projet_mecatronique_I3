"""Helpers protocole + serial pour les tests P8.6 (harness manuel + pytest).

Module privé au dossier firmware/tests_devkit/. Importé par :
- run_p86_manual.py (harness interactif, exécutable directement)
- tests/integration/conftest.py (fixtures pytest)
"""

import binascii
import glob
import re
import time

import serial

PORT_GLOB = "/dev/cu.usbserial-*"
BAUD = 115200


def find_devkit_port() -> str | None:
    """Retourne le premier port DevKit détecté (ordre lexico) ou None."""
    matches = sorted(glob.glob(PORT_GLOB))
    return matches[0] if matches else None


# --- Helpers protocole ---


def crc16(data: str) -> str:
    """CRC-16 CCITT-FALSE sur la zone CRC, retourne hex 4 chars majuscules."""
    return f"{binascii.crc_hqx(data.encode('ascii'), 0xFFFF):04X}"


def make_frame(type_, args="", seq=0, ack=None, version=None) -> bytes:
    body = type_
    if args:
        body += " " + args
    body += f"|seq={seq}"
    if ack is not None:
        body += f"|ack={ack}"
    if version is not None:
        body += f"|v={version}"
    return f"<{body}|crc={crc16(body)}>\n".encode("ascii")


FRAME_RE = re.compile(r"<([^>]+)>")


def parse_frames(text: str):
    out = []
    for m in FRAME_RE.finditer(text):
        body = m.group(1)
        parts = body.split("|")
        head = parts[0].split(" ", 1)
        type_ = head[0]
        args = head[1] if len(head) > 1 else ""
        fields = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                fields[k] = v
        crc_recv = fields.pop("crc", None)
        zone = body.rsplit("|crc=", 1)[0]
        crc_calc = crc16(zone)
        crc_ok = (crc_recv == crc_calc)
        out.append({"type": type_, "args": args, "crc_ok": crc_ok, "raw": m.group(0), **fields})
    return out


# --- Helpers serial ---


def reset_esp(s: serial.Serial) -> None:
    s.dtr = False  # GPIO0 high (boot Flash)
    s.rts = True   # EN low (reset)
    time.sleep(0.1)
    s.reset_input_buffer()
    s.rts = False  # EN high (run)


def keepalive(s: serial.Serial) -> None:
    """Trame KEEPALIVE valide pour rafraichir le watchdog UART (3 s) du firmware."""
    s.write(make_frame("KEEPALIVE", seq=0))


def read_for(s: serial.Serial, duration: float) -> str:
    start = time.time()
    buf = bytearray()
    while time.time() - start < duration:
        chunk = s.read(4096)
        if chunk:
            buf.extend(chunk)
    return buf.decode("ascii", errors="replace")


def wait_for(s: serial.Serial, pattern: str, timeout: float = 5.0) -> str:
    start = time.time()
    buf = bytearray()
    rx = re.compile(pattern)
    while time.time() - start < timeout:
        chunk = s.read(2048)
        if chunk:
            buf.extend(chunk)
            if rx.search(buf.decode("ascii", errors="replace")):
                return buf.decode("ascii", errors="replace")
    return buf.decode("ascii", errors="replace")
