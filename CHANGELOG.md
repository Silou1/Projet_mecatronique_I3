# Changelog

Tous les changements notables de ce projet seront documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté — P9 Intégration logicielle RPi ↔ ESP32 (2026-05-04)
- `quoridor_engine.NackCode` : enum des codes d'erreur typés alignés sur le protocole UART (`ILLEGAL`, `OUT_OF_BOUNDS`, `WRONG_TURN`, `WALL_BLOCKED`, `NO_WALLS_LEFT`, `INVALID_FORMAT`)
- `quoridor_engine.GameSession` : classe d'orchestration de partie en mode plateau, avec cycle handshake → game loop → gameover → close et re-handshake automatique sur `ERR` récupérable
- `main.py --mode plateau --port <chemin>` : nouveau mode CLI qui dispatche vers `GameSession.run()`
- `main.py --debug` : mode verbeux pour les logs de session
- Thread keepalive 1 Hz dans `UartClient`, démarré dans `connect()` et stoppé dans `close()`
- Compteur `UartClient.get_rejected_count()` pour les trames mal formées rejetées silencieusement
- Détection du thread reader mort dans `_send_frame` avec `UartError` immédiat
- Stubs firmware `CMD WALL` et `CMD GAMEOVER` dans `GameController::tickConnected` (réponse `DONE` sans action mécanique, action réelle reportée à P11)

### Modifié — P9
- `InvalidMoveError(message, code)` : argument `code: NackCode` désormais obligatoire
- `_reset_session()` remet `is_connected` à `False` après reboot ESP32 spontané
- `handle_err_received()` remet `is_connected` à `False` après `CMD_RESET` envoyé, pour forcer le re-handshake côté orchestrateur

### Tests — P9
- `tests/test_game_session.py` couvre le flux entrant `ACK`/`NACK`, le flux sortant IA, `GAMEOVER`, les `ERR` et la boucle principale
- `tests/test_main_cli.py` couvre `argparse` (`--mode`, `--port`, `--difficulty`, `--debug`)
- Compilation firmware validée par `pio run` : `SUCCESS`, RAM 6.7 %, Flash 23.1 %

### Reporté — P9.5
- Tests d'intégration E2E sur DevKit ESP32 : checklist dans [`firmware/INTEGRATION_TESTS_PENDING.md`](firmware/INTEGRATION_TESTS_PENDING.md)

### Ajouté — P8 Protocole UART Plan 2 (2026-05-01, en cours)
- **Spec complet** du protocole UART Plan 2 (`docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md`) : trames texte framees, CRC-16 CCITT-FALSE, sequencement avec ack matching, idempotence retry CMD, politique d'erreurs typees, vecteurs de reference figes
- **Plan d'implementation** detaille en 30 tasks (`docs/superpowers/plans/2026-05-01-protocole-uart-plan-2-implementation.md`)
- **Module Python `quoridor_engine/uart_client.py`** (~600 lignes) : client UART complet avec encodage/decodage de trames, threading background, sequencement, retry idempotent CMD (3 essais, 15 s), gestion d'erreurs typees (UartError, UartTimeoutError, UartProtocolError, UartVersionError, UartHardwareError), classification recuperable/non-recuperable des codes ERR, auto CMD_RESET pour erreurs recuperables, gestion §6.6 (RPi reboote + ESP32 en ERROR)
- **91 tests unitaires** sur `tests/test_uart_client.py` (avec MockSerial et MockClock dans `tests/conftest.py`), couverture **99 %** sur uart_client.py (cible spec : ≥ 90 %)
- **Refactor complet `firmware/src/UartLink.{h,cpp}`** : nouvelle API `sendFrame` / `log` / `logf` / `tryGetFrame` / `respondCmdDone` / `respondCmdErr` / `emitSpontaneousErr` / `tickErrReemission` / `clearErrState`, framing CRC-16 CCITT-FALSE, mutex FreeRTOS pour synchroniser les acces a Serial entre Core 0 et Core 1, dedup CMD idempotent
- **Documentation utilisateur** reecrite : `docs/06_protocole_uart.md`
- Ajout dependance `pyserial>=3.5` a `requirements.txt`

### Modifie — P8
- `firmware/src/main.cpp` : emet `BOOT_START` et `SETUP_DONE` en trames protocolaires framees, appelle `tickErrReemission` dans loop()
- `firmware/src/GameController.cpp` et tous les autres modules ESP32 : tous les `Serial.print` directs remplaces par `UartLink::log` / `logf`, suppression des appels `sendLine` / `tryReadLine` (API Plan 1 supprimee)
- `quoridor_engine/__init__.py` : exporte `UartClient`, `Frame`, et toutes les exceptions UART
- 181 tests unitaires (90 anciens + 91 uart_client)

### Reporte — P8.6
- Tests d'integration ESP32 DevKit ↔ Python reportes au 2026-05-04 (DevKit indisponible). Checklist : `firmware/INTEGRATION_TESTS_PENDING.md`

### Ajouté
- Audit complet du PCB v2 (hardware/AUDIT_PCB_V2.md)
- Guide de modifications PCB pour EasyEDA (Word, envoye a Jean)
- Diagrammes Mermaid pour l'architecture (docs/flowcharts/)
- Documentation du jeu et de l'IA (docs/comprendre_le_jeu.md)
- Configuration CI/CD avec GitHub Actions

### Modifié
- Passage du plateau de 9x9 a 6x6 (2 joueurs, 6 murs chacun)
- 90 tests unitaires, 82% de couverture
- Correction commentaire main.py (taille plateau 9 → 6)
- Nettoyage des fichiers electronique obsoletes (ancien audit v1)
- Reorganisation du repo : regroupement docs/ et hardware/, suppression des dossiers Schema_PCB/ et electronique/

## [1.0.0] - 2025-10-20

### Ajouté
- 🎲 **Moteur de jeu complet**
  - Gestion de l'état du jeu (positions, murs, tours)
  - Validation complète des coups (déplacements et murs)
  - Détection des situations de victoire
  - Historique des coups avec fonction "undo"
  
- 🤖 **Intelligence Artificielle**
  - Algorithme Minimax avec élagage Alpha-Beta
  - 3 niveaux de difficulté (Facile, Normal, Difficile)
  - Fonction d'évaluation heuristique sophistiquée
  - Pathfinding optimisé (BFS)

- 🖥️ **Interface Console**
  - Affichage ASCII avec couleurs (via colorama)
  - Mode Joueur vs Joueur
  - Mode Joueur vs IA
  - Commandes intuitives et aide interactive

- 🧪 **Tests Unitaires**
  - 90 tests unitaires complets
  - 82% de couverture du moteur principal (core.py)
  - Tests pour toutes les règles du jeu
  - Tests de l'IA et des cas limites

- 📚 **Documentation**
  - README complet avec exemples
  - Guide de contribution (CONTRIBUTING.md)
  - Documentation détaillée des tests
  - Note de projet pour l'équipe

### En cours de développement
- 🔌 Interface materielle ESP32-WROOM + Raspberry Pi (PCB en cours)
- 📡 Communication UART ESP32 <-> RPi

---

## Types de changements

- **Ajouté** : pour les nouvelles fonctionnalités
- **Modifié** : pour les changements aux fonctionnalités existantes
- **Déprécié** : pour les fonctionnalités qui seront bientôt supprimées
- **Supprimé** : pour les fonctionnalités supprimées
- **Corrigé** : pour les corrections de bugs
- **Sécurité** : en cas de vulnérabilités
