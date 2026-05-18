"""Tests de UartBridge (utilise des mocks, pas de hardware requis)."""
from unittest.mock import MagicMock, patch

import pytest

from webapp.uart_bridge import UartBridge, init


class TestInit:
    def test_init_sans_port_retourne_none(self):
        with patch("webapp.uart_bridge._find_devkit_port", return_value=None):
            assert init() is None

    def test_init_avec_erreur_uart_retourne_none(self):
        with patch("webapp.uart_bridge._find_devkit_port", return_value="/dev/null"), \
             patch("webapp.uart_bridge._open_client", side_effect=Exception("boom")):
            assert init() is None

    def test_init_succes_retourne_bridge(self):
        fake_client = MagicMock()
        with patch("webapp.uart_bridge._find_devkit_port", return_value="/dev/null"), \
             patch("webapp.uart_bridge._open_client", return_value=fake_client):
            bridge = init()
            assert bridge is not None
            assert bridge.available is True


class TestForwardMove:
    def test_forward_deplacement_envoie_pawn(self):
        fake_client = MagicMock()
        bridge = UartBridge(fake_client)
        move = ("deplacement", {"type": "deplacement", "target": [4, 3]})
        bridge.forward_move(move)
        fake_client.send_cmd.assert_called_once_with("PAWN", "4 3")
        assert bridge.available is True

    def test_forward_mur_envoie_wall(self):
        fake_client = MagicMock()
        bridge = UartBridge(fake_client)
        move = ("mur", {"type": "mur", "orientation": "h", "row": 2, "col": 3})
        bridge.forward_move(move)
        fake_client.send_cmd.assert_called_once_with("WALL", "h 2 3")
        assert bridge.available is True

    def test_forward_erreur_desactive_disponibilite(self):
        fake_client = MagicMock()
        fake_client.send_cmd.side_effect = Exception("uart dead")
        bridge = UartBridge(fake_client)
        bridge.forward_move(("deplacement", {"type": "deplacement", "target": [4, 3]}))
        assert bridge.available is False

    def test_forward_no_op_quand_indisponible(self):
        fake_client = MagicMock()
        bridge = UartBridge(fake_client)
        bridge.available = False
        bridge.forward_move(("deplacement", {"type": "deplacement", "target": [4, 3]}))
        fake_client.send_cmd.assert_not_called()

    def test_forward_type_inconnu_no_op(self):
        """Un type de coup inconnu ne doit ni lever ni désactiver le bridge."""
        fake_client = MagicMock()
        bridge = UartBridge(fake_client)
        bridge.forward_move(("blabla", {}))
        fake_client.send_cmd.assert_not_called()
        assert bridge.available is True
