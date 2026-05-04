# Protocole UART — RPi ↔ ESP32 (Plan 2)

> **Statut** : ✅ *Plan 2 figé. Implémentation en cours dans P8.*
>
> **Spec de référence** : [`superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md`](superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md). Cette page est un résumé pratique pour l'équipe ; en cas de divergence apparente, le spec fait foi.

## En une phrase

Trames texte framées `<TYPE [args]|seq=N[|ack=M][|v=K]|crc=XXXX>\n`, intégrité CRC-16 CCITT-FALSE, séquencement modulo 256 avec `ack=M` sur les réponses, retry idempotent uniquement sur les `CMD ...` côté RPi (3 essais, 15 s).

## Liaison physique

- **UART0** entre RPi 3/4 et ESP32-WROOM
- **115200 bauds**, fin de ligne `LF`
- Câble direct (pas de bus intermédiaire)
- ⚠️ **Partagée avec le port USB de debug ESP32** : voir §"Co-existence debug" plus bas

## Format des trames

```
<TYPE [arg1 arg2 ...] | seq=N [|ack=M] [|v=K] | crc=XXXX>\n
```

| Champ | Description | Obligatoire ? |
|---|---|---|
| `<` ... `>\n` | Délimiteurs structurels | Oui |
| `TYPE` | Mot-clé MAJUSCULES (ex : `MOVE_REQ`, `CMD`) | Oui |
| Arguments | Mots-clés MAJUSCULES ou entiers décimaux, séparés par espaces | Selon TYPE |
| `seq=N` | Numéro de séquence émetteur (0–255) | Oui |
| `ack=M` | Seq de la requête à laquelle on répond | Sur réponses uniquement |
| `v=K` | Version protocole | Sur `HELLO` uniquement (v=1 actuel) |
| `crc=XXXX` | CRC-16 CCITT-FALSE en hexa MAJUSCULES sur 4 chars | Oui (toujours en dernier) |

**Calcul CRC** : sur les octets entre `<` (exclu) et `|crc=` (exclu).
**Polynôme** : 0x1021, **init** : 0xFFFF, **xorOut** : 0x0000, sans réflexion.
**Implémentation Python** : `binascii.crc_hqx(data, 0xFFFF)` — dans la stdlib.

**Vecteurs de référence figés** (cf. spec §3.5) :

| Input (zone CRC) | CRC attendu |
|---|---|
| `MOVE_REQ 3 4\|seq=42` | `0xAED2` |
| `CMD MOVE 2 5\|seq=43` | `0x8489` |
| `KEEPALIVE\|seq=0` | `0x74D8` |

**Longueur max** : 80 octets (toute trame plus longue est rejetée silencieusement).

## Catalogue des trames

### ESP32 → RPi (8 types)

| TYPE | Args | Quand |
|---|---|---|
| `BOOT_START` | aucun | Tout début de `setup()` |
| `SETUP_DONE` | aucun | Fin du `setup()` |
| `HELLO` | aucun (`v=1` séparé) | Toutes les 200 ms en `WAITING_RPI` |
| `MOVE_REQ` | `<row> <col>` | Détection clic 1 case |
| `WALL_REQ` | `<h\|v> <row> <col>` | Détection clic 2 cases adjacentes |
| `DONE` | aucun | Fin d'exécution d'une `CMD ...` reçue (porte `ack=`) |
| `ERR` | `<code>` | Entrée dans `ERROR` (réémis 1 s, peut porter `ack=`) |

### RPi → ESP32 (10 types)

| TYPE | Args | Quand |
|---|---|---|
| `HELLO_ACK` | aucun | Réponse à `HELLO` (active `CONNECTED`) |
| `KEEPALIVE` | aucun | Toutes les 1 s en session active |
| `ACK` | aucun | Validation d'un `MOVE_REQ`/`WALL_REQ` |
| `NACK` | `<raison>` | Refus d'un `MOVE_REQ`/`WALL_REQ` |
| `CMD MOVE` | `<row> <col>` | Coup IA déplacement |
| `CMD WALL` | `<h\|v> <row> <col>` | Coup IA mur |
| `CMD HIGHLIGHT` | `[<row> <col> ...]` (0 à 8) | Surbrillance ; vide = clear |
| `CMD SET_TURN` | `<j1\|j2>` | Indicateur visuel de tour |
| `CMD GAMEOVER` | `<j1\|j2>` | Fin de partie + servo |
| `CMD_RESET` | aucun | Reset depuis `ERROR` |

### Codes d'erreur (`ERR <code>`)

**Récupérables (auto `CMD_RESET`)** : `UART_LOST`, `BUTTON_MATRIX`
**Non récupérables (alerte humain)** : `MOTOR_TIMEOUT`, `LIMIT_UNEXPECTED`, `HOMING_FAILED`, `I2C_NACK`, `BOOT_I2C`, `BOOT_LED`, `BOOT_HOMING`

### Codes de raison (`NACK <code>`)

`ILLEGAL`, `OUT_OF_BOUNDS`, `WRONG_TURN`, `WALL_BLOCKED`, `NO_WALLS_LEFT`, `INVALID_FORMAT`

## Séquencement et idempotence

- Chaque émetteur (ESP32 et Python) maintient son propre compteur `tx_seq` ∈ [0, 255], incrémenté modulo 256 à chaque trame émise.
- **Sur retry de `CMD ...` côté RPi : on réutilise le même seq** (sinon l'idempotence ne marcherait pas).
- ESP32 stocke `last_cmd_seq_processed` + `last_cmd_result` pour dédup. Si un retry arrive pour la même seq déjà traitée → renvoie `DONE` sans re-exécuter.
- Si retry pendant exécution en cours → ignore en silence (le RPi attendra son timeout).

## Politique de retransmission

| Trame | Retry auto ? |
|---|---|
| `MOVE_REQ` / `WALL_REQ` | Non (l'humain reclique) |
| `CMD ...` | **Oui** : 2 retries (3 essais total), timeout 15 s, idempotent |
| `KEEPALIVE` | Émis périodiquement (1 s) |
| `HELLO` | Réémis périodiquement (200 ms) tant que pas d'`HELLO_ACK` |
| `ERR` | Réémis périodiquement (1 s) tant que ESP32 en `ERROR` |
| `ACK` / `NACK` / `DONE` | Non (réponses) |

## Co-existence debug ↔ protocole

L'UART0 est **physiquement la même** que le port USB de debug ESP32. Pour éviter la collision :

- **Trames protocolaires** : commencent par `<`, se terminent par `>\n`. Émises uniquement via `UartLink::sendFrame()`.
- **Logs de debug** : préfixés `[XXX]`, jamais commençant par `<`. Émis via `UartLink::log("XXX", ...)`.
- **Côté Python** : la condition "premier caractère = `<`" classe la ligne comme protocolaire. Sinon → log ESP32 (affiché dans le buffer debug).
- **Synchronisation FreeRTOS** : un mutex sur les accès à `Serial` empêche l'entrelacement entre Core 0 et Core 1 (sinon une trame en cours d'émission peut être corrompue par un log d'une autre tâche).

## Mode injection test

Pour les tests manuels au Serial Monitor (sans hardware), l'ESP32 accepte **en réception** un format simplifié :

```
BTN <row> <col>\n
```

Cette ligne (sans framing ni CRC) est interprétée comme un clic simulé. **Asymétrique** : seul l'ESP32 accepte ce format, le Python ne l'émet jamais.

## Pour aller plus loin

- **Spec complet** (toutes les décisions, justifications, diagrammes, vecteurs CRC, stratégie de tests) : [`superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md`](superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md)
- **Implémentation côté ESP32** : [`firmware/src/UartLink.{h,cpp}`](../firmware/src/)
- **Implémentation côté Python** : [`quoridor_engine/uart_client.py`](../quoridor_engine/uart_client.py)
- **Tests Python** : [`tests/test_uart_client.py`](../tests/test_uart_client.py)
- **Plan d'implémentation P8** : [`superpowers/plans/2026-05-01-protocole-uart-plan-2-implementation.md`](superpowers/plans/2026-05-01-protocole-uart-plan-2-implementation.md)

---

## Note P9 (2026-05-04) — sous-ensemble émis par la couche d'orchestration

La couche `GameSession` côté RPi (P9) émet uniquement les CMD qui modifient
l'état du jeu : `CMD MOVE`, `CMD WALL`, `CMD GAMEOVER`. Les CMD purement
visuelles (`CMD HIGHLIGHT`, `CMD SET_TURN`) sont réservées à P11, quand les
drivers LEDs réels seront en place. Jusque-là, le firmware les laisse au
catch-all `CMD non-impl`.

Côté firmware, P9 ajoute des stubs pour `CMD WALL` et `CMD GAMEOVER` dans
`GameController::tickConnected` : la trame est acceptée, loggée en debug, puis
un `DONE` est renvoyé immédiatement sans action mécanique. Ces stubs seront
remplacés en P11 par la logique réelle (mouvement moteur pour `WALL`,
déclenchement servo pour `GAMEOVER`).

Aucune modification du format de trame, des codes d'erreur ou du séquencement
n'est introduite par P9. Le protocole reste strictement défini par la spec
[`2026-05-01-protocole-uart-plan-2-design.md`](superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md).
