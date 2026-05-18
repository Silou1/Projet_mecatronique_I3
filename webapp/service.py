"""Service singleton qui détient l'état du jeu et orchestre l'IA.

Cette couche enveloppe `quoridor_engine` et `AI` pour exposer une API thread-safe
adaptée au backend web : création/reset de partie, application de coups,
sérialisation pour /api/state.
"""
from __future__ import annotations

import threading
import time
from typing import Optional, TYPE_CHECKING

from quoridor_engine import GameState, AI, InvalidMoveError
from quoridor_engine.core import PLAYER_ONE, PLAYER_TWO, create_new_game

if TYPE_CHECKING:
    from webapp.uart_bridge import UartBridge


# Délais minimaux entre deux coups IA, en secondes
_DELAIS = {"lent": 2.5, "normal": 1.5, "rapide": 0.7}


class QuoridorService:
    """Singleton qui détient l'état partagé de la partie.

    Toutes les méthodes publiques acquièrent `_lock` avant de toucher l'état.
    Le thread `tick` appelle aussi `_lock` ; les sections critiques doivent être courtes.
    """

    def __init__(self, uart_bridge: Optional["UartBridge"] = None):
        self._uart_bridge = uart_bridge
        self._lock = threading.Lock()
        # Réglages persistés entre parties (cf. spec §9.7)
        self._mode: str = "human_vs_ai"
        self._difficulty: str = "normal"
        self._speed: str = "normal"
        self._plateau_mode: bool = False
        self._reset_partie()

    def _reset_partie(self) -> None:
        """Remet l'état partie à zéro. À appeler dans le lock (ou avant init)."""
        self._state: Optional[GameState] = None
        self._ai_j1: Optional[AI] = None
        self._ai_j2: Optional[AI] = None
        self._status: str = "waiting"
        self._winner: Optional[str] = None
        self._turn_count: int = 0
        self._ai_thinking: bool = False
        self._last_ai_move_at: float = 0.0
        self._last_error: Optional[dict] = None
        self._wall_placement_mode: Optional[str] = None

    def new_game(self, mode: str, difficulty: str, plateau_mode: bool) -> None:
        """Démarre une nouvelle partie."""
        with self._lock:
            self._reset_partie()
            self._mode = mode
            self._difficulty = difficulty
            self._plateau_mode = plateau_mode
            self._state = create_new_game()
            if mode == "human_vs_ai":
                self._ai_j2 = AI(player=PLAYER_TWO, difficulty=difficulty)
            elif mode == "ai_vs_ai":
                self._ai_j1 = AI(player=PLAYER_ONE, difficulty=difficulty)
                self._ai_j2 = AI(player=PLAYER_TWO, difficulty=difficulty)
            self._status = "playing"
            self._last_ai_move_at = time.monotonic()

    def to_dict(self) -> dict:
        """Sérialise l'état pour /api/state."""
        with self._lock:
            return self._to_dict_unlocked()

    def _to_dict_unlocked(self) -> dict:
        plateau = {
            "available": self._uart_bridge is not None and self._uart_bridge.available,
            "mode_active": self._plateau_mode,
            "connected": (
                self._uart_bridge is not None
                and self._uart_bridge.available
                and self._plateau_mode
            ),
        }

        if self._state is None:
            return {
                "mode": self._mode,
                "difficulty": self._difficulty,
                "speed": self._speed,
                "status": self._status,
                "turn_count": 0,
                "current_player": None,
                "ai_thinking": False,
                "players": {},
                "walls": [],
                "winner": None,
                "plateau": plateau,
                "last_error": self._last_error,
                "wall_placement_mode": None,
            }

        is_ai_j1 = self._ai_j1 is not None
        is_ai_j2 = self._ai_j2 is not None

        return {
            "mode": self._mode,
            "difficulty": self._difficulty,
            "speed": self._speed,
            "status": self._status,
            "turn_count": self._turn_count,
            "current_player": self._state.current_player,
            "ai_thinking": self._ai_thinking,
            "players": {
                "j1": {
                    "position": list(self._state.player_positions[PLAYER_ONE]),
                    "walls_remaining": self._state.player_walls[PLAYER_ONE],
                    "is_ai": is_ai_j1,
                    "is_winner": self._winner == PLAYER_ONE,
                },
                "j2": {
                    "position": list(self._state.player_positions[PLAYER_TWO]),
                    "walls_remaining": self._state.player_walls[PLAYER_TWO],
                    "is_ai": is_ai_j2,
                    "is_winner": self._winner == PLAYER_TWO,
                },
            },
            "walls": [
                {"orientation": w[0], "row": w[1], "col": w[2]}
                for w in self._state.walls
            ],
            "winner": self._winner,
            "plateau": plateau,
            "last_error": self._last_error,
            "wall_placement_mode": self._wall_placement_mode,
        }

    def apply_user_move(self, move_payload: dict) -> None:
        """Applique un coup envoyé par l'utilisateur (humain).

        Raises:
            InvalidMoveError: si la partie n'est pas active, si ce n'est pas
                              le tour de l'humain, ou si le coup est invalide.
        """
        from quoridor_engine.core import NackCode, move_pawn, place_wall

        with self._lock:
            if self._status != "playing":
                raise InvalidMoveError("Aucune partie active.", NackCode.WRONG_TURN)
            if self._mode == "ai_vs_ai":
                raise InvalidMoveError(
                    "Pas de coup humain en mode IA vs IA.", NackCode.WRONG_TURN
                )
            if self._is_ai_turn_unlocked():
                raise InvalidMoveError(
                    "Ce n'est pas le tour du joueur humain.", NackCode.WRONG_TURN
                )

            player = self._state.current_player
            move_type = move_payload.get("type")

            if move_type == "deplacement":
                target = tuple(move_payload["target"])
                new_state = move_pawn(self._state, player, target)
            elif move_type == "mur":
                wall = (
                    move_payload["orientation"],
                    int(move_payload["row"]),
                    int(move_payload["col"]),
                    2,
                )
                new_state = place_wall(self._state, player, wall)
            else:
                raise InvalidMoveError(
                    f"Type de coup inconnu: {move_type!r}",
                    NackCode.INVALID_FORMAT,
                )

            self._state = new_state
            self._turn_count += 1
            self._wall_placement_mode = None
            self._last_ai_move_at = time.monotonic()
            self._check_game_over_unlocked()
            self._forward_to_plateau_unlocked((move_type, move_payload))

    def _is_ai_turn_unlocked(self) -> bool:
        """True si le tour courant est celui d'une IA. Suppose le lock acquis."""
        if self._state is None:
            return False
        if self._state.current_player == PLAYER_ONE and self._ai_j1 is not None:
            return True
        if self._state.current_player == PLAYER_TWO and self._ai_j2 is not None:
            return True
        return False

    def _check_game_over_unlocked(self) -> None:
        """Met à jour status/winner si la partie est terminée. Suppose le lock acquis."""
        if self._state is None:
            return
        is_over, winner = self._state.is_game_over()
        if is_over:
            self._status = "finished"
            self._winner = winner

    def set_wall_mode(self, orientation: Optional[str]) -> None:
        """Active ou désactive le mode placement de mur."""
        with self._lock:
            if orientation not in (None, "h", "v"):
                raise ValueError(f"Orientation invalide: {orientation!r}")
            self._wall_placement_mode = orientation

    def _forward_to_plateau_unlocked(self, move: tuple) -> None:
        """Forward best-effort au plateau physique si actif. Suppose le lock acquis."""
        if not self._plateau_mode:
            return
        if self._uart_bridge is None or not self._uart_bridge.available:
            return
        try:
            self._uart_bridge.forward_move(move)
        except Exception as e:  # noqa: BLE001
            self._last_error = {
                "code": "PLATEAU_LOST",
                "message": f"Plateau déconnecté: {e}",
            }
