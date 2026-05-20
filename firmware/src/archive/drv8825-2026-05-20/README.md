# Sketches DRV8825 — Archive 2026-05-20

Sketches archives le 2026-05-20 lors de la cloture de la session bring-up breadboard.

## Pourquoi

Tentative de migration A4988 -> DRV8825 le matin du 2026-05-20 pour profiter du microstepping.
Resultat : 2 cartes DRV8825 sur 3 defectueuses (drivers grilles, probablement Vref mal regle
ou SLP/RST flottants). Retour aux L298N. Les sketches restent ici pour reference si une
prochaine session reessaie avec de nouveaux drivers.

## Contenu

- `bringup_motor1.cpp` : test moteur 1 isole sur DRV8825 (STEP=14, DIR=27, EN=26)
- `bringup_motor2.cpp` : jumeau pour M2 (STEP=16, DIR=17, EN=21)
- `bringup_motors_indep.cpp` : controle bas niveau 2 drivers DRV8825 + 2 moteurs
- `bringup_driver2_on.cpp` : ultra-minimal, active EN du driver 2 pour calibration Vref
- `bringup_motors_drv8825.cpp` : premier prototype CoreXY sur DRV8825 (HOME + GOTO + microstepping 1/4)

## Lien

Voir `docs/superpowers/specs/2026-05-20-bringup-breadboard-validation.md` pour le contexte
complet (etat valide en L298N, calibration, matrices murs).
