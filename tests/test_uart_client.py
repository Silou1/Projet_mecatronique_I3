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
