# Pinout ESP32-WROOM

> ⚠️ **INVARIANT — Source de vérité : `firmware/src/bringup_l298n_complet.cpp`.**
> Toute modification de pin ici doit être synchronisée avec le sketch
> et **validée physiquement** sur le plateau avant d'être propagée à la doc.

## Module cible

ESP32-WROOM (Freenove DevKit). Wi-Fi natif intégré au SoC, USB-série pour debug et flash.

## Moteurs CoreXY (2× L298N)

### Moteur M1 (L298N #1)

| Signal | GPIO |
|---|---|
| IN1 | 14 |
| IN2 | 27 |
| IN3 | 26 |
| IN4 | 25 |
| ENA (PWM) | 33 |
| ENB (PWM) | 32 |

### Moteur M2 (L298N #2)

| Signal | GPIO |
|---|---|
| IN1 | 16 |
| IN2 | 17 |
| IN3 | 21 |
| IN4 | 22 |
| ENA (PWM) | 19 |
| ENB (PWM) | 23 |

## Capteurs de fin de course

| Capteur | GPIO | Mode |
|---|---|---|
| Fin de course X | 13 | `INPUT_PULLUP` (LOW = appuyé) |
| Fin de course Y | 18 | `INPUT_PULLUP` (LOW = appuyé) |

## Servo SG90 (levée de mur)

| Signal | GPIO ou alim |
|---|---|
| Signal | 4 |
| V+ | alimentation 5 V externe (pas via ESP32) |
| GND | commun |

Pulses : 500 µs (0°) à 2500 µs (180°).

## Pins libres et précautions pour futurs ajouts

Pour tout ajout de périphérique (Wi-Fi futur, boutons, LEDs, expander I²C), **vérifier
d'abord dans NotebookLM `7d0bccd1-df3f-456d-99a0-1192766043ba`** (« ESP32 Development Board
Pinout Reference Map ») avant câblage. Précautions générales :

- **Strapping pins** (GPIO 0, 2, 5, 12, 15) : à éviter en sortie au boot, état au reset
  conditionne le mode de démarrage.
- **Pins ADC2** : indisponibles pour la lecture analogique quand le Wi-Fi est actif
  (ne pas y mettre de capteurs analogiques si Wi-Fi prévu).
- **GPIO 34-39** : input-only, pas de pull-up interne.
- **Le Wi-Fi natif ESP32-WROOM n'occupe pas de GPIO** (la radio est intégrée au SoC),
  mais peut interférer avec les pins ADC2 listées dans la datasheet.
