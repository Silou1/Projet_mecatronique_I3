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


from dataclasses import dataclass
from quoridor_engine.core import GameState, get_possible_pawn_moves, PLAYER_ONE, PLAYER_TWO


@dataclass(frozen=True)
class LedColor:
    """Couleur RGB d'une LED, composantes 0-255 (nominales avant attenuation firmware)."""
    r: int
    g: int
    b: int


# Palette (valeurs nominales, le firmware applique setBrightness(102) = 40%)
COLOR_OFF        = LedColor(0,   0,   0  )  # fond eteint
COLOR_PLAYER_ONE = LedColor(0,   0,   255)  # J1 humain : bleu
COLOR_PLAYER_TWO = LedColor(255, 0,   0  )  # J2 IA : rouge
COLOR_LEGAL_MOVE = LedColor(0,   64,  64 )  # coups legaux : cyan dim (P1 bonus)


@dataclass(frozen=True)
class RenderOptions:
    """Options de rendu (extensibles pour scope futur)."""
    show_legal_moves: bool = False


def render_state(state: GameState, opts: RenderOptions) -> list[LedColor]:
    """Convertit un GameState en frame complete de 36 couleurs.

    Fonction pure : sortie totalement determinee par les inputs, pas de side effect.

    Args:
        state: etat de la partie en cours
        opts: options de rendu (P0/P1 toggles)

    Returns:
        Liste de 36 LedColor, index = position sur le strip serpentin.
    """
    frame: list[LedColor] = [COLOR_OFF] * 36

    # P1 (bonus) : coups legaux peints EN PREMIER (ecrases par les pions ensuite)
    if opts.show_legal_moves:
        for row, col in get_possible_pawn_moves(state, state.current_player):
            frame[engine_to_strip_index(row, col)] = COLOR_LEGAL_MOVE

    # P0 : pions peints EN DERNIER pour ecraser tout coup legal au meme endroit
    r1, c1 = state.player_positions[PLAYER_ONE]
    r2, c2 = state.player_positions[PLAYER_TWO]
    frame[engine_to_strip_index(r1, c1)] = COLOR_PLAYER_ONE
    frame[engine_to_strip_index(r2, c2)] = COLOR_PLAYER_TWO

    return frame
