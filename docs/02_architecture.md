# Architecture globale

Vue d'ensemble du projet : deux machines, un canal de communication, une séparation nette des
responsabilités. Le Mac fait tourner toute la logique logicielle ; l'ESP32 pilote le hardware.

## Vue d'ensemble

```
┌────────────────────────────────────────────────────────────────┐
│  Mac (Python 3.12)                                             │
│                                                                │
│  ┌─────────────────────┐   ┌────────────────────────────────┐  │
│  │  quoridor_engine/   │   │  webapp/                       │  │
│  │  - core.py          │◄──│  - server.py  (FastAPI :8000)  │  │
│  │  - ai.py            │   │  - service.py (orchestration)  │  │
│  │  (moteur + IA)      │   │  - uart_bridge.py (optionnel)  │  │
│  └─────────────────────┘   └──────────────┬─────────────────┘  │
│                                           │ USB-série (actuel)  │
│                                           │ Wi-Fi AP (phase 5)  │
└───────────────────────────────────────────┼────────────────────┘
                                            │ 115200 bauds
                              ┌─────────────▼─────────────────┐
                              │  ESP32-WROOM                  │
                              │  bringup_l298n_complet.cpp    │
                              │  (sketch monolithique)        │
                              │  - CoreXY (2× NEMA17 + L298N) │
                              │  - Servo (levée mur)          │
                              │  - 2× fins de course (homing) │
                              └─────────────┬─────────────────┘
                                            │ GPIO, PWM
                                            ▼
                              ┌─────────────────────────────┐
                              │  Plateau physique Quoridor  │
                              │  - Piston CoreXY (chariot)  │
                              │  - Servo 0°/180° (murs)     │
                              │  - Breadboard + alim 12 V   │
                              └─────────────────────────────┘
```

Le Mac est le seul cerveau du jeu : règles, IA, état de partie, interface utilisateur.
L'ESP32 est un actionneur intelligent : il reçoit des commandes texte et traduit chaque
instruction en mouvement physique (déplacement du chariot, levée de mur).

## Composants logiciels

### `quoridor_engine/`

Moteur de jeu pur Python, sans aucune dépendance à l'interface ou au hardware.

- **`core.py`** : `GameState` (dataclass immuable), règles Quoridor 6×6, validation des coups,
  pathfinding BFS anti-blocage. Chaque coup retourne un nouvel état (permet undo et arbre IA).
- **`ai.py`** : Minimax avec élagage Alpha-Bêta et table de transposition. Choisit le meilleur
  coup pour le joueur IA à partir de l'état courant.

### `webapp/`

Interface de démonstration servie par FastAPI sur le port 8000. Accès depuis n'importe quel
navigateur sur le réseau local (iPhone, PC, Mac).

| Fichier | Rôle |
|---|---|
| `server.py` | Point d'entrée FastAPI + uvicorn. Routes API + `GET /` sert le HTML. |
| `service.py` | `QuoridorService` singleton thread-safe. État partie, tick IA, orchestration. |
| `uart_bridge.py` | Passerelle optionnelle vers l'ESP32. Détection auto au démarrage. |
| `schemas.py` | Modèles Pydantic pour les payloads et réponses JSON. |
| `static/` | Frontend : HTML5 + CSS3 + JS vanilla + SVG inline. Zéro framework, zéro build. |

Le frontend interroge `/api/state` toutes les 500 ms (polling HTTP, sans WebSocket — choix
fiabilité). Animations CSS sur les transitions pions et murs.

### `firmware/src/bringup_l298n_complet.cpp`

Sketch ESP32 monolithique. Aucune refonte prévue ; des commandes supplémentaires pourront
être ajoutées en phase 5 (Wi-Fi).

Responsabilités du sketch :
- **Homing** : déplacement jusqu'aux fins de course (X=GPIO13, Y=GPIO18, INPUT_PULLUP),
  définition de l'origine bas-gauche.
- **GOTO** : déplacement CoreXY en pas (calibration : 100 pas = 2 cm, 1 mm = 5 pas).
- **LEVER / BAISSER** : servo GPIO4, 0° = levé, 180° = repos.
- **WALL** : commande haut niveau — calcule la position physique du mur via les matrices
  `MURS_H` / `MURS_V`, enchaîne GOTO + LEVER + BAISSER pour chaque case concernée.
- **PING** : réponse PONG (handshake et détection de présence de l'ESP32).

Pinout :
- M1 : IN1=14, IN2=27, IN3=26, IN4=25, ENA=33, ENB=32
- M2 : IN1=16, IN2=17, IN3=21, IN4=22, ENA=19, ENB=23
- Convention X : M1 et M2 sens opposés. Convention Y : M1 et M2 même sens.

Voir `docs/hardware/pinout.md`, `docs/hardware/calibration.md` et
`docs/hardware/positions-murs.md` pour les détails mesurés.

## Transport ESP32 ↔ Mac

### USB-série (mode actuel, validé)

Câble USB-C direct entre le Mac et l'ESP32. Côté Mac : `/dev/tty.usbserial-*` (détection
automatique par `uart_bridge.py`). Baudrate 115200. Ce mode est utilisé en développement
et constitue le fallback fiable pour la démo.

### Wi-Fi en mode AP (cible phase 5, prévu, non implémenté)

L'ESP32 crée un point d'accès Wi-Fi nommé `Quoridor-ESP32`. Le Mac s'y connecte comme
client et joint l'ESP32 via son IP fixe (ex. `192.168.4.1`). Le protocole d'application
est identique à l'USB-série (même format texte, même baudrate logique). Pas de refonte
firmware requise : seule la couche transport change.

### Protocole d'application (commun aux deux transports)

Texte brut ligne par ligne (`\n`), encodage UTF-8. Sans framing binaire ni CRC.
Debuggable directement au moniteur série.

| Commande Mac → ESP32 | Réponse ESP32 |
|---|---|
| `PING` | `PONG` |
| `WALL <H\|V> <row> <col>` | `WALL OK <H\|V> <row> <col> raised=<n>` |
| `GOTO <x> <y>` | `OK` ou `ERR <msg>` |
| `HOME` | `OK` |
| `LEVER` | `OK` |
| `BAISSER` | `OK` |

`raised=<n>` : nombre de cases physiquement manipulées (1 ou 2 selon le mur).

## Modes d'exécution

### Mode dev (sessions de codage actuelles)

Le Mac est connecté à Internet via tethering USB de l'iPhone (Personal Hotspot).
L'ESP32 est connecté en USB-C au Mac. La webapp tourne sur `http://localhost:8000`,
accessible depuis Safari Mac. L'iPhone fournit Internet, pas le réseau ESP32.

### Mode démo (cible vendredi)

L'iPhone est débranché du Mac et se connecte au Wi-Fi `Quoridor-ESP32` de l'ESP32.
Le Mac est aussi sur ce réseau Wi-Fi. L'iPhone accède à la webapp via l'IP du Mac sur
le réseau ESP32 (typiquement `192.168.4.2:8000`). Aucun accès Internet requis.

Si le Wi-Fi est instable lors de la démo, fallback immédiat sur USB-C direct : la
webapp et l'`uart_bridge.py` détectent automatiquement `/dev/tty.usbserial-*` au boot.

### Mode autonome

Aucun ESP32 connecté. La webapp tourne en local sur le Mac, le moteur Python gère
intégralement l'état de partie et l'IA. Les murs sont posés visuellement dans
l'interface SVG, sans action physique. C'est le mode de démo minimum (P0).

## Flux d'un coup (avec plateau physique)

1. Le joueur clique dans la webapp (déplacement de pion ou pose de mur).
2. La webapp valide via `quoridor_engine` : déplacement légal, mur non bloquant (BFS).
3. Si déplacement de pion : mise à jour de l'état interne seulement (pas de commande ESP32).
4. Si pose de mur : la webapp envoie `WALL <H|V> <row> <col>` à l'ESP32 via `uart_bridge.py`.
5. L'ESP32 calcule la position physique depuis les matrices `MURS_H` / `MURS_V`.
6. L'ESP32 enchaîne : `GOTO` jusqu'à la 1re case → `LEVER` → `BAISSER`. Si le mur occupe
   2 cases physiques, répète GOTO + LEVER + BAISSER pour la 2e case.
7. L'ESP32 répond `WALL OK <H|V> <row> <col> raised=<n>`.
8. La webapp met à jour l'affichage SVG (confirmation visuelle).

Si l'ESP32 ne répond pas dans le délai ou renvoie `ERR`, la webapp affiche une
notification `PLATEAU_LOST` et continue en mode autonome (fallback gracieux).

## Décisions clés

### Pourquoi le Mac comme cerveau

Souplesse maximale de développement : Python natif, Claude Code, pytest, debug facile.
Pas de mise au point d'un système embarqué intermédiaire à configurer. Performance
largement suffisante pour l'IA Minimax sur un plateau 6×6. Facilite les ajustements
de dernière minute (J-2 d'une démo).

### Pourquoi l'ESP32

Wi-Fi natif intégré (utile pour la phase 5 sans câble). GPIO suffisants pour le CoreXY
(2× L298N, 4 entrées chacun) + servo + 2 capteurs. Communauté Arduino mature,
flashage trivial via USB-C. Pas de PSRAM requise pour ce sketch.

### Pourquoi un protocole texte

Debuggable directement au moniteur série sans outil externe. Lisible dans les logs
webapp. Évolutif sans recompilation (ajout de commandes en phase 5). Aucune dépendance
à une librairie de framing propriétaire. Identique sur USB-série et Wi-Fi TCP.

## Stack technique

| Domaine | Choix |
|---|---|
| Langage Mac | Python 3.12 |
| Framework API | FastAPI 0.110+, uvicorn (standard) |
| Bibliothèques Python | `pyserial` (USB-série), `pytest` (tests), `colorama` (console) |
| Frontend | HTML5 + CSS3 + JS vanilla + SVG inline (zéro build) |
| Langage ESP32 | Arduino C++ (PlatformIO, framework Arduino) |
| Communication actuelle | USB-série 115200 bauds, `/dev/tty.usbserial-*` |
| Communication cible | Wi-Fi mode AP, mêmes commandes texte sur TCP |
| Format protocole | Texte brut ligne par ligne, sans framing binaire |

## Pour aller plus loin

- [03_moteur_jeu.md](03_moteur_jeu.md) — API et concepts du moteur Python
- [04_ia.md](04_ia.md) — Détails de l'IA Minimax (Alpha-Bêta, heuristique)
- [hardware/pinout.md](hardware/pinout.md) — Pinout complet ESP32 et L298N
- [hardware/calibration.md](hardware/calibration.md) — Calibration pas ↔ mm
- [hardware/positions-murs.md](hardware/positions-murs.md) — Matrices MURS_H / MURS_V
