"""Session de jeu plateau (orchestration RPi <-> ESP32 via UART).

Spec : docs/superpowers/specs/2026-05-03-p9-integration-rpi-esp32-design.md
"""

from .ai import AI
from .core import InvalidMoveError, Move, NackCode, QuoridorGame
from .uart_client import Frame, UartClient, UartError, UartHardwareError, UartTimeoutError


class GameSession:
    """Orchestre une partie en mode plateau physique."""

    HANDSHAKE_TIMEOUT_S = 15.0

    def __init__(
        self,
        game: QuoridorGame,
        ai: AI,
        uart: UartClient,
        debug: bool = False,
    ):
        self.game = game
        self.ai = ai
        self.uart = uart
        self.debug = debug
        self._unexpected_frame_count = 0

    def run(self) -> None:
        """Lance la session plateau."""
        try:
            self.uart.connect(timeout=self.HANDSHAKE_TIMEOUT_S)
            self._game_loop()
            self._send_gameover()
        finally:
            self.uart.close()

    def _game_loop(self) -> None:
        """Alterne tour humain (j1) et tour IA (j2) jusqu'à la fin de partie."""
        while True:
            is_over, _winner = self.game.is_game_over()
            if is_over:
                return

            if self.game.get_current_player() == "j1":
                self._await_player_intent()
            else:
                self._send_ai_move()

    def _await_player_intent(self) -> None:
        """Attend une intention plateau et traite aussi les ERR spontanées."""
        while True:
            frame = self.uart.receive(timeout=0.5)
            if frame is None:
                self._check_health()
                continue

            if frame.type in ("MOVE_REQ", "WALL_REQ"):
                self._process_player_intent(frame)
                return

            if frame.type == "ERR":
                self._handle_err(frame)
                return

            self._unexpected_frame_count += 1
            if self.debug:
                print(f"[debug] frame inattendue ignoree: {frame}")

    def _check_health(self) -> None:
        """Lève immédiatement si le thread de lecture UART est mort."""
        if not self.uart._is_reader_alive():
            raise UartError("reader thread died - partie interrompue")

    def _parse_intent_to_move(self, frame: Frame) -> Move | None:
        """Convertit une trame MOVE_REQ ou WALL_REQ en coup moteur."""
        parts = frame.args.split()

        try:
            if frame.type == "MOVE_REQ":
                if len(parts) != 2:
                    return None
                row, col = int(parts[0]), int(parts[1])
                return ("deplacement", (row, col))

            if frame.type == "WALL_REQ":
                if len(parts) != 3:
                    return None
                orient, row, col = parts[0], int(parts[1]), int(parts[2])
                if orient not in ("h", "v"):
                    return None
                return ("mur", (orient, row, col, 2))

        except ValueError:
            return None

        return None

    def _move_to_cmd_args(self, coup: Move) -> str:
        """Serialise un coup moteur en arguments CMD pour le firmware ESP32."""
        kind, payload = coup

        if kind == "deplacement":
            row, col = payload
            return f"MOVE {row} {col}"

        if kind == "mur":
            orient, row, col, _ = payload
            return f"WALL {orient} {row} {col}"

        raise ValueError(f"coup non reconnu: {coup!r}")

    def _process_player_intent(self, frame: Frame) -> None:
        """Valide une intention joueur et répond ACK ou NACK au firmware."""
        coup = self._parse_intent_to_move(frame)
        if coup is None:
            self.uart.send_nack(frame.seq, NackCode.INVALID_FORMAT.value)
            if self.debug:
                print(f"[debug] NACK INVALID_FORMAT seq={frame.seq} args={frame.args!r}")
            return

        try:
            self.game.play_move(coup)
        except InvalidMoveError as exc:
            self.uart.send_nack(frame.seq, exc.code.value)
            if self.debug:
                print(f"[debug] NACK {exc.code.value} seq={frame.seq}: {exc}")
            return

        self.uart.send_ack(frame.seq)
        if self.debug:
            print(f"[debug] ACK seq={frame.seq} coup={coup}")

    def _send_ai_move(self) -> None:
        """Envoie le coup IA au firmware, puis le commit après DONE."""
        state = self.game.get_current_state()
        coup = self.ai.find_best_move(state, verbose=False)
        cmd_args = self._move_to_cmd_args(coup)

        if self.debug:
            print(f"[debug] IA -> CMD {cmd_args}")

        self.uart.send_cmd("CMD", cmd_args)
        self.game.play_move(coup)

    def _handle_err(self, frame: Frame) -> None:
        """Traite une ERR firmware, avec reconnexion si elle est récupérable."""
        result = self.uart.handle_err_received(frame)
        if result == "RESET_SENT":
            if self.debug:
                print(f"[debug] ERR recuperable {frame.args} -> CMD_RESET, reconnexion")
            self.uart.connect(timeout=self.HANDSHAKE_TIMEOUT_S)
            if self.debug:
                print("[debug] reconnexion reussie")

    def _send_gameover(self) -> None:
        """Envoie CMD GAMEOVER en fin de partie si un gagnant existe."""
        winner = self.game.get_winner()
        if winner is None:
            return

        if self.debug:
            print(f"[debug] FIN DE PARTIE -> CMD GAMEOVER {winner}")

        try:
            self.uart.send_cmd("CMD", f"GAMEOVER {winner}")
        except (UartTimeoutError, UartHardwareError) as exc:
            if self.debug:
                print(f"[debug] CMD GAMEOVER echec : {exc}")
