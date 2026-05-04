"""Session de jeu plateau (orchestration RPi <-> ESP32 via UART).

Spec : docs/superpowers/specs/2026-05-03-p9-integration-rpi-esp32-design.md
"""

from .ai import AI
from .core import QuoridorGame
from .uart_client import UartClient


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

    def _send_gameover(self) -> None:
        """Envoi GAMEOVER, implemente en Task 14."""
        raise NotImplementedError("implemente en Task 14")
