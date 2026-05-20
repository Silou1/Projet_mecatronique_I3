"""Tests de UartBridge (utilise des mocks, pas de hardware requis)."""
from unittest.mock import patch, MagicMock

from webapp.uart_bridge import UartBridge, init, _open_and_handshake


# ---------- init() ----------

def test_init_no_port_returns_none():
    with patch("webapp.uart_bridge._find_devkit_port", return_value=None):
        assert init() is None


def test_init_handshake_failure_returns_none():
    with patch("webapp.uart_bridge._find_devkit_port", return_value="/dev/null"), \
         patch("webapp.uart_bridge._open_and_handshake", return_value=None):
        assert init() is None


def test_init_handshake_success_returns_bridge():
    fake_serial = MagicMock()
    with patch("webapp.uart_bridge._find_devkit_port", return_value="/dev/null"), \
         patch("webapp.uart_bridge._open_and_handshake", return_value=fake_serial):
        bridge = init()
        assert bridge is not None
        assert bridge.available is True


# ---------- _open_and_handshake() ----------

def test_open_and_handshake_pong_received():
    fake_serial = MagicMock()
    fake_serial.readline.return_value = b"PONG\n"
    with patch("webapp.uart_bridge.serial.Serial", return_value=fake_serial):
        result = _open_and_handshake("/dev/null")
        assert result is fake_serial
        fake_serial.write.assert_called_with(b"PING\n")


def test_open_and_handshake_no_pong_returns_none_and_closes():
    fake_serial = MagicMock()
    fake_serial.readline.return_value = b""
    with patch("webapp.uart_bridge.serial.Serial", return_value=fake_serial), \
         patch("webapp.uart_bridge.PING_TIMEOUT_S", 0.05):
        result = _open_and_handshake("/dev/null")
        assert result is None
        fake_serial.close.assert_called()


def test_open_and_handshake_serial_open_exception_returns_none():
    with patch("webapp.uart_bridge.serial.Serial", side_effect=OSError("boom")):
        assert _open_and_handshake("/dev/null") is None


# ---------- UartBridge.forward_move() ----------

def test_forward_wall_h_writes_swapped_v():
    """Mur 'h' engine -> 'V' firmware (inversion conventionnelle plateau)."""
    fake = MagicMock()
    b = UartBridge(fake)
    b.forward_move(("mur", {"orientation": "h", "row": 2, "col": 3}))
    fake.write.assert_called_with(b"WALL V 2 3\n")
    fake.flush.assert_called()


def test_forward_wall_v_writes_swapped_h():
    """Mur 'v' engine -> 'H' firmware (inversion conventionnelle plateau)."""
    fake = MagicMock()
    b = UartBridge(fake)
    b.forward_move(("mur", {"orientation": "v", "row": 0, "col": 4}))
    fake.write.assert_called_with(b"WALL H 0 4\n")


def test_forward_pawn_is_noop():
    fake = MagicMock()
    b = UartBridge(fake)
    b.forward_move(("deplacement", {"target": [4, 2]}))
    fake.write.assert_not_called()


def test_forward_serial_exception_deactivates():
    fake = MagicMock()
    fake.write.side_effect = OSError("port mort")
    b = UartBridge(fake)
    b.forward_move(("mur", {"orientation": "h", "row": 0, "col": 0}))
    assert b.available is False


def test_forward_when_unavailable_is_noop():
    fake = MagicMock()
    b = UartBridge(fake)
    b.available = False
    b.forward_move(("mur", {"orientation": "h", "row": 0, "col": 0}))
    fake.write.assert_not_called()


def test_forward_unknown_move_type_does_not_crash():
    fake = MagicMock()
    b = UartBridge(fake)
    b.forward_move(("inconnu", {}))
    fake.write.assert_not_called()
    assert b.available is True
