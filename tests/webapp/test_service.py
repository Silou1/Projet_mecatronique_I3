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
