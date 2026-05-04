# Quoridor Interactif

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> Plateau Quoridor physique interactif où un joueur humain affronte une intelligence artificielle.
> Architecture **Raspberry Pi (Python / IA) ↔ ESP32 (firmware C++)** via UART.
>
> Projet mécatronique ICAM 2025-2026 — Année 3

---

## Démarrage rapide

```bash
git clone https://github.com/Silou1/Projet_mecatronique_I3.git
cd Projet_mecatronique_I3
pip install -r requirements.txt
python main.py
```

Choisir **1** (Joueur vs Joueur) ou **2** (Joueur vs IA, 3 niveaux). Plus de détails : [docs/01_demarrage.md](docs/01_demarrage.md).

## Architecture

| Couche | Rôle | Technologie |
|---|---|---|
| **Raspberry Pi 3/4** | Moteur de jeu, IA Minimax, orchestration | Python 3.10+ |
| **ESP32-WROOM** | Firmware temps réel : FSM, moteurs, LEDs, boutons | Arduino C++ + FreeRTOS |
| **UART0 @ 115200 bauds** | Communication entre les deux processeurs | Série |

Vue d'ensemble complète : [docs/02_architecture.md](docs/02_architecture.md).

## État du projet

| Phase | État |
|---|---|
| Moteur de jeu Python (règles, validation, undo) | ✅ |
| IA Minimax + alpha-bêta | ✅ |
| Interface console | ✅ |
| Tests Python (226 tests, ≥ 99 % sur le module UART) | ✅ |
| Firmware ESP32 — squelette + FSM (Plan 1) | ✅ |
| **Protocole UART Plan 2** — design, code Python (`uart_client.py`), refactor firmware (`UartLink`) | ✅ |
| **Intégration logicielle RPi ↔ ESP32** — `GameSession`, mode `--mode plateau` (P9.1–P9.4, P9.6) | ✅ |
| Tests d'intégration firmware ↔ Python sur DevKit (P8.6) | 🚧 attente DevKit |
| Tests E2E partie complète PvIA sur DevKit (P9.5) | 🚧 attente DevKit |
| Drivers hardware réels + PCB v2 (P10–P14) | 📋 |

Plan global détaillé : [docs/00_plan_global.md](docs/00_plan_global.md).

## Documentation

- 📖 [docs/](docs/) — index complet (architecture, moteur, IA, firmware, hardware, tests, protocole UART)
- 🎯 [docs/00_plan_global.md](docs/00_plan_global.md) — **ROADMAP maître**
- 🔧 [hardware/](hardware/) — PCB v2, audit, mapping pins
- ⚙️ [firmware/](firmware/) — code ESP32 (PlatformIO)
- 🧪 [tests/](tests/) — suite pytest

## Tests

```bash
pytest                                          # 226 tests (moteur/IA + UART + GameSession + CLI), ~8 s
pytest --cov=quoridor_engine --cov-report=html  # couverture
```

Plus : [docs/08_tests.md](docs/08_tests.md).

## Contribution

Conventions de code et de commits dans [CONTRIBUTING.md](CONTRIBUTING.md).

## Équipe

Projet mené par une équipe de 6 étudiants ICAM 3A. Développeur principal : **Silouane Chaumais** ([@Silou1](https://github.com/Silou1)).

## License

MIT — voir [LICENSE](LICENSE).
