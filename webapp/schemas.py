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
