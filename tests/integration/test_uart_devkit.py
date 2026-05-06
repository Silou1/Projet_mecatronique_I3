"""Tests d'intégration P8.6 — protocole UART Plan 2 sur DevKit ESP32 réel.

Portage 1:1 des 8 scénarios de firmware/tests_devkit/run_p86_manual.py.
Marqueur @pytest.mark.devkit : skippé si aucun /dev/cu.usbserial-* présent.
"""

import re

import pytest

from _uart_helpers import crc16, keepalive, make_frame, read_for, wait_for


@pytest.mark.devkit
def test_sc_1_handshake(raw_devkit):
    """Sc 1 — Handshake nominal : BOOT_START → HELLO → HELLO_ACK → state 3."""
    out = wait_for(raw_devkit, r"<HELLO\|seq=(\d+)\|v=1\|crc=", timeout=4.0)
    m = re.search(r"<HELLO\|seq=(\d+)\|v=1\|crc=", out)
    assert m, "aucun HELLO reçu"
    raw_devkit.write(make_frame("HELLO_ACK", seq=0, ack=int(m.group(1))))
    out2 = wait_for(raw_devkit, r"\[FSM\] -> state 3", timeout=2.0)
    assert "state 3" in out2, "pas de transition vers state 3 (CONNECTED)"


@pytest.mark.devkit
def test_sc_2_btn_humain(connected_devkit):
    """Sc 2 — BTN x y → MOVE_REQ → ACK → EXECUTING → DONE."""
    connected_devkit.reset_input_buffer()
    connected_devkit.write(b"BTN 3 4\n")
    out = wait_for(connected_devkit, r"<MOVE_REQ 3 4\|seq=(\d+)\|crc=", timeout=2.0)
    m = re.search(r"<MOVE_REQ 3 4\|seq=(\d+)\|crc=([0-9A-F]+)>", out)
    assert m, "pas de MOVE_REQ 3 4 émis"
    move_seq = int(m.group(1))
    crc_recv = m.group(2)
    crc_calc = crc16(f"MOVE_REQ 3 4|seq={move_seq}")
    assert crc_recv == crc_calc, f"CRC MOVE_REQ invalide (recu {crc_recv}, calculé {crc_calc})"
    connected_devkit.write(make_frame("ACK", seq=0, ack=move_seq))
    out2 = wait_for(connected_devkit, r"\[FSM\] -> state 5", timeout=2.0)
    assert "state 5" in out2, "pas de transition state 5 (EXECUTING)"
    out3 = wait_for(connected_devkit, rf"<DONE\|seq=\d+\|ack={move_seq}\|crc=", timeout=4.0)
    assert "DONE" in out3, "pas de DONE reçu"


@pytest.mark.devkit
def test_sc_3_cmd_ia(connected_devkit):
    """Sc 3 — CMD MOVE r c → DONE."""
    connected_devkit.reset_input_buffer()
    cmd_seq = 10
    connected_devkit.write(make_frame("CMD", "MOVE 2 5", seq=cmd_seq))
    out = wait_for(connected_devkit, rf"<DONE\|seq=\d+\|ack={cmd_seq}\|crc=", timeout=4.0)
    assert "DONE" in out, "pas de DONE reçu pour CMD MOVE"


@pytest.mark.devkit
def test_sc_4_idempotence(connected_devkit):
    """Sc 4 — Replay même CMD avec même seq → DONE renvoyé sans re-exécution."""
    connected_devkit.reset_input_buffer()
    cmd_seq = 20
    frame = make_frame("CMD", "MOVE 1 1", seq=cmd_seq)
    connected_devkit.write(frame)
    out1 = wait_for(connected_devkit, rf"<DONE\|seq=\d+\|ack={cmd_seq}\|crc=", timeout=4.0)
    assert "DONE" in out1, "pas de DONE pour 1ère émission"
    # 2e émission, même frame
    connected_devkit.reset_input_buffer()
    connected_devkit.write(frame)
    out2 = wait_for(connected_devkit, rf"<DONE\|seq=\d+\|ack={cmd_seq}\|crc=", timeout=2.0)
    assert "DONE" in out2, "pas de DONE renvoyé sur replay"
    n_exec_2 = out2.count("[MOT] exec command")
    assert n_exec_2 == 0, f"commande re-executée ({n_exec_2}x) au lieu d'être idempotente"


@pytest.mark.devkit
def test_sc_5_crc_corrompu(connected_devkit):
    """Sc 5 — Trame avec CRC bidon → rejet silencieux (pas d'ACK/ERR/transition)."""
    keepalive(connected_devkit)  # rafraîchir watchdog avant test passif
    connected_devkit.reset_input_buffer()
    connected_devkit.write(b"<KEEPALIVE|seq=0|crc=0000>\n")
    out = read_for(connected_devkit, 1.0)
    assert "<ACK" not in out, "trame CRC bidon a déclenché un ACK"
    assert "<ERR" not in out, "trame CRC bidon a déclenché un ERR"
    assert "[FSM] ->" not in out, "trame CRC bidon a déclenché une transition d'état"
    keepalive(connected_devkit)  # éviter expiration watchdog avant prochain test


@pytest.mark.devkit
def test_sc_6_trame_longue(connected_devkit):
    """Sc 6 — Trame > 80 octets → rejet silencieux."""
    keepalive(connected_devkit)
    connected_devkit.reset_input_buffer()
    payload = b"<" + b"A" * 95 + b">\n"
    connected_devkit.write(payload)
    out = read_for(connected_devkit, 1.0)
    assert "<ACK" not in out, "trame longue a déclenché un ACK"
    assert "<ERR" not in out, "trame longue a déclenché un ERR"
    assert "[FSM] ->" not in out, "trame longue a déclenché une transition d'état"
    keepalive(connected_devkit)


@pytest.mark.devkit
def test_sc_7_btn_sans_framing(connected_devkit):
    """Sc 7 — Mode injection BTN x y (sans <>) → MOVE_REQ x y émis."""
    connected_devkit.reset_input_buffer()
    connected_devkit.write(b"BTN 5 5\n")
    out = wait_for(connected_devkit, r"<MOVE_REQ 5 5\|seq=(\d+)\|crc=", timeout=2.0)
    m = re.search(r"<MOVE_REQ 5 5\|seq=(\d+)\|crc=", out)
    assert m, "pas de MOVE_REQ 5 5 après BTN injection"
    move_seq = int(m.group(1))
    # Répondre ACK pour ne pas laisser la FSM dans un état sale
    connected_devkit.write(make_frame("ACK", seq=0, ack=move_seq))
    wait_for(connected_devkit, rf"<DONE\|seq=\d+\|ack={move_seq}", timeout=4.0)


@pytest.mark.devkit
def test_sc_8_err_reset(connected_devkit):
    """Sc 8 — ERR initial → réémission 1Hz → CMD_RESET → BOOT_START.

    Note : dans le stub MotionControl, (99,99) est accepté ; l'ERR observée
    vient du watchdog UART (3 s sans trame valide pendant la phase passive),
    pas d'une erreur métier. Validation par erreur métier reportée à P11.
    """
    connected_devkit.reset_input_buffer()
    cmd_seq = 30
    connected_devkit.write(make_frame("CMD", "MOVE 99 99", seq=cmd_seq))
    out = wait_for(connected_devkit, r"<ERR ", timeout=4.0)
    assert "<ERR " in out, "pas de ERR initial reçu"
    # Réémission ERR pendant 2.5 s (informatif, on ne fail pas si pas vu)
    out2 = read_for(connected_devkit, 2.5)
    err_reemissions = re.findall(r"<ERR [^>]+>", out2)
    err_no_ack = [e for e in err_reemissions if "|ack=" not in e]
    # CMD_RESET → BOOT_START
    connected_devkit.reset_input_buffer()
    connected_devkit.write(make_frame("CMD_RESET", seq=0))
    out3 = wait_for(connected_devkit, r"<BOOT_START\|seq=0", timeout=4.0)
    assert "<BOOT_START" in out3, "pas de reboot après CMD_RESET"
    # Trace info pour debug si besoin (visible avec -s)
    print(f"[sc 8] ERR ré-émis sans ack : {len(err_no_ack)}")
