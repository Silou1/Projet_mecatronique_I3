"""Tests du QuoridorService."""
import time

import pytest

from webapp.service import QuoridorService
from quoridor_engine import InvalidMoveError


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
        service._turn_count = 7
        service.new_game(mode="human_vs_ai", difficulty="facile", plateau_mode=False)
        state = service.to_dict()
        assert state["turn_count"] == 0
        assert state["difficulty"] == "facile"


class TestApplyUserMoveDeplacement:
    def test_deplacement_valide_change_tour(self, service):
        service.new_game(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        service.apply_user_move({"type": "deplacement", "target": (4, 3)})
        state = service.to_dict()
        assert state["players"]["j1"]["position"] == [4, 3]
        assert state["current_player"] == "j2"
        assert state["turn_count"] == 1

    def test_deplacement_invalide_leve_erreur(self, service):
        service.new_game(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        with pytest.raises(InvalidMoveError):
            service.apply_user_move({"type": "deplacement", "target": (0, 0)})

    def test_deplacement_pendant_tour_ai_rejete(self, service):
        service.new_game(mode="human_vs_ai", difficulty="normal", plateau_mode=False)
        service.apply_user_move({"type": "deplacement", "target": (4, 3)})
        with pytest.raises(InvalidMoveError):
            service.apply_user_move({"type": "deplacement", "target": (1, 3)})

    def test_deplacement_en_mode_ai_vs_ai_rejete(self, service):
        service.new_game(mode="ai_vs_ai", difficulty="facile", plateau_mode=False)
        with pytest.raises(InvalidMoveError):
            service.apply_user_move({"type": "deplacement", "target": (4, 3)})


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
        assert state["wall_placement_mode"] is None


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
        assert state["difficulty"] == "difficile"
        assert state["speed"] == "rapide"
        assert state["mode"] == "human_vs_ai"


class TestTick:
    def test_tick_once_fait_jouer_ai_quand_son_tour(self, service):
        service.new_game(mode="human_vs_ai", difficulty="facile", plateau_mode=False)
        service.apply_user_move({"type": "deplacement", "target": (4, 3)})
        service._last_ai_move_at = 0.0
        played = service.tick_once()
        assert played is True
        state = service.to_dict()
        assert state["current_player"] == "j1"
        assert state["turn_count"] == 2

    def test_tick_once_no_op_si_tour_humain(self, service):
        service.new_game(mode="human_vs_ai", difficulty="facile", plateau_mode=False)
        played = service.tick_once()
        assert played is False

    def test_tick_once_no_op_si_paused(self, service):
        service.new_game(mode="ai_vs_ai", difficulty="facile", plateau_mode=False)
        service.pause()
        service._last_ai_move_at = 0.0
        played = service.tick_once()
        assert played is False

    def test_tick_respecte_delai(self, service):
        service.new_game(mode="ai_vs_ai", difficulty="facile", plateau_mode=False)
        service._last_ai_move_at = time.monotonic()
        played = service.tick_once()
        assert played is False
