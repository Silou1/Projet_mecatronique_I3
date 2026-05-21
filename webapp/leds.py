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


import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webapp.plateau import PlateauBridge

log = logging.getLogger(__name__)


class LedRenderer:
    """Maintient l'etat des LEDs et envoie les diffs au firmware via PlateauBridge.

    Le rendu est declenche manuellement via update(state) apres chaque mutation
    de GameState. La classe garde le dernier frame en memoire et ne pousse que
    les LEDs qui ont change (diff). En cas de reconnexion du bridge (firmware
    reboote), on_reconnect() force un re-push complet.
    """

    def __init__(self, bridge: "PlateauBridge"):
        self._bridge = bridge
        self._last_frame: list[LedColor] | None = None
        self._options = RenderOptions(show_legal_moves=False)

    def set_options(self, options: RenderOptions) -> None:
        """Modifie les options de rendu (toggle P1 par ex). Force un re-render."""
        self._options = options
        self._last_frame = None  # force full frame au prochain update

    def update(self, state: GameState) -> None:
        """Calcule le nouveau frame et envoie le diff au firmware.

        No-op silencieux si le bridge n'est pas disponible (mode autonome ou
        ESP32 hors ligne).
        """
        if not self._bridge.available:
            return
        new_frame = render_state(state, self._options)
        if self._last_frame is None:
            self._send_full_frame(new_frame)
        else:
            self._send_diff(self._last_frame, new_frame)
        self._last_frame = new_frame

    def on_reconnect(self) -> None:
        """A appeler quand le bridge recupere la connexion apres coupure.

        Le firmware a reboote, son buffer LED est a 0. On re-pousse le dernier
        frame connu pour resynchroniser.
        """
        if self._last_frame is not None:
            self._send_full_frame(self._last_frame)

    def _send_full_frame(self, frame: list[LedColor]) -> None:
        self._send_line("LEDCLEAR")
        for idx, color in enumerate(frame):
            if color != COLOR_OFF:
                self._send_line(f"LED {idx} {color.r} {color.g} {color.b}")
        self._send_line("LEDSHOW")

    def _send_diff(self, old: list[LedColor], new: list[LedColor]) -> None:
        changed = [(idx, c) for idx, (o, c) in enumerate(zip(old, new)) if o != c]
        if not changed:
            return  # rien a faire, pas de LEDSHOW non plus
        for idx, color in changed:
            self._send_line(f"LED {idx} {color.r} {color.g} {color.b}")
        self._send_line("LEDSHOW")

    def _send_line(self, line: str) -> None:
        """Envoi best-effort. Toute exception est avalee silencieusement (cf.
        pattern de _forward_to_plateau_unlocked dans service.py)."""
        try:
            self._bridge.transport.write_line(line)
        except Exception as e:  # noqa: BLE001
            log.warning("LED forward echoue (%s)", e)
