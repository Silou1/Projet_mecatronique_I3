"""Sous-systeme LED : mapping engine <-> strip + rendu de GameState.

Le strip WS2812B physique forme un serpentin 6x6 sur le plateau, avec l'entree
DIN en bas-gauche. Les rangees physiques alternent : rangee 0 (bas) va de gauche
a droite, rangee 1 va de droite a gauche, etc.

L'engine Quoridor utilise sa propre convention : (row, col) avec row=0 en haut,
col=0 a gauche. Ce module fait la traduction.

Comportement visuel en partie :
- Cases libres : blanc tres doux (COLOR_FREE).
- Pion J1 : bleu (COLOR_PLAYER_ONE).
- Pion J2 : rouge (COLOR_PLAYER_TWO).
- Pion du joueur courant : clignote (alterne entre couleur pleine et COLOR_FREE,
  toggle declenche par LedRenderer.tick() depuis un thread externe a 1 Hz).
- Luminosite globale poussee a 60% pendant la partie via LEDBRIGHT 153.

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


def _ring_of(row: int, col: int) -> int:
    """Index d'anneau concentrique de la case (row, col) autour du centre virtuel.

    Plateau 6x6, centre virtuel (2.5, 2.5). Distance Chebyshev :
      ring 0 = 4 cases centrales  (2,2)(2,3)(3,2)(3,3)
      ring 1 = 12 cases du cadre intermediaire
      ring 2 = 20 cases du bord
    """
    return int(max(abs(2 * row - 5), abs(2 * col - 5)) / 2)


# Table de lookup ring[strip_idx] -> 0|1|2, pre-calculee une fois.
_RING_OF_STRIP_IDX: list[int] = [0] * 36
for _r in range(6):
    for _c in range(6):
        _RING_OF_STRIP_IDX[engine_to_strip_index(_r, _c)] = _ring_of(_r, _c)


from dataclasses import dataclass
from quoridor_engine.core import GameState, PLAYER_ONE, PLAYER_TWO


@dataclass(frozen=True)
class LedColor:
    """Couleur RGB d'une LED, composantes 0-255 (nominales avant attenuation firmware)."""
    r: int
    g: int
    b: int


# Palette nominale. Le firmware applique setBrightness ; en partie on pousse a
# 153 (60%), hors partie on reste a 102 (40%).
# Pas de clignotement : la canal serie est monopolise par les pulses moteurs
# pendant un WALL, le clignotement timeouterait. A la place, on differencie le
# joueur courant par contraste de luminosite.
COLOR_OFF        = LedColor(0,   0,   0  )  # extinction complete (hors partie / clear)
COLOR_FREE       = LedColor(20,  20,  20 )  # blanc tres tres doux : cases libres
COLOR_PLAYER_ONE = LedColor(0,   0,   255)  # J1 courant : bleu plein
COLOR_PLAYER_TWO = LedColor(255, 0,   0  )  # J2 courant : rouge plein
COLOR_PLAYER_ONE_DIM = LedColor(0, 0, 60)   # J1 non-courant : bleu attenue
COLOR_PLAYER_TWO_DIM = LedColor(60, 0, 0)   # J2 non-courant : rouge attenue


# Luminosite globale poussee par le service au demarrage de partie.
BRIGHTNESS_GAME = 153  # ~60% : le pion en pleine couleur ressort vraiment
BRIGHTNESS_IDLE = 102  # ~40% : valeur de repos cote firmware (cf. setup())


@dataclass(frozen=True)
class RenderOptions:
    """Options de rendu. Conserve pour extension future."""
    pass


def render_state(state: GameState, opts: RenderOptions) -> list[LedColor]:
    """Convertit un GameState en frame complete de 36 couleurs.

    Fonction pure. Le joueur courant est mis en pleine couleur, l'autre en
    couleur attenuee, le fond en blanc tres doux. Contraste de luminosite a
    la place du clignotement (incompatible avec les pulses moteurs).
    """
    frame: list[LedColor] = [COLOR_FREE] * 36

    r1, c1 = state.player_positions[PLAYER_ONE]
    r2, c2 = state.player_positions[PLAYER_TWO]
    idx1 = engine_to_strip_index(r1, c1)
    idx2 = engine_to_strip_index(r2, c2)

    current = state.current_player
    frame[idx1] = COLOR_PLAYER_ONE if current == PLAYER_ONE else COLOR_PLAYER_ONE_DIM
    frame[idx2] = COLOR_PLAYER_TWO if current == PLAYER_TWO else COLOR_PLAYER_TWO_DIM

    return frame


def render_animation_frame(step: int, color: LedColor) -> list[LedColor]:
    """Frame d'animation "onde concentrique depuis le centre" (mode victory).

    Cycle de 4 etapes (step % 4), 250 ms par etape -> 1 s par cycle :
      0 : anneau 0 a pleine couleur, reste eteint
      1 : anneau 1 plein, anneau 0 attenue (1/4 intensite)
      2 : anneau 2 plein, anneau 1 attenue
      3 : tout eteint (pause avant boucle suivante)

    Fonction pure.
    """
    phase = step % 4
    if phase == 3:
        return [COLOR_OFF] * 36
    full_ring = phase
    dim_ring = phase - 1  # -1 = aucun en dim (phase 0)
    dim = LedColor(color.r // 4, color.g // 4, color.b // 4)
    frame: list[LedColor] = [COLOR_OFF] * 36
    for idx in range(36):
        ring = _RING_OF_STRIP_IDX[idx]
        if ring == full_ring:
            frame[idx] = color
        elif ring == dim_ring:
            frame[idx] = dim
    return frame


import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webapp.plateau import PlateauBridge

log = logging.getLogger(__name__)


class LedRenderer:
    """Maintient l'etat des LEDs et envoie les diffs au firmware via PlateauBridge.

    Trois sources d'updates concurrentes (toutes thread-safe via _push_lock) :
      - update(state)   : mutation logique (coup joue, HOME termine).
      - tick(state)     : flip de phase pour l'animation de clignotement (1 Hz).
      - clear()         : extinction totale (reset partie).
      - on_reconnect()  : firmware redemarre, re-push de la derniere frame.
    """

    def __init__(self, bridge: "PlateauBridge"):
        self._bridge = bridge
        self._last_frame: list[LedColor] | None = None
        self._options = RenderOptions()
        self._push_lock = threading.Lock()

    def set_options(self, options: RenderOptions) -> None:
        """Modifie les options de rendu. Force un re-render."""
        with self._push_lock:
            self._options = options
            self._last_frame = None

    def update(self, state: GameState) -> None:
        """Calcule le frame et envoie le diff au firmware.

        No-op silencieux si le bridge n'est pas disponible.
        """
        if not self._bridge.available:
            return
        with self._push_lock:
            new_frame = render_state(state, self._options)
            self._push_frame_unlocked(new_frame)

    def clear(self) -> None:
        """Eteint toutes les LEDs (frame OFF totale). Pour reset_partie."""
        if not self._bridge.available:
            return
        with self._push_lock:
            self._send_line("LEDCLEAR")
            self._send_line("LEDSHOW")
            self._last_frame = [COLOR_OFF] * 36

    def fill_idle_white(self) -> None:
        """Affiche un blanc doux uniforme sur les 36 LEDs.

        Sert au reset_partie (au lieu du clear total) : visuel "plateau en
        veille" plutot que noir, transition plus douce entre 2 parties.
        """
        if not self._bridge.available:
            return
        with self._push_lock:
            new_frame = [COLOR_FREE] * 36
            self._push_frame_unlocked(new_frame)

    def push_animation_frame(self, step: int, color: LedColor) -> None:
        """Push une frame de l'animation 'onde depuis le centre' (mode victory).

        L'appelant gere le step (compteur incremental) et la couleur. No-op si
        le bridge n'est pas disponible.
        """
        if not self._bridge.available:
            return
        with self._push_lock:
            new_frame = render_animation_frame(step, color)
            self._push_frame_unlocked(new_frame)

    def set_brightness(self, value: int) -> None:
        """Envoie LEDBRIGHT <value> au firmware. value dans [0..255]."""
        if not self._bridge.available:
            return
        with self._push_lock:
            self._send_line(f"LEDBRIGHT {value}")

    def on_reconnect(self) -> None:
        """A appeler quand le bridge recupere la connexion apres coupure.

        Le firmware a reboote, son buffer LED est a 0. On re-pousse le dernier
        frame connu pour resynchroniser.
        """
        with self._push_lock:
            if self._last_frame is None:
                return
            self._send_full_frame(self._last_frame)

    def _push_frame_unlocked(self, new_frame: list[LedColor]) -> None:
        """Send full ou diff selon l'etat. _push_lock doit etre tenu."""
        if self._last_frame is None:
            self._send_full_frame(new_frame)
        else:
            self._send_diff(self._last_frame, new_frame)
        self._last_frame = new_frame

    def _send_full_frame(self, frame: list[LedColor]) -> None:
        self._send_line("LEDCLEAR")
        for idx, color in enumerate(frame):
            if color != COLOR_OFF:
                self._send_line(f"LED {idx} {color.r} {color.g} {color.b}")
        self._send_line("LEDSHOW")

    def _send_diff(self, old: list[LedColor], new: list[LedColor]) -> None:
        changed = [(idx, c) for idx, (o, c) in enumerate(zip(old, new)) if o != c]
        if not changed:
            return
        for idx, color in changed:
            self._send_line(f"LED {idx} {color.r} {color.g} {color.b}")
        self._send_line("LEDSHOW")

    def _send_line(self, line: str) -> None:
        """Envoi best-effort, sérialisé via send_command_await (lock TX + drain).

        Le firmware répond `OK` ou `ERR ...` à chaque commande LED. Passe par
        send_command_await pour drainer d'éventuels verbeux résiduels et pour
        déclencher mark_alive sur chaque round-trip réussi (renforce la
        stabilité du heartbeat USB).
        """
        try:
            self._bridge.send_command_await(
                line, accept_prefixes=("OK", "ERR"), timeout=2.0,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("LED forward echoue (%s)", e)
