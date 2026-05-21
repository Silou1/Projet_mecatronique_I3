"""Outil CLI pour bring-up du strip LED WS2812B via serial.

Usage :
    python tools/led_test.py serpentin     # scan LED 0 → 35 en blanc, 150 ms chacune
    python tools/led_test.py coins         # allume 4 coins + 2 positions de depart
    python tools/led_test.py clear         # eteint toutes les LEDs
    python tools/led_test.py pixel <idx> <r> <g> <b>   # une LED precise
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports


def find_esp32_port() -> str:
    """Trouve le port USB de l'ESP32 (macOS : /dev/cu.usbserial-*)."""
    for port in list_ports.comports():
        if "usbserial" in port.device or "SLAB" in (port.description or ""):
            return port.device
    raise SystemExit("ESP32 introuvable sur /dev/cu.usbserial-*")


def send(ser: serial.Serial, line: str) -> str:
    """Envoie une ligne, attend la reponse (max 2 s)."""
    ser.reset_input_buffer()
    ser.write((line + "\n").encode())
    ser.flush()
    deadline = time.monotonic() + 2.0
    buf = ""
    while time.monotonic() < deadline:
        chunk = ser.read(ser.in_waiting or 1).decode(errors="replace")
        if chunk:
            buf += chunk
            if "\n" in buf:
                return buf.split("\n")[0].strip()
    return "(timeout)"


def cmd_clear(ser: serial.Serial) -> None:
    print(send(ser, "LEDCLEAR"))


def cmd_pixel(ser: serial.Serial, idx: int, r: int, g: int, b: int) -> None:
    print(send(ser, f"LED {idx} {r} {g} {b}"))
    print(send(ser, "LEDSHOW"))


def cmd_serpentin(ser: serial.Serial) -> None:
    """Allume LED 0 a 35 en blanc, 150 ms chacune. Permet de valider l'ordre du serpentin."""
    send(ser, "LEDCLEAR")
    for idx in range(36):
        send(ser, f"LED {idx} 80 80 80")  # blanc dim
        send(ser, "LEDSHOW")
        time.sleep(0.15)
        send(ser, f"LED {idx} 0 0 0")     # eteindre avant la suivante
    send(ser, "LEDSHOW")
    print("Serpentin termine.")


def cmd_coins(ser: serial.Serial) -> None:
    """Allume les 4 coins + 2 positions de depart des pions."""
    send(ser, "LEDCLEAR")
    cases = [
        (0,  255, 0,   0,   "LED 0  bas-gauche  rouge"),
        (5,  0,   255, 0,   "LED 5  bas-droite  vert"),
        (30, 255, 255, 0,   "LED 30 haut-droite jaune"),
        (35, 255, 255, 255, "LED 35 haut-gauche blanc"),
        (3,  0,   0,   255, "LED 3  bas-centre  bleu (depart J1)"),
        (32, 255, 0,   0,   "LED 32 haut-centre rouge (depart J2)"),
    ]
    for idx, r, g, b, label in cases:
        send(ser, f"LED {idx} {r} {g} {b}")
        print(label)
    send(ser, "LEDSHOW")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serpentin")
    sub.add_parser("coins")
    sub.add_parser("clear")
    p_pix = sub.add_parser("pixel")
    p_pix.add_argument("idx", type=int)
    p_pix.add_argument("r", type=int)
    p_pix.add_argument("g", type=int)
    p_pix.add_argument("b", type=int)
    args = parser.parse_args()

    port = find_esp32_port()
    print(f"Connexion a {port} ...")
    with serial.Serial(port, 115200, timeout=2) as ser:
        time.sleep(2)  # laisser l'ESP32 finir son boot
        if args.cmd == "serpentin":
            cmd_serpentin(ser)
        elif args.cmd == "coins":
            cmd_coins(ser)
        elif args.cmd == "clear":
            cmd_clear(ser)
        elif args.cmd == "pixel":
            cmd_pixel(ser, args.idx, args.r, args.g, args.b)


if __name__ == "__main__":
    main()
