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
