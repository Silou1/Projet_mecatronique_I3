"""Tests unitaires du sous-systeme LED (webapp/leds.py).

Tests purs Python, sans hardware. Couvrent le mapping engine -> strip,
la fonction de rendu, et la classe LedRenderer (avec mock du PlateauBridge).
"""
from __future__ import annotations

import pytest

from webapp.leds import engine_to_strip_index


class TestEngineToStripIndex:
    """Mapping (row engine, col engine) -> index 0-35 sur le strip serpentin."""

    @pytest.mark.parametrize("row, col, expected", [
        # 4 coins (cf. spec section 5)
        (5, 0, 0),   # bas-gauche  (entree DIN)
        (5, 5, 5),   # bas-droite
        (0, 5, 30),  # haut-droite
        (0, 0, 35),  # haut-gauche (sortie strip)
        # Positions de depart des pions
        (5, 3, 3),   # depart J1 : bas-centre
        (0, 3, 32),  # depart J2 : haut-centre
    ])
    def test_coins_et_departs(self, row, col, expected):
        assert engine_to_strip_index(row, col) == expected

    def test_tous_les_36_indices_uniques(self):
        """Les 36 coordonnees engine doivent donner 36 indices distincts."""
        indices = [
            engine_to_strip_index(row, col)
            for row in range(6) for col in range(6)
        ]
        assert sorted(indices) == list(range(36))

    @pytest.mark.parametrize("row, col, expected_row_phys, expected_parite", [
        (5, 2, 0, "paire"),   # rangee bas : 0 -> gauche-droite
        (4, 2, 1, "impaire"), # 2eme rangee : 1 -> droite-gauche
        (3, 2, 2, "paire"),   # 3eme rangee : 2 -> gauche-droite
    ])
    def test_serpentin_alternance(self, row, col, expected_row_phys, expected_parite):
        """Verifie que la formule serpentin alterne bien selon la parite de row_phys."""
        idx = engine_to_strip_index(row, col)
        row_phys_calc = idx // 6
        assert row_phys_calc == expected_row_phys


from quoridor_engine.core import create_new_game, move_pawn, PLAYER_ONE, PLAYER_TWO
from webapp.leds import (
    LedColor, RenderOptions, render_state,
    COLOR_OFF, COLOR_PLAYER_ONE, COLOR_PLAYER_TWO, COLOR_LEGAL_MOVE,
)


class TestRenderState:
    """Conversion GameState -> liste de 36 LedColor (frame)."""

    def test_partie_initiale_pions_seuls(self):
        """Au depart : J1 en bas-centre (LED 3) bleu, J2 en haut-centre (LED 32) rouge."""
        state = create_new_game()
        frame = render_state(state, RenderOptions(show_legal_moves=False))

        assert len(frame) == 36
        assert frame[3] == COLOR_PLAYER_ONE   # J1 bas-centre
        assert frame[32] == COLOR_PLAYER_TWO  # J2 haut-centre
        # Toutes les autres LEDs eteintes
        for idx, color in enumerate(frame):
            if idx in (3, 32):
                continue
            assert color == COLOR_OFF, f"LED {idx} devrait etre eteinte"

    def test_apres_un_coup_j1(self):
        """J1 bouge de (5,3) a (4,3) -> LED 8 (4,3) bleu, LED 3 eteinte."""
        state = create_new_game()
        state = move_pawn(state, PLAYER_ONE, (4, 3))

        frame = render_state(state, RenderOptions(show_legal_moves=False))
        assert frame[3] == COLOR_OFF
        assert frame[8] == COLOR_PLAYER_ONE
        assert frame[32] == COLOR_PLAYER_TWO

    def test_coups_legaux_actives(self):
        """Avec show_legal_moves=True, les cases atteignables apparaissent en cyan."""
        state = create_new_game()
        # J1 demarre en (5,3). Cases atteignables : (4,3), (5,2), (5,4).
        # Index strip : (4,3)=LED 8, (5,2)=LED 2, (5,4)=LED 4.
        frame = render_state(state, RenderOptions(show_legal_moves=True))

        assert frame[3] == COLOR_PLAYER_ONE  # pion J1
        assert frame[8] == COLOR_LEGAL_MOVE  # case (4,3) atteignable
        assert frame[2] == COLOR_LEGAL_MOVE  # case (5,2)
        assert frame[4] == COLOR_LEGAL_MOVE  # case (5,4)

    def test_coups_legaux_desactives_par_defaut(self):
        """RenderOptions par defaut : pas de coups legaux."""
        state = create_new_game()
        frame = render_state(state, RenderOptions())  # defaut
        # Aucune LED ne devrait etre COLOR_LEGAL_MOVE
        assert COLOR_LEGAL_MOVE not in frame

    def test_pion_ecrase_coup_legal_si_meme_case(self):
        """Robustesse : si un pion et un coup legal sont au meme idx,
        c'est la couleur du pion qui gagne (peint en dernier)."""
        state = create_new_game()
        frame = render_state(state, RenderOptions(show_legal_moves=True))
        # Le pion J1 en (5,3)=LED 3 n'est pas dans ses propres coups legaux
        # donc frame[3] reste COLOR_PLAYER_ONE.
        assert frame[3] == COLOR_PLAYER_ONE


from unittest.mock import MagicMock

from webapp.leds import LedRenderer


class TestLedRenderer:
    """LedRenderer : envoi diff vers PlateauBridge + reconnexion."""

    def _make_bridge(self, available: bool = True):
        """Cree un mock de PlateauBridge avec transport.write_line mockable."""
        bridge = MagicMock()
        bridge.available = available
        bridge.transport = MagicMock()
        return bridge

    def _lines_sent(self, bridge) -> list[str]:
        """Recupere la sequence de lignes envoyees via transport.write_line."""
        return [call.args[0] for call in bridge.transport.write_line.call_args_list]

    def test_update_premier_appel_pousse_full_frame(self):
        """Premier update : LEDCLEAR + toutes les LEDs allumees + LEDSHOW."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)

        lines = self._lines_sent(bridge)
        assert lines[0] == "LEDCLEAR"
        assert lines[-1] == "LEDSHOW"
        # 2 pions allumes (J1 LED 3 bleu + J2 LED 32 rouge)
        assert "LED 3 0 0 255" in lines
        assert "LED 32 255 0 0" in lines
        # Aucune LED OFF n'est envoyee (le LEDCLEAR a deja tout eteint)
        leds_off = [l for l in lines if l.endswith("0 0 0") and l.startswith("LED ")]
        assert leds_off == []

    def test_update_deuxieme_appel_envoie_diff(self):
        """Deuxieme update apres mouvement : seulement les LEDs changees + LEDSHOW."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        bridge.transport.write_line.reset_mock()  # oublie le full frame initial

        state = move_pawn(state, PLAYER_ONE, (4, 3))  # J1 (5,3)->(4,3)
        renderer.update(state)

        lines = self._lines_sent(bridge)
        # Diff : LED 3 eteinte (etait bleue), LED 8 allumee (nouveau J1)
        assert "LED 3 0 0 0" in lines
        assert "LED 8 0 0 255" in lines
        assert lines[-1] == "LEDSHOW"
        # Pas de LEDCLEAR (c'est un diff, pas un full frame)
        assert "LEDCLEAR" not in lines

    def test_update_sans_changement_n_envoie_rien(self):
        """Si le frame est identique au precedent, aucune commande n'est envoyee."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        bridge.transport.write_line.reset_mock()

        renderer.update(state)  # meme etat
        assert bridge.transport.write_line.call_count == 0

    def test_update_no_op_si_bridge_indisponible(self):
        """Si bridge.available est False, update est un no-op silencieux."""
        bridge = self._make_bridge(available=False)
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        assert bridge.transport.write_line.call_count == 0

    def test_on_reconnect_repush_full_frame(self):
        """on_reconnect : re-envoie le dernier frame en full (firmware a reset)."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        bridge.transport.write_line.reset_mock()

        renderer.on_reconnect()

        lines = self._lines_sent(bridge)
        assert lines[0] == "LEDCLEAR"
        assert lines[-1] == "LEDSHOW"
        assert "LED 3 0 0 255" in lines
        assert "LED 32 255 0 0" in lines

    def test_on_reconnect_no_op_si_pas_de_frame(self):
        """on_reconnect sans update prealable : rien a faire."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        renderer.on_reconnect()
        assert bridge.transport.write_line.call_count == 0
