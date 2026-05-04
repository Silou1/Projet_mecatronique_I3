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


class TestProcessPlayerIntent:
    """Spec P9 §4.4 : MOVE_REQ/WALL_REQ valide -> ACK ; invalide -> NACK <code>."""

    def _make_connected_session(self, mock_serial):
        from quoridor_engine import QuoridorGame, AI, GameSession, UartClient

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(QuoridorGame(), AI(player="j2"), client)
        return session, client

    def test_valid_move_req_sends_ack(self, mock_serial):
        session, client = self._make_connected_session(mock_serial)
        client._start_reader_thread()
        try:
            frame = Frame(type="MOVE_REQ", args="4 3", seq=42)

            session._process_player_intent(frame)

            tx = mock_serial.get_tx()
            assert b"<ACK|" in tx
            assert b"ack=42" in tx
            assert session.game.get_current_player() == "j2"
        finally:
            client.close()

    def test_invalid_move_req_sends_nack_with_code(self, mock_serial):
        session, client = self._make_connected_session(mock_serial)
        client._start_reader_thread()
        try:
            frame = Frame(type="MOVE_REQ", args="0 0", seq=43)

            session._process_player_intent(frame)

            tx = mock_serial.get_tx()
            assert b"<NACK ILLEGAL|" in tx
            assert b"ack=43" in tx
        finally:
            client.close()

    def test_malformed_move_req_sends_nack_invalid_format(self, mock_serial):
        session, client = self._make_connected_session(mock_serial)
        client._start_reader_thread()
        try:
            frame = Frame(type="MOVE_REQ", args="xyz", seq=44)

            session._process_player_intent(frame)

            tx = mock_serial.get_tx()
            assert b"<NACK INVALID_FORMAT|" in tx
            assert b"ack=44" in tx
        finally:
            client.close()


class TestSendAiMove:
    """Spec P9 §5.2 : tour IA -> CMD MOVE/WALL -> DONE -> commit moteur."""

    def _make_connected_session_with_ai(self, mock_serial, fake_move):
        from quoridor_engine import QuoridorGame, GameSession, UartClient

        class FakeAI:
            def __init__(self, move):
                self._move = move
                self.player = "j2"

            def find_best_move(self, state, verbose=False):
                return self._move

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(QuoridorGame(), FakeAI(fake_move), client)
        return session, client

    def test_ai_pawn_move_sends_cmd_then_commits(self, mock_serial):
        session, client = self._make_connected_session_with_ai(
            mock_serial, ("deplacement", (1, 3))
        )
        client._start_reader_thread()
        try:
            session.game.play_move(("deplacement", (4, 3)))
            done = Frame(type="DONE", args="", seq=0, ack=0)
            mock_serial.inject_rx(done.encode())

            session._send_ai_move()

            tx = mock_serial.get_tx()
            assert b"<CMD MOVE 1 3|" in tx
            assert session.game.get_current_player() == "j1"
        finally:
            client.close()

    def test_ai_wall_move_sends_cmd_wall(self, mock_serial):
        session, client = self._make_connected_session_with_ai(
            mock_serial, ("mur", ("h", 1, 1, 2))
        )
        client._start_reader_thread()
        try:
            session.game.play_move(("deplacement", (4, 3)))
            done = Frame(type="DONE", args="", seq=0, ack=0)
            mock_serial.inject_rx(done.encode())

            session._send_ai_move()

            tx = mock_serial.get_tx()
            assert b"<CMD WALL h 1 1|" in tx
        finally:
            client.close()


class TestSendGameover:
    """Spec P9 §5.4 : fin de partie -> CMD GAMEOVER <winner>."""

    def test_send_gameover_with_winner(self, mock_serial):
        from quoridor_engine import AI, GameSession, UartClient

        class StubGame:
            def get_winner(self):
                return "j1"

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(StubGame(), AI(player="j2"), client)
        client._start_reader_thread()
        try:
            done = Frame(type="DONE", args="", seq=0, ack=0)
            mock_serial.inject_rx(done.encode())

            session._send_gameover()

            tx = mock_serial.get_tx()
            assert b"<CMD GAMEOVER j1|" in tx
        finally:
            client.close()

    def test_send_gameover_no_winner_is_no_op(self, mock_serial):
        from quoridor_engine import AI, GameSession, UartClient

        class StubGame:
            def get_winner(self):
                return None

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(StubGame(), AI(player="j2"), client)
        client._start_reader_thread()
        try:
            session._send_gameover()

            tx = mock_serial.get_tx()
            assert b"GAMEOVER" not in tx
        finally:
            client.close()


class TestHandleErr:
    """Spec P9 §6.4 : ERR récupérable -> reconnect ; non-récupérable -> remonte."""

    def test_recoverable_err_triggers_reconnect(self, mock_serial):
        from quoridor_engine import QuoridorGame, AI, GameSession, UartClient

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(QuoridorGame(), AI(player="j2"), client)
        client._start_reader_thread()
        try:
            hello = Frame(type="HELLO", args="", seq=0, version=UartClient.PROTOCOL_VERSION)
            mock_serial.inject_rx(hello.encode())

            err = Frame(type="ERR", args="UART_LOST", seq=99)
            session._handle_err(err)

            tx = mock_serial.get_tx()
            assert b"CMD_RESET" in tx
            assert b"HELLO_ACK" in tx
            assert client.is_connected is True
        finally:
            client.close()

    def test_non_recoverable_err_raises(self, mock_serial):
        import pytest
        from quoridor_engine import QuoridorGame, AI, GameSession, UartClient
        from quoridor_engine.uart_client import UartHardwareError

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(QuoridorGame(), AI(player="j2"), client)
        client._start_reader_thread()
        try:
            err = Frame(type="ERR", args="HOMING_FAILED", seq=100)
            with pytest.raises(UartHardwareError):
                session._handle_err(err)
        finally:
            client.close()


class TestGameLoop:
    """Spec P9 §4.2 : alternance j1 plateau / j2 IA."""

    def test_loop_exits_when_game_is_over(self, mock_serial):
        from quoridor_engine import AI, GameSession, UartClient

        class StubGame:
            def is_game_over(self):
                return (True, "j1")

            def get_current_player(self):
                return "j1"

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(StubGame(), AI(player="j2"), client)
        client._start_reader_thread()
        try:
            session._game_loop()
        finally:
            client.close()

    def test_check_health_raises_if_reader_dead(self, mock_serial):
        import pytest
        from quoridor_engine import QuoridorGame, AI, GameSession, UartClient
        from quoridor_engine.uart_client import UartError

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(QuoridorGame(), AI(player="j2"), client)

        with pytest.raises(UartError):
            session._check_health()
