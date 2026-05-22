"""Schémas Pydantic pour les payloads et réponses de la web app."""
from typing import Literal, Optional, Tuple
from pydantic import BaseModel, Field


Mode = Literal["human_vs_ai", "ai_vs_ai", "human_vs_human"]
Difficulty = Literal["facile", "normal", "difficile"]
Speed = Literal["lent", "normal", "rapide"]
Status = Literal["waiting", "playing", "paused", "finished"]
Orientation = Literal["h", "v"]
PlayerId = Literal["j1", "j2"]


class NewGamePayload(BaseModel):
    """Payload de POST /api/new-game.

    Le mode plateau physique est dérivé automatiquement côté serveur :
    plateau actif ssi le transport ESP32 est joignable au moment de la
    création de la partie.
    """
    mode: Mode
    difficulty: Difficulty


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


TransportKind = Literal["wifi", "serial", "none"]


class ClientStatusInfo(BaseModel):
    polling_active: bool
    polling_interval_ms: int


class TransportStatusInfo(BaseModel):
    kind: TransportKind
    description: str
    alive: bool
    last_pong_at_iso: Optional[str] = None
    last_pong_age_seconds: Optional[float] = None
    latency_avg_ms: Optional[float] = None
    startup_error: Optional[str] = None


class PlateauStatusInfo(BaseModel):
    homed: bool
    ready: bool


class StatusResponse(BaseModel):
    client: ClientStatusInfo
    transport: TransportStatusInfo
    plateau: PlateauStatusInfo


class TransportSwitchRequest(BaseModel):
    kind: Literal["wifi", "serial"]  # 'none' n'est pas une cible de switch utilisateur


class TransportSwitchResponse(BaseModel):
    success: bool
    description: str
    error: Optional[str] = None


class StateResponse(BaseModel):
    """Réponse de GET /api/state."""
    mode: Mode = "human_vs_ai"
    difficulty: Difficulty = "normal"
    speed: Speed = "normal"
    status: Status = "waiting"
    turn_count: int = 0
    current_player: Optional[PlayerId] = None
    ai_thinking: bool = False
    players: dict[str, PlayerInfo] = Field(default_factory=dict)
    walls: list[WallInfo] = Field(default_factory=list)
    winner: Optional[PlayerId] = None
    plateau: PlateauInfo = Field(
        default_factory=lambda: PlateauInfo(available=False, mode_active=False, connected=False)
    )
    last_error: Optional[ErrorInfo] = None
    wall_placement_mode: Optional[Orientation] = None
