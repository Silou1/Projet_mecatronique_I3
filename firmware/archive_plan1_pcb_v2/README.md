# Archive — Plan 1 firmware + PCB v2

**Date d'archivage : 2026-05-19** (suite à l'abandon de la PCB v2).

## Contenu

| Fichier | Description |
|---|---|
| `Pins.h.original` | Mapping pins ESP32 au moment de l'abandon (matrice boutons 6×6, LED data, servo, I2C MCP23017). Référence historique. |
| `INTEGRATION_TESTS_PENDING.md` | Scénarios E2E P8.6 et P9.5 (Plan 2 protocole UART + intégration RPi-ESP32). Statut au 2026-05-06 : 8 scénarios validés en pytest, le 9e partiellement. |
| `tests_devkit_archive/run_p86_manual.py` | Harness manuel P8.6 (Serial Monitor avec scénarios 1–8 du protocole UART). Exécuté avec succès le 2026-05-06, porté en pytest ensuite. |
| `tests_devkit_archive/run_p95_e2e.py` | Harness E2E P9.5 (GameSession + UartClient sur DevKit réel). Scénarios 1–3 validés, 4 différé. Référence bonne pratique pour CLI inject, threads daemon, keepalive. |

## Pourquoi c'est archivé et pas supprimé

Ces fichiers documentent du travail **validé** côté **protocole UART** et **architecture FSM**, qui reste pertinent même si la chaîne hardware (moteurs/servo/fins de course) doit être recâblée. Les harness manuels servent de référence pour les futurs tests E2E sur breadboard.

## Pourquoi le PCB v2 a été abandonné

Voir [../../hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md](../../hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md).

## Ce qui n'a PAS été archivé (reste actif dans `firmware/src/`)

- `tests_devkit/_uart_helpers.py` : helpers Python génériques (crc16, find_devkit_port, etc.), conservés.

## src_plan2/ — Code firmware Plan 2 (ajouté 2026-05-20)

Lors de la clôture de la session bring-up breadboard (2026-05-20), l'architecture Plan 2 a été archivée ici. Raisons :

1. **PCB v2 abandonnée** : le mapping `Pins.h` et toute la structure modules (matrice boutons + LEDs WS2812 pilotées par ESP32) étaient câblés pour la PCB v2.
2. **Split GPIO décidé le 2026-05-20** : le RPi pilote désormais les 36 boutons + 36 LEDs WS2812. L'ESP32 ne pilote plus que CoreXY + servo + capteurs. Donc `ButtonMatrix`, `LedDriver`, `LedAnimator` côté ESP32 sont obsolètes.
3. **`GameController` et `MotionControl`** étaient stubs (sleep + DONE). À refaire en s'appuyant sur la logique validée dans `bringup_l298n_complet.cpp`.
4. **`UartLink`** reste pertinent : protocole UART Plan 2 (framing + CRC-16 + seq/ack). Sera réutilisé comme base pour Plan 3 (intégration RPi ↔ ESP32 sur breadboard), avec adaptations.

### Contenu de `src_plan2/`

- `main.cpp` : entrée Plan 2 (WDT 5 s + init modules + loop FSM)
- `Pins.h` : header vide post-abandon PCB v2 (seulement `PIN_LED_DEBUG`)
- `ButtonMatrix.{cpp,h}` : scan 6x6 boutons (sera côté RPi désormais)
- `LedDriver.{cpp,h}` + `LedAnimator.{cpp,h}` : WS2812 + patterns (côté RPi désormais)
- `GameController.{cpp,h}` : FSM 7 états (BOOT/WAITING_RPI/DEMO/CONNECTED/...)
- `MotionControl.{cpp,h}` : interface Command/Result FreeRTOS (stub, jamais validé sur cible)
- `UartLink.{cpp,h}` : **à réutiliser pour Plan 3** (protocole UART validé en pytest)
