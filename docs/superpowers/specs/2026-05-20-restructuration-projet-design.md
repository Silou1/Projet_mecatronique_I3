---
title: Restructuration du projet Quoridor — pivot Mac+Wi-Fi
date: 2026-05-20
status: validated
scope: phases 0 à 4 (préparation au pivot Wi-Fi, hors implémentation Wi-Fi)
---

# Spec — Restructuration du projet (phases 0 à 4)

## 1. Contexte

Le 2026-05-20, à J-2 de la présentation finale ICAM, l'équipe Quoridor opère un **pivot stratégique** :

- Le **Raspberry Pi** comme cerveau du système est abandonné. Le code Python (webapp + IA) tournera désormais sur le **Mac** de l'utilisateur (MacBook M5 2026), présenté comme "cloud local".
- Le **transport ESP32 ↔ ordinateur** était jusqu'ici de l'UART série direct via câble USB. Pour le livrable final, on vise du **Wi-Fi en principal (ESP32 en mode AP)**, USB-série en **backup explicite**.
- La démo de mi-projet a eu lieu en USB-C direct ; elle a fonctionné (levée des murs Quoridor correctement déclenchée). Le système mécanique CoreXY + servo + capteurs est **validé physiquement**.

L'historique technique du projet (specs `superpowers/`, plans, docs `00-08`, sketches firmware intermédiaires) reflète massivement l'architecture pré-pivot (RPi, FSM Plan 2, protocole CRC-16, PCB v2). Cette dette documentaire bloque la suite : tout nouveau sous-agent ou collaborateur qui ouvre le repo croule sous des informations obsolètes.

**Objectif de cette spec** : restructurer la documentation et le repo pour repartir d'une base propre, **avant** d'attaquer l'implémentation Wi-Fi (phase 5, hors scope de cette spec).

## 2. Décisions architecturales (actées en brainstorming)

### 2.1 Transport ESP32 ↔ Mac

- **Wi-Fi principal**, USB-série backup explicite (livrable final).
- Topologie Wi-Fi cible : **ESP32 en mode AP** créant son propre réseau `Quoridor-ESP32` avec mot de passe défini. Le Mac s'y connecte comme client. Le téléphone se connecte aussi pour servir d'interface webapp pendant la démo.
- Internet sur le Mac pendant le dev : **tethering USB iPhone** (l'iPhone reste branché en USB-C au Mac, "Personal Hotspot" actif). macOS gère l'ordre des interfaces nativement.
- Mode démo : on débranche le téléphone du Mac, le téléphone rejoint le Wi-Fi de l'ESP32 et accède à la webapp via l'IP du Mac (~`192.168.4.2:8000`). Pas d'Internet requis.
- Mode fallback : USB-C direct Mac ↔ ESP32, webapp sur l'écran du Mac.

### 2.2 Protocole d'application

Texte ligne par ligne, **identique sur USB et Wi-Fi** :

- `PING` → `PONG` (handshake)
- `WALL <H|V> <row> <col>` avec `row, col ∈ [0..4]` → `WALL OK <orient> <r> <c> raised=<n>` ou `WALL ERR <raison>`
- Autres commandes existantes du sketch bring-up : `HOME`, `GOTO`, `LEVER`, `BAISSER`, `STATUS`, `DEMO`, etc. (debug/manuel)
- Logs verbeux acceptés en sortie (la couche transport Python filtre les lignes utiles).

### 2.3 Workflow git

- Branche unique : `main`. Pas de feature branches. Pas de PR.
- Commits locaux à chaque étape cohérente. Push direct vers `origin/main` à la fin de chaque phase validée.
- Pas de tags ni de releases.

## 3. Invariants à NE JAMAIS casser

Ces éléments sont validés physiquement (bring-up 2026-05-20) et doivent être préservés tels quels. Tout sous-agent et toute opération de cette spec en hérite **automatiquement**.

1. **Sketch `firmware/src/bringup_l298n_complet.cpp`** : pas de refonte. Ajout possible (Wi-Fi phase 5) sans casser les comportements existants (HOME auto, GOTO, LEVER/BAISSER, WALL, DEMO, parsing série).

2. **Pinout ESP32-WROOM** (extrait du sketch, source de vérité) :
   - M1 (L298N #1) : IN1=`14`, IN2=`27`, IN3=`26`, IN4=`25`, ENA=`33`, ENB=`32`
   - M2 (L298N #2) : IN1=`16`, IN2=`17`, IN3=`21`, IN4=`22`, ENA=`19`, ENB=`23`
   - Capteurs : `PIN_LIMIT_X=13`, `PIN_LIMIT_Y=18` (mode `INPUT_PULLUP`, LOW = appuyé)
   - Servo : `PIN_SERVO=4`

3. **Convention machine** (validée physiquement) :
   - X pur = M1 et M2 **sens opposés**, HOME via capteur 13
   - Y pur = M1 et M2 **même sens**, HOME via capteur 18
   - Servo : 180° = repos (piston bas), 0° = mur levé
   - Origine (0, 0) en **bas-gauche** du plateau, axes croissant vers haut et droite

4. **Calibration** : 100 pas full-step = 2 cm (1 cm = 50 pas, 1 mm = 5 pas). Course X ≈ 110 mm, Y ≈ 101 mm.

5. **18 positions de murs validées 2026-05-20** (9 H + 9 V), valeurs gelées dans le sketch (matrices `MURS_H[j][i]` et `MURS_V[j][i]`). Les 42 autres positions sont marquées `_NA` (à mesurer après la démo). **À revalider physiquement** par l'utilisateur pendant les tests du 2026-05-21 (doute de saisie possible).

6. **Protocole texte commun** sur USB et (futur) Wi-Fi : `PING`/`PONG`, `WALL`, `OK`, `ERR`. Seul canal accepté par la webapp.

## 4. Structure cible

### 4.1 Documentation (`docs/`)

```
docs/
├── README.md                          ← index avec liens
├── 01_projet.md                       ← vision, contexte ICAM, règles Quoridor, objectifs
├── 02_architecture.md                 ← Mac ↔ ESP32 (Wi-Fi prio + USB backup), schéma, flux
├── 03_demarrage.md                    ← installation, lancer webapp, modes dev/démo, dépannage
├── 04_engine.md                       ← moteur de jeu + IA (quoridor_engine/)
├── 05_webapp.md                       ← FastAPI + frontend SVG + transports
├── 06_firmware.md                     ← sketch ESP32, commandes série, plan Wi-Fi
├── 07_protocole.md                    ← protocole texte commun PING/WALL/OK/ERR
├── 08_tests.md                        ← pytest, couverture, marqueurs, tests devkit
├── hardware/
│   ├── pinout.md                      ← pins ESP32 figées (INVARIANT)
│   ├── positions-murs.md              ← 18/60 mesurées (INVARIANT, à revalider)
│   └── calibration.md                 ← conventions axes, courses, servo
└── flowcharts/
    ├── README.md
    ├── 01_*.md … 09_*.md              ← sources mermaid/markdown
    └── png/                           ← versions PNG conservées
```

### 4.2 Racine du projet (après ménage)

Conservé :
- `CLAUDE.md` (mis à jour pour refléter le pivot)
- `README.md` (réécrit en index court avec lien vers `docs/`)
- `main.py`, `pyproject.toml`, `requirements.txt`, `.gitignore`
- `.claude/settings.local.json` (perm NotebookLM, indispensable aux sessions Claude Code)
- `quoridor_engine/`, `webapp/`, `tests/`, `firmware/`, `hardware/`, `docs/`

Supprimé :
- `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`, `.editorconfig`, `.coverage`
- `.superpowers/brainstorm/` (état local du brainstorming superpowers, non utile en repo)

## 5. Plan d'exécution

Chaque phase est un atome de travail : un commit, un push (sauf phase 0 et 1 qui peuvent être groupées si très courtes).

### Phase 0 — Spec restructuration (ce document)

- Artefact : `docs/superpowers/specs/2026-05-20-restructuration-projet-design.md`.
- Sera supprimé en phase 3 (couvert par la doc cible).
- Sous-agents : aucun, rédaction Claude directe.
- Critère d'acceptation : spec validée par l'utilisateur, commit local.
- Commit : `docs(spec): plan de restructuration projet post-pivot Mac+Wi-Fi`

### Phase 1 — Préserver les invariants

Créer trois fichiers dans `docs/hardware/` extraits du sketch :

#### `docs/hardware/pinout.md`
- Header d'avertissement : "Source de vérité : `firmware/src/bringup_l298n_complet.cpp`. Toute modification ici doit être synchronisée avec le sketch et validée physiquement."
- Tableau des pins (M1, M2, capteurs, servo) — voir §3.2.
- Mention : "Pins libres ESP32-WROOM restantes : vérifier dans NotebookLM `7d0bccd1-…` avant tout ajout (Wi-Fi natif n'occupe pas de GPIO mais peut interférer avec les pins ADC2)."

#### `docs/hardware/positions-murs.md`
- Header d'avertissement : "Valeurs gelées au 2026-05-20 (18/60 mesurées). Source de vérité : matrices `MURS_H[j][i]` et `MURS_V[j][i]` dans `firmware/src/bringup_l298n_complet.cpp`. **À revalider physiquement le 2026-05-21** (doute de saisie possible)."
- Convention : origine (0, 0) en bas-gauche, j=0 en bas, i=0 à gauche, valeurs en pas.
- Tableau MURS_H (9 mesurés / 30) avec marqueur `_NA` pour les 21 manquants.
- Tableau MURS_V (9 mesurés / 30) avec marqueur `_NA` pour les 21 manquants.

#### `docs/hardware/calibration.md`
- Header d'avertissement : "Source de vérité : commentaires et constantes dans `firmware/src/bringup_l298n_complet.cpp`."
- Conventions axes (§3.3).
- Calibration : 100 pas = 2 cm, courses approximatives.
- Servo : 180° repos / 0° levé, pulses min/max 500-2500 µs.
- Notes safety mécanique : servo positionné à 180° en premier au boot, drivers OFF par défaut.

Sous-agents : aucun, je fais ça directement (extraction simple).

Critère d'acceptation : les 3 fichiers existent, contenu identique au sketch, headers d'avertissement présents.

Commit : `docs(hardware): figer pinout + positions murs + calibration (invariants)`

### Phase 2 — Reconstruire `docs/01-08` + README

8 fichiers `.md` + 1 README, à créer/réécrire **en parallèle** via sous-agents Sonnet (modèle `claude-sonnet-4-6`).

**Règles communes à tous les sous-agents Sonnet de la phase 2 :**

1. Langue : français (variables, comments, docstrings, prose). Anglais uniquement pour les noms de classes Python (PascalCase).
2. Style : factuel, concis, max 100 chars/ligne pour le code et 120 pour la prose.
3. **Aucune mention** de : Raspberry Pi, RPi, `/dev/ttyAMA*`, MCP23017, FSM Plan 2, FreeRTOS, CRC-16, CCITT, `<TYPE|seq=…|crc=…>`, PCB v2, HELLO_ACK, KEEPALIVE, MOVE_REQ/WALL_REQ, NACK.
4. **Mentions positives obligatoires** : Mac ↔ ESP32, USB-série en backup, Wi-Fi en mode AP (cible phase 5), protocole texte `PING`/`PONG`/`WALL`/`OK`/`ERR`.
5. Reprise des invariants §3 dans tout document touchant au hardware.
6. Pour les blocs "à venir phase 5" (Wi-Fi notamment), utiliser le ton "prévu, non implémenté à ce jour", pas "TODO" passif.

**Détail par fichier (un sous-agent par fichier) :**

#### `docs/README.md`
- Sous-agent : Sonnet, prompt court (< 200 mots).
- Contenu attendu : 1 paragraphe d'intro (1-2 phrases sur le projet), index des 8 docs avec une ligne par fichier, lien vers `docs/hardware/`.

#### `docs/01_projet.md`
- Sections : Vision (jeu Quoridor 6x6 sur plateau physique mécatronique) ; Contexte ICAM (3A, équipe 6 personnes) ; Règles du jeu (mouvements pions, placement murs, victoire, notation cases a-f / 1-6) ; Objectifs pédagogiques (intégration logiciel/hardware, communication série/réseau).
- Sources : sections REGLE-JEU de l'ancien `01_demarrage.md` (notation cases, déplacements valides), extraits vision de l'ancien `00_plan_global.md`.

#### `docs/02_architecture.md`
- Sections : Vue d'ensemble (diagramme texte Mac → ESP32 → plateau) ; Composants (moteur jeu, IA, webapp, firmware) ; Transports (Wi-Fi AP en cible + USB en backup) ; Modes (dev avec tethering iPhone, démo avec téléphone client) ; Flux d'un coup (déplacement et mur, du clic UI au mouvement physique) ; Décisions clés (pourquoi pas de RPi, pourquoi mode AP).
- Sources : structure de l'ancien `02_architecture.md` (sans le bloc Plan 2 / FSM / CRC).

#### `docs/03_demarrage.md`
- Sections : Prérequis (Python 3.10+, Homebrew, USB-C) ; Installation (clone, venv, requirements.txt) ; Lancer la webapp (autonome, sans ESP32) ; Connecter l'ESP32 en USB (procédure éprouvée) ; Connecter l'ESP32 en Wi-Fi (placeholder "phase 5") ; Modes dev (tethering iPhone) et démo (téléphone client) ; Dépannage.
- Sources : sections SETUP de l'ancien `01_demarrage.md` + nouveau contenu transports.

#### `docs/04_engine.md`
- Sections : Vue d'ensemble (`quoridor_engine/` = moteur de jeu + IA, un seul module Python) ; Constantes (`BOARD_SIZE=6`, `MAX_WALLS=6`, départs et objectifs) ; API publique (`QuoridorGame`, `GameState`, `AI`, `InvalidMoveError`) ; Format des coups (`('deplacement', (r,c))`, `('mur', ('h'|'v', r, c, 2))`) ; Choix de conception (immutabilité `GameState`, `FrozenSet[Wall]`, BFS pathfinding, façade) ; IA Minimax + Alpha-Bêta + iterative deepening + transposition table ; Heuristique d'évaluation ; Déterminisme et tie-breaking ; Tests associés.
- Sources : ancien `03_moteur_jeu.md` + `04_ia.md` (fusion).

#### `docs/05_webapp.md`
- Sections : Vue d'ensemble (FastAPI port 8000, frontend SVG vanilla servi en statique) ; Modules (`webapp/server.py`, `webapp/service.py`, `webapp/uart_bridge.py`, `webapp/schemas.py`) ; Modes (autonome moteur+IA, hybride avec plateau) ; Sélection du transport (placeholder pour env var `QUORIDOR_TRANSPORT=serial|wifi` — implémentation phase 5) ; Flux d'un coup ; Tests `tests/webapp/`.
- Sources : `webapp/README.md` à la racine + nouveau contenu transports.

#### `docs/06_firmware.md`
- Sections : Vue d'ensemble (ESP32-WROOM, sketch monolithique `bringup_l298n_complet.cpp`) ; Compilation/flash via PlatformIO (`pio run`, `pio run -t upload`, `pio device monitor`) ; Architecture du sketch (setup auto avec HOME, loop série, parser ligne par ligne, watchdog désactivé) ; Commandes série supportées (lister exhaustivement depuis le code) ; Plan d'ajout Wi-Fi (phase 5, court paragraphe).
- Sources : commentaires d'en-tête du sketch + ancien `05_firmware.md` épuré.

#### `docs/07_protocole.md`
- Sections : Vue d'ensemble (protocole texte ligne par ligne, baudrate 115200 sur USB, même payload sur Wi-Fi en phase 5) ; Commandes (`PING`/`PONG`, `WALL <H|V> <row> <col>` avec `row, col ∈ [0..4]`) ; Réponses (`WALL OK <H|V> <r> <c> raised=<n>`, `WALL ERR <raison>`) ; Codes d'erreur (`WALL ERR orientation`, `WALL ERR borne`, `WALL ERR syntaxe`) ; Idempotence et garanties (au moins une livraison côté webapp) ; Exemple de session (`PING → PONG → WALL H 2 3 → WALL OK H 2 3 raised=2`).
- Sources : implémentation actuelle de `webapp/uart_bridge.py` + handler `WALL` du sketch (lignes 736-762).

#### `docs/08_tests.md`
- Sections : Lancer pytest (`pytest`, `pytest -m "not devkit"`, `--cov`, fichier/classe précis) ; Structure des tests (lister les `tests/test_*.py` actuels seulement — ne **pas** mentionner `test_uart_client.py` ni `test_game_session.py` qui seront supprimés en phase 3) ; Couverture cible (~80%) ; Tests hardware (`-m devkit`, `tests/integration/test_uart_devkit.py`).
- Sources : ancien `08_tests.md` épuré.

**Mode d'orchestration des 9 sous-agents :** lancer les 9 en parallèle (un seul message avec 9 tool calls Agent). Chaque sous-agent reçoit en input : la spec actuelle (§3 invariants + §4 structure + ses propres sections §5 ci-dessus + règles communes). Chaque sous-agent **écrit directement le fichier** dans `docs/` via Write. Je relis chacun avant le commit unique.

Critère d'acceptation : 9 fichiers créés, aucune mention interdite (§5.2 règles communes), pinout/calibration cohérents avec `docs/hardware/`.

Commit : `docs: refonte complète post-pivot Mac+Wi-Fi (phase 2/4)`

### Phase 3 — Ménage destructif

Opérations groupées en un seul commit (toutes des suppressions, aucune ambiguïté de logique).

**Suppression de fichiers :**
- Anciens docs racine `docs/` : `00_plan_global.md`, `01_demarrage.md`, `02_architecture.md`, `03_moteur_jeu.md`, `04_ia.md`, `05_firmware.md`, `06_protocole_uart.md`, `07_hardware.md`, `08_tests.md`. (L'ancien `docs/README.md` a déjà été écrasé en phase 2 par le nouveau `docs/README.md`. Le `README.md` à la racine du projet n'est pas concerné — il sera mis à jour plus bas dans cette phase.)
- `docs/superpowers/specs/` : tous les `.md` **sauf** `2026-05-20-restructuration-projet-design.md` (cette spec).
- `docs/superpowers/plans/` : tous les `.md` (et `archive/` si présent).
- `docs/superpowers/specs/archive/` : tout.
- `docs/flowcharts/pdf/` : tout le dossier.
- `docs/flowcharts/exports/*.pdf` : tous les PDF (garder les `.png`).
- `docs/flowcharts/rapport/` : à examiner avant la phase ; si c'est le rapport ICAM ou des notes utiles, garder ; sinon drop. Décision à prendre pendant l'exécution.
- Racine projet : `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`, `.editorconfig`, `.coverage`.
- Tests obsolètes : `tests/test_uart_client.py` (43 KB, Plan 2), `tests/test_game_session.py` (10.7 KB, Plan 2).
- `.superpowers/brainstorm/` : tout (état local non-utile en repo).

**Déplacements (archivage) :**
- `firmware/src/bringup_motor1_l298n.cpp`, `bringup_limit_switch.cpp`, `bringup_servo.cpp`, `bringup_motors_and_limits.cpp`, `bringup_l298n_indep.cpp` → `firmware/src/archive/bringup-staging-2026-05-20/`. Garder pour traçabilité des étapes de bring-up, mais clairement séparés du sketch de production.

**Conservé sans changement :**
- `.claude/settings.local.json` : perm NotebookLM indispensable.
- `firmware/src/archive/drv8825-2026-05-20/` : archive existante.
- `firmware/src/bringup_l298n_complet.cpp` : sketch de production.
- `hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/` : traçabilité postmortem.
- `docs/flowcharts/*.md` : sources mermaid des flowcharts.
- `docs/flowcharts/png/` : versions PNG conservées.

**Mises à jour :**
- `CLAUDE.md` racine : retirer toute mention RPi, MCP23017, FSM Plan 2 ; ajouter le pivot Mac+Wi-Fi/USB ; ajouter mention de la nouvelle structure `docs/`. Cible : 60-100 lignes.
- `README.md` racine : index court (5-10 lignes), pointer vers `docs/`.
- `.gitignore` : vérifier que `.coverage`, `.pytest_cache/`, `.venv/`, `__pycache__/`, `.DS_Store` sont bien ignorés ; ajouter si manquants.

**Vérification post-suppression (critères d'acceptation) :**
- `pytest -m "not devkit"` passe sans `ImportError` (sinon il reste des références à `quoridor_engine.uart_client` ou `quoridor_engine.GameSession` à nettoyer).
- `python main.py` lance le jeu console sans erreur.
- `git status` propre après tous les `git rm` et `git mv`.

Sous-agents : aucun, opérations directes (rm/mv/Edit).

Commit : `chore: ménage projet (drop legacy specs/plans/RPi/Plan2, racine GitHub-pro)`

### Phase 4 — Consolidation WIP UART + push GitHub

**Examiner les modifs locales non commitées :**
- `firmware/src/bringup_l298n_complet.cpp` (+73 lignes) : ajout commande `WALL` + handler.
- `webapp/uart_bridge.py` (+19 lignes), `webapp/service.py` (+8 lignes), `tests/webapp/test_uart_bridge.py` (+10 lignes) : intégration `WALL` côté Python.
- `docs/superpowers/plans/2026-05-20-webapp-esp32-walls.md` (untracked) : déjà supprimé en phase 3.

**Décision :** ces 4 modifs étendent le protocole texte avec la commande `WALL` (déjà éprouvée en démo de mi-projet). Elles sont cohérentes en tant qu'ensemble et tiennent debout sans Wi-Fi. → **Commit + push**.

**Push GitHub :**
- Commits déjà existants : `3bf5917` (spec walls), `9003447` (refonte uart_bridge texte brut).
- Nouveaux commits : phase 1 (invariants), phase 2 (refonte docs), phase 3 (ménage), phase 4 (WIP UART consolidé).
- Total : 5 nouveaux commits à pousser + 2 existants = 7 commits cumulés.

Commande : `git push origin main`.

Critère d'acceptation :
- `git status` propre, working tree clean.
- `git log origin/main..HEAD` vide après push.
- Le repo GitHub `Silou1/Projet_mecatronique_I3` reflète la nouvelle structure (à vérifier dans le navigateur).

Commit phase 4 : `feat(webapp): commande WALL bout-en-bout (firmware + service + tests)`

## 6. Hors scope

À couvrir par des specs dédiées **après** cette restructuration :

- **Phase 5** : implémentation du transport Wi-Fi (ESP32 en mode AP, abstraction `Transport` côté Python avec `SerialTransport` et `WiFiTransport`, sélection via env var `QUORIDOR_TRANSPORT`, tests). Sera une spec séparée + plan d'exécution multi-agents avec Opus pour les morceaux non triviaux.
- **Phase 5b** : boutons physiques + LEDs RGB sur l'ESP32, expander I/O (référence non-MCP23017 à identifier), protocole d'envoi des appuis ESP32 → Mac, intégration côté webapp.
- **Phase 6** : polish démo + dry-run vendredi matin.

## 7. Risques et pièges identifiés

1. **18 positions de murs potentiellement erronées** : valeurs à revalider physiquement le 2026-05-21. Pas de modification tant que le test physique n'a pas été fait. La doc `docs/hardware/positions-murs.md` porte un avertissement explicite.

2. **Perm NotebookLM** : `.claude/settings.local.json` doit absolument rester. Sa suppression ferait perdre l'accès direct à la datasheet ESP32 (NotebookLM `7d0bccd1-…`) et briserait les workflows hardware des futures sessions.

3. **`docs/flowcharts/rapport/`** : statut inconnu. À ouvrir avant la phase 3 et décider garder/drop selon contenu.

4. **Tests cassés par drop** : après suppression de `test_uart_client.py` et `test_game_session.py`, vérifier que `pytest -m "not devkit"` tourne sans `ImportError`. Le module `quoridor_engine.uart_client` peut lui-même être à dropper s'il n'est plus utilisé (vérifier les imports). Idem pour `quoridor_engine.GameSession`.

5. **Sous-agents phase 2** : risque de dérive (les sous-agents Sonnet peuvent ré-introduire des mentions RPi ou Plan 2 par inertie d'apprentissage). Mitigation : la règle §5.2.3 (mentions interdites) + relecture systématique de ma part avant commit.

6. **Cohérence pinout entre sources** : le pinout existe dans 3 endroits après phase 1 (sketch, `docs/hardware/pinout.md`, `docs/06_firmware.md`). Si un jour les pins changent, il faut synchroniser les 3. La source de vérité reste le sketch, les docs renvoient à lui.

## 8. Annexe — Mapping ancien → nouveau

| Nouveau fichier | Contenu | Sources |
|---|---|---|
| `docs/README.md` | Index + table des matières | Ancien `README.md` (réécrit) |
| `docs/01_projet.md` | Vision, contexte ICAM, règles Quoridor | `01_demarrage.md` [REGLE-JEU] + `00_plan_global.md` (vue d'ensemble) |
| `docs/02_architecture.md` | Mac↔ESP32 Wi-Fi+USB, schéma, flux | `02_architecture.md` (refait sans Plan 2) |
| `docs/03_demarrage.md` | Setup, lancement, modes dev/démo | `01_demarrage.md` [SETUP] + nouveau Wi-Fi/USB |
| `docs/04_engine.md` | Moteur jeu + IA (un module) | `03_moteur_jeu.md` + `04_ia.md` (fusion) |
| `docs/05_webapp.md` | FastAPI, frontend, transports | `02_architecture.md` (bloc webapp) + nouveau |
| `docs/06_firmware.md` | Sketch ESP32, commandes, plan Wi-Fi | `05_firmware.md` (refait sans FSM Plan 2) |
| `docs/07_protocole.md` | Protocole texte commun | `06_protocole_uart.md` (intégralement réécrit) |
| `docs/08_tests.md` | pytest, couverture, devkit | `08_tests.md` (épuré) |
| `docs/hardware/pinout.md` | Pins ESP32 figées | Extrait sketch + `07_hardware.md` (bloc pins) |
| `docs/hardware/positions-murs.md` | 18/60 valeurs + revalidation | Extrait sketch (matrices MURS_H/V) |
| `docs/hardware/calibration.md` | Conventions axes, courses, servo | `07_hardware.md` (bloc calibration) |

## 9. Critères d'acceptation globaux (fin phase 4)

- ✅ 5 nouveaux commits poussés sur `origin/main` (en plus des 2 existants `3bf5917` et `9003447`).
- ✅ `git status` propre, working tree clean.
- ✅ `pytest -m "not devkit"` passe sans erreur (ou les tests cassés sont explicitement supprimés et leur disparition justifiée dans le commit message).
- ✅ `python main.py` lance le jeu console sans erreur.
- ✅ Structure `docs/` conforme à §4.1.
- ✅ Racine du projet conforme à §4.2 (LICENSE/CONTRIBUTING/CHANGELOG/.editorconfig/.coverage absents).
- ✅ `CLAUDE.md` à jour sans mention RPi/MCP23017/Plan 2.
- ✅ Aucune mention de RPi, FSM Plan 2, CRC-16, MCP23017 dans `docs/` ou dans le code actif (les références dans `hardware/archive/` et `firmware/src/archive/` restent OK pour la traçabilité).
- ✅ `.claude/settings.local.json` toujours présent.
