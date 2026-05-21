"""Tests des schémas Pydantic pour /api/status et /api/transport/switch."""
from __future__ import annotations

import pytest

from webapp.schemas import (
    StatusResponse, ClientStatusInfo, TransportStatusInfo, PlateauStatusInfo,
    TransportSwitchRequest, TransportSwitchResponse,
)


def test_status_response_minimal():
    s = StatusResponse(
        client=ClientStatusInfo(polling_active=True, polling_interval_ms=500),
        transport=TransportStatusInfo(
            kind="wifi",
            description="wifi 192.168.4.1:3333",
            alive=True,
            last_pong_at_iso=None,
            last_pong_age_seconds=None,
            latency_avg_ms=None,
            startup_error=None,
        ),
        plateau=PlateauStatusInfo(homed=False, ready=False),
    )
    assert s.transport.kind == "wifi"
    assert s.plateau.ready is False


def test_transport_switch_request_valid():
    req = TransportSwitchRequest(kind="serial")
    assert req.kind == "serial"


def test_transport_switch_request_invalid_kind():
    with pytest.raises(ValueError):
        TransportSwitchRequest(kind="bluetooth")  # type: ignore[arg-type]


def test_transport_switch_response_success():
    r = TransportSwitchResponse(success=True, description="serial /dev/cu.usbserial-110", error=None)
    assert r.success is True
    assert r.error is None


def test_transport_switch_response_failure():
    r = TransportSwitchResponse(success=False, description="wifi 192.168.4.1:3333", error="timeout")
    assert r.success is False
    assert r.error == "timeout"
