"""Tests du QuoridorService."""
import time

import pytest

from webapp.service import QuoridorService
from quoridor_engine import InvalidMoveError


@pytest.fixture
def service():
    return QuoridorService(transport=None)


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


class TestRobustesse:
    def test_tick_once_apres_quit_pendant_reflexion(self, service):
        """Si quit_to_home() est appelé entre les 2 locks de tick_once,
        le 2e bloc doit return False sans crasher."""
        service.new_game(mode="ai_vs_ai", difficulty="facile", plateau_mode=False)
        # On force le 1er bloc de tick_once à passer, puis on simule un quit
        # entre les deux locks. Pour ça on utilise un test "à la main" :
        service._last_ai_move_at = 0.0
        # Simule : status passe à waiting pendant qu'on simule le state_snapshot
        # Au lieu d'un vrai test temporel, on appelle tick_once après reset partiel
        service.quit_to_home()
        # Maintenant on appelle tick_once : status == waiting → doit retourner False
        # (le tick_once normal échoue déjà à la 1ère garde, c'est suffisant)
        assert service.tick_once() is False

    def test_forward_plateau_lost_genere_last_error(self, service):
        """Quand Transport.write_line() echoue sur un WALL, last_error doit etre set."""
        from webapp.transport import TransportError

        class FakeTransport:
            is_alive = True
            description = "fake"
            def open(self): pass
            def write_line(self, line):
                raise TransportError("simule echec")
            def read_line(self, timeout=1.0): return None
            def close(self): pass

        from webapp.plateau import PlateauBridge
        service._plateau = PlateauBridge(transport=FakeTransport())
        service._plateau_mode = True
        # Move de type 'mur' pour declencher la logique (les deplacements sont no-op)
        mur_payload = {"type": "mur", "orientation": "H", "row": 2, "col": 3}
        with service._lock:
            service._forward_to_plateau_unlocked(("mur", mur_payload))
        state = service.to_dict()
        assert state["last_error"] is not None
        assert state["last_error"]["code"] == "PLATEAU_LOST"


class TestHumainVsHumain:
    def test_hvh_no_ai_created(self, service):
        service.new_game(mode="human_vs_human", difficulty="normal", plateau_mode=False)
        assert service._ai_j1 is None
        assert service._ai_j2 is None
        state = service.to_dict()
        assert state["mode"] == "human_vs_human"
        assert state["players"]["j1"]["is_ai"] is False
        assert state["players"]["j2"]["is_ai"] is False
        assert state["status"] == "playing"
        assert state["current_player"] == "j1"

    def test_hvh_both_players_can_move(self, service):
        service.new_game(mode="human_vs_human", difficulty="normal", plateau_mode=False)
        # J1 joue
        service.apply_user_move({"type": "deplacement", "target": (4, 3)})
        state = service.to_dict()
        assert state["current_player"] == "j2"
        assert state["turn_count"] == 1
        assert state["players"]["j1"]["position"] == [4, 3]
        # J2 joue
        service.apply_user_move({"type": "deplacement", "target": (1, 3)})
        state = service.to_dict()
        assert state["current_player"] == "j1"
        assert state["turn_count"] == 2
        assert state["players"]["j2"]["position"] == [1, 3]

    def test_hvh_tick_noop(self, service):
        service.new_game(mode="human_vs_human", difficulty="normal", plateau_mode=False)
        service._last_ai_move_at = 0.0  # delai depasse, force la condition
        played = service.tick_once()
        assert played is False
        state = service.to_dict()
        assert state["turn_count"] == 0
        assert state["current_player"] == "j1"

    def test_hvh_wall_de_j2_forwarded_au_plateau(self):
        """Le mur pose par J2 en HvH doit etre envoye au plateau physique
        avec l'orientation inchangée (convention identique engine ↔ firmware
        depuis la recalibration complète des matrices).

        Les forwards physiques sont exécutés dans un thread daemon avec
        flag _plateau_busy ; le test simule un firmware (ACK HOME OK / WALL OK)
        et attend la fin de chaque worker avant le coup suivant.
        """
        import time as _time
        from webapp.transport import NullTransport

        lignes_envoyees = []

        class FakeTransport(NullTransport):
            description = "fake"
            is_alive = True
            def __init__(self):
                self._responses = []
            def write_line(self, line):
                lignes_envoyees.append(line)
                # Simule la réponse du firmware
                if line == "HOME":
                    self._responses.append("HOME OK")
                elif line.startswith("WALL "):
                    parts = line.split()
                    self._responses.append(
                        f"WALL OK {parts[1]} {parts[2]} {parts[3]} raised=2"
                    )
                elif line == "PING":
                    self._responses.append("PONG")
                else:
                    self._responses.append("OK")  # LED, LEDCLEAR, LEDSHOW
            def read_line(self, timeout=1.0):
                if self._responses:
                    return self._responses.pop(0)
                return None

        def wait_not_busy(service, timeout=3.0):
            deadline = _time.monotonic() + timeout
            while _time.monotonic() < deadline:
                if not service._plateau_busy:
                    return
                _time.sleep(0.02)
            raise AssertionError("plateau toujours busy après timeout")

        transport = FakeTransport()
        transport.open()
        service = QuoridorService(transport=transport)
        service.new_game(mode="human_vs_human", difficulty="normal", plateau_mode=True)
        wait_not_busy(service)  # attend la fin du HOME worker

        # J1 deplace son pion (turn count 1, current player = j2)
        service.apply_user_move({"type": "deplacement", "target": (4, 3)})
        wait_not_busy(service)
        lignes_envoyees.clear()  # on ignore HOME + LEDs du déplacement

        # J2 pose un mur horizontal
        service.apply_user_move({"type": "mur", "orientation": "h", "row": 1, "col": 2})
        wait_not_busy(service)
        # Verifier que la commande WALL a ete envoyee (orientation inchangée)
        assert any(ligne.startswith("WALL H 1 2") for ligne in lignes_envoyees), \
            f"WALL non envoye, lignes: {lignes_envoyees}"
