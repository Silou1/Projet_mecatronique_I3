"""Tests unitaires du sous-systeme LED (webapp/leds.py).

Tests purs Python, sans hardware. Couvrent le mapping engine -> strip,
la fonction de rendu (avec phase de clignotement), et la classe LedRenderer
(avec mock du PlateauBridge).
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
    LedColor, RenderOptions, render_state, render_animation_frame,
    COLOR_OFF, COLOR_FREE, COLOR_PLAYER_ONE, COLOR_PLAYER_TWO,
    COLOR_PLAYER_ONE_DIM, COLOR_PLAYER_TWO_DIM,
)


class TestRenderState:
    """Conversion GameState -> liste de 36 LedColor (frame)."""

    def test_partie_initiale_j1_courant(self):
        """Au depart, J1 est courant : LED 3 bleu plein, LED 32 rouge attenue, fond blanc doux."""
        state = create_new_game()
        assert state.current_player == PLAYER_ONE
        frame = render_state(state, RenderOptions())

        assert len(frame) == 36
        assert frame[3] == COLOR_PLAYER_ONE        # J1 courant : plein
        assert frame[32] == COLOR_PLAYER_TWO_DIM   # J2 non-courant : attenue
        for idx, color in enumerate(frame):
            if idx in (3, 32):
                continue
            assert color == COLOR_FREE, f"LED {idx} devrait etre blanc doux"

    def test_apres_coup_j1_devient_j2_courant(self):
        """Apres un coup de J1, current_player passe a J2 -> J1 devient attenue, J2 plein."""
        state = create_new_game()
        state = move_pawn(state, PLAYER_ONE, (4, 3))
        assert state.current_player == PLAYER_TWO

        frame = render_state(state, RenderOptions())
        assert frame[3] == COLOR_FREE                 # ancienne case J1 liberee
        assert frame[8] == COLOR_PLAYER_ONE_DIM       # J1 non-courant : attenue
        assert frame[32] == COLOR_PLAYER_TWO          # J2 courant : plein

    def test_palette_restreinte(self):
        """Le rendu n'utilise que 5 couleurs : free, J1 plein/dim, J2 plein/dim."""
        state = create_new_game()
        frame = render_state(state, RenderOptions())
        palette_attendue = {
            COLOR_FREE,
            COLOR_PLAYER_ONE, COLOR_PLAYER_ONE_DIM,
            COLOR_PLAYER_TWO, COLOR_PLAYER_TWO_DIM,
        }
        assert set(frame).issubset(palette_attendue)


class TestRenderAnimationFrame:
    """Animation 'onde concentrique depuis le centre' pour le mode victory."""

    BLUE = LedColor(0, 0, 255)
    BLUE_DIM = LedColor(0, 0, 63)  # 255 // 4 = 63

    # Indices strip des 4 cases centrales (anneau 0) : (2,2)(2,3)(3,2)(3,3)
    RING_0_INDICES = {14, 15, 20, 21}

    def test_step_0_seul_anneau_centre_allume(self):
        """Step 0 : les 4 LEDs centrales (anneau 0) sont a pleine couleur, reste eteint."""
        frame = render_animation_frame(0, self.BLUE)
        for idx in range(36):
            if idx in self.RING_0_INDICES:
                assert frame[idx] == self.BLUE, f"LED {idx} (anneau 0) devrait etre bleu plein"
            else:
                assert frame[idx] == COLOR_OFF, f"LED {idx} devrait etre eteinte"

    def test_step_1_anneau_1_plein_anneau_0_dim(self):
        """Step 1 : anneau 1 a pleine couleur (12 LEDs), anneau 0 attenue (4 LEDs)."""
        frame = render_animation_frame(1, self.BLUE)
        # Anneau 0 doit etre en dim
        for idx in self.RING_0_INDICES:
            assert frame[idx] == self.BLUE_DIM
        # On compte les LEDs a pleine couleur : doit etre 12 (anneau 1)
        nb_plein = sum(1 for c in frame if c == self.BLUE)
        assert nb_plein == 12

    def test_step_2_anneau_2_plein_anneau_1_dim(self):
        """Step 2 : anneau 2 plein (20 LEDs bord), anneau 1 dim (12), anneau 0 OFF."""
        frame = render_animation_frame(2, self.BLUE)
        for idx in self.RING_0_INDICES:
            assert frame[idx] == COLOR_OFF, f"LED {idx} (anneau 0) doit etre OFF"
        nb_plein = sum(1 for c in frame if c == self.BLUE)
        nb_dim = sum(1 for c in frame if c == self.BLUE_DIM)
        assert nb_plein == 20
        assert nb_dim == 12

    def test_step_3_tout_eteint(self):
        """Step 3 : pause avant la boucle suivante, tout eteint."""
        frame = render_animation_frame(3, self.BLUE)
        assert frame == [COLOR_OFF] * 36

    def test_cycle_boucle_step_4_revient_au_centre(self):
        """Le cycle est de 4 etapes : step 4 == step 0."""
        f0 = render_animation_frame(0, self.BLUE)
        f4 = render_animation_frame(4, self.BLUE)
        assert f0 == f4

    def test_couleur_rouge_appliquee(self):
        """L'animation utilise la couleur fournie (rouge ici)."""
        red = LedColor(255, 0, 0)
        red_dim = LedColor(63, 0, 0)
        frame = render_animation_frame(1, red)
        for idx in self.RING_0_INDICES:
            assert frame[idx] == red_dim


from unittest.mock import MagicMock

from webapp.leds import LedRenderer


class TestLedRenderer:
    """LedRenderer : envoi diff vers PlateauBridge + reconnexion + animation."""

    def _make_bridge(self, available: bool = True):
        """Cree un mock de PlateauBridge avec send_command_await mockable."""
        bridge = MagicMock()
        bridge.available = available
        bridge.send_command_await = MagicMock(return_value="OK")
        return bridge

    def _lines_sent(self, bridge) -> list[str]:
        """Recupere la sequence de lignes envoyees via send_command_await."""
        return [call.args[0] for call in bridge.send_command_await.call_args_list]

    def test_update_premier_appel_pousse_full_frame(self):
        """Premier update : LEDCLEAR + toutes les LEDs allumees (blanc + pions) + LEDSHOW."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)

        lines = self._lines_sent(bridge)
        assert lines[0] == "LEDCLEAR"
        assert lines[-1] == "LEDSHOW"
        assert "LED 3 0 0 255" in lines       # J1 courant : bleu plein
        assert "LED 32 60 0 0" in lines       # J2 non-courant : rouge dim
        # 34 cases blanches doivent etre envoyees
        whites = [l for l in lines if l.endswith("20 20 20") and l.startswith("LED ")]
        assert len(whites) == 34

    def test_update_deuxieme_appel_envoie_diff(self):
        """Diff apres mouvement J1 (5,3)->(4,3) : LED 3 redevient blanche, LED 8 devient bleu dim, LED 32 devient rouge plein."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        bridge.send_command_await.reset_mock()

        state = move_pawn(state, PLAYER_ONE, (4, 3))
        renderer.update(state)

        lines = self._lines_sent(bridge)
        assert "LED 3 20 20 20" in lines      # ancienne case J1 redevient blanche
        assert "LED 8 0 0 60" in lines        # J1 nouveau, non-courant : bleu dim
        assert "LED 32 255 0 0" in lines      # J2 devient courant : rouge plein
        assert lines[-1] == "LEDSHOW"
        assert "LEDCLEAR" not in lines

    def test_update_sans_changement_n_envoie_rien(self):
        """Si le frame est identique au precedent, aucune commande n'est envoyee."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        bridge.send_command_await.reset_mock()

        renderer.update(state)
        assert bridge.send_command_await.call_count == 0

    def test_update_no_op_si_bridge_indisponible(self):
        """Si bridge.available est False, update est un no-op silencieux."""
        bridge = self._make_bridge(available=False)
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        assert bridge.send_command_await.call_count == 0

    def test_clear_eteint_tout_et_reset(self):
        """clear() envoie LEDCLEAR+LEDSHOW et reset _last_frame en OFF total."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        bridge.send_command_await.reset_mock()

        renderer.clear()

        lines = self._lines_sent(bridge)
        assert lines == ["LEDCLEAR", "LEDSHOW"]

    def test_set_brightness_envoie_ledbright(self):
        """set_brightness pousse LEDBRIGHT <v>."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        renderer.set_brightness(153)

        lines = self._lines_sent(bridge)
        assert lines == ["LEDBRIGHT 153"]

    def test_push_animation_frame_step_0_centre(self):
        """push_animation_frame(0, bleu) : allume les 4 LEDs centrales en bleu."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        renderer.push_animation_frame(0, LedColor(0, 0, 255))

        lines = self._lines_sent(bridge)
        assert lines[0] == "LEDCLEAR"
        assert lines[-1] == "LEDSHOW"
        # 4 LEDs centrales doivent etre envoyees en bleu
        bleus = [l for l in lines if l.endswith("0 0 255")]
        assert len(bleus) == 4

    def test_push_animation_frame_no_op_bridge_indisponible(self):
        """push_animation_frame no-op si bridge.available == False."""
        bridge = self._make_bridge(available=False)
        renderer = LedRenderer(bridge)

        renderer.push_animation_frame(0, LedColor(255, 0, 0))
        assert bridge.send_command_await.call_count == 0

    def test_on_reconnect_repush_full_frame(self):
        """on_reconnect : re-envoie le dernier frame en full (firmware a reset)."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        bridge.send_command_await.reset_mock()

        renderer.on_reconnect()

        lines = self._lines_sent(bridge)
        assert lines[0] == "LEDCLEAR"
        assert lines[-1] == "LEDSHOW"
        assert "LED 3 0 0 255" in lines       # J1 courant : bleu plein
        assert "LED 32 60 0 0" in lines       # J2 non-courant : rouge dim

    def test_on_reconnect_no_op_si_pas_de_frame(self):
        """on_reconnect sans update prealable : rien a faire."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        renderer.on_reconnect()
        assert bridge.send_command_await.call_count == 0
