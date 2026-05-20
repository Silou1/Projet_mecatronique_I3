# Documentation — Quoridor Interactif

Projet pédagogique ICAM 3A : jeu Quoridor 6×6 sur plateau mécatronique, piloté depuis le Mac via
un ESP32-WROOM branché en USB-série. Le Mac exécute l'IA et la webapp FastAPI ; l'ESP32 pilote le
CoreXY, le servo et les détecteurs de position. Pour les détails complets du projet, voir
[01_projet.md](01_projet.md).

---

## Table des matières

1. **[01_projet.md](01_projet.md)** — Présentation générale : règles du Quoridor, objectifs
   pédagogiques, périmètre de la démo.

2. **[02_architecture.md](02_architecture.md)** — Vue d'ensemble des composants (Mac, ESP32,
   webapp) et de leurs interactions.

3. **[03_demarrage.md](03_demarrage.md)** — Installation pas à pas, premier lancement de la
   webapp, commandes utiles, dépannage.

4. **[04_engine.md](04_engine.md)** — Moteur Python : `GameState` (dataclass immuable), règles,
   pathfinding BFS, API publique.

5. **[05_webapp.md](05_webapp.md)** — Webapp FastAPI (port 8000) : routes, `QuoridorService`,
   frontend SVG vanilla, mode autonome et mode plateau physique.

6. **[06_firmware.md](06_firmware.md)** — Firmware Arduino C++ sur ESP32 : sketch de production
   `bringup_l298n_complet.cpp`, CoreXY, servo, détecteurs de fin de course.

7. **[07_protocole.md](07_protocole.md)** — Protocole texte brut Mac ↔ ESP32 sur USB-série
   (115 200 bauds) : commandes, réponses, gestion des erreurs.
   Mode Wi-Fi AP prévu, non implémenté à ce jour.

8. **[08_tests.md](08_tests.md)** — Stratégie de tests : pytest Python (moteur + webapp) et
   scénarios de validation firmware (commandes manuelles).

---

## Sous-dossier `hardware/`

Invariants physiques du plateau, stables une fois le câblage validé.

| Fichier | Contenu |
|---|---|
| [`hardware/pinout.md`](hardware/pinout.md) | Affectation complète des GPIO ESP32 (moteurs, servo, fins de course) |
| [`hardware/positions-murs.md`](hardware/positions-murs.md) | Coordonnées XY machine de chaque position de mur (grille 6×6) |
| [`hardware/calibration.md`](hardware/calibration.md) | Correspondance pas ↔ distance : 1 mm = 5 pas, 1 cm = 50 pas |

---

## Convention de langage

Toute la prose et les commentaires de code sont rédigés en **français**.
L'anglais est réservé aux noms de classes Python (PascalCase : `GameState`, `QuoridorService`…)
et aux termes techniques consacrés (FastAPI, Minimax, Alpha-Bêta, CoreXY).
