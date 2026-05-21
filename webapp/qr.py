"""Génération de QR code pour partager l'URL de la webapp sur un téléphone.

Détecte l'IP du Mac sur l'interface réseau active (en0 typiquement),
construit `http://<IP>:8000`, et renvoie un QR SVG.
"""
from __future__ import annotations

import io
import socket

import segno


def detect_lan_ip() -> str:
    """Retourne l'IP du Mac sur le LAN (interface qui sert la route par défaut).

    Astuce : on ouvre un socket UDP vers une IP externe (sans envoyer), l'OS
    nous donne l'IP source sur l'interface qui sert. Marche même sans Internet
    (pas d'envoi réel).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 1.1.1.1 : IP arbitraire (Cloudflare DNS). Pas de paquet envoyé,
        # juste la résolution de l'interface.
        s.connect(("1.1.1.1", 80))
        ip = s.getsockname()[0]
    except OSError:
        # Pas de route par défaut (mode AP sans Internet). On essaie 192.168.4.1
        # qui est l'IP de l'ESP32 en mode AP, ce qui donne notre IP sur cet AP.
        try:
            s.connect(("192.168.4.1", 80))
            ip = s.getsockname()[0]
        except OSError:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def webapp_url(port: int = 8000) -> str:
    """Construit l'URL de la webapp sur le LAN."""
    return f"http://{detect_lan_ip()}:{port}"


def qr_svg(content: str, scale: int = 6) -> bytes:
    """Genere un QR code SVG (bytes) pour le contenu donne."""
    qr = segno.make(content, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=scale, border=2)
    return buf.getvalue()
