"""Tests de la factory make_transport() pilotée par env var."""
from __future__ import annotations

import pytest

from webapp.transport import (
    make_transport, SerialTransport, WiFiTransport, NullTransport,
)


def test_make_transport_default_is_wifi(monkeypatch):
    monkeypatch.delenv("QUORIDOR_TRANSPORT", raising=False)
    t = make_transport()
    assert isinstance(t, WiFiTransport)


def test_make_transport_wifi_explicit(monkeypatch):
    monkeypatch.setenv("QUORIDOR_TRANSPORT", "wifi")
    t = make_transport()
    assert isinstance(t, WiFiTransport)


def test_make_transport_serial(monkeypatch):
    monkeypatch.setenv("QUORIDOR_TRANSPORT", "serial")
    t = make_transport()
    assert isinstance(t, SerialTransport)


def test_make_transport_none(monkeypatch):
    monkeypatch.setenv("QUORIDOR_TRANSPORT", "none")
    t = make_transport()
    assert isinstance(t, NullTransport)


def test_make_transport_invalid_value(monkeypatch):
    monkeypatch.setenv("QUORIDOR_TRANSPORT", "bluetooth")
    with pytest.raises(ValueError, match="QUORIDOR_TRANSPORT"):
        make_transport()


def test_make_transport_case_insensitive(monkeypatch):
    monkeypatch.setenv("QUORIDOR_TRANSPORT", "WiFi")
    t = make_transport()
    assert isinstance(t, WiFiTransport)


def test_make_transport_wifi_default_host_is_mdns(monkeypatch):
    """Sans QUORIDOR_WIFI_HOST, le defaut est quoridor.local (mDNS)."""
    monkeypatch.setenv("QUORIDOR_TRANSPORT", "wifi")
    monkeypatch.delenv("QUORIDOR_WIFI_HOST", raising=False)
    t = make_transport()
    assert isinstance(t, WiFiTransport)
    assert "quoridor.local" in t.description


def test_make_transport_wifi_host_override(monkeypatch):
    """QUORIDOR_WIFI_HOST override le defaut mDNS (utile si mDNS plante)."""
    monkeypatch.setenv("QUORIDOR_TRANSPORT", "wifi")
    monkeypatch.setenv("QUORIDOR_WIFI_HOST", "172.20.10.7")
    t = make_transport()
    assert isinstance(t, WiFiTransport)
    assert "172.20.10.7:3333" in t.description
