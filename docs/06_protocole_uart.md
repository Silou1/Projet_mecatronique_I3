# Protocole UART — RPi ↔ ESP32

> **Statut** : 🚧 *À définir lors du Plan 2 firmware. Cette page est un placeholder qui consolide ce qui existe déjà et liste les questions ouvertes.*

## Contexte

- Liaison série **UART0** entre RPi 3/4 et ESP32-WROOM
- Vitesse : **115200 bauds**, fin de ligne `LF`
- Cette UART est **partagée avec le port USB** de debug de l'ESP32 → attention à ne pas confondre debug et trafic protocolaire

## Plan 1 — Protocole texte simplifié (actuel)

Le firmware Plan 1 utilise un protocole texte ligne-par-ligne, suffisant pour les tests mais sans framing ni intégrité.

### Trames émises par l'ESP32

| Trame | Sens | Description |
|---|---|---|
| `BOOT_START` | ESP32 → RPi | Émise en début de `setup()` |
| `SETUP_DONE` | ESP32 → RPi | Fin du `setup()` |
| `HELLO` | ESP32 → RPi | Émise toutes les 200 ms en état `WAITING_RPI` |
| `MOVE_REQ <ligne> <col>` | ESP32 → RPi | Demande de validation d'un coup détecté sur la matrice |
| `DONE` | ESP32 → RPi | Fin d'exécution motrice |
| `ERR <code>` | ESP32 → RPi | Erreur (ex : `ERR UART_LOST`) |

### Trames reçues par l'ESP32

| Trame | Sens | Description |
|---|---|---|
| `HELLO_ACK` | RPi → ESP32 | Confirmation du RPi, fait passer ESP32 en `CONNECTED` |
| `KEEP` | RPi → ESP32 | Keepalive (à envoyer toutes les ≤ 3 s pour rester `CONNECTED`) |
| `ACK` | RPi → ESP32 | Validation d'un `MOVE_REQ` |
| `NACK` | RPi → ESP32 | Refus d'un `MOVE_REQ` (coup invalide) |
| `CMD MOVE <ligne> <col>` | RPi → ESP32 | Commande directe (typiquement coup de l'IA) |
| `RESET` | RPi → ESP32 | Reboot l'ESP32 depuis l'état `ERROR` |
| `BTN <ligne> <col>` | (test) | Injection d'un appui bouton via Serial Monitor pour tests sans hardware |

### Limites

- Pas de checksum / CRC
- Pas de framing binaire (lignes de texte arbitraires)
- Pas de versioning du protocole
- Pas de séquencement / retransmission
- Pas de gestion d'ID de commande (impossible de corréler `MOVE_REQ` ↔ `ACK` si plusieurs en vol)

## Plan 2 — Protocole binaire à concevoir (📋 à faire)

Questions à trancher :

1. **Format binaire ou texte enrichi** ? (texte = debuggable au Serial Monitor, binaire = plus compact et fiable)
2. **Framing** : COBS, SLIP, byte stuffing, longueur fixe ?
3. **Intégrité** : CRC-8, CRC-16, simple checksum XOR ?
4. **Versioning** : champ version dans chaque trame ?
5. **ID de séquence** : pour matcher requêtes/réponses
6. **Timeouts et retransmissions** : politique côté RPi ? côté ESP32 ?
7. **Bibliothèques candidates** : `pyserial` côté RPi (déjà standard), `MicroProtoSockets` ou framing custom côté ESP32

## Pour aller plus loin

- Implémentation actuelle ESP32 : [firmware/src/UartLink.{cpp,h}](../firmware/src/)
- Côté Python (à écrire) : module `quoridor_engine/uart_client.py` ou équivalent — voir Phase P8 dans [00_plan_global.md](00_plan_global.md)
- Scénarios de test série : [firmware/TESTS_PENDING.md](../firmware/TESTS_PENDING.md)
