"""Tests des routes FastAPI (avec TestClient, pas de hardware)."""
import pytest
from fastapi.testclient import TestClient

from webapp.server import create_app


@pytest.fixture
def client():
    app = create_app(transport=None)
    return TestClient(app)


class TestRootRoute:
    def test_get_root_retourne_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "Quoridor" in r.text


class TestGetState:
    def test_get_state_initial(self, client):
        r = client.get("/api/state")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "waiting"
        assert data["players"] == {}
        assert data["plateau"]["available"] is False

    def test_get_state_apres_new_game(self, client):
        client.post(
            "/api/new-game",
            json={"mode": "human_vs_ai", "difficulty": "normal", "plateau_mode": False},
        )
        r = client.get("/api/state")
        data = r.json()
        assert data["status"] == "playing"
        assert data["current_player"] == "j1"


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
        assert r.json()["detail"]["code"]

    def test_pose_mur_horizontal(self, client):
        self._start(client)
        r = client.post(
            "/api/move",
            json={"type": "mur", "orientation": "h", "row": 4, "col": 2},
        )
        assert r.status_code == 200
        data = r.json()
        assert {"orientation": "h", "row": 4, "col": 2} in data["walls"]


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
        assert r.status_code == 422

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
