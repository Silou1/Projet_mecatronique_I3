# Plan d'implémentation — Web app de démo Quoridor

> **Pour les agents :** SOUS-SKILL REQUIS — Utiliser superpowers:subagent-driven-development (recommandé) ou superpowers:executing-plans pour exécuter ce plan tâche par tâche. Les étapes utilisent la syntaxe checkbox (`- [ ]`) pour le tracking.

**Spec source :** [`docs/superpowers/specs/2026-05-18-webapp-demo-quoridor-design.md`](../specs/2026-05-18-webapp-demo-quoridor-design.md)

**Goal :** Construire une web app servie par le Raspberry Pi (FastAPI + polling HTTP + HTML/JS vanilla + SVG) qui permet de jouer au Quoridor depuis Safari iPhone, avec deux modes (humain vs IA, IA vs IA) et un mode plateau physique optionnel à fallback gracieux.

**Architecture :** Backend Python (FastAPI) qui réutilise `quoridor_engine` et `AI` existants via une couche `QuoridorService` singleton + thread daemon pour l'IA. UART mirroré par un `UartBridge` optionnel détecté au boot. Frontend single-page HTML avec deux vues (accueil/jeu), polling 500 ms sur `/api/state`, plateau SVG inline interactif. Style C2 affiné (palette beige/bois subtile, rigueur iOS).

**Tech Stack :** Python 3.12 · FastAPI · uvicorn · pyserial · HTML5 · CSS3 · JavaScript vanilla · SVG inline · pytest · TestClient FastAPI.

**Conventions du repo :**
- Tests pytest dans `tests/`, marqueur `devkit` pour matériel.
- French pour variables/comments, English pour class names (cf. `CLAUDE.md`).
- 4-space indentation, max 100 chars/line, type hints partout.
- uv pour le venv (Python 3.12.13 dans `.venv/`).

**Critère de succès final :** une session démo de 5 minutes sur iPhone Safari pointé vers l'IP du RPi, parcourant les 3 scénarios manuels du §12.2 de la spec, sans plantage.

---

## Phase 0 — Setup projet

### Task 0.1 : Créer la structure `webapp/` et ajouter les dépendances

**Files:**
- Create: `webapp/__init__.py`
- Create: `webapp/static/.gitkeep`
- Modify: `requirements.txt`
- Modify: `pyproject.toml`

- [ ] **Étape 1 — Créer les répertoires et fichiers vides**

```bash
cd /Users/silouanechaumais/Documents/01_ICAM/2025-2026_Année_3/Projet_mécatronique/programmation
mkdir -p webapp/static
touch webapp/__init__.py webapp/static/.gitkeep
```

- [ ] **Étape 2 — Modifier `requirements.txt`**

Remplacer le contenu (préserver tout l'existant, ajouter en bas) :

```
# Dépendances du projet Quoridor Interactif

# Interface console - Couleurs dans le terminal (optionnel mais recommandé)
colorama>=0.4.6

# Tests unitaires (Phase 5)
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-timeout>=2.2.0

# Futurs ajouts possibles pour l'interface matérielle (Phase suivante)
# RPi.GPIO>=0.7.1  # Pour Raspberry Pi (décommenter si nécessaire)
# gpiozero>=1.6.2  # Alternative plus simple pour GPIO

# Communication serie avec ESP32 (Phase P8)
pyserial>=3.5

# Web app de démo (Phase P13, ajouté 2026-05-18)
fastapi>=0.110
uvicorn[standard]>=0.27
httpx>=0.27  # pour fastapi.testclient
```

- [ ] **Étape 3 — Modifier `pyproject.toml`**

Ajouter `webapp` à la liste des testpaths et déclarer la dépendance optionnelle pour la web app. Remplacer le contenu par :

```toml
[project]
name = "quoridor-mecatronique"
version = "0.1.0"
description = "Moteur de jeu Quoridor 6x6 + intégration ESP32 (projet mécatronique ICAM 3A)"
requires-python = ">=3.12"

[project.optional-dependencies]
devkit = ["pyserial>=3.5"]
webapp = ["fastapi>=0.110", "uvicorn[standard]>=0.27", "httpx>=0.27"]

[tool.pytest.ini_options]
markers = [
  "devkit: tests qui requièrent le DevKit ESP32 branché (skipés sinon)",
]
testpaths = ["tests"]
```

- [ ] **Étape 4 — Installer les nouvelles dépendances**

```bash
uv pip install "fastapi>=0.110" "uvicorn[standard]>=0.27" "httpx>=0.27"
```

Attendu : aucune erreur, les paquets s'installent dans `.venv/`.

- [ ] **Étape 5 — Vérifier l'import**

```bash
python -c "import fastapi; import uvicorn; print(fastapi.__version__, uvicorn.__version__)"
```

Attendu : deux numéros de version affichés sans erreur.

- [ ] **Étape 6 — Commit**

```bash
git add webapp/ requirements.txt pyproject.toml
git commit -m "feat(webapp): structure initiale + dependances FastAPI"
```

---

### Task 0.2 : Schémas Pydantic

**Files:**
- Create: `webapp/schemas.py`
- Create: `tests/webapp/__init__.py`
- Create: `tests/webapp/test_schemas.py`

- [ ] **Étape 1 — Écrire les tests qui échouent**

Créer `tests/webapp/test_schemas.py` :

```python
"""Tests des schémas Pydantic de la web app."""
import pytest
from pydantic import ValidationError

from webapp.schemas import (
    NewGamePayload,
    MovePayload,
    SpeedPayload,
    WallModePayload,
    StateResponse,
)


class TestNewGamePayload:
    def test_payload_valide(self):
        p = NewGamePayload(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        assert p.mode == "human_vs_ai"
        assert p.difficulty == "normal"
        assert p.plateau_mode is False

    def test_mode_invalide_rejete(self):
        with pytest.raises(ValidationError):
            NewGamePayload(mode="duel", difficulty="normal", plateau_mode=False)

    def test_difficulte_invalide_rejetee(self):
        with pytest.raises(ValidationError):
            NewGamePayload(mode="human_vs_ai", difficulty="extreme", plateau_mode=False)


class TestMovePayload:
    def test_deplacement_valide(self):
        p = MovePayload(type="deplacement", target=(3, 2))
        assert p.type == "deplacement"
        assert p.target == (3, 2)

    def test_mur_valide(self):
        p = MovePayload(type="mur", orientation="h", row=2, col=3)
        assert p.type == "mur"
        assert p.orientation == "h"

    def test_type_invalide_rejete(self):
        with pytest.raises(ValidationError):
            MovePayload(type="rotation")


class TestSpeedPayload:
    def test_vitesse_valide(self):
        assert SpeedPayload(speed="lent").speed == "lent"
        assert SpeedPayload(speed="rapide").speed == "rapide"

    def test_vitesse_invalide_rejetee(self):
        with pytest.raises(ValidationError):
            SpeedPayload(speed="ultraflash")


class TestWallModePayload:
    def test_active_horizontal(self):
        assert WallModePayload(orientation="h").orientation == "h"

    def test_desactivation_avec_null(self):
        assert WallModePayload(orientation=None).orientation is None
```

- [ ] **Étape 2 — Lancer les tests, vérifier qu'ils échouent**

```bash
pytest tests/webapp/test_schemas.py -v
```

Attendu : FAIL avec `ModuleNotFoundError: No module named 'webapp.schemas'`.

- [ ] **Étape 3 — Implémenter les schémas**

Créer `webapp/schemas.py` :

```python
"""Schémas Pydantic pour les payloads et réponses de la web app."""
from typing import Literal, Optional, Tuple
from pydantic import BaseModel, Field


Mode = Literal["human_vs_ai", "ai_vs_ai"]
Difficulty = Literal["facile", "normal", "difficile"]
Speed = Literal["lent", "normal", "rapide"]
Status = Literal["waiting", "playing", "paused", "finished"]
Orientation = Literal["h", "v"]
PlayerId = Literal["j1", "j2"]


class NewGamePayload(BaseModel):
    """Payload de POST /api/new-game."""
    mode: Mode
    difficulty: Difficulty
    plateau_mode: bool = False


class MovePayload(BaseModel):
    """Payload de POST /api/move.

    Pour un déplacement : type='deplacement', target=(r, c).
    Pour un mur : type='mur', orientation, row, col (longueur 2 implicite).
    """
    type: Literal["deplacement", "mur"]
    target: Optional[Tuple[int, int]] = None
    orientation: Optional[Orientation] = None
    row: Optional[int] = None
    col: Optional[int] = None


class SpeedPayload(BaseModel):
    speed: Speed


class WallModePayload(BaseModel):
    orientation: Optional[Orientation] = None


class PlayerInfo(BaseModel):
    position: Tuple[int, int]
    walls_remaining: int
    is_ai: bool
    is_winner: bool = False


class WallInfo(BaseModel):
    orientation: Orientation
    row: int
    col: int


class PlateauInfo(BaseModel):
    available: bool
    mode_active: bool
    connected: bool


class ErrorInfo(BaseModel):
    code: str
    message: str


class StateResponse(BaseModel):
    """Réponse de GET /api/state."""
    mode: Mode = "human_vs_ai"
    difficulty: Difficulty = "normal"
    speed: Speed = "normal"
    status: Status = "waiting"
    turn_count: int = 0
    current_player: Optional[PlayerId] = None
    ai_thinking: bool = False
    players: dict = Field(default_factory=dict)
    walls: list = Field(default_factory=list)
    winner: Optional[PlayerId] = None
    plateau: PlateauInfo = Field(
        default_factory=lambda: PlateauInfo(available=False, mode_active=False, connected=False)
    )
    last_error: Optional[ErrorInfo] = None
    wall_placement_mode: Optional[Orientation] = None
```

- [ ] **Étape 4 — Relancer les tests, vérifier qu'ils passent**

```bash
pytest tests/webapp/test_schemas.py -v
```

Attendu : tous les tests PASS.

- [ ] **Étape 5 — Commit**

```bash
git add webapp/schemas.py tests/webapp/
git commit -m "feat(webapp): schemas Pydantic pour payloads et reponses API"
```

---

## Phase 1 — Backend : QuoridorService

### Task 1.1 : Skeleton du service + `new_game()`

**Files:**
- Create: `webapp/service.py`
- Create: `tests/webapp/test_service.py`

- [ ] **Étape 1 — Écrire le test qui échoue**

Créer `tests/webapp/test_service.py` :

```python
"""Tests du QuoridorService."""
import pytest

from webapp.service import QuoridorService


@pytest.fixture
def service():
    return QuoridorService(uart_bridge=None)


class TestNewGame:
    def test_etat_initial_status_waiting(self, service):
        state = service.to_dict()
        assert state["status"] == "waiting"
        assert state["current_player"] is None

    def test_new_game_human_vs_ai_demarre_partie(self, service):
        service.new_game(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        state = service.to_dict()
        assert state["status"] == "playing"
        assert state["mode"] == "human_vs_ai"
        assert state["difficulty"] == "normal"
        assert state["current_player"] == "j1"
        assert state["players"]["j1"]["is_ai"] is False
        assert state["players"]["j2"]["is_ai"] is True
        assert state["players"]["j1"]["position"] == [5, 3]
        assert state["players"]["j2"]["position"] == [0, 3]
        assert state["players"]["j1"]["walls_remaining"] == 6
        assert state["players"]["j2"]["walls_remaining"] == 6
        assert state["walls"] == []
        assert state["turn_count"] == 0

    def test_new_game_ai_vs_ai(self, service):
        service.new_game(mode="ai_vs_ai", difficulty="facile", plateau_mode=False)
        state = service.to_dict()
        assert state["mode"] == "ai_vs_ai"
        assert state["players"]["j1"]["is_ai"] is True
        assert state["players"]["j2"]["is_ai"] is True

    def test_new_game_efface_partie_precedente(self, service):
        service.new_game(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        # Simule un coup en mémoire pour vérifier le reset
        service._turn_count = 7
        service.new_game(mode="human_vs_ai", difficulty="facile", plateau_mode=False)
        state = service.to_dict()
        assert state["turn_count"] == 0
        assert state["difficulty"] == "facile"
```

- [ ] **Étape 2 — Lancer le test, vérifier qu'il échoue**

```bash
pytest tests/webapp/test_service.py -v
```

Attendu : FAIL avec `ModuleNotFoundError: No module named 'webapp.service'`.

- [ ] **Étape 3 — Implémenter le skeleton du service**

Créer `webapp/service.py` :

```python
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
from quoridor_engine.core import PLAYER_ONE, PLAYER_TWO

if TYPE_CHECKING:
    from webapp.uart_bridge import UartBridge


# Délais minimaux entre deux coups IA, en secondes
_DELAIS = {"lent": 2.5, "normal": 1.5, "rapide": 0.7}


class QuoridorService:
    """Singleton qui détient l'état partagé de la partie.

    Toutes les méthodes publiques acquièrent `_lock` avant de toucher l'état.
    Le thread `tick` (cf. Task 1.6) appelle aussi `_lock` ; les sections
    critiques doivent être courtes.
    """

    def __init__(self, uart_bridge: Optional["UartBridge"] = None):
        self._uart_bridge = uart_bridge
        self._lock = threading.Lock()
        self._reset_partie()
        # Réglages persistés entre parties (cf. spec §9.7)
        self._mode: str = "human_vs_ai"
        self._difficulty: str = "normal"
        self._speed: str = "normal"
        self._plateau_mode: bool = False

    def _reset_partie(self) -> None:
        """Remet l'état partie à zéro. À appeler dans le lock."""
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
            self._state = GameState.create_initial()
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
        """Version sans lock (appelée depuis l'intérieur du lock)."""
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
```

- [ ] **Étape 4 — Vérifier que `GameState.create_initial()` existe**

```bash
grep -n "create_initial\|create_new\|def initial" quoridor_engine/core.py
```

Si la méthode n'existe pas exactement sous ce nom, ouvrir `quoridor_engine/core.py` pour trouver la factory existante (ex: `_create_initial_state`, `initial_game_state`, ou un constructeur dans `QuoridorGame.__init__`). Adapter l'appel dans `service.py` à la signature réelle. Si nécessaire, importer depuis `quoridor_engine.core`.

- [ ] **Étape 5 — Relancer les tests**

```bash
pytest tests/webapp/test_service.py -v
```

Attendu : les 4 tests PASS. Si KO, lire l'erreur, ajuster l'import / factory de `GameState`.

- [ ] **Étape 6 — Commit**

```bash
git add webapp/service.py tests/webapp/test_service.py
git commit -m "feat(webapp): QuoridorService skeleton + new_game()"
```

---

### Task 1.2 : `apply_user_move()` pour déplacement de pion

**Files:**
- Modify: `webapp/service.py`
- Modify: `tests/webapp/test_service.py`

- [ ] **Étape 1 — Ajouter les tests qui échouent**

Ajouter à la fin de `tests/webapp/test_service.py` :

```python
class TestApplyUserMoveDeplacement:
    def test_deplacement_valide_change_tour(self, service):
        service.new_game(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        # J1 démarre en (5, 3), peut monter en (4, 3)
        service.apply_user_move({"type": "deplacement", "target": (4, 3)})
        state = service.to_dict()
        assert state["players"]["j1"]["position"] == [4, 3]
        assert state["current_player"] == "j2"
        assert state["turn_count"] == 1

    def test_deplacement_invalide_leve_erreur(self, service):
        service.new_game(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        # J1 ne peut pas sauter à (0, 0)
        with pytest.raises(InvalidMoveError):
            service.apply_user_move({"type": "deplacement", "target": (0, 0)})

    def test_deplacement_pendant_tour_ai_rejete(self, service):
        service.new_game(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        service.apply_user_move({"type": "deplacement", "target": (4, 3)})
        # Maintenant c'est au tour de J2 (IA), l'humain ne peut pas jouer
        with pytest.raises(InvalidMoveError):
            service.apply_user_move({"type": "deplacement", "target": (1, 3)})

    def test_deplacement_en_mode_ai_vs_ai_rejete(self, service):
        service.new_game(mode="ai_vs_ai", difficulty="facile", plateau_mode=False)
        # En IA vs IA, aucun coup humain n'est accepté
        with pytest.raises(InvalidMoveError):
            service.apply_user_move({"type": "deplacement", "target": (4, 3)})
```

Ajouter l'import en haut du fichier :

```python
from quoridor_engine import InvalidMoveError
```

- [ ] **Étape 2 — Lancer les tests, vérifier qu'ils échouent**

```bash
pytest tests/webapp/test_service.py::TestApplyUserMoveDeplacement -v
```

Attendu : FAIL `AttributeError: 'QuoridorService' object has no attribute 'apply_user_move'`.

- [ ] **Étape 3 — Implémenter `apply_user_move()` pour les déplacements**

Ajouter dans `webapp/service.py`, dans la classe `QuoridorService` après `new_game()` :

```python
    def apply_user_move(self, move_payload: dict) -> None:
        """Applique un coup envoyé par l'utilisateur (humain).

        Args:
            move_payload: dict avec 'type' = 'deplacement' ou 'mur' et les
                          coordonnées associées.

        Raises:
            InvalidMoveError: si la partie n'est pas active, si ce n'est pas
                              le tour de l'humain, ou si le coup est invalide.
        """
        from quoridor_engine.core import (
            NackCode,
            move_pawn,
            place_wall,
        )

        with self._lock:
            if self._status != "playing":
                raise InvalidMoveError(
                    "Aucune partie active.", NackCode.WRONG_TURN
                )
            if self._mode == "ai_vs_ai":
                raise InvalidMoveError(
                    "Pas de coup humain en mode IA vs IA.", NackCode.WRONG_TURN
                )
            # En H vs IA, seul J1 est humain. Si current_player == j2, c'est l'IA.
            if self._is_ai_turn_unlocked():
                raise InvalidMoveError(
                    "Ce n'est pas le tour du joueur humain.",
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
            self._forward_to_plateau_unlocked(
                ("deplacement" if move_type == "deplacement" else "mur", move_payload)
            )

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

    def _forward_to_plateau_unlocked(self, move: tuple) -> None:
        """Forward best-effort au plateau physique si actif. Suppose le lock acquis."""
        if not self._plateau_mode:
            return
        if self._uart_bridge is None or not self._uart_bridge.available:
            return
        try:
            self._uart_bridge.forward_move(move)
        except Exception as e:  # noqa: BLE001 — robustesse délibérée
            self._last_error = {
                "code": "PLATEAU_LOST",
                "message": f"Plateau déconnecté: {e}",
            }
```

- [ ] **Étape 4 — Relancer les tests**

```bash
pytest tests/webapp/test_service.py -v
```

Attendu : tous les tests PASS. Si KO, vérifier que les fonctions `move_pawn` et `place_wall` ont bien la signature `(state, player, target_or_wall) -> GameState`.

- [ ] **Étape 5 — Commit**

```bash
git add webapp/service.py tests/webapp/test_service.py
git commit -m "feat(webapp): apply_user_move pour deplacements de pion"
```

---

### Task 1.3 : `apply_user_move()` pour placement de mur + `set_wall_mode()`

**Files:**
- Modify: `webapp/service.py`
- Modify: `tests/webapp/test_service.py`

- [ ] **Étape 1 — Ajouter les tests qui échouent**

Ajouter à `tests/webapp/test_service.py` :

```python
class TestApplyUserMoveMur:
    def test_pose_mur_horizontal_valide(self, service):
        service.new_game(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        service.apply_user_move(
            {"type": "mur", "orientation": "h", "row": 4, "col": 2}
        )
        state = service.to_dict()
        assert {"orientation": "h", "row": 4, "col": 2} in state["walls"]
        assert state["players"]["j1"]["walls_remaining"] == 5
        assert state["current_player"] == "j2"
        assert state["turn_count"] == 1
        assert state["wall_placement_mode"] is None  # auto-reset après pose


class TestWallMode:
    def test_active_mur_horizontal(self, service):
        service.new_game(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        service.set_wall_mode("h")
        assert service.to_dict()["wall_placement_mode"] == "h"

    def test_basculer_h_vers_v(self, service):
        service.new_game(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        service.set_wall_mode("h")
        service.set_wall_mode("v")
        assert service.to_dict()["wall_placement_mode"] == "v"

    def test_desactivation_avec_null(self, service):
        service.new_game(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        service.set_wall_mode("h")
        service.set_wall_mode(None)
        assert service.to_dict()["wall_placement_mode"] is None
```

- [ ] **Étape 2 — Lancer les tests, vérifier l'échec**

```bash
pytest tests/webapp/test_service.py::TestWallMode -v
```

Attendu : FAIL `AttributeError: 'QuoridorService' object has no attribute 'set_wall_mode'`.

- [ ] **Étape 3 — Ajouter `set_wall_mode()` dans `webapp/service.py`**

Ajouter après `apply_user_move()` :

```python
    def set_wall_mode(self, orientation: Optional[str]) -> None:
        """Active ou désactive le mode placement de mur.

        Args:
            orientation: 'h', 'v' ou None pour désactiver.
        """
        with self._lock:
            if orientation not in (None, "h", "v"):
                raise ValueError(f"Orientation invalide: {orientation!r}")
            self._wall_placement_mode = orientation
```

- [ ] **Étape 4 — Relancer les tests**

```bash
pytest tests/webapp/test_service.py -v
```

Attendu : tous les tests PASS (mur + wall_mode).

- [ ] **Étape 5 — Commit**

```bash
git add webapp/service.py tests/webapp/test_service.py
git commit -m "feat(webapp): placement de mur + set_wall_mode"
```

---

### Task 1.4 : `pause()`, `resume()`, `set_speed()`, `quit_to_home()`

**Files:**
- Modify: `webapp/service.py`
- Modify: `tests/webapp/test_service.py`

- [ ] **Étape 1 — Ajouter les tests**

Ajouter à `tests/webapp/test_service.py` :

```python
class TestControles:
    def test_pause_change_status(self, service):
        service.new_game(mode="ai_vs_ai", difficulty="facile", plateau_mode=False)
        service.pause()
        assert service.to_dict()["status"] == "paused"

    def test_resume_remet_playing(self, service):
        service.new_game(mode="ai_vs_ai", difficulty="facile", plateau_mode=False)
        service.pause()
        service.resume()
        assert service.to_dict()["status"] == "playing"

    def test_pause_hors_partie_no_op(self, service):
        # Pas de partie en cours → pause ne plante pas, status reste 'waiting'
        service.pause()
        assert service.to_dict()["status"] == "waiting"

    def test_set_speed_persiste(self, service):
        service.set_speed("rapide")
        assert service.to_dict()["speed"] == "rapide"
        service.new_game(mode="ai_vs_ai", difficulty="facile", plateau_mode=False)
        assert service.to_dict()["speed"] == "rapide"

    def test_quit_to_home_efface_partie_garde_reglages(self, service):
        service.new_game(mode="human_vs_ai", difficulty="difficile", plateau_mode=False)
        service.set_speed("rapide")
        service.quit_to_home()
        state = service.to_dict()
        assert state["status"] == "waiting"
        assert state["difficulty"] == "difficile"  # réglage gardé
        assert state["speed"] == "rapide"
        assert state["mode"] == "human_vs_ai"  # mode gardé
```

- [ ] **Étape 2 — Lancer les tests, vérifier l'échec**

```bash
pytest tests/webapp/test_service.py::TestControles -v
```

Attendu : FAIL.

- [ ] **Étape 3 — Implémenter les méthodes**

Ajouter dans `webapp/service.py`, après `set_wall_mode()` :

```python
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
        """Change la vitesse IA vs IA. Valeurs valides : lent/normal/rapide."""
        if speed not in _DELAIS:
            raise ValueError(f"Vitesse invalide: {speed!r}")
        with self._lock:
            self._speed = speed

    def quit_to_home(self) -> None:
        """Termine la partie en cours, retour à l'accueil. Garde mode/difficulté/vitesse."""
        with self._lock:
            self._reset_partie()
            # _mode, _difficulty, _speed, _plateau_mode sont conservés exprès
```

- [ ] **Étape 4 — Relancer les tests**

```bash
pytest tests/webapp/test_service.py -v
```

Attendu : tous PASS.

- [ ] **Étape 5 — Commit**

```bash
git add webapp/service.py tests/webapp/test_service.py
git commit -m "feat(webapp): pause/resume/set_speed/quit_to_home"
```

---

### Task 1.5 : Thread `tick` pour faire jouer l'IA

**Files:**
- Modify: `webapp/service.py`
- Modify: `tests/webapp/test_service.py`

- [ ] **Étape 1 — Ajouter les tests**

Ajouter à `tests/webapp/test_service.py` :

```python
class TestTick:
    def test_tick_once_fait_jouer_ai_quand_son_tour(self, service):
        """En H vs IA, après le coup humain, tick() doit faire jouer l'IA."""
        service.new_game(mode="human_vs_ai", difficulty="facile", plateau_mode=False)
        service.apply_user_move({"type": "deplacement", "target": (4, 3)})
        # Forcer le délai à 0 pour ne pas attendre
        service._last_ai_move_at = 0.0
        played = service.tick_once()
        assert played is True
        state = service.to_dict()
        # L'IA J2 a joué, donc current_player redevient j1
        assert state["current_player"] == "j1"
        assert state["turn_count"] == 2

    def test_tick_once_no_op_si_tour_humain(self, service):
        service.new_game(mode="human_vs_ai", difficulty="facile", plateau_mode=False)
        # current_player = j1 (humain), tick ne doit rien faire
        played = service.tick_once()
        assert played is False

    def test_tick_once_no_op_si_paused(self, service):
        service.new_game(mode="ai_vs_ai", difficulty="facile", plateau_mode=False)
        service.pause()
        service._last_ai_move_at = 0.0
        played = service.tick_once()
        assert played is False

    def test_tick_respecte_delai(self, service):
        """Si le délai n'est pas écoulé, tick() ne joue pas."""
        service.new_game(mode="ai_vs_ai", difficulty="facile", plateau_mode=False)
        service._last_ai_move_at = time.monotonic()  # juste maintenant
        played = service.tick_once()
        assert played is False


import time  # noqa: E402 — utilisé dans le test ci-dessus
```

Ajouter en haut du fichier : `import time`.

- [ ] **Étape 2 — Lancer les tests, vérifier l'échec**

```bash
pytest tests/webapp/test_service.py::TestTick -v
```

Attendu : FAIL `AttributeError: 'QuoridorService' object has no attribute 'tick_once'`.

- [ ] **Étape 3 — Implémenter `tick_once()` et le thread daemon**

Ajouter dans `webapp/service.py` :

```python
    def tick_once(self) -> bool:
        """Effectue une itération de tick : si c'est au tour d'une IA
        et que le délai est écoulé, joue le coup IA.

        Returns:
            True si un coup IA a été joué, False sinon.
        """
        from quoridor_engine.core import move_pawn, place_wall, NackCode

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

        # Réflexion IA HORS du lock (peut prendre 0.1-2s)
        try:
            move = current_ai.find_best_move(self._state, verbose=False)
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
            # Forward au plateau si actif
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
```

- [ ] **Étape 4 — Relancer les tests**

```bash
pytest tests/webapp/test_service.py -v
```

Attendu : tous PASS (incluant les 4 nouveaux tests).

- [ ] **Étape 5 — Commit**

```bash
git add webapp/service.py tests/webapp/test_service.py
git commit -m "feat(webapp): thread tick + tick_once() pour faire jouer l'IA"
```

---

## Phase 2 — UART Bridge

### Task 2.1 : `UartBridge` avec init défensif et `forward_move()`

**Files:**
- Create: `webapp/uart_bridge.py`
- Create: `tests/webapp/test_uart_bridge.py`

- [ ] **Étape 1 — Écrire les tests**

Créer `tests/webapp/test_uart_bridge.py` :

```python
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
    def test_forward_envoie_au_client(self):
        fake_client = MagicMock()
        bridge = UartBridge(fake_client)
        move = ("deplacement", {"type": "deplacement", "target": [4, 3]})
        bridge.forward_move(move)
        fake_client.send_user_move.assert_called_once()
        assert bridge.available is True

    def test_forward_erreur_desactive_disponibilite(self):
        fake_client = MagicMock()
        fake_client.send_user_move.side_effect = Exception("uart dead")
        bridge = UartBridge(fake_client)
        # Ne doit pas lever : on log et on désactive
        bridge.forward_move(("deplacement", {}))
        assert bridge.available is False

    def test_forward_no_op_quand_indisponible(self):
        fake_client = MagicMock()
        bridge = UartBridge(fake_client)
        bridge.available = False
        bridge.forward_move(("deplacement", {}))
        fake_client.send_user_move.assert_not_called()
```

- [ ] **Étape 2 — Lancer, vérifier l'échec**

```bash
pytest tests/webapp/test_uart_bridge.py -v
```

Attendu : FAIL `ModuleNotFoundError`.

- [ ] **Étape 3 — Implémenter `UartBridge`**

Créer `webapp/uart_bridge.py` :

```python
"""Wrapper optionnel autour de UartClient pour mirrorer les coups sur le plateau.

Detection au boot : si un port est trouvé et le handshake passe, le bridge est
actif. Sinon, init() retourne None et la web app reste 100 % autonome.

Erreur en cours de partie : log + désactivation locale (available=False). Pas
de tentative de reconnexion (cf. spec §10.4).
"""
from __future__ import annotations

import glob
import logging
import platform
from typing import Optional

log = logging.getLogger(__name__)


def _find_devkit_port() -> Optional[str]:
    """Cherche le port série du DevKit/PCB ESP32.

    Mac : /dev/cu.usbserial-*
    Linux/RPi : /dev/ttyUSB* puis /dev/ttyAMA0 (UART hardware RPi)
    """
    system = platform.system()
    if system == "Darwin":
        ports = sorted(glob.glob("/dev/cu.usbserial-*"))
    else:
        ports = sorted(glob.glob("/dev/ttyUSB*"))
        if not ports:
            # RPi UART hardware (GPIO TX/RX), si pas de USB
            ports = sorted(glob.glob("/dev/ttyAMA*"))
    return ports[0] if ports else None


def _open_client(port: str):
    """Ouvre un UartClient et fait le handshake. Lève une exception si KO."""
    from quoridor_engine import UartClient
    client = UartClient(port)
    client.connect()  # handshake Plan 2 (cf. spec UART)
    return client


def init() -> Optional["UartBridge"]:
    """Tente de détecter et d'ouvrir le port UART.

    Returns:
        UartBridge si succès, None sinon.
    """
    port = _find_devkit_port()
    if port is None:
        log.info("UartBridge: aucun port detecte, mode autonome.")
        return None
    try:
        client = _open_client(port)
    except Exception as e:  # noqa: BLE001
        log.warning("UartBridge: handshake echoue sur %s (%s), mode autonome.", port, e)
        return None
    log.info("UartBridge: connecte sur %s.", port)
    return UartBridge(client)


class UartBridge:
    """Mirror best-effort des coups vers le firmware ESP32.

    En cas d'erreur (timeout, port mort, etc.), `available` passe à False
    et les forwards suivants sont no-op silencieux.
    """

    def __init__(self, client):
        self._client = client
        self.available: bool = True

    def forward_move(self, move: tuple) -> None:
        """Envoie un coup au plateau. No-op si indisponible.

        En cas d'erreur, log et désactive `available`. Ne lève PAS.

        Args:
            move: tuple (move_type, payload) où payload est le dict envoyé
                  à l'API (cohérent avec MovePayload côté schemas).
        """
        if not self.available:
            return
        try:
            # send_user_move() est l'API attendue côté UartClient.
            # Si l'API existante diffère (ex: send_cmd / send_frame), adapter ici.
            self._client.send_user_move(move)
        except Exception as e:  # noqa: BLE001
            log.warning("UartBridge: forward echoue (%s), desactivation mirroring.", e)
            self.available = False

    def close(self) -> None:
        """Ferme proprement la connexion UART."""
        try:
            if hasattr(self._client, "close"):
                self._client.close()
        except Exception:  # noqa: BLE001
            pass
```

- [ ] **Étape 4 — Vérifier l'API exacte de `UartClient`**

```bash
grep -n "def send\|def connect\|def close" quoridor_engine/uart_client.py | head -20
```

Si la méthode `send_user_move()` n'existe pas, adapter la ligne `self._client.send_user_move(move)` à la méthode disponible (ex : `send_frame()`, `send_cmd_pawn()`, `send_cmd_wall()`). Convertir le format `move` au format attendu par `UartClient` (cf. `docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md` pour les types de trames).

Si l'adaptation est non triviale, mettre dans `UartBridge.forward_move()` un dispatcher :

```python
move_type, payload = move
if move_type == "deplacement":
    r, c = payload["target"]
    self._client.send_cmd_pawn(r, c)  # nom exact à confirmer
else:  # 'mur'
    self._client.send_cmd_wall(payload["orientation"], payload["row"], payload["col"])
```

- [ ] **Étape 5 — Relancer les tests**

```bash
pytest tests/webapp/test_uart_bridge.py -v
```

Attendu : tous PASS.

- [ ] **Étape 6 — Commit**

```bash
git add webapp/uart_bridge.py tests/webapp/test_uart_bridge.py
git commit -m "feat(webapp): UartBridge avec fallback gracieux"
```

---

## Phase 3 — API FastAPI

### Task 3.1 : `server.py` avec route `GET /`

**Files:**
- Create: `webapp/server.py`
- Create: `webapp/static/index.html` (placeholder)
- Create: `tests/webapp/test_api.py`

- [ ] **Étape 1 — Placeholder HTML**

Créer `webapp/static/index.html` (sera remplacé en phase 4) :

```html
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Quoridor — chargement</title>
</head>
<body>
  <p>Frontend en cours de construction.</p>
</body>
</html>
```

- [ ] **Étape 2 — Écrire le test**

Créer `tests/webapp/test_api.py` :

```python
"""Tests des routes FastAPI (avec TestClient, pas de hardware)."""
import pytest
from fastapi.testclient import TestClient

from webapp.server import create_app


@pytest.fixture
def client():
    app = create_app(uart_bridge=None)
    return TestClient(app)


class TestRootRoute:
    def test_get_root_retourne_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "Quoridor" in r.text
```

- [ ] **Étape 3 — Implémenter le serveur**

Créer `webapp/server.py` :

```python
"""Point d'entree FastAPI pour la web app de demo Quoridor.

Lancement standalone :
    python -m webapp.server

Le serveur écoute sur 0.0.0.0:8000 (accessible depuis le réseau local).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from webapp.service import QuoridorService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def create_app(uart_bridge: Optional[object] = None) -> FastAPI:
    """Crée et configure l'application FastAPI.

    Args:
        uart_bridge: instance optionnelle de UartBridge (None en tests).

    Returns:
        Application FastAPI prête à servir.
    """
    app = FastAPI(title="Quoridor Demo")
    service = QuoridorService(uart_bridge=uart_bridge)
    app.state.service = service

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(
            STATIC_DIR / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    return app


def main() -> None:
    """Entrypoint CLI."""
    import uvicorn
    from webapp import uart_bridge as uart_bridge_module

    bridge = uart_bridge_module.init()
    app = create_app(uart_bridge=bridge)
    app.state.service.start_tick_thread()

    log.info("Quoridor web app demarree sur http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
```

- [ ] **Étape 4 — Lancer les tests**

```bash
pytest tests/webapp/test_api.py -v
```

Attendu : `test_get_root_retourne_html` PASS.

- [ ] **Étape 5 — Test fumée manuel**

```bash
python -m webapp.server &
sleep 2
curl -s http://localhost:8000/ | head -5
kill %1
```

Attendu : la 1<sup>re</sup> ligne contient `<!doctype html>`.

- [ ] **Étape 6 — Commit**

```bash
git add webapp/server.py webapp/static/index.html tests/webapp/test_api.py
git commit -m "feat(webapp): server FastAPI + route GET /"
```

---

### Task 3.2 : Route `GET /api/state`

**Files:**
- Modify: `webapp/server.py`
- Modify: `tests/webapp/test_api.py`

- [ ] **Étape 1 — Ajouter le test**

Ajouter à `tests/webapp/test_api.py` :

```python
class TestGetState:
    def test_get_state_initial(self, client):
        r = client.get("/api/state")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "waiting"
        assert data["players"] == {}
        assert data["plateau"]["available"] is False  # uart_bridge=None dans la fixture

    def test_get_state_apres_new_game(self, client):
        client.post(
            "/api/new-game",
            json={"mode": "human_vs_ai", "difficulty": "normal", "plateau_mode": False},
        )
        r = client.get("/api/state")
        data = r.json()
        assert data["status"] == "playing"
        assert data["current_player"] == "j1"
```

- [ ] **Étape 2 — Lancer le test, vérifier l'échec**

```bash
pytest tests/webapp/test_api.py::TestGetState -v
```

Attendu : FAIL (404 sur `/api/state`).

- [ ] **Étape 3 — Ajouter la route**

Dans `webapp/server.py`, à l'intérieur de `create_app()` avant `return app` :

```python
    @app.get("/api/state")
    def get_state():
        return service.to_dict()
```

- [ ] **Étape 4 — Relancer**

```bash
pytest tests/webapp/test_api.py -v
```

Le test `test_get_state_initial` doit PASS. Le second test `test_get_state_apres_new_game` continuera de fail tant que `POST /api/new-game` n'est pas implémentée (Task 3.3).

- [ ] **Étape 5 — Commit**

```bash
git add webapp/server.py tests/webapp/test_api.py
git commit -m "feat(webapp): route GET /api/state"
```

---

### Task 3.3 : Route `POST /api/new-game`

**Files:**
- Modify: `webapp/server.py`

- [ ] **Étape 1 — Le test existe déjà (`test_get_state_apres_new_game`)**

- [ ] **Étape 2 — Vérifier l'échec actuel**

```bash
pytest tests/webapp/test_api.py::TestGetState::test_get_state_apres_new_game -v
```

Attendu : FAIL (POST /api/new-game retourne 404 ou 405).

- [ ] **Étape 3 — Ajouter la route**

Dans `webapp/server.py`, dans `create_app()` :

```python
    from webapp.schemas import NewGamePayload  # importer en haut du fichier

    @app.post("/api/new-game")
    def post_new_game(payload: NewGamePayload):
        if payload.plateau_mode and (uart_bridge is None or not uart_bridge.available):
            return _error_response("PLATEAU_UNAVAILABLE", "Plateau non détecté.", 400)
        service.new_game(
            mode=payload.mode,
            difficulty=payload.difficulty,
            plateau_mode=payload.plateau_mode,
        )
        return service.to_dict()
```

Ajouter aussi cette fonction utilitaire en bas du module (hors `create_app`) :

```python
def _error_response(code: str, message: str, status_code: int):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": code, "message": message}},
    )
```

Et l'import en haut de `server.py` :

```python
from webapp.schemas import NewGamePayload, MovePayload, SpeedPayload, WallModePayload
```

- [ ] **Étape 4 — Relancer**

```bash
pytest tests/webapp/test_api.py -v
```

Attendu : tous PASS.

- [ ] **Étape 5 — Commit**

```bash
git add webapp/server.py
git commit -m "feat(webapp): route POST /api/new-game"
```

---

### Task 3.4 : Route `POST /api/move`

**Files:**
- Modify: `webapp/server.py`
- Modify: `tests/webapp/test_api.py`

- [ ] **Étape 1 — Ajouter les tests**

Ajouter à `tests/webapp/test_api.py` :

```python
class TestPostMove:
    def _start(self, client):
        client.post(
            "/api/new-game",
            json={"mode": "human_vs_ai", "difficulty": "facile", "plateau_mode": False},
        )

    def test_deplacement_valide(self, client):
        self._start(client)
        r = client.post(
            "/api/move",
            json={"type": "deplacement", "target": [4, 3]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["players"]["j1"]["position"] == [4, 3]

    def test_deplacement_invalide_retourne_400(self, client):
        self._start(client)
        r = client.post(
            "/api/move",
            json={"type": "deplacement", "target": [0, 0]},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["code"]  # contient un code d'erreur

    def test_pose_mur_horizontal(self, client):
        self._start(client)
        r = client.post(
            "/api/move",
            json={"type": "mur", "orientation": "h", "row": 4, "col": 2},
        )
        assert r.status_code == 200
        data = r.json()
        assert {"orientation": "h", "row": 4, "col": 2} in data["walls"]
```

- [ ] **Étape 2 — Lancer, vérifier l'échec**

```bash
pytest tests/webapp/test_api.py::TestPostMove -v
```

Attendu : FAIL (404).

- [ ] **Étape 3 — Ajouter la route**

Dans `webapp/server.py`, dans `create_app()` :

```python
    @app.post("/api/move")
    def post_move(payload: MovePayload):
        from quoridor_engine import InvalidMoveError

        move_dict = payload.model_dump()
        try:
            service.apply_user_move(move_dict)
        except InvalidMoveError as e:
            return _error_response(e.code.value, str(e), 400)
        return service.to_dict()
```

- [ ] **Étape 4 — Relancer**

```bash
pytest tests/webapp/test_api.py -v
```

Attendu : tous PASS.

- [ ] **Étape 5 — Commit**

```bash
git add webapp/server.py tests/webapp/test_api.py
git commit -m "feat(webapp): route POST /api/move"
```

---

### Task 3.5 : Routes restantes (pause/resume/speed/wall-mode/quit)

**Files:**
- Modify: `webapp/server.py`
- Modify: `tests/webapp/test_api.py`

- [ ] **Étape 1 — Ajouter les tests**

Ajouter à `tests/webapp/test_api.py` :

```python
class TestRoutesControles:
    def _start_ai_vs_ai(self, client):
        client.post(
            "/api/new-game",
            json={"mode": "ai_vs_ai", "difficulty": "facile", "plateau_mode": False},
        )

    def test_pause_resume(self, client):
        self._start_ai_vs_ai(client)
        r = client.post("/api/pause")
        assert r.status_code == 200
        assert r.json()["status"] == "paused"
        r = client.post("/api/resume")
        assert r.json()["status"] == "playing"

    def test_set_speed(self, client):
        r = client.post("/api/speed", json={"speed": "rapide"})
        assert r.status_code == 200
        assert r.json()["speed"] == "rapide"

    def test_set_speed_invalide_retourne_422(self, client):
        r = client.post("/api/speed", json={"speed": "ultraflash"})
        assert r.status_code == 422  # Pydantic rejette avant d'arriver au handler

    def test_wall_mode_active_horizontal(self, client):
        client.post(
            "/api/new-game",
            json={"mode": "human_vs_ai", "difficulty": "facile", "plateau_mode": False},
        )
        r = client.post("/api/wall-mode", json={"orientation": "h"})
        assert r.status_code == 200
        assert r.json()["wall_placement_mode"] == "h"

    def test_quit_retour_waiting(self, client):
        self._start_ai_vs_ai(client)
        r = client.post("/api/quit")
        assert r.status_code == 200
        assert r.json()["status"] == "waiting"
```

- [ ] **Étape 2 — Lancer, vérifier l'échec**

```bash
pytest tests/webapp/test_api.py::TestRoutesControles -v
```

Attendu : FAIL (404).

- [ ] **Étape 3 — Ajouter les routes**

Dans `webapp/server.py`, dans `create_app()` :

```python
    @app.post("/api/pause")
    def post_pause():
        service.pause()
        return service.to_dict()

    @app.post("/api/resume")
    def post_resume():
        service.resume()
        return service.to_dict()

    @app.post("/api/speed")
    def post_speed(payload: SpeedPayload):
        service.set_speed(payload.speed)
        return service.to_dict()

    @app.post("/api/wall-mode")
    def post_wall_mode(payload: WallModePayload):
        service.set_wall_mode(payload.orientation)
        return service.to_dict()

    @app.post("/api/quit")
    def post_quit():
        service.quit_to_home()
        return service.to_dict()
```

- [ ] **Étape 4 — Relancer**

```bash
pytest tests/webapp/test_api.py -v
```

Attendu : tous PASS.

- [ ] **Étape 5 — Lancer la suite complète backend**

```bash
pytest tests/webapp/ -v
```

Attendu : tous les tests `tests/webapp/` PASS (au moins 30 tests).

- [ ] **Étape 6 — Vérifier la non-régression globale**

```bash
pytest -m "not devkit" -q
```

Attendu : tous les tests PASS, au moins 234 + ~30 nouveaux.

- [ ] **Étape 7 — Commit**

```bash
git add webapp/server.py tests/webapp/test_api.py
git commit -m "feat(webapp): routes pause/resume/speed/wall-mode/quit"
```

---

## Phase 4 — Frontend

### Task 4.1 : HTML structure (2 vues, mobile-first)

**Files:**
- Modify: `webapp/static/index.html` (réécriture complète)

- [ ] **Étape 1 — Réécrire `webapp/static/index.html`**

```html
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="theme-color" content="#faf6ee">
  <title>Quoridor</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>

  <!-- ============ VUE ACCUEIL ============ -->
  <section id="view-home" class="view">
    <header class="home-header">
      <h1>Quoridor</h1>
      <p class="subtitle">Choisis ton mode</p>
    </header>

    <div class="home-form">
      <label class="field-label">Mode</label>
      <div class="chip-group" data-field="mode">
        <button class="chip selected" data-value="human_vs_ai">Humain vs IA</button>
        <button class="chip" data-value="ai_vs_ai">IA vs IA</button>
      </div>

      <label class="field-label">Difficulté</label>
      <div class="chip-group" data-field="difficulty">
        <button class="chip" data-value="facile">Facile</button>
        <button class="chip selected" data-value="normal">Normal</button>
        <button class="chip" data-value="difficile">Difficile</button>
      </div>

      <div id="speed-block" class="hidden">
        <label class="field-label">Vitesse IA vs IA</label>
        <div class="chip-group" data-field="speed">
          <button class="chip" data-value="lent">Lent</button>
          <button class="chip selected" data-value="normal">Normal</button>
          <button class="chip" data-value="rapide">Rapide</button>
        </div>
      </div>

      <div class="toggle-row">
        <label class="field-label">Plateau physique</label>
        <button id="plateau-toggle" class="toggle" disabled>
          <span class="toggle-knob"></span>
        </button>
        <span id="plateau-hint" class="hint">Plateau non détecté</span>
      </div>

      <button id="btn-start" class="btn-primary">Commencer la partie →</button>
    </div>
  </section>

  <!-- ============ VUE JEU ============ -->
  <section id="view-game" class="view hidden">
    <header class="game-bar">
      <button id="btn-home" class="icon-btn" aria-label="Retour accueil">←</button>
      <span class="game-title"><strong>Quoridor</strong> · Tour <span id="turn-count">0</span></span>
      <button id="btn-menu" class="icon-btn" aria-label="Menu">⋯</button>
    </header>

    <div class="status-bar">
      <span class="player-info j1"><span class="dot dot-j1"></span>J1 · <span id="j1-walls">6</span> murs</span>
      <span id="turn-indicator">Ton tour</span>
      <span class="player-info j2"><span class="dot dot-j2"></span>J2 · <span id="j2-walls">6</span> murs</span>
    </div>

    <div class="board-wrap">
      <svg id="board" viewBox="0 0 360 360" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="boardBg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#f4e8d2"/>
            <stop offset="100%" stop-color="#ead9b8"/>
          </linearGradient>
          <linearGradient id="cellGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#fbf3df"/>
            <stop offset="100%" stop-color="#f5ead0"/>
          </linearGradient>
          <radialGradient id="pawnBlue" cx="35%" cy="35%" r="65%">
            <stop offset="0%" stop-color="#5b9fd9"/>
            <stop offset="100%" stop-color="#1f5f8f"/>
          </radialGradient>
          <radialGradient id="pawnRed" cx="35%" cy="35%" r="65%">
            <stop offset="0%" stop-color="#e57a6c"/>
            <stop offset="100%" stop-color="#9c2f23"/>
          </radialGradient>
          <linearGradient id="wallGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#7a4a22"/>
            <stop offset="100%" stop-color="#4f2e12"/>
          </linearGradient>
          <filter id="softShadow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceAlpha" stdDeviation="2"/>
            <feOffset dx="0" dy="2"/>
            <feComponentTransfer><feFuncA type="linear" slope="0.35"/></feComponentTransfer>
            <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>
        <rect width="360" height="360" rx="20" fill="url(#boardBg)"/>
        <g id="cells"></g>
        <g id="walls-layer"></g>
        <g id="intersections" class="hidden"></g>
        <circle id="pawn-j1" class="pawn" r="20" fill="url(#pawnBlue)" filter="url(#softShadow)" cx="180" cy="300"/>
        <circle id="pawn-j2" class="pawn" r="20" fill="url(#pawnRed)" filter="url(#softShadow)" cx="180" cy="60"/>
      </svg>
    </div>

    <div id="game-actions" class="game-actions">
      <button id="btn-wall-h" class="btn-secondary">Mur H</button>
      <button id="btn-wall-v" class="btn-secondary">Mur V</button>
    </div>

    <div id="ai-vs-ai-controls" class="ai-controls hidden">
      <div class="chip-group" data-field="speed-ingame">
        <button class="chip" data-value="lent">Lent</button>
        <button class="chip selected" data-value="normal">Normal</button>
        <button class="chip" data-value="rapide">Rapide</button>
      </div>
      <button id="btn-pause" class="btn-secondary">Pause</button>
    </div>
  </section>

  <!-- ============ MODAL FIN DE PARTIE ============ -->
  <div id="modal-end" class="modal hidden">
    <div class="modal-card">
      <div class="trophy">🏆</div>
      <h2 id="end-winner">J1 gagne en N tours !</h2>
      <div class="modal-actions">
        <button id="btn-replay" class="btn-primary">Rejouer</button>
        <button id="btn-home-from-end" class="btn-secondary">Retour accueil</button>
      </div>
    </div>
  </div>

  <!-- ============ TOAST ============ -->
  <div id="toast" class="toast hidden"></div>

  <!-- ============ OVERLAY RECONNEXION ============ -->
  <div id="overlay-reconnect" class="overlay hidden">
    <div class="overlay-content">Reconnexion…</div>
  </div>

  <script src="/static/app.js" defer></script>
</body>
</html>
```

- [ ] **Étape 2 — Vérifier que le fichier sert bien**

```bash
python -m webapp.server &
sleep 2
curl -s http://localhost:8000/ | grep -c "view-home\|view-game"
kill %1
```

Attendu : `2` (les deux IDs sont présents).

- [ ] **Étape 3 — Commit**

```bash
git add webapp/static/index.html
git commit -m "feat(webapp): HTML structure 2 vues + plateau SVG"
```

---

### Task 4.2 : CSS palette C2 affinée

**Files:**
- Create: `webapp/static/style.css`

- [ ] **Étape 1 — Écrire le CSS**

Créer `webapp/static/style.css` :

```css
:root {
  --bg: #faf6ee;
  --board-bg: #ead9b8;
  --cell-light: #fbf3df;
  --cell-dark: #f5ead0;
  --grid: #c9a96e;
  --wood-dark: #5a3818;
  --primary: #b86b3a;
  --primary-dark: #8b4520;
  --text: #2c1810;
  --text-soft: #6b5a44;
  --muted: #d9c8a3;
  --error: #c0392b;
}

* { box-sizing: border-box; }

html, body {
  margin: 0; padding: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, "SF Pro Text", system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  font-size: 16px;
  min-height: 100vh;
  min-height: 100dvh;
}

.view {
  padding: max(env(safe-area-inset-top), 20px) 20px max(env(safe-area-inset-bottom), 20px);
  max-width: 480px;
  margin: 0 auto;
}

.hidden { display: none !important; }

/* === Accueil === */
.home-header { text-align: center; margin: 40px 0 30px; }
.home-header h1 { font-size: 32px; font-weight: 700; margin: 0; }
.subtitle { color: var(--text-soft); font-size: 15px; margin: 4px 0; }

.field-label {
  display: block; font-size: 13px; font-weight: 500;
  color: var(--text-soft); margin: 16px 0 6px;
  text-transform: uppercase; letter-spacing: 0.4px;
}

.chip-group { display: flex; gap: 8px; flex-wrap: wrap; }
.chip {
  flex: 1; min-width: 80px;
  padding: 10px 14px; border-radius: 12px;
  background: #f0e8d8; color: var(--text-soft);
  border: 1.5px solid transparent;
  font-size: 14px; font-weight: 500;
  cursor: pointer; transition: all 0.15s ease-out;
  font-family: inherit;
}
.chip.selected {
  background: var(--primary); color: white;
  border-color: var(--primary-dark);
}
.chip:active { transform: scale(0.97); }

.toggle-row {
  display: flex; align-items: center; gap: 12px;
  margin: 20px 0 24px;
}
.toggle-row .field-label { margin: 0; flex: 1; }
.toggle {
  width: 50px; height: 28px; border-radius: 14px;
  background: #d9c8a3; border: none; padding: 2px;
  position: relative; cursor: pointer;
  transition: background 0.2s;
}
.toggle.on { background: var(--primary); }
.toggle:disabled { opacity: 0.5; cursor: not-allowed; }
.toggle-knob {
  display: block;
  width: 24px; height: 24px; border-radius: 50%;
  background: white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  transition: transform 0.2s;
}
.toggle.on .toggle-knob { transform: translateX(22px); }
.hint { font-size: 12px; color: var(--text-soft); }

.btn-primary {
  width: 100%;
  padding: 14px;
  border-radius: 14px;
  background: var(--primary);
  color: white;
  font-size: 16px; font-weight: 600;
  border: none; cursor: pointer;
  margin-top: 24px;
  font-family: inherit;
  box-shadow: 0 2px 6px rgba(184, 107, 58, 0.3);
  transition: transform 0.1s;
}
.btn-primary:active { transform: scale(0.98); }

.btn-secondary {
  padding: 10px 18px;
  border-radius: 12px;
  background: #f0e8d8;
  color: var(--text);
  font-size: 14px; font-weight: 500;
  border: none; cursor: pointer;
  font-family: inherit;
}
.btn-secondary.active {
  background: var(--primary); color: white;
}
.btn-secondary:active { transform: scale(0.97); }

/* === Vue jeu === */
.game-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 4px 16px;
}
.icon-btn {
  background: transparent; border: none;
  font-size: 24px; cursor: pointer; color: var(--text);
  padding: 4px 8px;
}
.game-title { font-size: 15px; color: var(--text-soft); }
.game-title strong { color: var(--text); font-weight: 600; }

.status-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 6px 12px;
  font-size: 13px;
}
.player-info { display: flex; align-items: center; gap: 6px; color: var(--text-soft); }
.dot { width: 10px; height: 10px; border-radius: 50%; }
.dot-j1 { background: radial-gradient(circle at 35% 35%, #5b9fd9, #1f5f8f); }
.dot-j2 { background: radial-gradient(circle at 35% 35%, #e57a6c, #9c2f23); }

#turn-indicator {
  font-size: 13px; font-weight: 600;
  color: var(--primary);
  padding: 4px 10px; border-radius: 8px;
  background: rgba(184, 107, 58, 0.12);
}
#turn-indicator.ai-thinking::after {
  content: "…"; animation: dots 1s steps(3, end) infinite;
}
@keyframes dots { 0%, 33% { content: "."; } 34%, 66% { content: ".."; } 67%, 100% { content: "..."; } }

.board-wrap {
  width: 100%; max-width: 360px; aspect-ratio: 1;
  margin: 0 auto;
}
#board { width: 100%; height: 100%; display: block; }

.cell {
  fill: url(#cellGrad);
  stroke: var(--grid); stroke-width: 0.6;
  cursor: pointer;
}
.cell.reachable { fill: #ffefc8; }

.pawn {
  transition: cx 0.4s ease-out, cy 0.4s ease-out;
}

.wall { fill: url(#wallGrad); }

.intersection {
  fill: var(--primary); opacity: 0.35; cursor: pointer;
  transition: opacity 0.15s;
}
.intersection:active { opacity: 0.8; }

.game-actions {
  display: flex; gap: 10px; justify-content: center;
  margin-top: 16px;
}

.ai-controls {
  display: flex; flex-direction: column; gap: 10px;
  margin-top: 16px; align-items: center;
}
.ai-controls .chip-group { width: 100%; max-width: 280px; }

/* === Modal fin de partie === */
.modal {
  position: fixed; inset: 0;
  background: rgba(44, 24, 16, 0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
  padding: 24px;
}
.modal-card {
  background: var(--bg);
  border-radius: 20px;
  padding: 32px 24px;
  max-width: 320px; width: 100%;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0,0,0,0.25);
}
.trophy { font-size: 56px; margin-bottom: 12px; }
.modal-card h2 { font-size: 20px; margin: 0 0 24px; }
.modal-actions { display: flex; flex-direction: column; gap: 10px; }

/* === Toast === */
.toast {
  position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
  background: var(--text); color: var(--bg);
  padding: 10px 18px; border-radius: 12px;
  font-size: 14px; max-width: 80vw;
  z-index: 200;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
  animation: toastIn 0.2s ease-out;
}
@keyframes toastIn { from { opacity: 0; transform: translateX(-50%) translateY(10px); } }

/* === Overlay reconnexion === */
.overlay {
  position: fixed; inset: 0;
  background: rgba(250, 246, 238, 0.92);
  backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
  z-index: 150;
}
.overlay-content {
  background: var(--bg);
  padding: 20px 32px;
  border-radius: 14px;
  font-size: 16px; font-weight: 500;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}

/* === Wall placement mode === */
body.wall-placement #intersections { display: block; }
body.wall-placement .cell { opacity: 0.6; cursor: default; }
```

- [ ] **Étape 2 — Tester visuellement (un seul écran)**

```bash
python -m webapp.server &
sleep 1
open "http://localhost:8000"
```

Vérifier : l'écran d'accueil s'affiche avec la palette beige/brun, les chips sont stylés, le bouton primary orange est visible. Pas de JS encore donc rien ne réagit aux clics. `kill` du serveur après vérification.

- [ ] **Étape 3 — Commit**

```bash
git add webapp/static/style.css
git commit -m "feat(webapp): CSS palette C2 affinee + responsive mobile"
```

---

### Task 4.3 : `app.js` — skeleton + polling + render plateau

**Files:**
- Create: `webapp/static/app.js`

- [ ] **Étape 1 — Écrire `app.js`**

Créer `webapp/static/app.js` :

```javascript
"use strict";

// ============ ÉTAT GLOBAL ============
const BOARD_SIZE = 6;
const SVG_VIEWBOX = 360;
const CELL = 50;         // taille d'une case en unités SVG
const MARGIN = 30;       // marge autour de la grille
let state = null;        // dernier state reçu
let consecutiveErrors = 0;
let pendingWallMode = null;  // synchro UI optimiste

const homeForm = {
  mode: "human_vs_ai",
  difficulty: "normal",
  speed: "normal",
  plateau_mode: false,
};

// ============ HELPERS GEO ============
function cellCenterXY(row, col) {
  // row 0 = haut, col 0 = gauche
  const x = MARGIN + col * CELL + CELL / 2;
  const y = MARGIN + row * CELL + CELL / 2;
  return { x, y };
}

function cellTopLeftXY(row, col) {
  return { x: MARGIN + col * CELL, y: MARGIN + row * CELL };
}

// ============ RENDER ============
function renderCells() {
  const layer = document.getElementById("cells");
  layer.innerHTML = "";
  for (let r = 0; r < BOARD_SIZE; r++) {
    for (let c = 0; c < BOARD_SIZE; c++) {
      const { x, y } = cellTopLeftXY(r, c);
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("class", "cell");
      rect.setAttribute("x", x);
      rect.setAttribute("y", y);
      rect.setAttribute("width", CELL);
      rect.setAttribute("height", CELL);
      rect.setAttribute("rx", "4");
      rect.dataset.row = r;
      rect.dataset.col = c;
      rect.addEventListener("click", () => handleCellClick(r, c));
      layer.appendChild(rect);
    }
  }
}

function renderIntersections() {
  // Les intersections sont les coins INTÉRIEURS de la grille,
  // soit (row, col) avec row ∈ [0, BOARD_SIZE-2] et col ∈ [0, BOARD_SIZE-2].
  // Un mur H couvre 2 cases en hauteur → row du mur = r, col = c
  // Un mur V couvre 2 cases en largeur → idem
  const layer = document.getElementById("intersections");
  layer.innerHTML = "";
  for (let r = 0; r < BOARD_SIZE - 1; r++) {
    for (let c = 0; c < BOARD_SIZE - 1; c++) {
      const { x, y } = cellTopLeftXY(r + 1, c);  // entre row r et r+1
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("class", "intersection");
      // Position du marqueur selon orientation
      // On affiche un seul indicateur générique au coin (r+1, c+1)
      // → on stocke l'orientation au moment du clic
      dot.setAttribute("cx", x + CELL);
      dot.setAttribute("cy", y);
      dot.setAttribute("r", 7);
      dot.dataset.row = r;
      dot.dataset.col = c;
      dot.addEventListener("click", () => handleIntersectionClick(r, c));
      layer.appendChild(dot);
    }
  }
}

function renderWalls(walls) {
  const layer = document.getElementById("walls-layer");
  layer.innerHTML = "";
  for (const w of walls) {
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("class", "wall");
    if (w.orientation === "h") {
      // Mur horizontal entre row w.row et w.row+1, couvre cols w.col et w.col+1
      const { x, y } = cellTopLeftXY(w.row + 1, w.col);
      rect.setAttribute("x", x);
      rect.setAttribute("y", y - 3);
      rect.setAttribute("width", CELL * 2);
      rect.setAttribute("height", 6);
    } else {
      // Mur vertical entre col w.col et w.col+1, couvre rows w.row et w.row+1
      const { x, y } = cellTopLeftXY(w.row, w.col + 1);
      rect.setAttribute("x", x - 3);
      rect.setAttribute("y", y);
      rect.setAttribute("width", 6);
      rect.setAttribute("height", CELL * 2);
    }
    rect.setAttribute("rx", "2");
    layer.appendChild(rect);
  }
}

function renderPawns(players) {
  const { x: x1, y: y1 } = cellCenterXY(players.j1.position[0], players.j1.position[1]);
  const { x: x2, y: y2 } = cellCenterXY(players.j2.position[0], players.j2.position[1]);
  const p1 = document.getElementById("pawn-j1");
  const p2 = document.getElementById("pawn-j2");
  p1.setAttribute("cx", x1);
  p1.setAttribute("cy", y1);
  p2.setAttribute("cx", x2);
  p2.setAttribute("cy", y2);
}

function renderHeader(state) {
  document.getElementById("turn-count").textContent = state.turn_count;
  document.getElementById("j1-walls").textContent = state.players.j1.walls_remaining;
  document.getElementById("j2-walls").textContent = state.players.j2.walls_remaining;
  const ind = document.getElementById("turn-indicator");
  if (state.status !== "playing" && state.status !== "paused") {
    ind.textContent = "";
    ind.classList.remove("ai-thinking");
    return;
  }
  if (state.status === "paused") {
    ind.textContent = "Pause";
    ind.classList.remove("ai-thinking");
    return;
  }
  if (state.ai_thinking) {
    ind.textContent = "IA réfléchit";
    ind.classList.add("ai-thinking");
  } else if (state.mode === "ai_vs_ai") {
    ind.textContent = `Tour de ${state.current_player.toUpperCase()}`;
    ind.classList.remove("ai-thinking");
  } else {
    ind.textContent = state.current_player === "j1" ? "Ton tour" : "IA joue";
    ind.classList.remove("ai-thinking");
  }
}

function renderViews(state) {
  const home = document.getElementById("view-home");
  const game = document.getElementById("view-game");
  if (state.status === "waiting") {
    home.classList.remove("hidden");
    game.classList.add("hidden");
  } else {
    home.classList.add("hidden");
    game.classList.remove("hidden");
  }

  // Mode IA vs IA : affiche les contrôles de vitesse + pause
  const aiCtrls = document.getElementById("ai-vs-ai-controls");
  const moveActions = document.getElementById("game-actions");
  if (state.mode === "ai_vs_ai") {
    aiCtrls.classList.remove("hidden");
    moveActions.classList.add("hidden");
  } else {
    aiCtrls.classList.add("hidden");
    moveActions.classList.remove("hidden");
  }
}

function renderWallMode(state) {
  document.body.classList.toggle("wall-placement", !!state.wall_placement_mode);
  document.getElementById("btn-wall-h").classList.toggle("active", state.wall_placement_mode === "h");
  document.getElementById("btn-wall-v").classList.toggle("active", state.wall_placement_mode === "v");
}

function renderModal(state) {
  const modal = document.getElementById("modal-end");
  if (state.status === "finished" && state.winner) {
    document.getElementById("end-winner").textContent =
      `${state.winner.toUpperCase()} gagne en ${state.turn_count} tours !`;
    modal.classList.remove("hidden");
  } else {
    modal.classList.add("hidden");
  }
}

function renderPlateauToggle(state) {
  const toggle = document.getElementById("plateau-toggle");
  const hint = document.getElementById("plateau-hint");
  if (state.plateau.available) {
    toggle.disabled = false;
    hint.textContent = state.plateau.connected ? "Connecté" : "Disponible";
  } else {
    toggle.disabled = true;
    toggle.classList.remove("on");
    hint.textContent = "Plateau non détecté";
  }
}

function renderError(state) {
  if (state.last_error && state.last_error.code) {
    showToast(state.last_error.message || state.last_error.code);
    // Le serveur garde last_error jusqu'à new-game/quit ; on le montre une fois
    // donc on garde une trace locale pour pas spammer.
    if (state.last_error.code !== window._lastShownError) {
      window._lastShownError = state.last_error.code;
    }
  }
}

function render(newState) {
  state = newState;
  document.getElementById("overlay-reconnect").classList.add("hidden");
  renderViews(state);
  if (state.status !== "waiting") {
    renderWalls(state.walls);
    renderPawns(state.players);
    renderHeader(state);
    renderWallMode(state);
  }
  renderModal(state);
  renderPlateauToggle(state);
  renderError(state);
}

// ============ ACTIONS UI ============
async function api(method, path, body) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    const detail = data.detail || {};
    throw new Error(detail.message || detail.code || `HTTP ${r.status}`);
  }
  return r.json();
}

async function handleCellClick(row, col) {
  if (!state || state.status !== "playing") return;
  if (state.wall_placement_mode) return;  // pas en mode mur
  if (state.mode === "ai_vs_ai") return;
  if (state.current_player !== "j1") return;  // pas mon tour
  try {
    const next = await api("POST", "/api/move", { type: "deplacement", target: [row, col] });
    render(next);
  } catch (e) {
    showToast(`Coup impossible : ${e.message}`);
  }
}

async function handleIntersectionClick(row, col) {
  if (!state || !state.wall_placement_mode) return;
  if (state.current_player !== "j1") return;
  const orientation = state.wall_placement_mode;
  try {
    const next = await api("POST", "/api/move", {
      type: "mur",
      orientation,
      row,
      col,
    });
    render(next);
  } catch (e) {
    showToast(`Coup impossible : ${e.message}`);
  }
}

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => t.classList.add("hidden"), 2500);
}

// ============ POLLING ============
async function poll() {
  try {
    const r = await fetch("/api/state");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    consecutiveErrors = 0;
    render(data);
  } catch (e) {
    consecutiveErrors++;
    if (consecutiveErrors >= 3) {
      document.getElementById("overlay-reconnect").classList.remove("hidden");
    }
  } finally {
    setTimeout(poll, 500);
  }
}

// ============ INIT ============
function initHandlers() {
  // Chip groups (accueil)
  document.querySelectorAll(".chip-group").forEach(group => {
    const field = group.dataset.field;
    group.querySelectorAll(".chip").forEach(chip => {
      chip.addEventListener("click", () => {
        group.querySelectorAll(".chip").forEach(c => c.classList.remove("selected"));
        chip.classList.add("selected");
        const value = chip.dataset.value;
        if (field === "speed-ingame") {
          api("POST", "/api/speed", { speed: value }).then(render).catch(e => showToast(e.message));
        } else {
          homeForm[field] = value;
          if (field === "mode") {
            document.getElementById("speed-block").classList.toggle("hidden", value !== "ai_vs_ai");
          }
        }
      });
    });
  });

  // Toggle plateau
  document.getElementById("plateau-toggle").addEventListener("click", e => {
    if (e.currentTarget.disabled) return;
    e.currentTarget.classList.toggle("on");
    homeForm.plateau_mode = e.currentTarget.classList.contains("on");
  });

  // Bouton start
  document.getElementById("btn-start").addEventListener("click", async () => {
    try {
      const next = await api("POST", "/api/new-game", homeForm);
      render(next);
    } catch (e) {
      showToast(e.message);
    }
  });

  // Boutons murs
  document.getElementById("btn-wall-h").addEventListener("click", async () => {
    const newMode = state.wall_placement_mode === "h" ? null : "h";
    await api("POST", "/api/wall-mode", { orientation: newMode }).then(render);
  });
  document.getElementById("btn-wall-v").addEventListener("click", async () => {
    const newMode = state.wall_placement_mode === "v" ? null : "v";
    await api("POST", "/api/wall-mode", { orientation: newMode }).then(render);
  });

  // Bouton retour accueil
  const goHome = async () => {
    if (state && state.status === "playing" && !confirm("Quitter la partie en cours ?")) return;
    const next = await api("POST", "/api/quit");
    render(next);
  };
  document.getElementById("btn-home").addEventListener("click", goHome);

  // Bouton pause/resume
  document.getElementById("btn-pause").addEventListener("click", async () => {
    const path = state.status === "paused" ? "/api/resume" : "/api/pause";
    const next = await api("POST", path);
    render(next);
    document.getElementById("btn-pause").textContent =
      next.status === "paused" ? "Reprendre" : "Pause";
  });

  // Modal fin de partie
  document.getElementById("btn-replay").addEventListener("click", async () => {
    const next = await api("POST", "/api/new-game", {
      mode: state.mode,
      difficulty: state.difficulty,
      plateau_mode: state.plateau.mode_active,
    });
    render(next);
  });
  document.getElementById("btn-home-from-end").addEventListener("click", goHome);
}

document.addEventListener("DOMContentLoaded", () => {
  renderCells();
  renderIntersections();
  initHandlers();
  poll();
});
```

- [ ] **Étape 2 — Tester manuellement le flux complet golden path**

```bash
python -m webapp.server
```

Dans Safari Mac ouvrir `http://localhost:8000`. Vérifier :
1. L'accueil s'affiche.
2. Mode = "Humain vs IA", Difficulté = "Facile", taper "Commencer".
3. La vue jeu s'affiche, le plateau est dessiné, les 2 pions sont visibles aux positions de départ.
4. Cliquer sur la case (4, 3) (juste au-dessus du pion bleu) — il bouge.
5. L'IA réfléchit puis joue (le pion rouge bouge dans la seconde).
6. Cliquer "Mur H" — le bouton devient highlight, les intersections apparaissent.
7. Cliquer une intersection — un mur horizontal apparaît, le compteur murs J1 passe à 5.
8. Re-cliquer "Mur H" pour sortir du mode.
9. Continuer jusqu'à fin de partie. La modal apparaît.
10. "Rejouer" doit relancer une partie avec les mêmes réglages.

`Ctrl+C` sur le serveur.

- [ ] **Étape 3 — Commit**

```bash
git add webapp/static/app.js
git commit -m "feat(webapp): app.js skeleton + polling + render + actions"
```

---

### Task 4.4 : Polish IA vs IA + animation de vitesse + indicateur visuel

**Files:**
- Modify: `webapp/static/app.js`

- [ ] **Étape 1 — Tester le mode IA vs IA actuel**

Lancer le serveur, démarrer une partie IA vs IA. Vérifier que les pions bougent automatiquement, que les chips de vitesse changent le rythme, que pause/reprendre marche.

- [ ] **Étape 2 — Si des bugs sont détectés : corriger ici**

Cas typiques à corriger si problèmes :

- Si le pion saute trop vite (animation < 400 ms) avec vitesse rapide → augmenter le délai mini côté serveur ou réduire l'animation côté CSS.
- Si pause ne stoppe pas visuellement le tick → vérifier que `service.pause()` change bien `_status` et que `tick_once()` retourne False.
- Si "Pause" / "Reprendre" ne switche pas le label → vérifier le code du gestionnaire `btn-pause`.

- [ ] **Étape 3 — Synchroniser le chip de vitesse en vue jeu avec le state serveur**

Dans la fonction `render(state)`, ajouter en bas avant le `renderError(state);` :

```javascript
  // Sync chip vitesse in-game avec le serveur
  const speedGroup = document.querySelector('[data-field="speed-ingame"]');
  if (speedGroup) {
    speedGroup.querySelectorAll(".chip").forEach(c => {
      c.classList.toggle("selected", c.dataset.value === state.speed);
    });
  }
```

- [ ] **Étape 4 — Commit**

```bash
git add webapp/static/app.js
git commit -m "feat(webapp): sync chip vitesse + polish IA vs IA"
```

---

## Phase 5 — Tests manuels et fiabilité

### Task 5.1 : Test golden path complet sur Safari Mac

**Pas de fichiers modifiés. Étapes uniquement.**

- [ ] **Étape 1 — Lancer le serveur**

```bash
python -m webapp.server
```

- [ ] **Étape 2 — Test 1 : Humain vs IA Normal**

Dans Safari sur le Mac, `http://localhost:8000`. Jouer une partie complète : 5-10 coups + au moins 1 mur posé. Critère : aucun plantage, l'IA répond toujours, le compteur de tour s'incrémente, fin de partie déclenche la modal.

- [ ] **Étape 3 — Test 2 : IA vs IA**

Refaire un test : Mode "IA vs IA", Difficulté "Facile", Vitesse "Normal", commencer. Vérifier :
- Les pions bougent automatiquement avec ~1.5 s entre coups.
- Changer la vitesse à "Rapide" pendant la partie : les coups suivants sont plus rapprochés.
- Cliquer "Pause" : les pions arrêtent. Cliquer "Reprendre" : ça repart.
- Attendre la fin de partie : la modal apparaît.

- [ ] **Étape 4 — Test 3 : Reload pendant une partie**

Pendant une partie en cours, recharger Safari (Cmd+R). La vue jeu doit revenir avec l'état exact d'avant le reload (positions, murs, tour). Si la vue accueil s'affiche à la place : bug, vérifier le `renderViews()`.

- [ ] **Étape 5 — Test 4 : Coup invalide humain**

En H vs IA, essayer de cliquer une case non adjacente au pion humain. Vérifier qu'un toast "Coup impossible" apparaît et que rien ne change côté serveur.

- [ ] **Étape 6 — Test 5 : Reconnexion**

Lancer le serveur, charger Safari, démarrer une partie. Killer le serveur (`Ctrl+C`). Vérifier que l'overlay "Reconnexion…" apparaît après ~2 s. Relancer le serveur. L'overlay doit disparaître au prochain poll réussi.

- [ ] **Étape 7 — Si tous les tests passent : commit la documentation**

Ajouter une section de doc sur le test à `docs/superpowers/plans/2026-05-18-webapp-demo-quoridor.md` (note de test passée le YYYY-MM-DD à HH:MM). Pas de commit obligatoire si rien à changer.

- [ ] **Étape 8 — Si un test échoue : noter le bug, créer une tâche correctrice, corriger, retester**

Ne pas avancer en Phase 6 tant que les 5 tests ne passent pas.

---

### Task 5.2 : Test depuis Safari iPhone (réseau local Mac)

**Pas de fichiers modifiés. Étapes uniquement.**

- [ ] **Étape 1 — Mac et iPhone sur le même Wi-Fi**

- [ ] **Étape 2 — Récupérer l'IP du Mac**

```bash
ipconfig getifaddr en0
```

(Si pas de résultat, essayer `en1`, `en2`. Noter l'IP, ex : `192.168.1.42`.)

- [ ] **Étape 3 — Lancer le serveur (déjà sur 0.0.0.0:8000)**

```bash
python -m webapp.server
```

- [ ] **Étape 4 — Ouvrir sur iPhone**

Safari iPhone → `http://192.168.1.42:8000` (remplacer par l'IP réelle).

- [ ] **Étape 5 — Refaire les tests 1, 2, 4 de Task 5.1 depuis l'iPhone**

Critères supplémentaires iPhone :
- Le plateau remplit bien l'écran (max-width 480 et aspect-ratio 1).
- Les chips de mode/difficulté sont tappables (pas de touche fantôme).
- Le tap sur intersection ne déclenche pas un zoom Safari (viewport bien configuré).
- Verrouiller l'écran 10 s, puis déverrouiller : la partie est toujours là, l'overlay reconnexion peut apparaître brièvement puis disparaître.

- [ ] **Étape 6 — Si bugs, corriger et recommit**

---

### Task 5.3 : Test fallback plateau physique (avec DevKit Freenove)

**Files:** aucun. Étapes uniquement.

- [ ] **Étape 1 — Sans DevKit branché**

Lancer le serveur. Logs : `UartBridge: aucun port detecte, mode autonome.` Charger Safari, vérifier que le toggle "Plateau physique" est grisé avec label "Plateau non détecté".

- [ ] **Étape 2 — Brancher le DevKit Freenove (cf. memory `project_brainstorm_progress.md` pour la procédure)**

`ls /dev/cu.usbserial-*` doit retourner un chemin. Killer le serveur et le relancer. Logs : `UartBridge: connecte sur /dev/cu.usbserial-XXX.`

- [ ] **Étape 3 — Recharger Safari**

Le toggle "Plateau physique" doit maintenant être activable, hint "Disponible".

- [ ] **Étape 4 — Activer le toggle, démarrer une partie**

L'API new-game doit accepter `plateau_mode=true`. Faire un coup humain. Vérifier dans les logs serveur que le forward UART a eu lieu (succès silencieux ou warning si l'API UartClient diffère du send_user_move attendu — corriger l'adapter dans `uart_bridge.py` si nécessaire).

- [ ] **Étape 5 — Débrancher le DevKit pendant la partie**

Faire un coup humain. Le serveur doit logguer un warning, `available` passe à False, le state suivant retourne `plateau.connected=false` et `last_error.code="PLATEAU_LOST"`. Toast côté Safari. La partie continue normalement.

- [ ] **Étape 6 — Si tout fonctionne, commit le log de test**

Ajouter au plan une note de validation, ou simplement noter mentalement la validation. Pas de modification de code obligatoire.

---

## Phase 6 — Déploiement RPi

### Task 6.1 : Préparer le déploiement sur Raspberry Pi 3

**Files:**
- Create: `webapp/README.md`

- [ ] **Étape 1 — Écrire la procédure**

Créer `webapp/README.md` :

```markdown
# Web app de démo Quoridor

Web app servie par le RPi (ou par le Mac en dev) pour démontrer le moteur
Quoridor et l'IA depuis un navigateur (iPhone Safari prioritaire).

Spec : [`docs/superpowers/specs/2026-05-18-webapp-demo-quoridor-design.md`](../docs/superpowers/specs/2026-05-18-webapp-demo-quoridor-design.md)
Plan : [`docs/superpowers/plans/2026-05-18-webapp-demo-quoridor.md`](../docs/superpowers/plans/2026-05-18-webapp-demo-quoridor.md)

## Lancement local (Mac)

```bash
uv pip install fastapi "uvicorn[standard]" httpx
python -m webapp.server
# → http://localhost:8000
```

Pour tester depuis l'iPhone (même Wi-Fi que le Mac) :

```bash
ipconfig getifaddr en0  # récupérer l'IP du Mac
# Safari iPhone : http://<ip-mac>:8000
```

## Déploiement RPi 3

### Étape 1 — Transfert du code

Trois options (à choisir avec Silouane le jour J) :

a. **SSH + git pull** : RPi sur le réseau, `ssh pi@<rpi>` puis `git pull` dans
   le repo cloné. Demande SSH + git config OK sur le RPi.

b. **scp depuis le Mac** :
   ```bash
   scp -r webapp/ pi@<rpi-ip>:/home/pi/quoridor/
   ```

c. **Clé USB + ssh / clavier-écran** : copie manuelle.

### Étape 2 — Dépendances Python sur le RPi

```bash
pip3 install fastapi "uvicorn[standard]" pyserial httpx
```

### Étape 3 — Lancement

```bash
cd /home/pi/quoridor
python3 -m webapp.server
# Serveur écoute sur 0.0.0.0:8000
```

### Étape 4 — Réseau pour la démo

**Recommandé : partage de connexion iPhone.**

1. iPhone : Réglages → Partage de connexion → activer.
2. RPi : se connecter au Wi-Fi de l'iPhone (configuré une fois dans
   `/etc/wpa_supplicant/wpa_supplicant.conf` ou via `raspi-config`).
3. iPhone : Réglages → Partage de connexion → "Personnes connectées" affiche
   le RPi avec son IP locale (généralement `172.20.10.x`).
4. Safari iPhone : `http://172.20.10.X:8000`.

### Étape 5 — Plateau physique (optionnel)

Si la PCB ou le DevKit Freenove est branché au RPi via USB :

```bash
ls /dev/ttyUSB* /dev/ttyAMA*  # vérifier qu'un port est détecté
```

Le serveur le détecte automatiquement au démarrage. Le toggle "Plateau
physique" devient activable sur l'écran d'accueil.

## Tests

```bash
pytest tests/webapp/ -v
# Pas de hardware requis pour ces tests.
```
```

- [ ] **Étape 2 — Commit**

```bash
git add webapp/README.md
git commit -m "docs(webapp): procedure de deploiement RPi"
```

---

## Vérification finale

### Task FIN : Suite de tests complète + bilan

- [ ] **Étape 1 — Suite complète**

```bash
pytest -m "not devkit" -q
```

Attendu : tous les tests passent (≥ 234 d'origine + ~30 webapp = ≥ 264).

- [ ] **Étape 2 — Vérifier qu'aucun fichier n'a été oublié**

```bash
git status
```

Attendu : `clean — nothing to commit`.

- [ ] **Étape 3 — Bilan**

Vérifier que tous les critères de la spec §2 (Objectifs) sont remplis :

- [x] Démontrer l'IA fonctionne sans hardware → Mode IA vs IA fonctionnel.
- [x] Jouer humain vs IA depuis Safari iPhone → Vue jeu mobile testée.
- [x] Spectacle IA vs IA ralenti → Slider de vitesse, délai mini de 1.5 s.
- [x] Mode plateau avec fallback gracieux → UartBridge détection au boot + désactivation run-time.
- [x] Fiabilité avant tout → Polling stateless, état serveur, no auto-reconnect.
- [x] Réutilisation max du code Python existant → `quoridor_engine`, `AI`, `UartClient` réutilisés.

Si tout est vert, le plan est exécuté. Sinon, créer une tâche correctrice spécifique.

---

## Notes pour les agents executors

- **Si un test ne fail pas alors qu'il devrait (étape "Lancer le test, vérifier qu'il échoue") :** c'est probablement parce que la dépendance est déjà partiellement implémentée. Lire l'erreur, ajuster le test pour qu'il échoue effectivement (par exemple en ciblant une méthode qui n'existe pas encore).
- **Si `UartClient.send_user_move()` n'existe pas :** lire `quoridor_engine/uart_client.py` et `quoridor_engine/game_session.py` pour trouver l'API réelle. Adapter le dispatcher dans `UartBridge.forward_move()` aux noms réels (`send_cmd_pawn`, `send_cmd_wall`, etc.) avant de poursuivre.
- **Si `GameState.create_initial()` n'existe pas :** chercher la factory existante dans `core.py` (probablement nommée `_create_initial_state` ou similaire, ou directement instanciée dans `QuoridorGame.__init__`). Importer la bonne fonction depuis `quoridor_engine.core` et remplacer l'appel.
- **Frontend : tester sur Safari Mac avant de tester sur iPhone.** Plus rapide d'itérer en local. iPhone uniquement pour validation finale.
- **En cas de doute sur les coordonnées SVG :** le viewBox est 360×360, marge 30 autour de la grille, cellules de 50 px. Pion en (5, 3) → centre = (30 + 3×50 + 25, 30 + 5×50 + 25) = (205, 305). Vérifier sur papier avant de coder.

---

## Suite logique post-exécution

Une fois ce plan exécuté avec succès, la web app est démontrable. Possibles évolutions ultérieures (hors scope de ce plan, à brainstormer si nécessaire) :
- Service systemd pour lancement auto au boot du RPi.
- Mode "spectateur" multi-clients distincts du joueur principal.
- Sauvegarde/restoration disque des parties en cours.
- Indicateur visuel sur le plateau des cases atteignables au tour courant.
- Intégration progressive du firmware mis à jour (boutons/LEDs) une fois la PCB soudée.
