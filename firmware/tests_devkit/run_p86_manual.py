#!/usr/bin/env python3
"""Validation P8.6 - protocole UART Plan 2 sur DevKit ESP32.

Joue les 8 scenarios de firmware/INTEGRATION_TESTS_PENDING.md en sequence,
stop on first FAIL. Pas un test pytest : outil hardware-dependent qui
necessite le DevKit branche sur /dev/cu.usbserial-*.

Pour la version pytest automatique, voir tests/integration/test_uart_devkit.py.
"""

import re
import sys

import serial

from _uart_helpers import (
    BAUD,
    crc16,
    find_devkit_port,
    keepalive,
    make_frame,
    read_for,
    reset_esp,
    wait_for,
)

PORT = find_devkit_port() or "/dev/cu.usbserial-110"


# --- Scenarios ---


def scenario_1_handshake(s):
    print("\n=== Scenario 1 : Handshake nominal ===")
    reset_esp(s)
    out = wait_for(s, r"<HELLO\|seq=(\d+)\|v=1\|crc=", timeout=4.0)
    print(out, end="")
    m = re.search(r"<HELLO\|seq=(\d+)\|v=1\|crc=", out)
    if not m:
        return False, "aucun HELLO recu"
    hello_seq = int(m.group(1))
    print(f">> recu HELLO seq={hello_seq}, envoi HELLO_ACK ack={hello_seq}")
    s.write(make_frame("HELLO_ACK", seq=0, ack=hello_seq))
    out2 = wait_for(s, r"\[FSM\] -> state 3", timeout=2.0)
    print(out2, end="")
    if "state 3" not in out2:
        return False, "pas de transition vers state 3 (CONNECTED)"
    return True, "transition CONNECTED ok"


def scenario_2_btn_humain(s):
    """Suppose que la FSM est deja en state 3 (CONNECTED) suite au sc 1."""
    print("\n=== Scenario 2 : Cycle nominal humain (BTN) ===")
    s.reset_input_buffer()
    s.write(b"BTN 3 4\n")
    out = wait_for(s, r"<MOVE_REQ 3 4\|seq=(\d+)\|crc=", timeout=2.0)
    print(out, end="")
    m = re.search(r"<MOVE_REQ 3 4\|seq=(\d+)\|crc=([0-9A-F]+)>", out)
    if not m:
        return False, "pas de MOVE_REQ 3 4 emis"
    move_seq = int(m.group(1))
    crc_recv = m.group(2)
    crc_calc = crc16(f"MOVE_REQ 3 4|seq={move_seq}")
    if crc_recv != crc_calc:
        return False, f"CRC MOVE_REQ invalide (recu {crc_recv}, calcule {crc_calc})"
    print(f">> MOVE_REQ seq={move_seq} valide, envoi ACK ack={move_seq}")
    s.write(make_frame("ACK", seq=0, ack=move_seq))
    # Attendre EXECUTING (state 5) puis DONE
    out2 = wait_for(s, r"\[FSM\] -> state 5", timeout=2.0)
    print(out2, end="")
    if "state 5" not in out2:
        return False, "pas de transition state 5 (EXECUTING)"
    out3 = wait_for(s, r"<DONE\|seq=\d+\|ack=" + str(move_seq) + r"\|crc=", timeout=4.0)
    print(out3, end="")
    if "DONE" not in out3:
        return False, "pas de DONE recu"
    return True, "BTN -> MOVE_REQ -> ACK -> EXECUTING -> DONE ok"


def scenario_3_cmd_ia(s):
    print("\n=== Scenario 3 : Cycle nominal IA (CMD MOVE) ===")
    s.reset_input_buffer()
    cmd_seq = 10
    s.write(make_frame("CMD", "MOVE 2 5", seq=cmd_seq))
    print(f">> envoi CMD MOVE 2 5 seq={cmd_seq}")
    out = wait_for(s, r"<DONE\|seq=\d+\|ack=" + str(cmd_seq) + r"\|crc=", timeout=4.0)
    print(out, end="")
    if "DONE" not in out:
        return False, "pas de DONE recu pour CMD MOVE"
    return True, "CMD MOVE -> DONE ok"


def scenario_4_idempotence(s):
    print("\n=== Scenario 4 : Idempotence CMD (meme seq) ===")
    s.reset_input_buffer()
    cmd_seq = 20
    frame = make_frame("CMD", "MOVE 1 1", seq=cmd_seq)
    s.write(frame)
    print(f">> 1ere emission CMD MOVE 1 1 seq={cmd_seq}")
    out1 = wait_for(s, r"<DONE\|seq=\d+\|ack=" + str(cmd_seq) + r"\|crc=", timeout=4.0)
    print(out1, end="")
    n_exec_1 = out1.count("[MOT] exec command")
    if "DONE" not in out1:
        return False, "pas de DONE pour 1ere emission"
    # 2e emission meme seq
    s.reset_input_buffer()
    s.write(frame)
    print(f">> 2e emission meme frame (seq={cmd_seq})")
    out2 = wait_for(s, r"<DONE\|seq=\d+\|ack=" + str(cmd_seq) + r"\|crc=", timeout=2.0)
    print(out2, end="")
    n_exec_2 = out2.count("[MOT] exec command")
    if "DONE" not in out2:
        return False, "pas de DONE renvoye sur replay"
    if n_exec_2 != 0:
        return False, f"commande re-executee ({n_exec_2}x) au lieu d'etre idempotente"
    return True, f"replay -> DONE sans re-execution ({n_exec_1} exec sur 1ere, 0 sur replay)"


def scenario_5_crc_corrompu(s):
    print("\n=== Scenario 5 : Trame CRC corrompu (rejet silencieux) ===")
    keepalive(s)  # rafraichir watchdog avant test passif
    s.reset_input_buffer()
    s.write(b"<KEEPALIVE|seq=0|crc=0000>\n")
    print(">> envoi KEEPALIVE avec CRC bidon (0000)")
    out = read_for(s, 1.0)
    print(out, end="")
    # Rien d'inhabituel ne doit apparaitre (pas d'ACK, pas d'ERR, pas de transition)
    if "<ACK" in out or "<ERR" in out or "[FSM] ->" in out:
        return False, "trame avec CRC bidon a declenche une reaction"
    keepalive(s)  # eviter expiration watchdog avant prochain test
    return True, "trame CRC bidon ignoree silencieusement"


def scenario_6_trame_longue(s):
    print("\n=== Scenario 6 : Trame > 80 octets (rejet) ===")
    keepalive(s)  # rafraichir watchdog avant test passif
    s.reset_input_buffer()
    payload = b"<" + b"A" * 95 + b">\n"
    print(f">> envoi trame de {len(payload)} octets")
    s.write(payload)
    out = read_for(s, 1.0)
    print(out, end="")
    if "<ACK" in out or "<ERR" in out or "[FSM] ->" in out:
        return False, "trame longue a declenche une reaction"
    keepalive(s)
    return True, "trame > 80 octets ignoree"


def scenario_7_btn_sans_framing(s):
    print("\n=== Scenario 7 : Mode injection BTN sans framing ===")
    s.reset_input_buffer()
    s.write(b"BTN 5 5\n")
    print(">> envoi BTN 5 5 (sans <>)")
    out = wait_for(s, r"<MOVE_REQ 5 5\|seq=(\d+)\|crc=", timeout=2.0)
    print(out, end="")
    m = re.search(r"<MOVE_REQ 5 5\|seq=(\d+)\|crc=", out)
    if not m:
        return False, "pas de MOVE_REQ 5 5 apres BTN injection"
    move_seq = int(m.group(1))
    # Repondre ACK pour ne pas laisser la FSM dans un etat sale
    s.write(make_frame("ACK", seq=0, ack=move_seq))
    wait_for(s, r"<DONE\|seq=\d+\|ack=" + str(move_seq), timeout=4.0)
    return True, "BTN injection -> MOVE_REQ ok"


def scenario_8_err_reset(s):
    print("\n=== Scenario 8 : ERR + CMD_RESET ===")
    s.reset_input_buffer()
    # Coup hors plateau pour forcer une erreur metier
    cmd_seq = 30
    s.write(make_frame("CMD", "MOVE 99 99", seq=cmd_seq))
    print(f">> envoi CMD MOVE 99 99 seq={cmd_seq} (coords invalides)")
    out = wait_for(s, r"<ERR ", timeout=4.0)
    print(out, end="")
    if "<ERR " not in out:
        return False, "pas de ERR initial recu"
    # Verifier reemission periodique (>= 1 ERR sans ack= dans la suite)
    out2 = read_for(s, 2.5)
    print(out2, end="")
    err_reemissions = re.findall(r"<ERR [^>]+>", out2)
    err_no_ack = [e for e in err_reemissions if "|ack=" not in e]
    if not err_no_ack:
        print(f"   note: {len(err_reemissions)} ERR vus dans 2.5s, dont 0 sans ack= "
              "(reemission peut-etre absente ou plus lente)")
    # CMD_RESET
    s.reset_input_buffer()
    s.write(make_frame("CMD_RESET", seq=0))
    print(">> envoi CMD_RESET")
    out3 = wait_for(s, r"<BOOT_START\|seq=0", timeout=4.0)
    print(out3, end="")
    if "<BOOT_START" not in out3:
        return False, "pas de reboot apres CMD_RESET"
    return True, f"ERR initial ok, reboot apres CMD_RESET ok ({len(err_no_ack)} ERR re-emis sans ack)"


# --- Main ---


SCENARIOS = [
    ("1 - Handshake nominal", scenario_1_handshake),
    ("2 - Cycle humain (BTN)", scenario_2_btn_humain),
    ("3 - Cycle IA (CMD MOVE)", scenario_3_cmd_ia),
    ("4 - Idempotence CMD", scenario_4_idempotence),
    ("5 - CRC corrompu", scenario_5_crc_corrompu),
    ("6 - Trame > 80 octets", scenario_6_trame_longue),
    ("7 - BTN sans framing", scenario_7_btn_sans_framing),
    ("8 - ERR + CMD_RESET", scenario_8_err_reset),
]


def main():
    only = None
    if len(sys.argv) > 1:
        only = int(sys.argv[1])
    s = serial.Serial(PORT, BAUD, timeout=0.1)
    try:
        results = []
        for i, (name, fn) in enumerate(SCENARIOS, start=1):
            if only is not None and i != only:
                continue
            ok, msg = fn(s)
            tag = "PASS" if ok else "FAIL"
            print(f"\n>>> [{tag}] Scenario {name} : {msg}")
            results.append((i, name, ok, msg))
            if not ok:
                print(f"\n!! Stop on first FAIL au scenario {i}")
                break
        print("\n========== RESUME ==========")
        for i, name, ok, msg in results:
            tag = "PASS" if ok else "FAIL"
            print(f"  [{tag}] {name} -- {msg}")
        all_ok = all(ok for _, _, ok, _ in results)
        sys.exit(0 if all_ok else 1)
    finally:
        s.close()


if __name__ == "__main__":
    main()
