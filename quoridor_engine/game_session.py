"""Session de jeu plateau (orchestration RPi <-> ESP32 via UART).

Spec : docs/superpowers/specs/2026-05-03-p9-integration-rpi-esp32-design.md
"""

from .ai import AI
from .core import Move, QuoridorGame
from .uart_client import Frame, UartClient


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
        """Boucle principale, implementee progressivement par les tasks suivantes."""
        raise NotImplementedError("implemente dans Tasks 11-16")

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

    def _send_gameover(self) -> None:
        """Envoi GAMEOVER, implemente en Task 14."""
        raise NotImplementedError("implemente en Task 14")
