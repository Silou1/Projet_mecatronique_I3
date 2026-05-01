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
