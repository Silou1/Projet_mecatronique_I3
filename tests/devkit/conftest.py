"""Fixtures pour tests devkit (ESP32 branché)."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WIFI_SWITCH = PROJECT_ROOT / "tools" / "wifi_switch.py"


@pytest.fixture
def wifi_fixture():
    """Bascule le Mac sur Quoridor-ESP32 pendant le test, restaure après.

    Pré-requis :
    - ESP32 flashé avec le firmware phase 5 (AP actif)
    - Variable d'env QUORIDOR_SSID_RESTORE = nom du SSID à restaurer
      après le test (ex: 'ICAM'). Sinon, la restauration ne sera pas
      possible et le test affichera un avertissement à la fin.

    Le fixture est tolérant : si la bascule échoue (premier passage GUI
    macOS, ESP32 hors ligne), le test peut quand même tenter sa
    connexion TCP — qui échouera proprement.
    """
    restore_ssid = os.environ.get("QUORIDOR_SSID_RESTORE")
    save_arg = ["--save-current", restore_ssid] if restore_ssid else []

    # Bascule
    try:
        subprocess.check_call(
            [sys.executable, str(WIFI_SWITCH), "to-esp32"] + save_arg,
            timeout=15,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        pytest.skip(f"Bascule Wi-Fi vers Quoridor-ESP32 echouee : {e}")
    # Laisse 3s à la liaison Wi-Fi
    time.sleep(3.0)

    yield

    # Restauration (best effort)
    try:
        subprocess.check_call(
            [sys.executable, str(WIFI_SWITCH), "restore"],
            timeout=15,
        )
        time.sleep(2.0)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        sys.stderr.write(
            f"\n⚠ Restauration Wi-Fi a echoue : {e}\n"
            f"  Reconnecte-toi manuellement au SSID precedent via le menu Wi-Fi macOS.\n"
        )
