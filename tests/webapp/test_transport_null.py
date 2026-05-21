"""Tests de NullTransport (mode autonome explicite)."""
from __future__ import annotations

import pytest

from webapp.transport import NullTransport, TransportError


def test_null_transport_open_is_noop():
    t = NullTransport()
    t.open()  # ne doit pas lever


def test_null_transport_write_raises():
    t = NullTransport()
    t.open()
    with pytest.raises(TransportError):
        t.write_line("PING")


def test_null_transport_read_returns_none():
    t = NullTransport()
    t.open()
    assert t.read_line() is None


def test_null_transport_close_is_noop():
    t = NullTransport()
    t.open()
    t.close()
    t.close()  # idempotent


def test_null_transport_is_alive_false():
    t = NullTransport()
    assert t.is_alive is False


def test_null_transport_description():
    t = NullTransport()
    assert t.description == "none (mode autonome)"
