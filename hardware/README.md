# Hardware — Quoridor mécatronique

## État actuel : bring-up breadboard

**Date de pivot : 2026-05-19.**

La PCB v2 (commandée 2026-04-28) a été **abandonnée** suite à une erreur de composant (PCA9548A reçu au lieu d'un MCP23017) et plusieurs conflits de pins sur le routage.

Le nouveau câblage se fait **sur breadboard**, avec les composants physiques conservés (ESP32-WROOM, 2× A4988, 2× steppers NEMA17, servo, 2× fins de course, alim 12V).

## Périmètre du bring-up

- 2× moteurs steppers (chaîne CoreXY) pilotés via **2× L298N** (pivot 2026-05-20, voir ci-dessous)
- 1× servo pour le mécanisme de placement des murs
- 2× fins de course (un par axe)

### Pivot driver moteur 2026-05-20 — DRV8825 → L298N

Lors du bring-up moteur 1, les drivers DRV8825 (reçus en remplacement des A4988 du spec initial) n'ont jamais pu être réglés : Vref bloqué à 0 V malgré câblage conforme, plusieurs tentatives infructueuses. Pivot vers **L298N** (pont en H générique) le jour de la démo. Pilotage en PWM sur ENA/ENB pour limiter le courant moyen (le L298N n'a pas de régulation interne contrairement au DRV8825).

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

## Archive

- [archive/pcb-v2-2026-04-28-ABANDONNEE/](archive/pcb-v2-2026-04-28-ABANDONNEE/) : ancienne PCB v2, audit complet, source EasyEDA, et postmortem
