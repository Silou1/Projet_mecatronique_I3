"""Tests pour GameSession (spec P9 §4-§6)."""

from quoridor_engine.uart_client import UartClient


class TestGameSessionConstruction:
    """Construction de l'orchestrateur plateau."""

    def test_can_construct_with_required_args(self, mock_serial):
        from quoridor_engine import QuoridorGame, AI, GameSession

        game = QuoridorGame()
        ai = AI(player="j2", difficulty="normal")
        uart = UartClient(mock_serial)
        session = GameSession(game, ai, uart, debug=False)

        assert session.game is game
        assert session.ai is ai
        assert session.uart is uart
        assert session.debug is False
        assert session._unexpected_frame_count == 0
