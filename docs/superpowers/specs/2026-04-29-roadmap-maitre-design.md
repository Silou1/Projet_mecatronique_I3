# Spec brainstorm — ROADMAP maître du projet Quoridor

**Date** : 2026-04-29
**Topic** : Définir la liste des phases globales du projet jusqu'à la démo finale, à inscrire dans `docs/00_plan_global.md`.
**Statut** : ✅ Validé par l'utilisateur

> **Livrable principal** : [`docs/00_plan_global.md`](../../00_plan_global.md) — ce fichier est la trace de la session brainstorm qui a produit la ROADMAP. À supprimer en fin de projet avec le reste de `docs/superpowers/`.

## Contexte

Le projet est passé en revue après une audit complète. Constat : le projet est correctement structuré côté code, mais il **manque un plan global unique** qui tracke l'avancement de bout en bout. Cette session formalise ce plan.

### Contraintes prises en compte

- **Solo dev sur le code** : Silouane est le seul à toucher au Python et au firmware. Les 5 autres membres de l'équipe sont sur la PCB (Jean), la modélisation 3D (Igor + Jean-Baptiste) et les dossiers administratifs (Pauline + Anna).
- **Pas de planning en jours/dates** : la ROADMAP raisonne en *avancement du code*, pas en calendrier. Un objectif réaliste de fin de projet existe (~20 mai 2026) mais n'apparaît pas dans le document.
- **Objectif final = démo complète** : plateau physique entièrement fonctionnel (boutons → IA → moteurs → murs qui montent → réinitialisation par servo). Pas de scope minimum à débattre.
- **Dépendances hardware externes** :
  - ESP32 DevKit nu disponible immédiatement
  - PCB v2 reçue le 10 mai (départ de la phase « bloc PCB »)
  - Mécanique 3D : système XY fonctionnel, levée de murs testée pour 4 murs, plateau complet en cours d'impression

## Décisions de design

### Choix 1 — Approche A : découpage par dépendance hardware

Trois approches étaient possibles :
- **A** Bloc DevKit (faisable maintenant) + Bloc PCB (après 10 mai)
- **B** Découpage strictement chronologique linéaire
- **C** Découpage par couche logicielle (protocole, drivers, intégration, tests)

**A retenue** car elle maximise l'avancement avant l'arrivée de la PCB. Tout le code logiciel (qui est l'essentiel du projet) peut être développé et testé sur le DevKit pendant qu'on attend la PCB.

### Choix 2 — Trois ajustements au découpage initial

Sur la première proposition à 10 phases (P6 à P15), trois ajustements ont été décidés :

1. **Fusion P11 (drivers hardware) + P12 (calibration mécanique)** → un seul P11 « Drivers hardware & calibration ».
   *Raison* : la séparation est artificielle, pour les moteurs A4988 et le servo on développe le driver et on calibre dans le même mouvement. Les autres drivers (matrice boutons, FastLED, MCP23017) n'ont pas de calibration mécanique.

2. **Refactor firmware absorbé dans P7** au lieu d'une phase séparée.
   *Raison* : les bugs et nettoyages éventuels du Plan 1 émergeront naturellement pendant la validation sur cible. Pas besoin d'une phase dédiée.

3. **Règles transversales en en-tête** plutôt que phases distinctes.
   *Raison* : maintenir `pytest` vert, doc à jour, CHANGELOG tenu, fallback hardware → ce sont des règles de fonctionnement valables tout au long du projet, pas des étapes ponctuelles.

→ Résultat : **9 phases** (P6 à P14) au lieu de 10, structure plus dense.

## Structure finale validée

### Règles transversales (s'appliquent à toutes les phases)

- 🟢 **Tests Python verts** à la fin de chaque phase (les 90 tests pytest ne régressent pas)
- 📝 **Documentation à jour au fil de l'eau** dans `docs/` (notamment 05_firmware, 06_protocole_uart, 07_hardware qui évoluent beaucoup)
- 📋 **`CHANGELOG.md` tenu à jour** : une entrée par fin de phase
- 🛟 **Fallback hardware** : si PCB bloquée, continuer en simulation sur DevKit ; si mécanique 3D en retard, tester moteurs en breadboard hors plateau

### Bloc DevKit (avant PCB)

| # | Phase | Sous-tâches principales |
|---|---|---|
| **P6** | Setup environnement firmware | Brancher DevKit, drivers USB-série, premier `pio run -t upload`, Serial Monitor |
| **P7** | Validation Plan 1 sur cible (+ refactor) | 7 scénarios de TESTS_PENDING.md, correction des bugs trouvés, suppression de TESTS_PENDING.md |
| **P8** | Protocole UART Plan 2 | Designer protocole final, refactor `UartLink`, créer module Python client UART, tests |
| **P9** | Intégration logicielle RPi ↔ ESP32 | Cycle complet en simulation avec DevKit (boutons/LEDs mockés côté ESP32) |

### Bloc PCB (après PCB)

| # | Phase | Sous-tâches principales |
|---|---|---|
| **P10** | Mise sous tension PCB v2 | Vérifications physiques, premier flash, FSM sur vraie carte |
| **P11** | Drivers hardware & calibration | Matrice boutons → FastLED → MCP23017 → A4988 + calibration XY → servo |
| **P12** | Logique de jeu complète sur plateau | Flux bout-en-bout : bouton → IA → moteurs → mur monte ; réinitialisation servo |
| **P13** | Tests d'intégration & robustesse | Parties bout-en-bout, tests de stress (perte UART, watchdog, parties longues) |
| **P14** | Livrable final | Doc utilisateur, doc technique finalisée, soutenance, nettoyage `superpowers/`, tag |

## Suivi d'avancement

L'état précis de chaque phase et sous-phase vit dans [`docs/00_plan_global.md`](../../00_plan_global.md). Ce fichier-ci ne sera plus mis à jour : il est la photographie de la session brainstorm du 2026-04-29.

## Suite

Pas de transition vers `writing-plans` ici : le ROADMAP **est** lui-même un plan de planning, pas un projet à implémenter. Quand on attaquera une phase précise (par exemple P8 « Protocole UART Plan 2 »), c'est à ce moment-là qu'on fera un brainstorm + plan dédié pour cette phase.
