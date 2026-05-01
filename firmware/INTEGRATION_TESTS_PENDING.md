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
