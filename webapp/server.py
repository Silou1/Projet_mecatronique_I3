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
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from webapp.schemas import (
    NewGamePayload,
    MovePayload,
    SpeedPayload,
    WallModePayload,
    TransportSwitchRequest,
)
from webapp.service import QuoridorService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def _make_transport_by_kind(kind: str):
    """Factory helper pour le switch endpoint, indirection facilitant les tests."""
    from webapp.transport import WiFiTransport, SerialTransport
    if kind == "wifi":
        return WiFiTransport()
    if kind == "serial":
        return SerialTransport()
    raise ValueError(f"kind invalide : {kind}")


def _error_response(code: str, message: str, status_code: int) -> JSONResponse:
    """Renvoie une réponse d'erreur uniforme."""
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": code, "message": message}},
    )


def create_app(transport: Optional[object] = None, startup_error: Optional[str] = None) -> FastAPI:
    """Crée et configure l'application FastAPI.

    Args:
        transport: instance Transport (peut être NullTransport ; None = autonome auto en tests).
        startup_error: message d'erreur si le transport demandé a échoué à l'open().
    """
    from quoridor_engine import InvalidMoveError
    from webapp.transport import NullTransport

    if transport is None:
        transport = NullTransport()
        transport.open()

    app = FastAPI(title="Quoridor Demo")
    service = QuoridorService(transport=transport, startup_error=startup_error)
    app.state.service = service
    app.state.transport = transport

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(
            STATIC_DIR / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    @app.get("/api/state")
    def get_state():
        return service.to_dict()

    @app.post("/api/new-game")
    def post_new_game(payload: NewGamePayload):
        if payload.plateau_mode and not service._plateau_available_unlocked():
            return _error_response(
                "PLATEAU_UNAVAILABLE", "Plateau non détecté.", 400
            )
        service.new_game(
            mode=payload.mode,
            difficulty=payload.difficulty,
            plateau_mode=payload.plateau_mode,
        )
        return service.to_dict()

    @app.post("/api/move")
    def post_move(payload: MovePayload):
        move_dict = payload.model_dump()
        try:
            service.apply_user_move(move_dict)
        except InvalidMoveError as e:
            return _error_response(e.code.value, str(e), 400)
        return service.to_dict()

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

    from webapp.transport import TransportError

    @app.post("/api/transport/switch")
    def post_transport_switch(payload: TransportSwitchRequest):
        new_t = _make_transport_by_kind(payload.kind)
        try:
            service._plateau.switch_transport(new_t)
            service._startup_error = None
            return {
                "success": True,
                "description": service._plateau.transport.description,
                "error": None,
            }
        except TransportError as e:
            return {
                "success": False,
                "description": service._plateau.transport.description,
                "error": str(e),
            }

    @app.get("/api/status")
    def get_status():
        plateau_dict = service._plateau.status_dict()
        desc = plateau_dict["description"]
        if desc.startswith("wifi"):
            kind = "wifi"
        elif desc.startswith("serial"):
            kind = "serial"
        else:
            kind = "none"
        return {
            "client": {
                "polling_active": True,
                "polling_interval_ms": 500,
            },
            "transport": {
                "kind": kind,
                "description": desc,
                "alive": plateau_dict["alive"],
                "last_pong_at_iso": plateau_dict["last_pong_at_iso"],
                "last_pong_age_seconds": plateau_dict["last_pong_age_seconds"],
                "latency_avg_ms": plateau_dict["latency_avg_ms"],
                "startup_error": service._startup_error,
            },
            "plateau": {
                "homed": False,  # suivi du homing physique : hors scope phase 5
                "ready": plateau_dict["alive"],
            },
        }

    return app


def main() -> None:
    """Entrypoint CLI."""
    import uvicorn
    from webapp.transport import make_transport, TransportError, NullTransport

    transport = make_transport()
    startup_error: str | None = None
    try:
        transport.open()
    except TransportError as e:
        log.warning("Transport %s indisponible : %s", transport.description, e)
        startup_error = str(e)
        transport = NullTransport()
        transport.open()

    app = create_app(transport=transport, startup_error=startup_error)
    app.state.service.start_tick_thread()
    app.state.service._plateau.start_heartbeat()
    app.state.service._plateau.start_reconnect_watcher()

    log.info("Quoridor web app demarree sur http://0.0.0.0:8000 (transport=%s)",
             transport.description)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
