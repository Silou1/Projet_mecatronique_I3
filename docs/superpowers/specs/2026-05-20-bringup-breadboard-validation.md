# Spec — Validation du bring-up breadboard

> **Status : VALIDÉ — 2026-05-20**
>
> CoreXY + servo + capteurs + matrices murs fonctionnels sur breadboard. Sketch de production : [firmware/src/bringup_l298n_complet.cpp](../../../firmware/src/bringup_l298n_complet.cpp). Spec de design initial (CLOSED) : [2026-05-19-bringup-breadboard-design.md](2026-05-19-bringup-breadboard-design.md).

## Contexte

Ce document consolide l'état final du bring-up breadboard à la fin de la session du **2026-05-20**. Il sert de référence unique pour la session suivante (Plan 3 — intégration RPi ↔ ESP32 via UART).

Historique court :
- **2026-04-28** : PCB v2 commandée, livrée avec erreur composants (PCA9548A reçu à la place du MCP23017 attendu).
- **2026-05-19** : PCB v2 abandonnée. Pivot vers breadboard. Spec design 2026-05-19.
- **2026-05-20 matin** : tentative migration A4988 → DRV8825 (microstepping). 2 cartes DRV8825 défectueuses sur 3, retour aux L298N.
- **2026-05-20 après-midi** : CoreXY + servo + capteurs validés en L298N. Matrices murs implémentées (18/60 positions mesurées).

## Composants validés

| Composant | Quantité | Rôle | État |
|---|---|---|---|
| ESP32-WROOM (Freenove DevKit) | 1 | Microcontrôleur principal | ✅ |
| Driver L298N | 2 | Pilotage des steppers (full-step 4-phase, ENA/ENB PWM) | ✅ |
| Moteur stepper NEMA17 | 2 | Système CoreXY (déplacement piston) | ✅ |
| Servo SG90 | 1 | Mécanisme de levée des murs | ✅ |
| Fin de course mécanique | 2 | Détection origine X et Y | ✅ |
| Alimentation 12V | 1 | VMOT partagé entre les 2 L298N | ✅ |
| Alimentation 5V externe | 1 | V+ servo (PAS le 5V ESP32) | ✅ |

## Mapping pins ESP32 définitif

| Fonction | GPIO | Note |
|---|---|---|
| M1 (L298N #1) IN1 | 14 | bobine A |
| M1 (L298N #1) IN2 | 27 | bobine A |
| M1 (L298N #1) IN3 | 26 | bobine B |
| M1 (L298N #1) IN4 | 25 | bobine B |
| M1 (L298N #1) ENA | 33 | PWM (limitation courant) |
| M1 (L298N #1) ENB | 32 | PWM (limitation courant) |
| M2 (L298N #2) IN1 | 16 | bobine A |
| M2 (L298N #2) IN2 | 17 | bobine A |
| M2 (L298N #2) IN3 | 21 | bobine B |
| M2 (L298N #2) IN4 | 22 | bobine B |
| M2 (L298N #2) ENA | 19 | PWM (limitation courant) |
| M2 (L298N #2) ENB | 23 | PWM (limitation courant) |
| Capteur fin de course X | 13 | INPUT_PULLUP, switch → GND |
| Capteur fin de course Y | 18 | INPUT_PULLUP, switch → GND |
| Servo SG90 (Signal) | 4 | LEDC PWM 50 Hz, pulse 500-2500 µs |
| LED debug intégrée | 2 | Diagnostics visuels |

**Jumpers L298N** : retirer les jumpers ENA et ENB sur chaque L298N (sinon ENA/ENB court-circuité à 5V, PWM inopérant). Garder le jumper 5V_EN en place (régulateur 5V alimenté depuis VMOT 12V).

**Masses communes obligatoires** : GND ESP32 + GND alim 12V + GND alim 5V servo doivent être reliés sur le même rail breadboard.

## Conventions machine (validées 2026-05-20)

### CoreXY

| Mouvement | Direction M1 | Direction M2 |
|---|---|---|
| X pur (+) | forward | backward (sens OPPOSÉS) |
| X pur (-) | backward | forward |
| Y pur (+) | forward | forward (MÊME sens) |
| Y pur (-) | backward | backward |

**Capteur X-** sur GPIO 13 (origine côté X-). **Capteur Y-** sur GPIO 18 (origine côté Y-).

### Servo

| Position | Angle | Sens physique |
|---|---|---|
| REPOS | 180° | Piston bas (état stable, aucune charge mécanique) |
| MUR LEVÉ | 0° | Piston haut (pousse le levier qui lève le mur) |

Au boot, le servo est ramené à 180° dès la toute première ligne du `setup()` (sécurité mécanique).

## Calibration

**Validée par mesure au mètre ruban le 2026-05-20** :

| Distance | Pas full-step |
|---|---|
| 1 mm | 5 pas |
| 1 cm | 50 pas |
| **2 cm** | **100 pas** ✅ pile (référence) |

Course mécanique mesurée :
- X : ~110 mm (~ 550 pas)
- Y : ~101 mm (~ 505 pas)

**Vitesse par défaut** : SPEED = 10000 µs (demi-période STEP, donne ~ 50 pas/s en full-step). Modifiable via commande `SPEED <us>` entre 500 et 10000.

**Duty cycle ENA/ENB par défaut** : DUTY = 40 % (régule courant moteur pour limiter chauffe L298N). Modifiable via commande `DUTY <pct>` entre 10 et 60.

## Sketches actifs

Tous dans `firmware/src/`. Conservés pour test/diagnostic par composant.

| Sketch | Env PlatformIO | Rôle |
|---|---|---|
| `bringup_l298n_complet.cpp` | `bringup_l298n_complet` ou `esp32dev` (défaut) | **Production validée** : HOME auto + GOTO + LEVER + matrices murs |
| `bringup_l298n_indep.cpp` | `bringup_l298n_indep` | Contrôle bas niveau indépendant (M1/M2/servo/capteurs) — diagnostic |
| `bringup_motors_and_limits.cpp` | `bringup_motors_and_limits` | CoreXY + capteurs sans servo (jalon intermédiaire) |
| `bringup_motor1_l298n.cpp` | `bringup_motor1_l298n` | Test M1 isolé en L298N |
| `bringup_servo.cpp` | `bringup_servo` | Test servo SG90 isolé |
| `bringup_limit_switch.cpp` | `bringup_limit_switch` | Test fin de course isolé |

## Sketch de production : `bringup_l298n_complet.cpp`

### Séquence boot automatique

1. Servo positionné à 180° (toute première ligne du `setup()`)
2. Init pins moteurs (drivers OFF par défaut)
3. `Serial.begin(115200)`
4. Activation des 2 drivers (PWM ENA/ENB à DUTY %)
5. **HOME X** : M1 et M2 sens opposés vers capteur GPIO 13, puis recul 20 pas
6. **HOME Y** : M1 et M2 même sens vers capteur GPIO 18, puis recul 20 pas
7. Origine (0, 0) établie
8. Entrée dans la boucle de commandes série

### Commandes série (115200 baud, LF)

| Commande | Effet |
|---|---|
| `HELP` | Liste des commandes |
| `STATUS` | Position actuelle (x, y) + état drivers/servo |
| `HOME` | Re-lance la séquence HOME complète |
| `GOTO <x> <y>` | Déplace le chariot à (x, y) en pas (x, y ∈ [0, 900]) |
| `X F <n>` / `X B <n>` | Mouvement X pur de n pas (forward/backward) |
| `Y F <n>` / `Y B <n>` | Mouvement Y pur de n pas |
| `M1 F <n>` / `M1 B <n>` | M1 seul (debug) |
| `M2 F <n>` / `M2 B <n>` | M2 seul (debug) |
| `LEVER` | Servo à 0° (mur levé) |
| `BAISSER` | Servo à 180° (repos) |
| `SERVO <deg>` | Servo à un angle arbitraire |
| `MUR H <i> <j>` | Va au mur horizontal (i, j) si mesuré dans `MURS_H` |
| `MUR V <i> <j>` | Va au mur vertical (i, j) si mesuré dans `MURS_V` |
| `TOUR` | Démarre le tour automatique de tous les murs mesurés |
| `NEXT` (ou `N`) | Passe au mur suivant dans le tour |
| `STOP` | Stoppe le tour |
| `LIST` | Affiche la grille des murs avec [X]/[. ] (mesurés/non mesurés) + compteur |
| `LIMITS` | État des 2 capteurs (lecture instantanée) |
| `LIMITS WATCH` | Mode surveillance continue capteurs |
| `EN ON` / `EN OFF` | Active/coupe les 2 drivers |
| `SPEED <us>` | Demi-période STEP en µs (500-10000) |
| `DUTY <pct>` | Duty cycle ENA/ENB (10-60 %) |

### Matrices de positions de murs

Le plateau Quoridor 6×6 compte 60 positions de murs au total :
- **30 murs horizontaux** : 6 colonnes × 5 lignes (`MURS_H[5][6]`, accès `MURS_H[j][i]`)
- **30 murs verticaux** : 5 colonnes × 6 lignes (`MURS_V[6][5]`, accès `MURS_V[j][i]`)

Chaque cellule contient les coordonnées `(x, y)` en pas full-step depuis l'origine HOME. Les positions non encore mesurées portent la sentinelle `_NA = {-1, -1}`.

**État au 2026-05-20** : 18 positions mesurées (8 coins + 4 centres + 6 autres), 42 restent à mesurer manuellement.

```
MURS_H (j de 4=haut à 0=bas, i de 0 à 5) :
  j=4 (haut) : (109,777) _NA  _NA  (409,777) _NA  (709,777)
  j=3        : _NA       _NA  _NA  _NA       _NA  _NA
  j=2        : (105,486) _NA  _NA  (482,406) _NA  (709,485)
  j=1        : _NA       _NA  _NA  _NA       _NA  _NA
  j=0 (bas)  : (102, 35) _NA  _NA  (406, 35) _NA  (709, 35)

MURS_V (j de 5=haut à 0=bas, i de 0 à 4) :
  j=5 (haut) : ( 34,707) _NA  (339,711) _NA  (784,705)
  j=4        : _NA       _NA  _NA       _NA  _NA
  j=3        : ( 33,408) _NA  (407,479) _NA  (782,400)
  j=2        : _NA       _NA  _NA       _NA  _NA
  j=1        : _NA       _NA  _NA       _NA  _NA
  j=0 (bas)  : ( 32,110) _NA  (330,107) _NA  (779,105)
```

Les commandes `MUR H/V <i> <j>` et `TOUR` refusent les positions `_NA`.

### Workflow de mesure (42 positions restantes)

Pour qu'un collaborateur complète les matrices :

1. Compiler et flasher : `cd firmware && pio run -e bringup_l298n_complet -t upload`
2. Ouvrir le moniteur série : `pio device monitor -e bringup_l298n_complet`
3. Attendre la fin du HOME auto (~10 s, on voit `origin (0, 0) etablie`)
4. Naviguer manuellement avec `X F/B <n>` et `Y F/B <n>` jusqu'à la position du levier du mur cible
5. Taper `STATUS` pour lire les coordonnées (x, y) en pas
6. Optionnel : `LEVER` puis `BAISSER` pour vérifier que le piston tombe bien sous le levier
7. Noter (x, y) et l'index (i, j) du mur correspondant
8. Éditer `firmware/src/bringup_l298n_complet.cpp`, lignes 140-148 (`MURS_H`) ou 169-177 (`MURS_V`) : remplacer le `_NA` par `{x, y}`
9. Recompiler et flasher
10. Vérifier avec `MUR H/V <i> <j>` ou `LIST`

## Pourquoi le retour à L298N (post-mortem DRV8825)

Tentative DRV8825 le matin du 2026-05-20 pour profiter du microstepping (réduction du bruit, mouvement plus fluide). Configuration testée : STEP/DIR/EN, SLP-RST pontés au 3.3V, M0/M1/M2 à 1/4 step (M0=GND, M1=3V3, M2=GND), Vref calibré pour ~0.5 A/bobine.

Résultat : **2 cartes DRV8825 défectueuses sur 3** (drivers grillés au premier branchement moteur). Causes probables :
- Vref mal réglé (dépassement courant nominal moteur)
- SLP ou RST flottant pendant une fraction de seconde au démarrage
- Clones DRV8825 (Chine) de qualité variable

Décision pragmatique : retour aux L298N (full-step, bruit mais robuste). Les sketches DRV8825 sont conservés dans [firmware/src/archive/drv8825-2026-05-20/](../../../firmware/src/archive/drv8825-2026-05-20/) pour reférence future.

## Architecture firmware actuelle

Le firmware courant n'a **plus** la structure modules (`GameController`, `UartLink`, `MotionControl`, `ButtonMatrix`, `LedDriver`, `LedAnimator`) du Plan 2. Tout est archivé dans [firmware/archive_plan1_pcb_v2/src_plan2/](../../../firmware/archive_plan1_pcb_v2/src_plan2/).

Raisons :
1. PCB v2 abandonnée → mapping `Pins.h` invalide
2. Split GPIO décidé le 2026-05-20 → RPi pilote les 36 boutons + 36 LEDs WS2812 (modules ESP32 obsolètes côté boutons/LEDs)
3. `MotionControl` était stub (sleep + DONE), jamais validé sur cible

`UartLink` reste pertinent (protocole Plan 2 validé en pytest avec MockSerial) et sera la base de la session Plan 3.

## Pistes — session Plan 3 (RPi ↔ ESP32)

À traiter dans la session suivante :

1. **Refonte `UartLink`** sur la base de [firmware/archive_plan1_pcb_v2/src_plan2/UartLink.cpp](../../../firmware/archive_plan1_pcb_v2/src_plan2/UartLink.cpp) (framing + CRC-16 + seq/ack OK).
2. **Nouveau `main.cpp`** qui reprend la logique de `bringup_l298n_complet.cpp` mais avec commandes UART au lieu de commandes série humaines.
3. **Portage matrices `MURS_H` + `MURS_V`** en table de lookup persistante. Compléter les 42 positions restantes par mesure physique.
4. **Adaptation `tests/integration/test_uart_devkit.py`** (déjà existant, 8 scénarios Plan 2) au nouveau firmware.
5. **Procédure de transfert** Mac → RPi3 du moteur Python + webapp (SSH/scp, voir [webapp/README.md](../../../webapp/README.md)).

## Vérifications de cette session

| Vérification | Résultat |
|---|---|
| Compilation `pio run -e esp32dev` (alias bringup_l298n_complet) | SUCCESS |
| Compilation `pio run -e bringup_l298n_complet` | SUCCESS |
| Compilation `pio run -e bringup_l298n_indep` | SUCCESS |
| HOME auto exécuté correctement au boot | ✅ |
| GOTO (x, y) atteint la position en pas attendue | ✅ |
| LEVER / BAISSER actionne le servo aux angles attendus | ✅ |
| Matrices `MURS_H[5][6]` + `MURS_V[6][5]` compilent | ✅ |
| 18 positions mesurées au mètre / observation visuelle | ✅ |
| Aucune référence A4988 / MCP23017 / PCA9548A dans la doc à jour | ✅ |
