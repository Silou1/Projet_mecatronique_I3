"""Tests pour GameSession (spec P9 §4-§6)."""

from quoridor_engine.uart_client import Frame, UartClient


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


class TestParseIntentToMove:
    """Conversion des intentions ESP32 vers coups moteur."""

    def _make_session(self, mock_serial):
        from quoridor_engine import QuoridorGame, AI, GameSession

        return GameSession(QuoridorGame(), AI(player="j2"), UartClient(mock_serial))

    def test_move_req_valid(self, mock_serial):
        session = self._make_session(mock_serial)
        frame = Frame(type="MOVE_REQ", args="3 4", seq=42)

        coup = session._parse_intent_to_move(frame)

        assert coup == ("deplacement", (3, 4))

    def test_wall_req_horizontal(self, mock_serial):
        session = self._make_session(mock_serial)
        frame = Frame(type="WALL_REQ", args="h 2 3", seq=43)

        coup = session._parse_intent_to_move(frame)

        assert coup == ("mur", ("h", 2, 3, 2))

    def test_wall_req_vertical(self, mock_serial):
        session = self._make_session(mock_serial)
        frame = Frame(type="WALL_REQ", args="v 1 2", seq=44)

        coup = session._parse_intent_to_move(frame)

        assert coup == ("mur", ("v", 1, 2, 2))

    def test_move_req_malformed_returns_none(self, mock_serial):
        session = self._make_session(mock_serial)
        frame = Frame(type="MOVE_REQ", args="abc", seq=45)

        coup = session._parse_intent_to_move(frame)

        assert coup is None

    def test_wall_req_invalid_orientation_returns_none(self, mock_serial):
        session = self._make_session(mock_serial)
        frame = Frame(type="WALL_REQ", args="x 2 3", seq=46)

        coup = session._parse_intent_to_move(frame)

        assert coup is None


class TestMoveToCmdArgs:
    """Conversion des coups moteur vers arguments CMD firmware."""

    def _make_session(self, mock_serial):
        from quoridor_engine import QuoridorGame, AI, GameSession

        return GameSession(QuoridorGame(), AI(player="j2"), UartClient(mock_serial))

    def test_pawn_move(self, mock_serial):
        session = self._make_session(mock_serial)
        coup = ("deplacement", (2, 5))

        assert session._move_to_cmd_args(coup) == "MOVE 2 5"

    def test_wall_horizontal(self, mock_serial):
        session = self._make_session(mock_serial)
        coup = ("mur", ("h", 1, 2, 2))

        assert session._move_to_cmd_args(coup) == "WALL h 1 2"

    def test_wall_vertical(self, mock_serial):
        session = self._make_session(mock_serial)
        coup = ("mur", ("v", 3, 4, 2))

        assert session._move_to_cmd_args(coup) == "WALL v 3 4"
