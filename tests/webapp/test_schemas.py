"""Tests des schémas Pydantic de la web app."""
import pytest
from pydantic import ValidationError

from webapp.schemas import (
    NewGamePayload,
    MovePayload,
    SpeedPayload,
    WallModePayload,
    StateResponse,
)


class TestNewGamePayload:
    def test_payload_valide(self):
        p = NewGamePayload(mode="human_vs_ai", difficulty="normal")
        assert p.mode == "human_vs_ai"
        assert p.difficulty == "normal"

    def test_mode_invalide_rejete(self):
        with pytest.raises(ValidationError):
            NewGamePayload(mode="duel", difficulty="normal")

    def test_difficulte_invalide_rejetee(self):
        with pytest.raises(ValidationError):
            NewGamePayload(mode="human_vs_ai", difficulty="extreme")

    def test_payload_accepte_human_vs_human(self):
        p = NewGamePayload(mode="human_vs_human", difficulty="normal")
        assert p.mode == "human_vs_human"


class TestMovePayload:
    def test_deplacement_valide(self):
        p = MovePayload(type="deplacement", target=(3, 2))
        assert p.type == "deplacement"
        assert p.target == (3, 2)

    def test_mur_valide(self):
        p = MovePayload(type="mur", orientation="h", row=2, col=3)
        assert p.type == "mur"
        assert p.orientation == "h"

    def test_type_invalide_rejete(self):
        with pytest.raises(ValidationError):
            MovePayload(type="rotation")


class TestSpeedPayload:
    def test_vitesse_valide(self):
        assert SpeedPayload(speed="lent").speed == "lent"
        assert SpeedPayload(speed="rapide").speed == "rapide"

    def test_vitesse_invalide_rejetee(self):
        with pytest.raises(ValidationError):
            SpeedPayload(speed="ultraflash")


class TestWallModePayload:
    def test_active_horizontal(self):
        assert WallModePayload(orientation="h").orientation == "h"

    def test_desactivation_avec_null(self):
        assert WallModePayload(orientation=None).orientation is None
