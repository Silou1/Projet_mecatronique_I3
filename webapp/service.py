"""Service singleton qui détient l'état du jeu et orchestre l'IA.

Cette couche enveloppe `quoridor_engine` et `AI` pour exposer une API thread-safe
adaptée au backend web : création/reset de partie, application de coups,
sérialisation pour /api/state.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional, TYPE_CHECKING

from quoridor_engine import GameState, AI, InvalidMoveError
from quoridor_engine.core import PLAYER_ONE, PLAYER_TWO, create_new_game
from webapp.leds import LedRenderer
from webapp.plateau import PlateauBridge

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from webapp.transport import Transport


# Délais minimaux entre deux coups IA, en secondes
_DELAIS = {"lent": 2.5, "normal": 1.5, "rapide": 0.7}


class QuoridorService:
    """Singleton qui détient l'état partagé de la partie.

    Toutes les méthodes publiques acquièrent `_lock` avant de toucher l'état.
    Le thread `tick` appelle aussi `_lock` ; les sections critiques doivent être courtes.
    """

    def __init__(self, transport: Optional["Transport"] = None, startup_error: Optional[str] = None):
        if transport is None:
            from webapp.transport import NullTransport
            transport = NullTransport()
            transport.open()
        self._plateau = PlateauBridge(transport=transport)
        self._led_renderer = LedRenderer(bridge=self._plateau)
        self._plateau.add_on_reconnect_callback(self._led_renderer.on_reconnect)
        # P1 (bonus) : afficher les cases atteignables du joueur courant en cyan dim
        from webapp.leds import RenderOptions
        self._led_renderer.set_options(RenderOptions(show_legal_moves=True))
        self._startup_error = startup_error
        self._lock = threading.Lock()
        # Réglages persistés entre parties (cf. spec §9.7)
        self._mode: str = "human_vs_ai"
        self._difficulty: str = "normal"
        self._speed: str = "normal"
        # True tant qu'un forward physique (WALL ou LED) est en cours. Bloque
        # le coup IA suivant et désactive les clics côté frontend.
        self._plateau_busy: bool = False
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
        # Eteindre les LEDs (state est None, donc on appelle directement LEDCLEAR)
        if self._plateau.available:
            try:
                self._plateau.send_command_await(
                    "LEDCLEAR", accept_prefixes=("OK", "ERR"), timeout=2.0,
                )
            except Exception:
                pass

    def new_game(self, mode: str, difficulty: str) -> None:
        """Démarre une nouvelle partie.

        Le mode plateau physique est dérivé automatiquement de la disponibilité
        du transport ESP32 (`self._plateau.available`) au moment du forward de
        chaque coup — pas figé au new_game.
        """
        with self._lock:
            self._reset_partie()
            self._mode = mode
            self._difficulty = difficulty
            self._state = create_new_game()
            if mode == "human_vs_ai":
                self._ai_j2 = AI(player=PLAYER_TWO, difficulty=difficulty)
            elif mode == "ai_vs_ai":
                self._ai_j1 = AI(player=PLAYER_ONE, difficulty=difficulty)
                self._ai_j2 = AI(player=PLAYER_TWO, difficulty=difficulty)
            elif mode == "human_vs_human":
                pass  # aucune IA, les deux joueurs poussent leurs coups via apply_user_move
            self._status = "playing"
            self._last_ai_move_at = time.monotonic()
            state_snapshot = self._state
            do_home = self._plateau.available
            if do_home:
                self._plateau_busy = True
        # I/O plateau HORS du lock : HOME peut prendre 5-15 s (chariot CoreXY),
        # le polling /api/state ne doit pas se figer pendant ce temps. On exécute
        # dans un thread daemon pour libérer la requête /api/new-game.
        def _home_worker():
            try:
                if do_home:
                    log.info("HOME -> envoi au plateau")
                    reply = self._plateau.send_command_await(
                        "HOME", accept_prefixes=("HOME OK", "HOME ERR"), timeout=20.0,
                    )
                    log.info("HOME -> reponse=%r", reply)
                self._led_renderer.update(state_snapshot)
            finally:
                with self._lock:
                    self._plateau_busy = False
        threading.Thread(target=_home_worker, daemon=True, name="home-worker").start()

    def to_dict(self) -> dict:
        """Sérialise l'état pour /api/state."""
        with self._lock:
            return self._to_dict_unlocked()

    def _to_dict_unlocked(self) -> dict:
        # Mode plateau dérivé dynamiquement de la disponibilité du transport :
        # available == mode_active == connected, donc inutile de les distinguer.
        # On garde les 3 clés pour compat frontend (statuts identiques).
        avail = self._plateau.available
        plateau = {
            "available": avail,
            "mode_active": avail,
            "connected": avail,
            "busy": self._plateau_busy,
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
            if self._is_ai_turn_unlocked():
                raise InvalidMoveError(
                    "Ce n'est pas le tour du joueur humain.", NackCode.WRONG_TURN
                )
            if self._plateau_busy:
                raise InvalidMoveError(
                    "Plateau occupé, attendez la fin du coup précédent.",
                    NackCode.WRONG_TURN,
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
            state_snapshot = self._state
            forward_args = (move_type, move_payload)
            self._start_physical_forward_unlocked(forward_args, state_snapshot)

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
        """Termine la partie. Garde mode/difficulté/vitesse."""
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
            if self._plateau_busy:
                return False  # attend la fin du forward physique du coup précédent
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
            state_snapshot = self._state
            forward_args = (move_type, payload)
            self._start_physical_forward_unlocked(forward_args, state_snapshot)
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

    def _start_physical_forward_unlocked(self, forward_args: tuple, state_snapshot: GameState) -> None:
        """Pose le flag busy et lance le worker thread daemon. Suppose lock acquis.

        Le worker exécute le forward WALL (5-10 s) puis l'update LED, et
        repasse _plateau_busy à False sous lock. Sert pour humain ET IA.
        """
        if self._plateau.available:
            self._plateau_busy = True

        def _worker():
            try:
                self._forward_to_plateau_unlocked(forward_args)
                self._led_renderer.update(state_snapshot)
            finally:
                with self._lock:
                    self._plateau_busy = False

        threading.Thread(target=_worker, daemon=True, name="physical-forward").start()

    def _forward_to_plateau_unlocked(self, move: tuple) -> None:
        """Forward best-effort au plateau physique si actif.

        Appelé HORS du service lock pour ne pas figer le polling /api/state
        pendant les 5-10 s d'exécution physique (CoreXY + servo).

        L'orientation H/V est transmise telle quelle : depuis la recalibration
        complète des matrices (60/60 murs, commit 1a420a9), le firmware suit la
        même convention que l'engine.
        """
        if not self._plateau.available:
            return
        move_type, payload = move
        if move_type != "mur":
            return  # déplacements de pion non répercutés sur le plateau
        try:
            orientation = payload["orientation"].upper()
            row = int(payload["row"])
            col = int(payload["col"])
            cmd = f"WALL {orientation} {row} {col}"
            log.info("WALL -> envoi %r", cmd)
            reply = self._plateau.send_command_await(
                cmd, accept_prefixes=("WALL OK", "WALL ERR"), timeout=12.0,
            )
            log.info("WALL -> reponse=%r", reply)
            if reply is None:
                self._last_error = {
                    "code": "PLATEAU_LOST",
                    "message": "Plateau déconnecté, partie en mode app.",
                }
            elif reply.startswith("WALL ERR"):
                self._last_error = {
                    "code": "WALL_FAIL",
                    "message": f"Plateau : {reply}",
                }
        except Exception as e:  # noqa: BLE001
            log.warning("WALL forward echoue (%s), desactivation plateau", e)
            self._last_error = {
                "code": "PLATEAU_LOST",
                "message": "Plateau déconnecté, partie en mode app.",
            }

    def _plateau_available_unlocked(self) -> bool:
        """True si le transport est ouvert (utilisable par /api/new-game)."""
        return self._plateau.available
