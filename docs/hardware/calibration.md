# Calibration et conventions machine

> ⚠️ **INVARIANT — Source de vérité : commentaires et constantes
> dans `firmware/src/bringup_l298n_complet.cpp`.**

## Conventions axes (CoreXY)

| Mouvement | Action moteurs | HOME via capteur |
|---|---|---|
| X pur | M1 et M2 en **sens opposés** | Capteur X (GPIO 13) |
| Y pur | M1 et M2 dans le **même sens** | Capteur Y (GPIO 18) |

Origine (0, 0) en bas-gauche du plateau (établie après HOME). X croissant vers la droite,
Y croissant vers le haut.

## Calibration pas / distance

Validée physiquement le 2026-05-20.

| Distance | Pas full-step |
|---|---|
| 2 cm | 100 pas |
| 1 cm | 50 pas |
| 1 mm | 5 pas |

Courses utiles validées :

- Axe X : ≈ 110 mm (≈ 550 pas)
- Axe Y : ≈ 101 mm (≈ 505 pas)

Borne logicielle dans le sketch : `GOTO_MAX = 900` pas sur chaque axe (limite de sécurité).

## Servo (levée de mur)

| Position | Angle |
|---|---|
| Repos (piston bas) | 180° |
| Mur levé | 0° |

Configuration PWM :

- Pulse min : 500 µs
- Pulse max : 2500 µs

Délais après commande :

- `LEVER` (passage à 0°) → 400 ms avant l'action suivante
- `BAISSER` (passage à 180°) → 400 ms avant l'action suivante

## Sécurité mécanique

1. Au boot : le servo est positionné à 180° **en tout premier** (avant tout autre setup),
   pour éviter qu'un piston levé ne bloque le chariot CoreXY.
2. Les drivers L298N sont **OFF par défaut**, activés uniquement quand un mouvement est
   demandé (commande `EN ON` ou mouvement explicite).
3. PWM (DUTY) par défaut : 40 % (bornes 10-60 %, configurables via `DUTY <pct>`).
4. Vitesse (SPEED) par défaut : 10000 µs entre pas (bornes 500-10000 µs, configurables
   via `SPEED <us>`).
5. Le watchdog matériel ESP32 est **désactivé** dans le sketch (mouvements bloquants
   `delayMicroseconds`, monothread).

## Comportement HOME

1. Si le capteur visé est déjà à LOW au démarrage du HOME : libération de 50 pas dans le
   sens opposé pour permettre une approche propre.
2. Approche par pas unitaires, maximum 4000 pas avant échec.
3. Au contact (capteur à LOW) : recul de 20 pas pour libérer le capteur et garder une marge.
4. Établissement de l'origine (0, 0) après HOME X puis HOME Y.

## Comportement en cas d'échec HOME

Le sketch coupe les drivers et attend une commande série (`HOME` manuel ou autre commande
de debug). À ce stade, vérifier dans l'ordre :

- Capteurs câblés correctement (état LOW au contact, mode `INPUT_PULLUP`).
- DUTY suffisant pour faire bouger le moteur sous charge (~40 %).
- Pas de blocage mécanique (courroies, fixations).
- Sens de rotation : si le moteur s'éloigne du capteur au lieu de s'en approcher,
  inverser le câblage IN1/IN2 ou IN3/IN4 du L298N concerné.
