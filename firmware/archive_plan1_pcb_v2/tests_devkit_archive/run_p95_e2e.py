#!/usr/bin/env python3
"""Harness E2E P9.5 - partie complete PvIA via UART sur DevKit ESP32.

Utilise directement le code de prod (GameSession, UartClient, QuoridorGame, AI)
et expose une CLI pour injecter des appuis bouton via le port serie partage.
GameSession tourne dans un thread daemon, le thread principal pilote la CLI.

Commandes :
  BTN <row> <col>      Injecte une trame "BTN row col" (sans framing) sur le
                       port serie. Le firmware la convertit en MOVE_REQ.
  simulate_uart_lost   Arrete le keepalive Python pendant 4 s : le firmware
                       passe en ERROR_STATE (UART_LOST), Python le detecte,
                       envoie CMD_RESET et refait le handshake.
  quit                 Arret propre.

Exemple :
  python firmware/tests_devkit/run_p95_e2e.py --port /dev/cu.usbserial-110 \\
      --difficulty normal
"""

import argparse
import os
import sys
import threading
import time

# Permet de lancer le script depuis n'importe quel cwd : ajoute la racine du
# projet (deux niveaux au-dessus) a sys.path pour importer quoridor_engine.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import serial

from quoridor_engine.ai import AI
from quoridor_engine.core import QuoridorGame
from quoridor_engine.game_session import GameSession
from quoridor_engine.uart_client import UartClient, UartError


def reset_esp(ser: serial.Serial) -> None:
    """Hard reset de l'ESP32 via DTR/RTS (circuit auto-program standard)."""
    ser.dtr = False  # GPIO0 high (boot Flash)
    ser.rts = True   # EN low (reset)
    time.sleep(0.1)
    ser.reset_input_buffer()
    ser.rts = False  # EN high (run)


def parse_args():
    p = argparse.ArgumentParser(description="Harness E2E P9.5 (DevKit ESP32).")
    p.add_argument("--port", default="/dev/cu.usbserial-110")
    p.add_argument(
        "--difficulty",
        choices=["facile", "normal", "difficile"],
        default="normal",
    )
    return p.parse_args()


def main():
    args = parse_args()

    ser = serial.Serial(args.port, 115200, timeout=0.05)
    print("[harness] reset ESP32...")
    reset_esp(ser)
    time.sleep(0.5)  # laisser le boot ESP32 emettre BOOT_START + HELLO

    uart = UartClient(ser)
    game = QuoridorGame()
    ai = AI(player="j2", difficulty=args.difficulty)
    session = GameSession(game, ai, uart, debug=True)

    session_done = threading.Event()
    session_exc = []

    def run_session():
        try:
            session.run()
        except BaseException as exc:
            session_exc.append(exc)
        finally:
            session_done.set()

    t = threading.Thread(target=run_session, daemon=True, name="GameSession")
    t.start()

    print("=== P9.5 E2E harness ===")
    print("Commandes : BTN <r> <c>, simulate_uart_lost, quit")
    print(f"IA difficulte : {args.difficulty}")

    # Attendre la fin du handshake avant d'ouvrir la CLI
    print("[harness] attente du handshake HELLO/HELLO_ACK...")
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if uart.is_connected or session_done.is_set():
            break
        time.sleep(0.1)
    if not uart.is_connected:
        print("[harness] echec handshake (timeout 10 s)")
        try:
            uart.close()
        except Exception:
            pass
        sys.exit(2)
    print("[harness] CONNECTED, CLI active")
    print()

    quitting = False
    try:
        while not session_done.is_set():
            try:
                line = input("> ").strip()
            except EOFError:
                quitting = True
                break

            if session_done.is_set():
                break

            if not line:
                continue

            if line == "quit":
                quitting = True
                break

            if line == "simulate_uart_lost":
                print("[harness] arret keepalive Python pendant 4 s "
                      "(firmware doit passer en ERROR_STATE UART_LOST)")
                uart._stop_keepalive.set()
                time.sleep(4.0)
                uart._stop_keepalive.clear()
                uart._start_keepalive_thread()
                print("[harness] keepalive relance")
                continue

            if line.startswith("BTN"):
                parts = line.split()
                if len(parts) != 3:
                    print("usage : BTN <row> <col>")
                    continue
                try:
                    row = int(parts[1])
                    col = int(parts[2])
                except ValueError:
                    print("BTN attend des entiers")
                    continue
                ser.write(f"BTN {row} {col}\n".encode("ascii"))
                print(f"[harness] BTN {row} {col} injecte")
                continue

            print(f"commande inconnue : {line!r}")

    finally:
        try:
            uart.close()
        except Exception:
            pass
        t.join(timeout=2)

    if session_exc:
        exc = session_exc[0]
        # Au shutdown utilisateur (quit/EOF), le main thread ferme l'UART
        # pendant que GameSession peut etre en train de _check_health() :
        # le reader meurt et la session leve UartError("reader thread died").
        # C'est un comportement attendu du shutdown, pas une vraie erreur.
        if (
            quitting
            and isinstance(exc, UartError)
            and "reader thread died" in str(exc)
        ):
            print("[harness] termine proprement (shutdown sur quit)")
            sys.exit(0)
        print(f"[harness] session a leve : {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)

    print("[harness] termine proprement")
    sys.exit(0)


if __name__ == "__main__":
    main()
