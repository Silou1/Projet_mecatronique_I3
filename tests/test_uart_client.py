"""Tests unitaires pour le module quoridor_engine.uart_client."""

import pytest
from quoridor_engine.uart_client import (
    UartError,
    UartTimeoutError,
    UartProtocolError,
    UartVersionError,
    UartHardwareError,
)


class TestExceptionHierarchy:
    """La hierarchie d'exceptions doit refleter le spec §9.2."""

    def test_all_inherit_from_uart_error(self):
        for cls in (UartTimeoutError, UartProtocolError, UartVersionError, UartHardwareError):
            assert issubclass(cls, UartError)

    def test_uart_error_inherits_from_exception(self):
        assert issubclass(UartError, Exception)

    def test_uart_hardware_error_carries_code(self):
        err = UartHardwareError("MOTOR_TIMEOUT")
        assert err.code == "MOTOR_TIMEOUT"
        assert "MOTOR_TIMEOUT" in str(err)


from quoridor_engine.uart_client import compute_crc


class TestCrc:
    """CRC-16 CCITT-FALSE (poly 0x1021, init 0xFFFF) sur les vecteurs figes du spec §3.5."""

    @pytest.mark.parametrize("data,expected", [
        ("MOVE_REQ 3 4|seq=42", 0xAED2),
        ("CMD MOVE 2 5|seq=43", 0x8489),
        ("KEEPALIVE|seq=0", 0x74D8),
    ])
    def test_crc_reference_vectors(self, data: str, expected: int):
        assert compute_crc(data.encode("ascii")) == expected

    def test_crc_returns_int_in_uint16_range(self):
        crc = compute_crc(b"hello")
        assert 0 <= crc <= 0xFFFF
        assert isinstance(crc, int)

    def test_crc_empty_returns_init_value(self):
        # CCITT-FALSE init=0xFFFF, sur input vide le CRC reste a init
        assert compute_crc(b"") == 0xFFFF


from quoridor_engine.uart_client import Frame


class TestFrameEncodeRequests:
    """Encodage de trames sans ack (requetes ou messages spontanes)."""

    def test_encode_keepalive(self):
        f = Frame(type="KEEPALIVE", args="", seq=0)
        encoded = f.encode()
        # Format attendu : <KEEPALIVE|seq=0|crc=XXXX>\n
        assert encoded.startswith(b"<KEEPALIVE|seq=0|crc=")
        assert encoded.endswith(b">\n")

    def test_encode_move_req(self):
        f = Frame(type="MOVE_REQ", args="3 4", seq=42)
        encoded = f.encode()
        assert encoded.startswith(b"<MOVE_REQ 3 4|seq=42|crc=")
        assert encoded.endswith(b">\n")

    def test_encode_hello_with_version(self):
        f = Frame(type="HELLO", args="", seq=2, version=1)
        encoded = f.encode()
        # Ordre des champs : seq puis v puis crc
        assert encoded.startswith(b"<HELLO|seq=2|v=1|crc=")
        assert encoded.endswith(b">\n")

    def test_encode_err_without_ack(self):
        # ERR spontane (reemission periodique en ERROR)
        f = Frame(type="ERR", args="UART_LOST", seq=99)
        encoded = f.encode()
        assert encoded.startswith(b"<ERR UART_LOST|seq=99|crc=")
        assert b"|ack=" not in encoded

    def test_encode_crc_is_4_hex_uppercase(self):
        f = Frame(type="KEEPALIVE", args="", seq=0)
        encoded = f.encode()
        crc_part = encoded.split(b"|crc=")[1].rstrip(b">\n")
        assert len(crc_part) == 4
        assert crc_part.decode("ascii") == crc_part.decode("ascii").upper()
        # Doit etre du hex valide
        int(crc_part, 16)

    def test_encode_seq_no_zero_padding(self):
        # Le seq lui-meme n'est pas zero-padde (decimal naturel)
        f = Frame(type="KEEPALIVE", args="", seq=7)
        encoded = f.encode()
        assert b"|seq=7|" in encoded
        assert b"|seq=07|" not in encoded

    def test_encode_keepalive_crc_matches_reference_vector(self):
        # Vecteur de reference du spec §3.5 : KEEPALIVE|seq=0 -> 0x74D8
        f = Frame(type="KEEPALIVE", args="", seq=0)
        encoded = f.encode()
        assert b"|crc=74D8>" in encoded

    def test_encode_move_req_crc_matches_reference_vector(self):
        # Vecteur de reference : MOVE_REQ 3 4|seq=42 -> 0xAED2
        f = Frame(type="MOVE_REQ", args="3 4", seq=42)
        encoded = f.encode()
        assert b"|crc=AED2>" in encoded


class TestFrameEncodeResponses:
    """Encodage de trames de reponse (avec ack=)."""

    def test_encode_ack(self):
        f = Frame(type="ACK", args="", seq=17, ack=42)
        encoded = f.encode()
        # Ordre : seq puis ack puis crc
        assert encoded.startswith(b"<ACK|seq=17|ack=42|crc=")
        assert encoded.endswith(b">\n")

    def test_encode_nack_with_reason(self):
        f = Frame(type="NACK", args="ILLEGAL", seq=18, ack=42)
        encoded = f.encode()
        assert encoded.startswith(b"<NACK ILLEGAL|seq=18|ack=42|crc=")

    def test_encode_done(self):
        f = Frame(type="DONE", args="", seq=44, ack=43)
        encoded = f.encode()
        assert encoded.startswith(b"<DONE|seq=44|ack=43|crc=")

    def test_encode_hello_ack(self):
        f = Frame(type="HELLO_ACK", args="", seq=0, ack=2)
        encoded = f.encode()
        assert encoded.startswith(b"<HELLO_ACK|seq=0|ack=2|crc=")

    def test_encode_err_with_ack_response_to_cmd(self):
        # ERR emis en reponse a une CMD echouee : porte un ack=
        f = Frame(type="ERR", args="MOTOR_TIMEOUT", seq=46, ack=43)
        encoded = f.encode()
        assert encoded.startswith(b"<ERR MOTOR_TIMEOUT|seq=46|ack=43|crc=")


class TestFrameDecodeValid:
    """Decodage de trames valides bien formees."""

    def test_decode_keepalive(self):
        # Encoder puis decoder doit redonner la meme Frame
        original = Frame(type="KEEPALIVE", args="", seq=0)
        encoded = original.encode()
        decoded = Frame.decode(encoded.rstrip(b"\n"))
        assert decoded.type == "KEEPALIVE"
        assert decoded.args == ""
        assert decoded.seq == 0
        assert decoded.ack is None
        assert decoded.version is None

    def test_decode_move_req(self):
        original = Frame(type="MOVE_REQ", args="3 4", seq=42)
        decoded = Frame.decode(original.encode().rstrip(b"\n"))
        assert decoded.type == "MOVE_REQ"
        assert decoded.args == "3 4"
        assert decoded.seq == 42

    def test_decode_ack_with_ack_field(self):
        original = Frame(type="ACK", args="", seq=17, ack=42)
        decoded = Frame.decode(original.encode().rstrip(b"\n"))
        assert decoded.ack == 42
        assert decoded.seq == 17

    def test_decode_hello_with_version(self):
        original = Frame(type="HELLO", args="", seq=2, version=1)
        decoded = Frame.decode(original.encode().rstrip(b"\n"))
        assert decoded.version == 1

    def test_decode_err_with_ack(self):
        original = Frame(type="ERR", args="MOTOR_TIMEOUT", seq=46, ack=43)
        decoded = Frame.decode(original.encode().rstrip(b"\n"))
        assert decoded.type == "ERR"
        assert decoded.args == "MOTOR_TIMEOUT"
        assert decoded.ack == 43

    def test_decode_handles_bytes_with_trailing_newline(self):
        # Le decoder doit accepter une trame avec ou sans \n final
        original = Frame(type="KEEPALIVE", args="", seq=0)
        with_newline = original.encode()  # avec \n
        decoded = Frame.decode(with_newline)
        assert decoded.type == "KEEPALIVE"


class TestFrameDecodeRejects:
    """Rejets de trames mal formees - couvre §3.6 du spec."""

    def test_reject_too_long(self):
        # Trame > 80 octets
        long_args = "A" * 80
        with pytest.raises(UartProtocolError, match="trop longue"):
            Frame.decode(f"<MOVE_REQ {long_args}|seq=0|crc=ABCD>".encode("ascii"))

    def test_reject_no_delimiters(self):
        with pytest.raises(UartProtocolError, match="delimiteurs"):
            Frame.decode(b"KEEPALIVE|seq=0|crc=ABCD")

    def test_reject_only_open_delimiter(self):
        with pytest.raises(UartProtocolError, match="delimiteurs"):
            Frame.decode(b"<KEEPALIVE|seq=0|crc=ABCD")

    def test_reject_lowercase_type(self):
        with pytest.raises(UartProtocolError, match="TYPE invalide"):
            Frame.decode(b"<keepalive|seq=0|crc=ABCD>")

    def test_reject_missing_seq(self):
        with pytest.raises(UartProtocolError, match="seq="):
            Frame.decode(b"<KEEPALIVE|crc=ABCD>")

    def test_reject_missing_crc(self):
        with pytest.raises(UartProtocolError, match="crc="):
            Frame.decode(b"<KEEPALIVE|seq=0>")

    def test_reject_lowercase_crc(self):
        with pytest.raises(UartProtocolError, match="format crc"):
            Frame.decode(b"<KEEPALIVE|seq=0|crc=abcd>")

    def test_reject_short_crc(self):
        with pytest.raises(UartProtocolError, match="format crc"):
            Frame.decode(b"<KEEPALIVE|seq=0|crc=AB>")

    def test_reject_crc_value_mismatch(self):
        # Trame valide en structure mais CRC incorrect
        with pytest.raises(UartProtocolError, match="CRC invalide"):
            Frame.decode(b"<KEEPALIVE|seq=0|crc=0000>")

    def test_reject_seq_out_of_range(self):
        with pytest.raises(UartProtocolError, match="seq hors plage"):
            # 256 hors plage [0,255]
            Frame.decode(b"<KEEPALIVE|seq=256|crc=ABCD>")

    def test_reject_unknown_metadata_field(self):
        with pytest.raises(UartProtocolError, match="champ inconnu"):
            Frame.decode(b"<KEEPALIVE|seq=0|foo=bar|crc=ABCD>")


class TestMocks:
    """Sanity checks pour MockSerial et MockClock (fixtures conftest.py)."""

    def test_mock_serial_write_and_get_tx(self, mock_serial):
        mock_serial.write(b"hello")
        assert mock_serial.get_tx() == b"hello"
        assert mock_serial.get_tx() == b""  # vide apres lecture

    def test_mock_serial_inject_rx_and_readline(self, mock_serial):
        mock_serial.inject_rx(b"line1\nline2\n")
        assert mock_serial.readline() == b"line1\n"
        assert mock_serial.readline() == b"line2\n"
        assert mock_serial.readline() == b""

    def test_mock_serial_in_waiting(self, mock_serial):
        assert mock_serial.in_waiting == 0
        mock_serial.inject_rx(b"abc")
        assert mock_serial.in_waiting == 3

    def test_mock_serial_close(self, mock_serial):
        assert mock_serial.is_open is True
        mock_serial.close()
        assert mock_serial.is_open is False

    def test_mock_clock_advance(self, mock_clock):
        assert mock_clock() == 0.0
        mock_clock.advance(15.0)
        assert mock_clock() == 15.0

    def test_mock_clock_callable_multiple_times(self, mock_clock):
        # Doit etre stable entre 2 appels sans advance
        t1 = mock_clock()
        t2 = mock_clock()
        assert t1 == t2


import threading
import time

from quoridor_engine.uart_client import UartClient


class TestUartClientInit:
    """Construction de UartClient + thread de lecture."""

    def test_init_does_not_open_port(self, mock_serial, mock_clock):
        # L'ouverture est differee a connect()
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        assert client.is_connected is False

    def test_close_stops_reader_thread(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()  # API interne pour tests
        assert client._reader_thread is not None
        assert client._reader_thread.is_alive()
        client.close()
        # Le thread doit s'arreter rapidement
        client._reader_thread.join(timeout=2)
        assert not client._reader_thread.is_alive()

    def test_reader_thread_parses_incoming_frames(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()

        # Inject une trame valide
        f = Frame(type="KEEPALIVE", args="", seq=5)
        mock_serial.inject_rx(f.encode())

        # Laisser le thread lire (court timeout)
        time.sleep(0.2)

        # La frame doit etre dans la queue interne
        received = client._rx_queue.get(timeout=1)
        assert received.type == "KEEPALIVE"
        assert received.seq == 5

        client.close()

    def test_reader_thread_classifies_debug_lines(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()

        mock_serial.inject_rx(b"[FSM] BOOT -> WAITING_RPI\n")
        time.sleep(0.2)

        # La ligne de debug doit etre dans le buffer debug, pas dans la rx_queue
        assert client._debug_lines  # non vide
        assert "[FSM]" in client._debug_lines[0]

        client.close()


from quoridor_engine.uart_client import UartVersionError


class TestHandshake:
    """Handshake HELLO / HELLO_ACK + verification version (§6.6 spec)."""

    def test_connect_sends_hello_ack_on_hello_v1(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock, expected_version=1)
        client._start_reader_thread()

        # Simule reception HELLO v=1
        hello = Frame(type="HELLO", args="", seq=2, version=1)
        mock_serial.inject_rx(hello.encode())

        # connect doit aboutir
        client.connect(timeout=1.0)
        assert client.is_connected

        # Verifier qu'on a bien envoye HELLO_ACK avec ack=2
        sent = mock_serial.get_tx()
        assert b"<HELLO_ACK|" in sent
        assert b"|ack=2|" in sent

        client.close()

    def test_connect_raises_version_error_on_mismatch(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock, expected_version=1)
        client._start_reader_thread()

        # Simule reception HELLO v=2 (incompatible)
        hello = Frame(type="HELLO", args="", seq=2, version=2)
        mock_serial.inject_rx(hello.encode())

        with pytest.raises(UartVersionError, match="version"):
            client.connect(timeout=1.0)

        client.close()

    def test_connect_raises_timeout_if_no_hello(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock, expected_version=1)
        client._start_reader_thread()

        result = []
        def runner():
            try:
                client.connect(timeout=0.5)
                result.append("connected")
            except UartTimeoutError as e:
                result.append("timeout")

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        # Avance l'horloge pour declencher le timeout
        time.sleep(0.1)
        mock_clock.advance(1.0)

        t.join(timeout=2)
        assert result == ["timeout"]

        client.close()


class TestKeepalive:
    """Emission de KEEPALIVE - methode appelable par le main loop."""

    def test_send_keepalive_writes_frame(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True

        client.send_keepalive()

        sent = mock_serial.get_tx()
        assert sent.startswith(b"<KEEPALIVE|seq=")
        assert sent.endswith(b">\n")

    def test_send_keepalive_increments_seq(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True

        client.send_keepalive()
        client.send_keepalive()

        sent = mock_serial.get_tx()
        # On doit voir seq=0 puis seq=1 (compteur initialise a 0)
        assert b"|seq=0|" in sent
        assert b"|seq=1|" in sent

    def test_send_keepalive_no_op_if_not_connected(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        # is_connected reste False (pas d'appel a connect)

        client.send_keepalive()

        # Rien ne doit etre envoye si pas connecte
        assert mock_serial.get_tx() == b""


class TestReceiveIntents:
    """Reception MOVE_REQ / WALL_REQ et reponse ACK/NACK."""

    def test_receive_returns_move_req(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        f = Frame(type="MOVE_REQ", args="3 4", seq=42)
        mock_serial.inject_rx(f.encode())

        intent = client.receive(timeout=1.0)
        assert intent.type == "MOVE_REQ"
        assert intent.args == "3 4"
        assert intent.seq == 42

        client.close()

    def test_receive_returns_none_on_timeout(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        intent = client.receive(timeout=0.1)
        assert intent is None

        client.close()

    def test_send_ack_carries_request_seq(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True

        client.send_ack(request_seq=42)

        sent = mock_serial.get_tx()
        assert sent.startswith(b"<ACK|seq=")
        assert b"|ack=42|" in sent

    def test_send_nack_carries_reason_and_request_seq(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True

        client.send_nack(request_seq=42, reason="ILLEGAL")

        sent = mock_serial.get_tx()
        assert sent.startswith(b"<NACK ILLEGAL|seq=")
        assert b"|ack=42|" in sent


class TestSendCmd:
    """Emission CMD avec retry idempotent (§5.5 spec)."""

    def test_send_cmd_returns_on_done_received(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        result = []
        def runner():
            try:
                client.send_cmd("CMD", "MOVE 2 5")
                result.append("done")
            except Exception as e:
                result.append(("err", e))

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        # Petite attente pour que la CMD parte
        time.sleep(0.1)

        # Recupere le seq utilise dans la trame TX
        sent = mock_serial.peek_tx()
        import re
        m = re.search(rb"\|seq=(\d+)\|", sent)
        assert m is not None
        seq_used = int(m.group(1))

        # Simule la reception de DONE avec le bon ack
        done = Frame(type="DONE", args="", seq=99, ack=seq_used)
        mock_serial.inject_rx(done.encode())

        t.join(timeout=2)
        assert result == ["done"]

        client.close()

    def test_send_cmd_retries_with_same_seq_on_timeout(self, mock_serial, mock_clock):
        """Apres timeout sans DONE, retransmettre la meme trame avec le meme seq."""
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        # Configure timeout court pour test
        client._cmd_timeout_seconds = 1.0

        result = []
        def runner():
            try:
                client.send_cmd("CMD", "MOVE 2 5")
                result.append("done")
            except UartTimeoutError as e:
                result.append(("timeout", e))

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        time.sleep(0.1)
        first_tx = mock_serial.peek_tx()
        import re
        first_seq = int(re.search(rb"\|seq=(\d+)\|", first_tx).group(1))

        # Avance l'horloge mock pour declencher le 1er retry
        mock_clock.advance(1.5)
        time.sleep(0.1)

        full_tx = mock_serial.peek_tx()
        # On doit voir 2 trames maintenant : envoi initial + retry, MEME seq
        all_seqs = re.findall(rb"\|seq=(\d+)\|", full_tx)
        assert len(all_seqs) >= 2
        assert all_seqs[0] == all_seqs[1]
        assert int(all_seqs[0]) == first_seq

        # Resoudre proprement
        done = Frame(type="DONE", args="", seq=99, ack=first_seq)
        mock_serial.inject_rx(done.encode())
        t.join(timeout=2)

        client.close()

    def test_send_cmd_raises_timeout_after_3_attempts(self, mock_serial, mock_clock):
        """3 essais sans DONE -> UartTimeoutError."""
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()
        client._cmd_timeout_seconds = 0.1

        result = []
        def runner():
            try:
                client.send_cmd("CMD", "MOVE 2 5")
                result.append("done")
            except UartTimeoutError as e:
                result.append("timeout")

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        # Avance assez pour 3 timeouts (avec un peu de marge)
        for _ in range(4):
            time.sleep(0.15)
            mock_clock.advance(0.2)

        t.join(timeout=3)
        assert result == ["timeout"]

        client.close()


class TestErrHandling:
    """Reception et classement des ERR (§4.3 spec)."""

    def test_err_recoverable_codes(self):
        from quoridor_engine.uart_client import is_recoverable_err
        assert is_recoverable_err("UART_LOST") is True
        assert is_recoverable_err("BUTTON_MATRIX") is True

    def test_err_unrecoverable_codes(self):
        from quoridor_engine.uart_client import is_recoverable_err
        for code in ["MOTOR_TIMEOUT", "LIMIT_UNEXPECTED", "HOMING_FAILED",
                     "I2C_NACK", "BOOT_I2C", "BOOT_LED", "BOOT_HOMING"]:
            assert is_recoverable_err(code) is False, f"{code} ne doit pas etre recuperable"

    def test_handle_err_recoverable_sends_cmd_reset(self, mock_serial, mock_clock):
        """Reception ERR UART_LOST -> envoi auto de CMD_RESET."""
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        err = Frame(type="ERR", args="UART_LOST", seq=99)
        mock_serial.inject_rx(err.encode())

        time.sleep(0.2)
        frame = client.receive(timeout=0.5)
        action = client.handle_err_received(frame)

        assert action == "RESET_SENT"
        sent = mock_serial.get_tx()
        assert b"<CMD_RESET|" in sent

        client.close()

    def test_handle_err_non_recoverable_raises_hardware_error(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        err = Frame(type="ERR", args="MOTOR_TIMEOUT", seq=99)
        mock_serial.inject_rx(err.encode())

        time.sleep(0.2)
        frame = client.receive(timeout=0.5)

        with pytest.raises(UartHardwareError, match="MOTOR_TIMEOUT"):
            client.handle_err_received(frame)


class TestConnectWithEspInError:
    """§6.6 : RPi reboote + ESP32 deja en ERROR."""

    def test_connect_sends_reset_if_only_err_received(self, mock_serial, mock_clock):
        """Si on recoit ERR au lieu de HELLO -> envoyer CMD_RESET et attendre HELLO."""
        client = UartClient(serial_port=mock_serial, clock=mock_clock, expected_version=1)
        client._start_reader_thread()

        # 1) ESP32 envoie ERR au lieu de HELLO
        err = Frame(type="ERR", args="UART_LOST", seq=99)
        mock_serial.inject_rx(err.encode())

        # 2) Connect doit envoyer CMD_RESET, puis attendre HELLO

        # Lance connect dans un thread
        result = []
        def runner():
            try:
                client.connect(timeout=2.0)
                result.append("connected")
            except Exception as e:
                result.append(("err", type(e).__name__))

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        # Attendre que connect ait envoye CMD_RESET
        time.sleep(0.5)

        sent = mock_serial.get_tx()
        assert b"<CMD_RESET|" in sent

        # 3) Simuler le reboot ESP32 : BOOT_START puis HELLO
        boot = Frame(type="BOOT_START", args="", seq=0)
        hello = Frame(type="HELLO", args="", seq=2, version=1)
        mock_serial.inject_rx(boot.encode() + hello.encode())

        t.join(timeout=3)
        assert result == ["connected"]

        client.close()

        client.close()


class TestDebugCoexistence:
    """Lignes ne commencant pas par '<' = logs debug, ignorees par le protocole (§7.4 spec)."""

    def test_debug_line_does_not_pollute_rx_queue(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()

        mock_serial.inject_rx(b"[FSM] BOOT -> WAITING_RPI\n")
        mock_serial.inject_rx(b"[BTN] tick=12345\n")

        time.sleep(0.2)

        # rx_queue doit etre vide (rien de protocolaire)
        assert client._rx_queue.empty()
        # debug_lines doit contenir les 2 lignes
        assert len(client._debug_lines) == 2
        assert "[FSM]" in client._debug_lines[0]
        assert "[BTN]" in client._debug_lines[1]

        client.close()

    def test_protocol_frame_after_debug_works(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()

        # Mix : log puis trame
        mock_serial.inject_rx(b"[FSM] starting\n")
        f = Frame(type="KEEPALIVE", args="", seq=0)
        mock_serial.inject_rx(f.encode())

        time.sleep(0.2)

        # La frame doit etre dans la queue
        received = client._rx_queue.get(timeout=1)
        assert received.type == "KEEPALIVE"
        # Le log dans debug
        assert any("[FSM]" in l for l in client._debug_lines)

        client.close()

    def test_line_with_lt_in_middle_is_debug(self, mock_serial, mock_clock):
        """[FSM] transition from <BOOT> n'est PAS une trame, c'est du debug."""
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()

        mock_serial.inject_rx(b"[FSM] transition from <BOOT>\n")

        time.sleep(0.2)

        assert client._rx_queue.empty()
        assert len(client._debug_lines) == 1

        client.close()

    def test_corrupted_protocol_frame_is_silently_dropped(self, mock_serial, mock_clock):
        """Une trame avec mauvais CRC est ignoree silencieusement (§3.6)."""
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()

        mock_serial.inject_rx(b"<KEEPALIVE|seq=0|crc=0000>\n")  # CRC bidon

        time.sleep(0.2)

        # Rien dans la queue (rejet silencieux)
        assert client._rx_queue.empty()

        client.close()


class TestSessionReset:
    """Reset session sur BOOT_START ou nouveau HELLO en session active (§5.1 spec)."""

    def test_boot_start_resets_tx_seq(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True

        # Avance le compteur
        for _ in range(10):
            client.send_keepalive()
        # tx_seq devrait etre a 10
        assert client._tx_seq == 10

        # Simule reception BOOT_START
        client._reset_session()

        assert client._tx_seq == 0
        assert client._last_request_seq is None

    def test_reader_resets_session_on_boot_start(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        # Avance le compteur
        for _ in range(5):
            client.send_keepalive()

        # Inject BOOT_START
        boot = Frame(type="BOOT_START", args="", seq=0)
        mock_serial.inject_rx(boot.encode())

        time.sleep(0.2)

        # tx_seq doit etre reset
        assert client._tx_seq == 0

        client.close()


class TestFrameDecodeEdgeCases:
    """Branches defensives de Frame.decode non couvertes par les tests de base."""

    def test_decode_strips_cr_before_lf(self):
        # L66 : strip \r apres avoir enleve \n -> doit accepter \r\n final
        original = Frame(type="KEEPALIVE", args="", seq=0)
        encoded_with_crlf = original.encode().rstrip(b"\n") + b"\r\n"
        decoded = Frame.decode(encoded_with_crlf)
        assert decoded.type == "KEEPALIVE"

    def test_decode_rejects_no_pipe_metadata(self):
        # L82 : len(parts) < 2 -> "trame sans champs metadata"
        # Construire une trame avec un seul champ (pas de '|')
        # On forge directement car il n'y a pas de CRC valide possible sans '|'
        with pytest.raises(UartProtocolError, match="champs metadata"):
            Frame.decode(b"<KEEPALIVE>")

    def test_decode_rejects_non_hex_crc(self):
        # L105-106 : int(crc_value, 16) leve ValueError -> "crc non hexadecimal"
        with pytest.raises(UartProtocolError, match="crc non hexadecimal"):
            Frame.decode(b"<KEEPALIVE|seq=0|crc=ZZZZ>")

    def test_decode_rejects_non_numeric_seq(self):
        # L116-117 : int(field[4:]) leve ValueError pour seq= non numerique
        body = "KEEPALIVE|seq=ABC"
        crc = compute_crc(body.encode("ascii"))
        raw = f"<{body}|crc={crc:04X}>".encode("ascii")
        with pytest.raises(UartProtocolError, match="seq non numerique"):
            Frame.decode(raw)

    def test_decode_rejects_non_numeric_ack(self):
        # L123-124 : int(field[4:]) leve ValueError pour ack= non numerique
        body = "ACK|seq=0|ack=XYZ"
        crc = compute_crc(body.encode("ascii"))
        raw = f"<{body}|crc={crc:04X}>".encode("ascii")
        with pytest.raises(UartProtocolError, match="ack non numerique"):
            Frame.decode(raw)

    def test_decode_rejects_ack_out_of_range(self):
        # L126 : ack hors [0, 255] -> "ack hors plage"
        body = "ACK|seq=0|ack=300"
        crc = compute_crc(body.encode("ascii"))
        raw = f"<{body}|crc={crc:04X}>".encode("ascii")
        with pytest.raises(UartProtocolError, match="ack hors plage"):
            Frame.decode(raw)

    def test_decode_rejects_non_numeric_version(self):
        # L130-131 : int(field[2:]) leve ValueError pour v= non numerique
        body = "HELLO|seq=0|v=abc"
        crc = compute_crc(body.encode("ascii"))
        raw = f"<{body}|crc={crc:04X}>".encode("ascii")
        with pytest.raises(UartProtocolError, match="v non numerique"):
            Frame.decode(raw)


class TestUartClientEdgeCases:
    """Branches defensives de UartClient non couvertes par les tests nominaux."""

    def test_reader_loop_breaks_on_serial_exception(self, mock_serial, mock_clock):
        # L259-260 : si serial.read() leve une exception, le thread s'arrete
        call_count = [0]
        original_read = mock_serial.read

        def failing_read(n):
            call_count[0] += 1
            if call_count[0] > 1:
                raise IOError("port ferme")
            return b""

        mock_serial.read = failing_read
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()
        time.sleep(0.3)
        # Le thread doit s'etre arrete apres l'exception
        assert not client._reader_thread.is_alive()

    def test_reader_loop_clears_buffer_on_overflow(self, mock_serial, mock_clock):
        # L272 : si buffer > 80 octets sans \n, _read_buffer est vide
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        # Injecte > 80 octets sans \n (pas de newline pour forcer accumulation)
        mock_serial.inject_rx(b"X" * 90)
        client._start_reader_thread()
        time.sleep(0.3)
        # Le buffer doit avoir ete vide (pas de crash, pas de \n = tout jete)
        assert len(client._read_buffer) == 0
        client.close()

    def test_dispatch_ignores_empty_stripped_line(self, mock_serial, mock_clock):
        # L283 : ligne vide apres rstrip -> return immediat
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._dispatch_line(b"\r\n")  # stripped -> b"" -> return
        assert client._rx_queue.empty()
        assert client._debug_lines == []

    def test_dispatch_debug_rotation_trims_old_lines(self, mock_serial, mock_clock):
        # L306 : quand debug_lines depasse MAX_DEBUG_LINES, rotation
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        # Injecter MAX_DEBUG_LINES + 5 lignes debug directement via _dispatch_line
        for i in range(client.MAX_DEBUG_LINES + 5):
            client._dispatch_line(f"[DBG] line {i}\n".encode("ascii"))
        assert len(client._debug_lines) == client.MAX_DEBUG_LINES

    def test_close_handles_serial_exception_gracefully(self, mock_serial, mock_clock):
        # L315-316 : serial.close() leve une exception -> ignoree silencieusement
        def failing_close():
            raise IOError("erreur fermeture")
        mock_serial.close = failing_close
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()
        # Ne doit pas lever d'exception
        client.close()
        assert client.is_connected is False

    def test_send_ack_no_op_if_not_connected(self, mock_serial, mock_clock):
        # L402 : send_ack ne fait rien si is_connected = False
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.send_ack(request_seq=42)
        assert mock_serial.get_tx() == b""

    def test_send_nack_no_op_if_not_connected(self, mock_serial, mock_clock):
        # L408 : send_nack ne fait rien si is_connected = False
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.send_nack(request_seq=42, reason="ILLEGAL")
        assert mock_serial.get_tx() == b""

    def test_send_cmd_raises_if_not_connected(self, mock_serial, mock_clock):
        # L419 : send_cmd leve UartError si is_connected = False
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        with pytest.raises(UartError, match="non connecte"):
            client.send_cmd("CMD", "MOVE 2 5")

    def test_send_cmd_raises_hardware_error_on_err_response(self, mock_serial, mock_clock):
        # L441-443 : si ERR recu avec ack=seq pendant send_cmd -> UartHardwareError
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        result = []
        def runner():
            try:
                client.send_cmd("CMD", "MOVE 2 5")
                result.append("done")
            except UartHardwareError as e:
                result.append(("hardware_err", e.code))

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        time.sleep(0.1)

        # Recupere le seq utilise
        sent = mock_serial.peek_tx()
        import re
        m = re.search(rb"\|seq=(\d+)\|", sent)
        assert m is not None
        seq_used = int(m.group(1))

        # Simule ERR avec ack=seq (erreur hardware)
        err = Frame(type="ERR", args="MOTOR_TIMEOUT", seq=99, ack=seq_used)
        mock_serial.inject_rx(err.encode())

        t.join(timeout=2)
        assert result == [("hardware_err", "MOTOR_TIMEOUT")]

        client.close()

    def test_send_cmd_requeues_unrelated_frames(self, mock_serial, mock_clock):
        # L449-450 : frames non liees a la requete courante sont remises en queue
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        result = []
        def runner():
            try:
                client.send_cmd("CMD", "MOVE 2 5")
                result.append("done")
            except Exception as e:
                result.append(("err", e))

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        time.sleep(0.1)

        # Recupere le seq utilise
        sent = mock_serial.peek_tx()
        import re
        m = re.search(rb"\|seq=(\d+)\|", sent)
        assert m is not None
        seq_used = int(m.group(1))

        # Injecte une MOVE_REQ (non liee) puis le DONE
        unrelated = Frame(type="MOVE_REQ", args="1 2", seq=10)
        done = Frame(type="DONE", args="", seq=99, ack=seq_used)
        mock_serial.inject_rx(unrelated.encode() + done.encode())

        t.join(timeout=2)
        assert result == ["done"]

        # La MOVE_REQ doit etre remise dans la queue
        requeued = client.receive(timeout=0.5)
        assert requeued is not None
        assert requeued.type == "MOVE_REQ"

        client.close()

    def test_handle_err_received_raises_on_non_err_frame(self, mock_serial, mock_clock):
        # L467 : leve ValueError si frame.type != "ERR"
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        f = Frame(type="KEEPALIVE", args="", seq=0)
        with pytest.raises(ValueError, match="ERR"):
            client.handle_err_received(f)

    def test_send_cmd_reset_no_op_if_not_connected(self, mock_serial, mock_clock):
        # L484 : send_cmd_reset ne fait rien si is_connected = False
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.send_cmd_reset()
        assert mock_serial.get_tx() == b""


class TestRejectedCount:
    """Verifie le compteur de trames mal formees (cf. spec P9 §9.2)."""

    def test_rejected_count_starts_at_zero(self, mock_serial):
        client = UartClient(mock_serial)
        assert client.get_rejected_count() == 0

    def test_rejected_count_increments_on_malformed_frame(self, mock_serial):
        client = UartClient(mock_serial)
        client._start_reader_thread()
        try:
            # Trame avec CRC invalide (volontairement faux)
            mock_serial.inject_rx(b"<MOVE_REQ 3 4|seq=0|crc=0000>\n")
            time.sleep(0.1)  # laisser le reader thread la consommer
            assert client.get_rejected_count() >= 1
        finally:
            client.close()
