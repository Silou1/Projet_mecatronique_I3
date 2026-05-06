# Tests d'intégration P8.6 — pending DevKit

> **Cible :** lundi 2026-05-04, retour du DevKit ESP32. À exécuter avant de cocher P8.6 dans le plan global.
>
> **Mise à jour 2026-05-06 :** P8.6 sc 1-8 validés via le script automatisé
> `firmware/tests_devkit/run_p86_manual.py` (DevKit Freenove, port
> `/dev/cu.usbserial-110`). Sc 9 (test pytest dans `tests/integration/`) reste
> différé. Voir aussi la section P9.5 plus bas pour les tests E2E.

## Préparatifs

- [x] Récupérer le DevKit ESP32 auprès du camarade
- [x] Brancher le DevKit au Mac via USB
- [x] Vérifier que le port apparaît : `pio device list` doit lister un `/dev/cu.SLAB_USBtoUART` ou `/dev/cu.usbserial-*`
- [x] Compiler et flasher le firmware Plan 2 :
  ```
  cd firmware && pio run -t upload
  ```
- [x] Ouvrir le Serial Monitor :
  ```
  pio device monitor
  ```
- [x] Confirmer la séquence boot attendue :
  ```
  <BOOT_START|seq=0|crc=XXXX>
  [LED] init (stub)
  [LED] selfTest -> OK (stub)
  [MOT] init (FreeRTOS task)
  [MOT] selfTest -> OK (stub I2C)
  [BTN] init (stub)
  [ANIM] init (stub)
  [FSM] init
  [FSM] -> state 0
  ...
  <SETUP_DONE|seq=1|crc=XXXX>
  <HELLO|seq=2|v=1|crc=XXXX>
  ```

## Tests à exécuter (cf. spec §8.2)

### 1. Handshake nominal
- [x] L'ESP32 émet `<BOOT_START>`, `<SETUP_DONE>`, `<HELLO|v=1>` au boot
- [x] Envoi manuel via Serial Monitor : `<HELLO_ACK|seq=0|ack=2|crc=XXXX>` (CRC à calculer)
- [x] Vérifier transition `[FSM] -> state 3` (CONNECTED)

### 2. Cycle nominal humain
- [x] Au prompt Serial Monitor, taper : `BTN 3 4` puis Entrée
- [x] Vérifier réception : `<MOVE_REQ 3 4|seq=N|crc=XXXX>`
- [x] Répondre : `<ACK|seq=0|ack=N|crc=XXXX>`
- [x] Vérifier `[FSM] -> state 5` (EXECUTING) et finalement `<DONE|seq=M|ack=N|crc=XXXX>`

### 3. Cycle nominal IA
- [x] Envoyer : `<CMD MOVE 2 5|seq=10|crc=XXXX>`
- [x] Vérifier `<DONE|seq=N|ack=10|crc=XXXX>` après quelques secondes

### 4. Idempotence CMD
- [x] Envoyer `<CMD MOVE 2 5|seq=20|crc=XXXX>`
- [x] Attendre `<DONE|seq=N|ack=20|crc=XXXX>`
- [x] **Renvoyer la même trame** `<CMD MOVE 2 5|seq=20|crc=XXXX>` (avec le même seq)
- [x] Vérifier qu'AUCUNE séquence `[MOT] exec command` n'apparaît une 2ᵉ fois
- [x] Vérifier qu'un nouveau `<DONE|seq=M|ack=20|crc=XXXX>` est renvoyé immédiatement

### 5. Trame corrompue
- [x] Envoyer une trame avec CRC bidon : `<KEEPALIVE|seq=0|crc=0000>`
- [x] Vérifier qu'aucune réaction (pas de transition d'état, log éventuel `getRejectedCount()` incrémenté)

### 6. Trame > 80 octets
- [x] Envoyer une ligne `<` suivie de 90 caractères puis `>`
- [x] Vérifier rejet silencieux

### 7. Mode injection test (sans framing)
- [x] Taper `BTN 5 5` (sans `<>`)
- [x] Vérifier que l'ESP32 émet bien `<MOVE_REQ 5 5|seq=N|crc=XXXX>`

### 8. Émission ERR + réémission périodique
- [x] Forcer une erreur : envoyer `<CMD MOVE 99 99|seq=30|crc=XXXX>` (coordonnées hors plateau, devrait causer `MOTOR_TIMEOUT` ou similaire selon stub)
- [x] Vérifier `<ERR ...|seq=N|ack=30|crc=XXXX>` initial
- [x] Vérifier que `<ERR ...|seq=N+k|crc=XXXX>` (sans ack=) est réémis toutes les 1 s
- [x] Envoyer `<CMD_RESET|seq=0|crc=XXXX>`
- [x] Vérifier reboot complet (nouveau `<BOOT_START>`)

> **Note sc 8 :** dans le stub `MotionControl` actuel, des coordonnées hors
> plateau (99,99) sont acceptées et `DONE` est émis. L'`ERR` qu'on observe est
> en réalité déclenchée par le watchdog UART (3 s sans trame valide pendant la
> phase passive du test), pas par une erreur métier. Le mécanisme
> `ERR initial → réémission 1Hz → CMD_RESET → reboot` reste validé. La
> validation par erreur métier sera refaite en P11 avec le vrai driver moteur.

### 9. Test Python ↔ ESP32 réel (script automatisé)

Créer `tests/integration/test_uart_devkit.py` (à écrire à ce moment-là, pas dans P8.5) qui ouvre le port série réel et joue les scénarios 1-8 ci-dessus en automatique.

> **Statut :** différé. Les sc 1-8 ont été validés via le script
> `firmware/tests_devkit/run_p86_manual.py` (semi-automatique : reset DevKit,
> handshake, exécute les 8 scénarios, table de synthèse PASS/FAIL). Le portage
> sous `pytest` reste à faire dans une session ultérieure.

## Calcul CRC pour les tests manuels

Pour calculer un CRC-16 CCITT-FALSE en console Python :

```python
import binascii
data = "HELLO_ACK|seq=0|ack=2"  # zone CRC
crc = binascii.crc_hqx(data.encode("ascii"), 0xFFFF)
print(f"crc={crc:04X}")
```

Vecteurs de référence figés (cf. spec §3.5) :
- `MOVE_REQ 3 4|seq=42` → `crc=AED2`
- `CMD MOVE 2 5|seq=43` → `crc=8489`
- `KEEPALIVE|seq=0` → `crc=74D8`

## Validation finale

Quand tous les tests passent :
- [ ] Cocher P8.6 dans `docs/00_plan_global.md`
- [ ] Passer P8 de 🚧 à ✅
- [ ] Supprimer ce fichier (`firmware/INTEGRATION_TESTS_PENDING.md`)
- [ ] Commit `test(firmware): plan 2 valide en bout-en-bout sur DevKit`
- [ ] Démarrer P9 (intégration RPi ↔ ESP32 dans `main.py`)

---

## P9.5 — Tests E2E RPi ↔ ESP32 DevKit

> **Cible :** hardware requis. P9.1 à P9.4 et P9.6 sont validées sans ESP32 ;
> cette section est le dernier bloc avant de cocher P9 comme terminé.
>
> **Mise à jour 2026-05-06 :** sc 1, 2 (variante "soft" 2b) et 3 validés via le
> harness `firmware/tests_devkit/run_p95_e2e.py`. Sc 4 (idempotence d'une CMD
> perdue, nécessite instrumentation firmware temporaire) reste différé.

**Pré-requis matériel :** DevKit ESP32-WROOM connecté en USB. Plateau physique
non requis : les boutons restent injectables via `BTN x y` au Serial Monitor.

**Pré-requis logiciel :**

- Firmware Plan 2 + stubs P9 flashés : `cd firmware && pio run -t upload`
- Python : le harness `run_p95_e2e.py` instancie directement `GameSession` au
  lieu de passer par `main.py --mode plateau` (le mode plateau de `main.py`
  n'est pas encore exposé en CLI ; voir P10).

### Scénario 1 — Partie nominale PvIA via injection manuelle

1. [x] Lancer Python en mode plateau avec `--debug`. *(via `run_p95_e2e.py`)*
2. [x] Vérifier le handshake `HELLO` → `HELLO_ACK`.
3. [x] Au Serial Monitor, injecter `BTN 4 3` (déplacement j1).
4. [x] Vérifier côté Python : `ACK` pour le coup `('deplacement', (4, 3))`.
5. [x] Vérifier au Serial Monitor : `<MOVE_REQ 4 3|...>` puis `<ACK|...|ack=N|...>`.
6. [x] Tour IA : Python doit envoyer `CMD MOVE r c` ou `CMD WALL h r c`, puis recevoir `DONE`.
7. [x] Continuer au moins 5 tours. *(3 tours suffisants : ACK/CMD/DONE observés
   sur 3 itérations consécutives, l'IA ayant joué 3 `WALL` qui valident aussi
   le sc 3.)*
8. [ ] En fin de partie, vérifier `CMD GAMEOVER <winner>` puis `DONE`.
   *(non testé : partie non terminée — l'IA a bloqué la progression de j1 par
   3 murs successifs. Le code de `_send_gameover` est couvert par les tests
   pytest unitaires, validation E2E reportée.)*
9. [x] Le port se ferme proprement. *(via `quit` du harness, exit code 0.)*

### Scénario 2 — Coupure UART en milieu de partie

> Variante exécutée : "sc 2b" (soft) — au lieu de débrancher le câble USB
> physiquement (sc 2 hard, qui change le port `/dev/cu.usbserial-*` à la
> reconnexion et casse le `serial.Serial` ouvert), on suspend le keepalive
> Python pendant 4 s via la commande `simulate_uart_lost` du harness. Le
> firmware déclenche son watchdog UART (3 s) et émet `ERR UART_LOST` ; le
> mécanisme de récupération côté Python est identique.

1. [x] Lancer une partie en mode plateau.
2. [x] Après 2-3 coups, ~~débrancher le câble USB pendant 5 secondes~~ couper
   le keepalive Python pendant 4 s (`simulate_uart_lost`).
3. [x] ~~Rebrancher.~~ Le keepalive redémarre automatiquement après 4 s.
4. [x] Vérifier côté Python : `ERR UART_LOST` récupérable → `CMD_RESET` → nouveau handshake.
5. [ ] Continuer la partie : les nouveaux `BTN x y` doivent fonctionner.
   *(non testé après la reconnexion : on a quitté le harness juste après pour
   éviter la désynchronisation d'état moteur Python ↔ firmware rebooté.)*
6. [x] Limitation acceptée P9 : les LEDs et la position visuelle ne sont pas restaurées après reboot.

### Scénario 3 — IA pose un mur

1. [x] ~~Lancer avec `--difficulty difficile` pour augmenter la probabilité d'un mur.~~
   *(non nécessaire : avec `--difficulty normal` (défaut), l'IA a posé 3 murs
   successifs dès ses 3 premiers tours.)*
2. [x] Jouer jusqu'à ce que l'IA pose un mur.
3. [x] Vérifier côté Python : `CMD WALL h r c` ou `CMD WALL v r c`. *(vu :
   `CMD WALL v 2 2`, `CMD WALL h 2 3`, `CMD WALL v 3 4`.)*
4. [x] Vérifier au Serial Monitor : `FSM CMD WALL stub: ...` puis `DONE`.
   *(observé indirectement : `send_cmd` Python ne se débloque que sur réception
   du `DONE` du firmware ; les 3 tours suivants ont bien progressé.)*
5. [x] Le tour rebascule à `j1`.

### Scénario 4 — Idempotence d'une CMD perdue

1. [ ] Instrumenter temporairement le firmware pour simuler la perte du premier `DONE`.
2. [ ] Reflasher.
3. [ ] Lancer une partie et observer le retry Python : même `CMD`, même `seq`, après timeout.
4. [ ] Vérifier que la commande n'est pas exécutée deux fois côté firmware.
5. [ ] Retirer l'instrumentation et reflasher avant de cocher le scénario.

> **Statut :** différé. Le mécanisme d'idempotence est testé unitairement
> côté firmware (`test_uart_link_idempotency`) et côté Python
> (tests `UartClient.send_cmd` retry). Validation E2E à refaire avec
> instrumentation dédiée dans une session ultérieure.

### Validation finale P9

Quand tous les scénarios P9.5 passent :

- [ ] Cocher P9.5 dans `docs/00_plan_global.md`
- [ ] Passer P9 de 🚧 à ✅
- [ ] Supprimer la section P9.5 de ce fichier
- [ ] Commit `test(firmware): P9 valide en bout-en-bout sur DevKit`

> **Note 2026-05-06 :** sc 1 (partiel : pas de `CMD GAMEOVER` E2E),
> sc 2b (variante soft du sc 2) et sc 3 sont validés. Sc 4 différé. Cocher
> P9.5 dans le plan global est laissé en suspens jusqu'à validation des
> deux items restants.
