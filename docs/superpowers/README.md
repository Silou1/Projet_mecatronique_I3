# Artefacts de session — specs et plans

Index des **specs** (décisions de design figées) et **plans** (étapes d'implémentation TDD) générés au fil des sessions Claude Code. Cet emplacement est à **nettoyer en fin de projet** (cf. P14.4 du [plan global](../00_plan_global.md)).

## Convention

- **Spec** = ce qu'on construit + pourquoi (décisions architecturales, justifications, alternatives écartées). Lecture utile pendant toute la durée du projet.
- **Plan** = comment on l'implémente, étape par étape (TDD, fichiers à créer/modifier, commandes exactes). Utile pendant l'exécution, archivable une fois la phase terminée.
- **Datage** : préfixe `YYYY-MM-DD-` sur tous les fichiers, suivi d'un nom descriptif court.

## Specs

| Date | Titre | Statut | Phase couverte |
|---|---|---|---|
| 2026-04-28 | [Architecture globale du firmware ESP32](specs/2026-04-28-firmware-esp32-architecture-globale-design.md) | ✅ implémenté (Plan 1 + Plan 2) | P5, P8.3 |
| 2026-04-29 | [Roadmap maître du projet](specs/2026-04-29-roadmap-maitre-design.md) | ✅ traduit en [00_plan_global.md](../00_plan_global.md) | P6–P14 |
| 2026-05-01 | [Protocole UART Plan 2](specs/2026-05-01-protocole-uart-plan-2-design.md) | ✅ implémenté côté Python + ESP32 | P8.1, P8.2 |

## Plans d'implémentation

| Date | Titre | Statut | Phase couverte |
|---|---|---|---|
| 2026-04-28 | [Firmware ESP32 — Plan 1 squelette](plans/2026-04-28-firmware-esp32-plan-1-squelette.md) | ✅ exécuté (commit `044564b`) | P5 |
| 2026-05-01 | [Protocole UART Plan 2 — implémentation](plans/2026-05-01-protocole-uart-plan-2-implementation.md) | 🚧 30 tasks exécutées sur 30, P8.6 reportée au 2026-05-04 | P8.2 → P8.6 |

## Procédure de nettoyage en P14.4

Quand le projet sera prêt à livrer (soutenance), supprimer ce dossier :

```bash
git rm -r docs/superpowers/
git commit -m "chore(docs): suppression des artefacts de session (P14.4)"
```

Les décisions de design qui méritent d'être conservées doivent au préalable être migrées dans les docs principales (`docs/02_architecture.md`, `docs/05_firmware.md`, `docs/06_protocole_uart.md`, etc.).
