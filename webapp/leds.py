"""Sous-systeme LED : mapping engine <-> strip + rendu de GameState.

Le strip WS2812B physique forme un serpentin 6x6 sur le plateau, avec l'entree
DIN en bas-gauche. Les rangees physiques alternent : rangee 0 (bas) va de gauche
a droite, rangee 1 va de droite a gauche, etc.

L'engine Quoridor utilise sa propre convention : (row, col) avec row=0 en haut,
col=0 a gauche. Ce module fait la traduction.

Voir spec : docs/superpowers/specs/2026-05-21-leds-design.md
"""
from __future__ import annotations


def engine_to_strip_index(row: int, col: int) -> int:
    """Convertit une coordonnee engine (row, col) en index 0-35 sur le strip.

    Engine : row=0 en haut, row=5 en bas, col=0 a gauche, col=5 a droite.
    Strip  : LED 0 = entree DIN bas-gauche ; serpentin alterne par rangee physique.

    Args:
        row: ligne engine (0-5)
        col: colonne engine (0-5)

    Returns:
        Index 0-35 sur le strip serpentin.
    """
    row_phys = 5 - row              # inversion verticale engine -> physique
    if row_phys % 2 == 0:           # rangee paire : gauche -> droite
        return row_phys * 6 + col
    return row_phys * 6 + (5 - col)  # rangee impaire : droite -> gauche
