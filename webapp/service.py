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
            # Re-home le plateau physique au debut de chaque partie pour repartir
            # d'un etat connu (chariot a l'origine).
            if (
                plateau_mode
                and self._uart_bridge is not None
                and self._uart_bridge.available
            ):
                self._uart_bridge.send_home()

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

    def pause(self) -> None:
        """Met la partie en pause (no-op si pas en 'playing')."""
        with self._lock:
            if self._status == "playing":
                self._status = "paused"

    def resume(self) -> None:
        """Reprend la partie depuis pause (no-op si pas en 'paused')."""
        with self._lock:
            if self._status == "paused":
                self._status = "playing"
                self._last_ai_move_at = time.monotonic()

    def set_speed(self, speed: str) -> None:
        """Change la vitesse IA vs IA."""
        if speed not in _DELAIS:
            raise ValueError(f"Vitesse invalide: {speed!r}")
        with self._lock:
            self._speed = speed

    def quit_to_home(self) -> None:
        """Termine la partie. Garde mode/difficulté/vitesse/plateau_mode."""
        with self._lock:
            self._reset_partie()

    def tick_once(self) -> bool:
        """Effectue une itération de tick : si c'est au tour d'une IA
        et que le délai est écoulé, joue le coup IA.

        Returns:
            True si un coup IA a été joué, False sinon.
        """
        from quoridor_engine.core import move_pawn, place_wall

        with self._lock:
            if self._status != "playing":
                return False
            if not self._is_ai_turn_unlocked():
                return False
            elapsed = time.monotonic() - self._last_ai_move_at
            if elapsed < _DELAIS[self._speed]:
                return False
            current_ai = (
                self._ai_j1 if self._state.current_player == PLAYER_ONE else self._ai_j2
            )
            self._ai_thinking = True
            state_snapshot = self._state

        # Réflexion IA HORS du lock (peut prendre 0.1-2s)
        try:
            move = current_ai.find_best_move(state_snapshot, verbose=False)
        except Exception as e:  # noqa: BLE001
            with self._lock:
                self._ai_thinking = False
                self._status = "finished"
                self._last_error = {
                    "code": "AI_CRASH",
                    "message": f"Erreur IA: {e}",
                }
            return False

        # Application du coup DANS le lock
        with self._lock:
            self._ai_thinking = False
            # Garde : si l'utilisateur a quitté la partie pendant que l'IA réfléchissait,
            # _state peut être None ou le status peut avoir changé.
            if self._status != "playing" or self._state is None:
                return False
            move_type, move_data = move
            try:
                if move_type == "deplacement":
                    self._state = move_pawn(
                        self._state, self._state.current_player, move_data
                    )
                else:  # 'mur'
                    self._state = place_wall(
                        self._state, self._state.current_player, move_data
                    )
            except InvalidMoveError as e:
                self._last_error = {"code": e.code.value, "message": str(e)}
                return False

            self._turn_count += 1
            self._last_ai_move_at = time.monotonic()
            self._check_game_over_unlocked()
            if move_type == "deplacement":
                payload = {"type": "deplacement", "target": list(move_data)}
            else:
                payload = {
                    "type": "mur",
                    "orientation": move_data[0],
                    "row": move_data[1],
                    "col": move_data[2],
                }
            self._forward_to_plateau_unlocked((move_type, payload))
            return True

    def start_tick_thread(self) -> None:
        """Démarre le thread daemon qui appelle tick_once() en boucle.

        Doit être appelé une seule fois, au démarrage du serveur.
        """
        if hasattr(self, "_tick_thread") and self._tick_thread.is_alive():
            return  # déjà démarré

        def _loop():
            while True:
                try:
                    self.tick_once()
                except Exception:  # noqa: BLE001 — robustesse maximale du thread
                    pass
                time.sleep(0.1)

        self._tick_thread = threading.Thread(target=_loop, daemon=True, name="tick")
        self._tick_thread.start()

    def _forward_to_plateau_unlocked(self, move: tuple) -> None:
        """Forward best-effort au plateau physique si actif. Suppose le lock acquis."""
        if not self._plateau_mode:
            return
        if self._uart_bridge is None or not self._uart_bridge.available:
            return
        self._uart_bridge.forward_move(move)  # ne lève jamais (cf. contrat UartBridge)
        # Si le bridge vient de se désactiver à cause d'une erreur, notifier le client.
        if not self._uart_bridge.available:
            self._last_error = {
                "code": "PLATEAU_LOST",
                "message": "Plateau déconnecté, partie en mode app.",
            }
