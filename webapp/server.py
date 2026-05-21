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
)
from webapp.service import QuoridorService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


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

    log.info("Quoridor web app demarree sur http://0.0.0.0:8000 (transport=%s)",
             transport.description)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
