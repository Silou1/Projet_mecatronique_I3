# Quoridor mécatronique

Jeu de plateau Quoridor 6×6 piloté par ordinateur, avec plateau physique
où les murs sont levés par un piston monté sur chariot CoreXY.

Projet pédagogique mécatronique — ICAM 2025-2026, année 3.

## Démarrage rapide

```bash
git clone https://github.com/Silou1/Projet_mecatronique_I3.git
cd Projet_mecatronique_I3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Webapp (jeu dans le navigateur)
python -m webapp.server
# → http://localhost:8000

# CLI console (sans plateau physique)
python main.py
```

## Documentation

Index complet : [`docs/README.md`](docs/README.md).

- [Présentation du projet](docs/01_projet.md)
- [Architecture Mac ↔ ESP32](docs/02_architecture.md)
- [Démarrage et dépannage](docs/03_demarrage.md)
- [Moteur de jeu + IA](docs/04_engine.md)
- [Webapp](docs/05_webapp.md)
- [Firmware ESP32](docs/06_firmware.md)
- [Protocole de communication](docs/07_protocole.md)
- [Tests](docs/08_tests.md)
- [Invariants hardware](docs/hardware/) — ne pas modifier sans accord

## Tests

```bash
pytest -m "not devkit"
```

## Équipe

Projet mené par une équipe de 6 étudiants ICAM 3A. Dépôt :
[github.com/Silou1/Projet_mecatronique_I3](https://github.com/Silou1/Projet_mecatronique_I3).
