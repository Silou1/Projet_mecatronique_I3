# Tests d'intégration P8.6 — pending DevKit

> **Cible :** lundi 2026-05-04, retour du DevKit ESP32. À exécuter avant de cocher P8.6 dans le plan global.

## Préparatifs

- [ ] Récupérer le DevKit ESP32 auprès du camarade
- [ ] Brancher le DevKit au Mac via USB
- [ ] Vérifier que le port apparaît : `pio device list` doit lister un `/dev/cu.SLAB_USBtoUART` ou `/dev/cu.usbserial-*`
- [ ] Compiler et flasher le firmware Plan 2 :
  ```
  cd firmware && pio run -t upload
  ```
- [ ] Ouvrir le Serial Monitor :
  ```
  pio device monitor
  ```
- [ ] Confirmer la séquence boot attendue :
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
- [ ] L'ESP32 émet `<BOOT_START>`, `<SETUP_DONE>`, `<HELLO|v=1>` au boot
- [ ] Envoi manuel via Serial Monitor : `<HELLO_ACK|seq=0|ack=2|crc=XXXX>` (CRC à calculer)
- [ ] Vérifier transition `[FSM] -> state 3` (CONNECTED)

### 2. Cycle nominal humain
- [ ] Au prompt Serial Monitor, taper : `BTN 3 4` puis Entrée
- [ ] Vérifier réception : `<MOVE_REQ 3 4|seq=N|crc=XXXX>`
- [ ] Répondre : `<ACK|seq=0|ack=N|crc=XXXX>`
- [ ] Vérifier `[FSM] -> state 5` (EXECUTING) et finalement `<DONE|seq=M|ack=N|crc=XXXX>`

### 3. Cycle nominal IA
- [ ] Envoyer : `<CMD MOVE 2 5|seq=10|crc=XXXX>`
- [ ] Vérifier `<DONE|seq=N|ack=10|crc=XXXX>` après quelques secondes

### 4. Idempotence CMD
- [ ] Envoyer `<CMD MOVE 2 5|seq=20|crc=XXXX>`
- [ ] Attendre `<DONE|seq=N|ack=20|crc=XXXX>`
- [ ] **Renvoyer la même trame** `<CMD MOVE 2 5|seq=20|crc=XXXX>` (avec le même seq)
- [ ] Vérifier qu'AUCUNE séquence `[MOT] exec command` n'apparaît une 2ᵉ fois
- [ ] Vérifier qu'un nouveau `<DONE|seq=M|ack=20|crc=XXXX>` est renvoyé immédiatement

### 5. Trame corrompue
- [ ] Envoyer une trame avec CRC bidon : `<KEEPALIVE|seq=0|crc=0000>`
- [ ] Vérifier qu'aucune réaction (pas de transition d'état, log éventuel `getRejectedCount()` incrémenté)

### 6. Trame > 80 octets
- [ ] Envoyer une ligne `<` suivie de 90 caractères puis `>`
- [ ] Vérifier rejet silencieux

### 7. Mode injection test (sans framing)
- [ ] Taper `BTN 5 5` (sans `<>`)
- [ ] Vérifier que l'ESP32 émet bien `<MOVE_REQ 5 5|seq=N|crc=XXXX>`

### 8. Émission ERR + réémission périodique
- [ ] Forcer une erreur : envoyer `<CMD MOVE 99 99|seq=30|crc=XXXX>` (coordonnées hors plateau, devrait causer `MOTOR_TIMEOUT` ou similaire selon stub)
- [ ] Vérifier `<ERR ...|seq=N|ack=30|crc=XXXX>` initial
- [ ] Vérifier que `<ERR ...|seq=N+k|crc=XXXX>` (sans ack=) est réémis toutes les 1 s
- [ ] Envoyer `<CMD_RESET|seq=0|crc=XXXX>`
- [ ] Vérifier reboot complet (nouveau `<BOOT_START>`)

### 9. Test Python ↔ ESP32 réel (script automatisé)

Créer `tests/integration/test_uart_devkit.py` (à écrire à ce moment-là, pas dans P8.5) qui ouvre le port série réel et joue les scénarios 1-8 ci-dessus en automatique.

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

**Pré-requis matériel :** DevKit ESP32-WROOM connecté en USB. Plateau physique
non requis : les boutons restent injectables via `BTN x y` au Serial Monitor.

**Pré-requis logiciel :**

- Firmware Plan 2 + stubs P9 flashés : `cd firmware && pio run -t upload`
- Python : `python main.py --mode plateau --port /dev/ttyUSB0 --debug`

### Scénario 1 — Partie nominale PvIA via injection manuelle

1. Lancer Python en mode plateau avec `--debug`.
2. Vérifier le handshake `HELLO` → `HELLO_ACK`.
3. Au Serial Monitor, injecter `BTN 4 3` (déplacement j1).
4. Vérifier côté Python : `ACK` pour le coup `('deplacement', (4, 3))`.
5. Vérifier au Serial Monitor : `<MOVE_REQ 4 3|...>` puis `<ACK|...|ack=N|...>`.
6. Tour IA : Python doit envoyer `CMD MOVE r c` ou `CMD WALL h r c`, puis recevoir `DONE`.
7. Continuer au moins 5 tours.
8. En fin de partie, vérifier `CMD GAMEOVER <winner>` puis `DONE`.
9. Le port se ferme proprement.

### Scénario 2 — Coupure UART en milieu de partie

1. Lancer une partie en mode plateau.
2. Après 2-3 coups, débrancher le câble USB pendant 5 secondes.
3. Rebrancher.
4. Vérifier côté Python : `ERR UART_LOST` récupérable → `CMD_RESET` → nouveau handshake.
5. Continuer la partie : les nouveaux `BTN x y` doivent fonctionner.
6. Limitation acceptée P9 : les LEDs et la position visuelle ne sont pas restaurées après reboot.

### Scénario 3 — IA pose un mur

1. Lancer avec `--difficulty difficile` pour augmenter la probabilité d'un mur.
2. Jouer jusqu'à ce que l'IA pose un mur.
3. Vérifier côté Python : `CMD WALL h r c` ou `CMD WALL v r c`.
4. Vérifier au Serial Monitor : `FSM CMD WALL stub: ...` puis `DONE`.
5. Le tour rebascule à `j1`.

### Scénario 4 — Idempotence d'une CMD perdue

1. Instrumenter temporairement le firmware pour simuler la perte du premier `DONE`.
2. Reflasher.
3. Lancer une partie et observer le retry Python : même `CMD`, même `seq`, après timeout.
4. Vérifier que la commande n'est pas exécutée deux fois côté firmware.
5. Retirer l'instrumentation et reflasher avant de cocher le scénario.

### Validation finale P9

Quand tous les scénarios P9.5 passent :

- [ ] Cocher P9.5 dans `docs/00_plan_global.md`
- [ ] Passer P9 de 🚧 à ✅
- [ ] Supprimer la section P9.5 de ce fichier
- [ ] Commit `test(firmware): P9 valide en bout-en-bout sur DevKit`
