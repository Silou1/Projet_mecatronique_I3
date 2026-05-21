"""Tests de l'interface abstraite Transport."""
from __future__ import annotations

import pytest

from webapp.transport import Transport, TransportError


def test_transport_is_abstract():
    """Transport ne peut pas être instancié directement."""
    with pytest.raises(TypeError):
        Transport()  # type: ignore[abstract]


def test_transport_error_is_exception():
    """TransportError est une Exception standard."""
    err = TransportError("test")
    assert isinstance(err, Exception)
    assert str(err) == "test"
