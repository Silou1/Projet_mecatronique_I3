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
    # 2026-05-22 : bascule AP -> STA tethering iPhone. Plus de wifi_switch.py
    # (Mac et ESP32 partagent le hotspot iPhone, plus de bascule networksetup).
    # Les tests devkit_wifi sont obsoletes en attendant un refactor STA.
    if not WIFI_SWITCH.exists():
        pytest.skip(
            "tools/wifi_switch.py retire (bascule mode STA tethering 2026-05-22). "
            "Tests devkit_wifi a refactorer pour le nouveau mode STA."
        )

    restore_ssid = os.environ.get("QUORIDOR_SSID_RESTORE")
    save_arg = ["--save-current", restore_ssid] if restore_ssid else []

    # Bascule sur Quoridor-ESP32 si pas déjà connecté.
    # Optimisation : on teste d'abord si on peut joindre 192.168.4.1:3333.
    # Si oui, on saute la bascule (gain de ~5-10s par test devkit_wifi).
    already_on_esp32 = _can_reach_esp32()
    if not already_on_esp32:
        try:
            subprocess.check_call(
                [sys.executable, str(WIFI_SWITCH), "to-esp32"] + save_arg,
                timeout=45,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            pytest.skip(f"Bascule Wi-Fi vers Quoridor-ESP32 echouee : {e}")
        time.sleep(3.0)

    yield

    # Restauration seulement si la variable QUORIDOR_AUTO_RESTORE=1 est positionnee.
    # Par defaut, on reste sur Quoridor-ESP32 pour chainer plusieurs tests devkit_wifi
    # sans payer le cout de bascule a chaque fois. L'utilisateur fera la restauration
    # manuelle a la fin (ou via wifi_switch.py restore).
    if os.environ.get("QUORIDOR_AUTO_RESTORE") == "1":
        try:
            subprocess.check_call(
                [sys.executable, str(WIFI_SWITCH), "restore"],
                timeout=45,
            )
            time.sleep(2.0)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            sys.stderr.write(
                f"\n⚠ Restauration Wi-Fi a echoue : {e}\n"
                f"  Reconnecte-toi manuellement au SSID precedent via le menu Wi-Fi macOS.\n"
            )


def _can_reach_esp32(host: str = "192.168.4.1", port: int = 3333, timeout: float = 1.0) -> bool:
    """Test rapide si l'ESP32 est joignable en TCP (= Mac deja sur l'AP)."""
    import socket as _s
    try:
        with _s.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, _s.timeout):
        return False
