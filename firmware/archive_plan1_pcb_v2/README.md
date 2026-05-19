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

- `main.cpp`, `GameController.{cpp,h}`, `UartLink.{cpp,h}` : code mature hardware-agnostic, conservé.
- `MotionControl.{cpp,h}`, `ButtonMatrix.{cpp,h}`, `LedDriver.{cpp,h}`, `LedAnimator.{cpp,h}` : stubs hardware-agnostic, conservés. Seront enrichis dans la session bring-up breadboard ou ultérieures.
- `Pins.h` : vidé (garde uniquement `PIN_LED_DEBUG`). Les pins du nouveau câblage seront définis dans la spec bring-up.
- `tests_devkit/_uart_helpers.py` : helpers Python génériques (crc16, find_devkit_port, etc.), conservés.
