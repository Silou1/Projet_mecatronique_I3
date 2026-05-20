# CLAUDE.md

Guide pour Claude Code (claude.ai/code) sur le projet Quoridor.

## Vue d'ensemble

Jeu Quoridor 6×6 sur plateau mécatronique. Projet pédagogique ICAM 3A (équipe de 6).

**Architecture (après pivot 2026-05-20)** :
- **Mac (Python)** : webapp FastAPI port 8000 + IA Minimax + moteur de jeu. Tourne sur le Mac
  de l'utilisateur. Internet via tethering USB iPhone pendant le développement.
- **ESP32-WROOM (Arduino C++)** : sketch monolithique unique
  [`firmware/src/bringup_l298n_complet.cpp`](firmware/src/bringup_l298n_complet.cpp).
  CoreXY + servo + capteurs fins de course.
- **Transport** : USB-série actuel (validé), Wi-Fi en mode AP (cible phase 5,
  *prévu, non implémenté à ce jour*).
- **Protocole** : texte ligne par ligne, identique USB/Wi-Fi : `PING`/`PONG`,
  `WALL <H|V> <r> <c>`, `OK`/`ERR`.

**État hardware (2026-05-20)** : breadboard (PCB v2 abandonnée, postmortem dans
[`hardware/archive/`](hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md)).
Bring-up validé : 18/60 positions de murs mesurées (à revalider physiquement,
voir [`docs/hardware/positions-murs.md`](docs/hardware/positions-murs.md)).

## Commandes

```bash
# Webapp (mode autonome ou hybride si ESP32 branché)
python -m webapp.server

# CLI console (sans plateau physique)
python main.py

# Tests
pytest                               # toute la suite
pytest -m "not devkit"               # même chose tant qu'aucun test devkit n'est enregistré
pytest --cov=quoridor_engine         # couverture
pytest tests/test_moves.py -v        # un fichier
```

## Architecture du repo

```
main.py                  → CLI console
quoridor_engine/
  core.py                → règles, GameState (frozen dataclass), NackCode, InvalidMoveError
  ai.py                  → Minimax + Alpha-Bêta + iterative deepening + transposition
webapp/
  server.py              → FastAPI port 8000
  service.py             → couche service entre API et moteur
  uart_bridge.py         → transport USB-série actuel (pyserial)
  schemas.py             → modèles Pydantic
firmware/src/
  bringup_l298n_complet.cpp  → sketch ESP32 de production
docs/                    → documentation projet (entrée : docs/README.md)
  hardware/              → INVARIANTS : pinout, positions murs, calibration
tests/                   → pytest (moteur, IA, webapp)
hardware/                → archive PCB v2 (postmortem)
```

## Code style

- Français pour les noms de variables, commentaires, docstrings, prose markdown.
- Anglais pour les noms de classes Python (PascalCase) et les termes très consacrés
  (FastAPI, CoreXY, Minimax).
- PEP 8, indentation 4 espaces, max 100 chars/ligne (code) ou 120 (markdown).
- Type hints utilisés partout.

## Workflow git

- Une seule branche : `main`. Pas de feature branches. Pas de PR.
- Commits locaux phase par phase. Push direct vers `origin/main` après validation.

## Référence ESP32

Pour toute question sur les GPIO, périphériques, strapping pins, ADC, RTC, PWM :
interroger le NotebookLM `ESP32 Development Board Pinout Reference Map`
(id `7d0bccd1-df3f-456d-99a0-1192766043ba`) via le MCP `notebooklm-mcp`. Ne pas se fier
aux pinouts third-party (Freenove DevKitC) qui peuvent diverger du SoC.
