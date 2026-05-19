# Hardware — Quoridor mécatronique

## État actuel : bring-up breadboard

**Date de pivot : 2026-05-19.**

La PCB v2 (commandée 2026-04-28) a été **abandonnée** suite à une erreur de composant (PCA9548A reçu au lieu d'un MCP23017) et plusieurs conflits de pins sur le routage.

Le nouveau câblage se fait **sur breadboard**, avec les composants physiques conservés (ESP32-WROOM, 2× A4988, 2× steppers NEMA17, servo, 2× fins de course, alim 12V).

## Périmètre du bring-up

- 2× moteurs steppers (chaîne CoreXY) pilotés via 2× A4988
- 1× servo pour le mécanisme de placement des murs
- 2× fins de course (un par axe)

## Documentation

- **Spec et mapping pins ESP32** : [docs/superpowers/specs/2026-05-19-bringup-breadboard-design.md](../docs/superpowers/specs/2026-05-19-bringup-breadboard-design.md) (créée pour la session bring-up)
- **Postmortem PCB v2** : [archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md](archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md) (raisons d'abandon, lessons learned)
- **Datasheet ESP32 (source de vérité GPIO)** : NotebookLM `ESP32 Development Board Pinout Reference Map` (id `7d0bccd1-df3f-456d-99a0-1192766043ba`), interrogeable via le MCP `notebooklm-mcp`

## Archive

- [archive/pcb-v2-2026-04-28-ABANDONNEE/](archive/pcb-v2-2026-04-28-ABANDONNEE/) : ancienne PCB v2, audit complet, source EasyEDA, et postmortem
