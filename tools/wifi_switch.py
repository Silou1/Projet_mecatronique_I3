"""Helper macOS pour basculer le Wi-Fi du Mac entre Quoridor-ESP32 et le SSID normal.

Usage :
    python tools/wifi_switch.py to-esp32 [--save-current SSID]
        # bascule sur Quoridor-ESP32. Sauvegarde le SSID donné (ou tente
        # de le détecter, peut échouer sur macOS Sonoma/Sequoia).
    python tools/wifi_switch.py restore
        # restaure le SSID précédent (lu depuis /tmp/quoridor_previous_ssid)
    python tools/wifi_switch.py status
        # affiche le SSID actuel (ou <inconnu> si macOS masque)

Sauvegarde le SSID précédent dans /tmp/quoridor_previous_ssid.
Détecte dynamiquement le nom de l'interface Wi-Fi via networksetup.

Limitation macOS Sonoma/Sequoia : le SSID actif est souvent masqué
(<redacted>) sauf si Location Services est autorisé pour le terminal.
D'où l'option --save-current SSID pour le forcer manuellement.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PREVIOUS_SSID_FILE = Path("/tmp/quoridor_previous_ssid")
ESP32_SSID = "Quoridor-ESP32"
ESP32_PASS = "quoridor2026"


def find_wifi_interface() -> str:
    """Détecte le nom de l'interface Wi-Fi macOS (typiquement 'en0')."""
    out = subprocess.check_output(["networksetup", "-listallhardwareports"], text=True)
    blocks = re.split(r"\n(?=Hardware Port:)", out)
    for block in blocks:
        if "Wi-Fi" in block:
            m = re.search(r"Device:\s*(\S+)", block)
            if m:
                return m.group(1)
    raise RuntimeError("Interface Wi-Fi non détectée via networksetup")


def get_current_ssid(iface: str) -> str | None:
    """Retourne le SSID actuel ou None si déconnecté/masqué.

    Sur macOS récent, le SSID peut être masqué (<redacted>). On retourne None
    dans ce cas pour signaler que la détection automatique a échoué.
    """
    # Tentative 1 : networksetup
    out = subprocess.check_output(
        ["networksetup", "-getairportnetwork", iface], text=True
    )
    m = re.search(r":\s*(.+)$", out.strip())
    if m:
        ssid = m.group(1).strip()
        if "not associated" in ssid.lower() or "redacted" in ssid.lower():
            return None
        return ssid
    return None


def set_ssid(iface: str, ssid: str, password: str | None = None) -> None:
    cmd = ["networksetup", "-setairportnetwork", iface, ssid]
    if password:
        cmd.append(password)
    subprocess.check_call(cmd)


def cmd_to_esp32(save_ssid: str | None) -> int:
    iface = find_wifi_interface()
    if save_ssid:
        previous = save_ssid
    else:
        previous = get_current_ssid(iface)
    if previous and previous != ESP32_SSID:
        PREVIOUS_SSID_FILE.write_text(previous)
        print(f"SSID precedent sauvegarde : {previous}")
    else:
        print("Aucun SSID precedent (macOS masque ?), restauration ne fonctionnera pas")
    set_ssid(iface, ESP32_SSID, ESP32_PASS)
    print(f"Bascule sur {ESP32_SSID} via {iface}")
    return 0


def cmd_restore() -> int:
    iface = find_wifi_interface()
    if not PREVIOUS_SSID_FILE.exists():
        print(f"Aucun SSID precedent sauvegarde dans {PREVIOUS_SSID_FILE}")
        print("Reconnecte-toi manuellement via le menu Wi-Fi macOS")
        return 1
    previous = PREVIOUS_SSID_FILE.read_text().strip()
    try:
        set_ssid(iface, previous)
        print(f"Restaure SSID precedent : {previous}")
    except subprocess.CalledProcessError as e:
        print(f"ERREUR : restauration {previous!r} echouee : {e}")
        print("Reconnecte-toi manuellement via le menu Wi-Fi macOS")
        return 2
    return 0


def cmd_status() -> int:
    iface = find_wifi_interface()
    current = get_current_ssid(iface)
    print(f"Interface : {iface}")
    print(f"SSID actuel : {current if current else '<inconnu/masque par macOS>'}")
    if PREVIOUS_SSID_FILE.exists():
        print(f"SSID precedent en cache : {PREVIOUS_SSID_FILE.read_text().strip()}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["to-esp32", "restore", "status"])
    parser.add_argument("--save-current",
                        help="SSID a sauvegarder explicitement (utile si macOS masque)")
    args = parser.parse_args()
    if args.action == "to-esp32":
        return cmd_to_esp32(args.save_current)
    elif args.action == "restore":
        return cmd_restore()
    elif args.action == "status":
        return cmd_status()
    return 2


if __name__ == "__main__":
    sys.exit(main())
