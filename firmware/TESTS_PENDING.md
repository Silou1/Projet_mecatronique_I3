# Tests d'intégration en attente de hardware

Le firmware Plan 1 compile sans erreur (`pio run` SUCCESS, RAM 6.6%, Flash 21.1%) et a été développé avec validation à chaque étape, mais **les scénarios d'intégration de la Task 9 du plan n'ont pas été exécutés sur cible** durant la session du 2026-04-28.

**Action attendue** : dès qu'un ESP32 (DevKit ou PCB v2) est branché en USB, exécuter ces 7 scénarios. Si tous passent, supprimer ce fichier et faire un commit `test(firmware): plan 1 valide en bout-en-bout sur cible`.

## Préparation

```bash
cd firmware
pio device list                                # repérer le port série de l'ESP32
pio run -t upload                              # flasher
pio device monitor                             # ouvrir le moniteur série (Ctrl+C pour quitter)
```

Configuration moniteur : 115200 bauds, fin de ligne = `LF` (Newline) — pas `CRLF`. Le filtre `direct` est déjà fixé dans `platformio.ini` donc l'output est brut.

Pour envoyer des commandes au firmware depuis le moniteur, taper la commande puis Entrée. Le firmware lit ligne par ligne (terminée par `\n`).

## Scénario 1 — Boot nominal vers DEMO

Reset l'ESP32 (bouton EN sur le DevKit). **Ne rien taper.**

Sortie attendue :
```
BOOT_START
[UartLink] init
[LedDriver] init (stub)
[LedAnimator] init (stub)
[ButtonMatrix] init (stub)
[MotionControl] init (FreeRTOS task)
[GameController] init
[GameController] -> state 0           # BOOT
SETUP_DONE
[LedDriver] selfTest -> OK (stub)
[MotionControl] selfTest -> OK (stub I2C)
[MotionControl] exec command kind=0   # HOMING
... ~1 s ...
[GameController] -> state 1           # WAITING_RPI
HELLO
HELLO
... répété ~15 fois (toutes les 200 ms) ...
[GameController] -> state 2           # DEMO
[GameController] DEMO tick
[GameController] DEMO tick
... toutes les 500 ms, LED bleue (GPIO2) clignote ...
```

Vérifier : la LED bleue intégrée du DevKit clignote en continu après ~3 s post-BOOT.

## Scénario 2 — Boot nominal vers CONNECTED

Reset. **Pendant les 3 s post-BOOT** (i.e. avant le passage à DEMO), taper :
```
HELLO_ACK
```

Sortie attendue : transition `-> state 3` (CONNECTED), plus de `HELLO`, plus de `DEMO tick`, LED bleue ne clignote pas.

## Scénario 3 — Cycle de jeu simulé complet

Depuis CONNECTED (scénario 2 réussi), envoyer `KEEP` toutes les ~2 s pour maintenir la connexion. Entre les KEEP :

3a. Simuler un clic bouton : taper `BTN 2 3`
- Attendu : `MOVE_REQ 2 3` émis sur UART, `[LedAnimator] play pattern=2` (PENDING_FLASH), `-> state 4` (BUTTON_INTENT_PENDING)

3b. Valider : taper `ACK`
- Attendu : `[MotionControl] exec command kind=1`, `[LedAnimator] play pattern=5` (EXECUTING_SPINNER), `-> state 5` (EXECUTING). Après ~1 s : `DONE` émis, `-> state 3` (CONNECTED).

3c. Re-simuler un clic : taper `BTN 1 1`

3d. Refuser : taper `NACK`
- Attendu : `[LedAnimator] play pattern=3` (NACK_FLASH), `-> state 3` (CONNECTED).

3e. Commande directe : taper `CMD MOVE 4 4`
- Attendu : `[MotionControl] exec command kind=1`, `-> state 5` (EXECUTING) directement (sans passer par BUTTON_INTENT_PENDING). Après ~1 s : `DONE` émis, `-> state 3`.

## Scénario 4 — Perte UART en CONNECTED

Depuis CONNECTED, **ne rien envoyer pendant 4 s.**

Attendu : après ~3 s de silence, `[GameController] ENTER ERROR code=UART_LOST`, `[LedAnimator] play pattern=6` (ERROR_PATTERN), `ERR UART_LOST` émis, `-> state 6` (ERROR_STATE).

## Scénario 5 — Escalade timeout intent

Reset, `HELLO_ACK`. Puis 3 fois de suite :
- Taper `BTN 0 0`
- Attendre 600 ms
- Taper `KEEP` (pour ne pas que ce soit l'UART_LOST de fond qui déclenche l'ERROR à la place)

Attendu :
- 1er timeout : `intent timeout (consecutive=1)`, `[LedAnimator] play pattern=4` (TIMEOUT_FLASH), retour CONNECTED.
- 2e timeout : `intent timeout (consecutive=2)`, retour CONNECTED.
- 3e timeout : `intent timeout (consecutive=3)`, `[GameController] ENTER ERROR code=UART_LOST`, `-> state 6`.

## Scénario 6 — Récupération depuis ERROR

Depuis ERROR_STATE (issu de scénario 4 ou 5), taper :
```
RESET
```

Attendu : `[GameController] RESET requested`, puis ~100 ms plus tard `BOOT_START` (l'ESP32 a redémarré).

## Scénario 7 — Watchdog (provocation contrôlée)

Test de robustesse du watchdog. **Modification temporaire à NE PAS COMMITER.**

Dans `firmware/src/GameController.cpp`, dans `tickDemo()`, ajouter au tout début :
```cpp
delay(7000);  // PROVOCATION watchdog -- A RETIRER APRES TEST
```

Compiler/flasher. Reset, ne rien taper. Le firmware passe BOOT → WAITING_RPI → DEMO. Au premier `tickDemo`, il bloque 7 s ; au bout de ~5 s, le watchdog déclenche et l'ESP32 reboote.

Attendu : observation d'un nouveau `BOOT_START` après ~5 s sans cause apparente côté UART.

**Retirer le `delay(7000)` après confirmation, recompiler, et NE PAS COMMITER cette ligne.**

## Scénario 8 — Couverture du spec

Cocher chaque état et chaque transition listés dans `docs/superpowers/specs/2026-04-28-firmware-esp32-architecture-globale-design.md` §2.4. Tous doivent avoir été observés via les scénarios 1 à 6 :

- [ ] BOOT (scénario 1, ligne `[GameController] -> state 0`)
- [ ] BOOT → WAITING_RPI (scénario 1)
- [ ] WAITING_RPI → DEMO (scénario 1)
- [ ] WAITING_RPI → CONNECTED (scénario 2)
- [ ] DEMO (état terminal — scénario 1)
- [ ] CONNECTED (scénario 2)
- [ ] CONNECTED → BUTTON_INTENT_PENDING (scénario 3a)
- [ ] BUTTON_INTENT_PENDING → EXECUTING (scénario 3b, ACK)
- [ ] BUTTON_INTENT_PENDING → CONNECTED (scénario 3d, NACK)
- [ ] BUTTON_INTENT_PENDING → CONNECTED (scénario 5, timeout)
- [ ] BUTTON_INTENT_PENDING → ERROR (scénario 5, 3 timeouts)
- [ ] CONNECTED → EXECUTING (scénario 3e, CMD direct)
- [ ] EXECUTING → CONNECTED (scénario 3b/3e, DONE)
- [ ] CONNECTED → ERROR (scénario 4, UART_LOST)
- [ ] ERROR → BOOT (scénario 6, RESET)

## En cas d'échec d'un scénario

**Ne pas patcher localement et ignorer.** Si un scénario ne donne pas la sortie attendue :
1. Noter le scénario, l'input envoyé, la sortie observée vs attendue.
2. Vérifier d'abord les soupçons triviaux : port série, vitesse 115200, fin de ligne LF dans le moniteur, ESP32 bien connecté.
3. Si le bug est réel, créer une note dans ce fichier et investiguer. Le firmware doit être **fiable** : un scénario qui échoue est un vrai bug à corriger avant de marquer le Plan 1 comme validé.
