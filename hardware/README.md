# Hardware — Quoridor mécatronique

## État actuel : bring-up breadboard

**Date de pivot : 2026-05-19.**

La PCB v2 (commandée 2026-04-28) a été **abandonnée** suite à une erreur de composant et plusieurs conflits de pins sur le routage (détails dans le postmortem ci-dessous).

Le nouveau câblage se fait **sur breadboard**, avec les composants physiques conservés (ESP32-WROOM, 2× L298N, 2× steppers NEMA17, servo, 2× fins de course, alim 12V).

## Périmètre du bring-up

- 2× moteurs steppers (chaîne CoreXY) pilotés via **2× L298N** (pivot 2026-05-20, voir ci-dessous)
- 1× servo pour le mécanisme de placement des murs
- 2× fins de course (un par axe)

### Pivot driver moteur 2026-05-20 — DRV8825 → L298N

Lors du bring-up moteur 1, les drivers DRV8825 (reçus en remplacement des drivers stepper du spec initial) n'ont jamais pu être réglés : Vref bloqué à 0 V malgré câblage conforme, plusieurs tentatives infructueuses. Pivot vers **L298N** (pont en H générique) le jour de la démo. Pilotage en PWM sur ENA/ENB pour limiter le courant moyen (le L298N n'a pas de régulation interne contrairement au DRV8825).

Compromis assumé : pas de microstepping, vitesse max plus basse, le L298N chauffe à fort DUTY. Acceptable pour la démo P0.

## Documentation

- **Spec et mapping pins ESP32** : [docs/superpowers/specs/2026-05-19-bringup-breadboard-design.md](../docs/superpowers/specs/2026-05-19-bringup-breadboard-design.md) (créée pour la session bring-up)
- **Postmortem PCB v2** : [archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md](archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md) (raisons d'abandon, lessons learned)
- **Datasheet ESP32 (source de vérité GPIO)** : NotebookLM `ESP32 Development Board Pinout Reference Map` (id `7d0bccd1-df3f-456d-99a0-1192766043ba`), interrogeable via le MCP `notebooklm-mcp`

## État de validation breadboard

Au fur et à mesure que les composants sont validés sur breadboard, ils sont listés ici avec leur câblage final et le sketch de test associé. Source de vérité : ce qui est ci-dessous a été testé physiquement, pas seulement spécifié.

### 2026-05-19 — Fin de course 1 (validé)

- **Pin ESP32 :** GPIO 13
- **Câblage :**
  - Une borne du switch → GPIO 13
  - Autre borne du switch → GND
  - **Pas de résistance externe** — pull-up interne de l'ESP32 activé en code (`INPUT_PULLUP`)
- **Sketch de test :** [firmware/src/bringup_limit_switch.cpp](../firmware/src/bringup_limit_switch.cpp)
- **Env PlatformIO :** `bringup_limit_switch` (isolé, n'embarque pas le firmware FSM)
  - Flash : `pio run -e bringup_limit_switch -t upload`
  - Monitor : `pio device monitor`
- **Comportement attendu :** au repos `LIMIT = HIGH (relache)` sur le moniteur série 115200. Appui sur le switch → `LIMIT = LOW (presse)`. Les transitions sont affichées uniquement aux changements d'état.

### 2026-05-20 — Moteur 1 via L298N (validé)

- **Driver utilisé :** L298N (pont en H rouge classique), pas le DRV8825 initialement prévu (voir Pivot driver moteur ci-dessus).
- **Pins ESP32 :**

| Pin L298N | GPIO ESP32 | Rôle |
|---|---|---|
| IN1 | 14 | phase A+ |
| IN2 | 27 | phase A− |
| IN3 | 26 | phase B+ |
| IN4 | 25 | phase B− |
| ENA | 33 | PWM canal A (limite courant moyen) |
| ENB | 32 | PWM canal B |

- **Câblage moteur (NEMA17, conventions StepperOnline) :**
  - OUT1 / OUT2 → bobine A (fils **noir / vert**)
  - OUT3 / OUT4 → bobine B (fils **rouge / bleu**)
- **Alim :** rail +12 V / GND breadboard. Jumpers ENA et ENB du L298N **retirés** (pour permettre le PWM). Jumper 5V_EN **en place** (régulateur 5V interne actif).
- **Sketch de test :** [firmware/src/bringup_motor1_l298n.cpp](../firmware/src/bringup_motor1_l298n.cpp) (séquence full-step 4 phases, PWM limitation courant)
- **Env PlatformIO :** `bringup_motor1_l298n`
  - Flash : `pio run -e bringup_motor1_l298n -t upload`
- **Paramètres validés (2026-05-20) :**
  - `SPEED = 8000` us (délai entre transitions, ~125 pas/s)
  - `DUTY = 60` % (PWM sur ENA/ENB)
  - L298N reste à température acceptable à ces réglages
- **Commandes série utiles :** `EN ON` / `EN OFF`, `M1 F <n>` / `M1 B <n>`, `SPEED <us>`, `DUTY <pct>`, `STATUS`, `HELP`
- **Limites connues :** pas de microstepping (full-step uniquement), couple moyen, vibration audible. Acceptable pour la démo.

### 2026-05-20 — CoreXY complet : M1 + M2 + 2 fins de course + homing (validé)

Cette session étend le bring-up M1 seul à la chaîne CoreXY complète. Sketch unifié remplace les deux sketches isolés précédents (qui restent dispos pour debug ciblé).

- **Moteur 2 via L298N #2** — mêmes spécifications électriques que M1 (jumpers ENA/ENB retirés, jumper 5V_EN en place, alim 12 V partagée).

| Pin L298N #2 | GPIO ESP32 | Rôle |
|---|---|---|
| IN1 | 16 | phase A+ |
| IN2 | 17 | phase A− |
| IN3 | 21 | phase B+ |
| IN4 | 22 | phase B− |
| ENA | 19 | PWM canal A |
| ENB | 23 | PWM canal B |

- **Capteur 2 (fin de course axe Y)** — GPIO 18, `INPUT_PULLUP`, switch entre GPIO et GND, pas de résistance externe (même montage que Capteur 1).

- **Convention CoreXY propre à cette machine (validée expérimentalement) :**
  - **X pur (vers/depuis Capteur 1)** : M1 et M2 en sens **opposés** (ΔA = −ΔB)
  - **Y pur (vers/depuis Capteur 2)** : M1 et M2 en **même** sens (ΔA = ΔB)

  C'est l'**inverse** de la convention CoreXY "standard" (ΔA = ΔX + ΔY, ΔB = ΔX − ΔY). Le sens dépend du routage des courroies et de la disposition des poulies sur cette machine ; le câblage électrique des moteurs est laissé tel quel, c'est le code qui s'adapte.

- **Sketch de test :** [firmware/src/bringup_motors_and_limits.cpp](../firmware/src/bringup_motors_and_limits.cpp)
- **Env PlatformIO :** `bringup_motors_and_limits`
  - Flash : `pio run -e bringup_motors_and_limits -t upload`
- **Commandes série utiles :**
  - `M1 F/B <n>` / `M2 F/B <n>` — un moteur seul (diagonale, **debug uniquement**)
  - `X F/B <n>` / `Y F/B <n>` — axe pur (les 2 moteurs coordonnés)
  - `LIMITS` / `LIMITS WATCH` — lecture des fins de course
  - `HOME` — homing CoreXY : approche Capteur 1, recul 20 pas, puis idem Capteur 2
  - `EN ON/OFF`, `SPEED <us>`, `DUTY <pct>`, `STATUS`, `HELP`
- **Comportement HOME validé :**
  - Pas garde-fou `HOME_PAS_MAX = 4000`
  - Reculs `HOME_RECUL_PAS = 20` après contact, `HOME_LIBERATION = 50` si capteur déjà LOW au lancement
  - Course mesurée au premier homing : ~553 pas en X, ~506 pas en Y entre le centre de la table et la butée (utile comme borne basse pour le dimensionnement logiciel ultérieur)
- **Comportement diagonal de M1/M2 seuls :** documenté dans l'aide du sketch. M1 ou M2 isolé produit un mouvement diagonal (X±Y) — utile pour vérifier qu'un moteur tourne et qu'aucune phase n'est inversée, mais **jamais à utiliser pour homing**.

### 2026-05-20 — Servo SG90 + intégration complète (validé)

Sketch d'intégration qui combine CoreXY + 2 fins de course + servo, avec tracking de position et commande `GOTO`. C'est le sketch utilisé pour préparer le cycle complet de placement d'un mur.

- **Servo SG90 (piston mécanisme de placement des murs)**

| Fil servo | Vers | Note |
|---|---|---|
| Signal (orange) | GPIO 4 ESP32 | PWM 50 Hz, signal 3.3V OK pour SG90 |
| V+ (rouge) | rail +5V alim **externe** dédiée | pas le 5V de l'ESP32 |
| GND (marron) | GND alim externe **ET** GND ESP32 | masse commune obligatoire |

- **Convention mécanique servo :**
  - **180° = position de REPOS** (piston bas, plateau en sécurité)
  - **0° = MUR LEVÉ** (piston haut)
  - Toute autre position au boot **casse le mécanisme**.

- **Sécurité boot :** dans le sketch `bringup_full`, l'init servo est la **toute première** opération de `setup()` (avant `Serial.begin`, avant l'init moteurs). La fenêtre entre l'alimentation de l'ESP32 et la mise en signal PWM à 180° est de l'ordre de 50 ms. Pendant cette fenêtre le servo n'a pas de couple mais ne bouge pas tout seul.

- **Règle opérationnelle :** toujours faire `BAISSER` avant de couper l'alimentation. Comme ça la position physique à l'instant de la coupure = 180°, et au prochain boot le code réécrit 180° par-dessus 180° → aucun mouvement.

- **Calibration mécanique (validée 2026-05-20) :**
  - **100 pas = 2 cm pile** sur X et Y (full-step, `SPEED=8000 us`, `DUTY=60 %`, L298N + NEMA17)
  - Donc **1 pas = 0.2 mm**, **1 cm = 50 pas**, **1 mm = 5 pas**
  - Conversion à utiliser pour donner les positions des murs en cm puis convertir en pas pour `GOTO`

- **Sketch de test :** [firmware/src/bringup_full.cpp](../firmware/src/bringup_full.cpp)
- **Env PlatformIO :** `bringup_full` (dépend de `madhephaestus/ESP32Servo`)
  - Flash : `pio run -e bringup_full -t upload`

- **Commandes série spécifiques à l'intégration :**
  - `GOTO <x> <y>` — déplacement absolu (en pas, depuis l'origine HOME). Sequentiel X puis Y. Bornes logicielles `GOTO_X_MAX = 700`, `GOTO_Y_MAX = 700`.
  - `LEVER` — servo → 0° (lève un mur)
  - `BAISSER` — servo → 180° (position de repos)
  - `SERVO <angle>` — angle arbitraire 0..180 (debug)
  - + toutes les commandes du sketch `bringup_motors_and_limits` (HOME, X/Y F/B, M1/M2 F/B, LIMITS, EN, SPEED, DUTY, STATUS, HELP)

- **Cycle de test cible :** `EN ON` → `HOME` → `GOTO x y` → `LEVER` → `BAISSER`. Validé manuellement le 2026-05-20 : les déplacements X et Y sont précis au pas près, le servo passe correctement de 180° à 0° et inversement.

### 2026-05-20 — Moteur 1 via DRV8825 (validé, isolé)

Reprise du bring-up DRV8825 après avoir analysé un montage qui fonctionne sur le même hardware (autre groupe ICAM). Les deux hypothèses sur l'échec précédent ont été **confirmées** : pont `SLP–RST` manquant **et** alim `VDD` logique non câblée. En les corrigeant + en ajoutant un condo 100 µF sur VMOT, le driver fonctionne du premier coup.

Périmètre de cette validation : **un seul moteur (M1) en isolation**. Le CoreXY complet et le sketch d'intégration `bringup_full` tournent **encore en L298N** ; la migration des deux drivers + réintégration CoreXY est l'étape suivante.

- **Pins ESP32 (3 GPIO/moteur) :**

| Pin DRV8825 | GPIO ESP32 | Note |
|---|---|---|
| STEP | 14 | impulsion = 1 pas (front montant) |
| DIR | 27 | sens de rotation |
| EN | 26 | **actif LOW** (LOW = driver alimenté) |
| VDD | 3V3 ESP32 | alim logique, **obligatoire** (oublié à la 1re tentative) |
| SLP | 3V3 (via pont avec RST) | doit être HIGH pour réveiller le driver |
| RST | 3V3 (via pont avec SLP) | doit être HIGH pour activer les sorties |
| M0 / M1 / M2 | non connectés | full step (200 pas/tour) |

- **Câblage puissance :**
  - VMOT → rail +12 V avec **condo électrolytique 100 µF** entre VMOT et GND au plus près du driver (**obligatoire** : sans lui les pics de flyback claquent le DRV8825).
  - GND logique + GND alim 12 V + GND ESP32 tous sur le même rail.
  - 1A / 1B → bobine A du NEMA17, 2A / 2B → bobine B.
  - **Ne jamais débrancher le moteur sous tension** (idem, tue le driver).

- **Calibration Vref (point critique) :**
  - Formule DRV8825 : `Vref = I_bobine × 5 × R_sense`. Avec R100 (= 0,1 Ω) sur ce module : `Vref = I × 0,5`.
  - À mesurer **moteur débranché, 12 V actif**, multimètre entre la vis du potentiomètre et GND.
  - **Point de départ sûr : Vref = 0,25 V (~0,5 A par bobine)**, largement suffisant pour faire tourner un NEMA17 à vide.
  - Maximum recommandé pour ce module sans flux d'air forcé : 0,5 V (~1 A par bobine). Au-delà, le driver entre en thermal shutdown.

- **Sketch de test :** [firmware/src/bringup_motor1.cpp](../firmware/src/bringup_motor1.cpp) (existait depuis la 1re tentative, pin EN corrigé 33 → 26 pour ce câblage)
- **Env PlatformIO :** `bringup_motor1`
  - Flash : `pio run -e bringup_motor1 -t upload`

- **Commandes série utiles :**
  - `EN ON` / `EN OFF` — active / coupe le driver (important pour la thermique, voir ci-dessous)
  - `M1 F <n>` / `M1 B <n>` — n pas dans un sens ou l'autre (200 = 1 tour complet)
  - `SPEED <us>` — demi-période STEP en µs, défaut 1000 (= 500 Hz). Plage 50–10000.
  - `STATUS`, `HELP`

- **Gestion thermique (le DRV8825 chauffe vite) :**
  - **Couper EN entre les mouvements** (`EN OFF` après chaque pas). Au repos, le driver maintient le courant dans les bobines = dissipation continue. Pour le firmware d'intégration, prévoir une coupure automatique de EN après ~500 ms d'immobilité.
  - **Ventilation forcée** : un petit fan 5 V dirigé sur le heatsink fait gagner 20–30 °C.
  - **Microstepping** (1/4 ou 1/8) lisse le profil de courant et diminue les pics thermiques — à câbler sur M0/M1/M2 lors de la phase d'intégration CoreXY.
  - Pour un usage prolongé à Vref > 0,3 V sans ventilation, la thermique devient le facteur limitant.

- **À valider lors de l'intégration CoreXY DRV8825 (étape suivante) :**
  - Comportement à 2 moteurs avec alim 12 V partagée (les pics de courant des deux drivers peuvent se cumuler).
  - Calibration `100 pas = 2 cm` mesurée en L298N : devrait rester identique en full-step DRV8825 (même moteur, même mécanique, même nombre de pas/tour), à reconfirmer.
  - Comportement HOME — le profil de courant DRV8825 est plus carré que le L298N PWM, donc le moteur perd moins de pas à basse vitesse.

### Pistes pour la prochaine itération driver moteur

**Statut au 2026-05-20 :** DRV8825 validé sur M1 isolé (voir section ci-dessus). Reste à faire pour finaliser la migration :

- Câbler le 2ᵉ DRV8825 sur M2 (STEP=16, DIR=17, EN=21) et libérer les pins L298N #2 (22, 19, 23, 25, 32, 33).
- Adapter `bringup_motors_and_limits.cpp` et `bringup_full.cpp` au pilotage 2-fils-par-pas (STEP/DIR/EN) au lieu de la séquence full-step 4 phases + PWM utilisée pour le L298N.
- Implémenter la coupure auto de EN après immobilité (gestion thermique).
- Câbler M0/M1/M2 vers 3V3/GND selon la table de vérité DRV8825 pour activer le microstepping (cible : 1/4 ou 1/8 pour le silence et la fluidité).

**Avantages déjà observés (sur M1) :** silence quasi total vs L298N, mouvement fluide sans saccades, libération de 3 GPIO par moteur (6 au total pour le CoreXY).

## Archive

- [archive/pcb-v2-2026-04-28-ABANDONNEE/](archive/pcb-v2-2026-04-28-ABANDONNEE/) : ancienne PCB v2, audit complet, source EasyEDA, et postmortem

## Sketch de production validé (2026-05-20)

Le sketch [firmware/src/bringup_l298n_complet.cpp](../firmware/src/bringup_l298n_complet.cpp) est le sketch de référence à jour. Il intègre :

- HOME automatique au boot (capteurs X et Y, recul 20 pas)
- Commandes série : `X F/B <n>`, `Y F/B <n>` (CoreXY), `GOTO <x> <y>`, `LEVER`, `BAISSER`, `MUR H/V <i> <j>`, `TOUR`, `NEXT`, `STOP`, `LIST`, `STATUS`
- Matrices murs `MURS_H[5][6]` et `MURS_V[6][5]` (60 positions, 18 mesurées au 2026-05-20)
- Convention CoreXY validée : X = M1+M2 sens opposés, Y = M1+M2 même sens
- Convention servo : 180° = REPOS, 0° = MUR LEVÉ
- Calibration : 100 pas = 2 cm pile (X et Y)

Flash :
```bash
cd firmware && pio run -e bringup_l298n_complet -t upload && pio device monitor -e bringup_l298n_complet
```

Tout le contexte validé : [docs/superpowers/specs/2026-05-20-bringup-breadboard-validation.md](../docs/superpowers/specs/2026-05-20-bringup-breadboard-validation.md).
