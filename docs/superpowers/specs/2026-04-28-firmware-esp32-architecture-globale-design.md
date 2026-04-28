# Architecture globale du firmware ESP32 — design

**Date :** 2026-04-28
**Auteur :** Silouane (brainstorming assisté)
**Statut :** validé, prêt pour planification d'implémentation
**Portée :** architecture globale du firmware ESP32 uniquement. Le protocole UART détaillé, les implémentations par module, et l'adaptation côté Python sont explicitement hors scope (specs ultérieurs).

## 1. Contexte

Quoridor 6×6 sur plateau physique, architecture bi-processeur :

- **Raspberry Pi** : moteur de jeu Python (`quoridor_engine/`) + IA minimax + interface console.
- **ESP32-WROOM** (Freenove) : pilotage du matériel.
- **Communication** : UART0 (GPIO1/3) en câble direct.
- **PCB v2** commandée le 2026-04-28, mapping figé (cf. `hardware/AUDIT_PCB_V2.md`).

Hardware piloté par l'ESP32 :

- Matrice 6×6 de boutons (12 GPIO directs : 6 colonnes IO0/4/16/17/5/18, 6 lignes IO13/14/27/26/25/33).
- LEDs (probablement WS2812B) sur pin 27.
- 2 moteurs Nema 17 via drivers A4988 commandés par MCP23017 I2C (adresse 0x20, port A = moteur Y, port B = moteur X).
- Servo SG90 sur IO32 (PWM).
- Liaison UART0 vers RPi.

Le PCB étant figé, le firmware doit s'adapter aux contraintes existantes (UART2 indisponible, GPIO16/17 consommés par la matrice boutons).

## 2. Décisions architecturales

### 2.1 Niveau d'abstraction de l'ESP32

**Décision :** ESP32 = exécutant moyen niveau, "interprète d'intentions et orchestrateur hardware".

**Frontière précise :**

- L'ESP32 **connaît** : coordonnées de plateau (row/col 0-5), types de mur (H/V), primitives sémantiques (`PLACE_WALL`, `MOVE_PAWN`, `HIGHLIGHT_CELLS`, `SET_TURN_INDICATOR`), interprétation des clics (1 clic bref = intention de déplacement, 2 clics simultanés dans une fenêtre de 50 ms = intention de mur).
- L'ESP32 **ne connaît pas** : les règles de Quoridor, le nombre de murs restants par joueur, à qui c'est le tour, quels coups sont légaux.
- Le RPi reste **maître absolu** : il reçoit les *intentions* émises par l'ESP32, les valide selon les règles, puis renvoie soit un ordre d'animation confirmé, soit un refus (NACK).

**Justification :**

- Le timing temps-réel local (push WS2812B, pulses moteurs A4988, debounce boutons) ne peut pas être déporté via UART à 115200 bauds — donc l'ESP32 doit avoir de l'intelligence locale, peu importe le découpage choisi.
- Une approche stateless (ESP32 = simple pont GPIO) inonderait l'UART (~1000 trames/s pour animer 36 LEDs à 30 fps) et ferait dépendre les animations de la latence série.
- Une approche full autonome (ESP32 embarque le moteur de jeu) duplique le code Python sans gain.
- Le moyen niveau permet en bonus le **mode démo** (animations autonomes au boot si RPi absent) et une **séparation propre des responsabilités** entre cerveau (RPi) et exécutant (ESP32), utile pour le debug et les tests modulaires.

### 2.2 Modèle d'exécution

**Décision : modèle hybride sur les deux cœurs ESP32.**

- **Core 1** (cœur Arduino par défaut) : superloop coopératif. Modules `ButtonMatrix`, `LedDriver`, `LedAnimator`, `UartLink`, `GameController`. Aucun `delay()`, aucune boucle non bornée.
- **Core 0** : tâche FreeRTOS unique dédiée à `MotionControl`. Elle consomme une queue de commandes de trajectoire postée par `GameController` et signale fin via une queue de retour.

**Watchdog `esp_task_wdt` activé sur les deux cœurs**, timeout 5 s. Tout freeze > 5 s déclenche un reboot ESP32 et un retour propre à `BOOT`.

**Justification :**

- Une approche FreeRTOS multi-tâches générale introduit des risques disproportionnés (race conditions, deadlocks, conflits avec le timing critique WS2812B) pour le besoin réel de ce projet.
- Une approche superloop pure forcerait des "freeze" pendant les déplacements moteurs longs (plusieurs secondes), dégradant l'UX.
- L'hybride exploite les deux cœurs ESP32 : pulses moteurs sur Core 0 sans perturber animations LEDs et scan boutons sur Core 1.

**Plan B technique :** si l'intégration FreeRTOS introduit des bugs réels difficiles à diagnostiquer (frames LED corrompues malgré sections critiques, race conditions sur queue, débordement stack), bascule sur **superloop pur** : les mouvements moteurs deviennent bloquants côté loop principale, les animations LED sont gelées sur un pattern statique pendant les mouvements. Cette bascule est explicitement autorisée et documentée.

### 2.3 Découpage en modules

**Décision : 6 modules + le sketch principal, sans interfaces virtuelles.**

```
firmware/
├── arduino_quoridor.ino     // setup() + loop() + lancement tâche moteurs
├── ButtonMatrix.{h,cpp}     // scan 6x6 + debounce + détection clic 1 / 2 cases simultanées
├── LedDriver.{h,cpp}        // pilote bas niveau WS2812B, buffer trame, push atomique
├── LedAnimator.{h,cpp}      // animations haut niveau (highlight, spinner, erreur, démo)
├── MotionControl.{h,cpp}    // tâche FreeRTOS : moteurs A4988 via MCP23017 + servo + homing
├── UartLink.{h,cpp}         // parsing trames RPi, sérialisation intentions, file de commandes
└── GameController.{h,cpp}   // FSM globale, orchestration des autres modules, mode démo
```

**Responsabilités :**

- `ButtonMatrix` : scan colonnes/lignes en non-bloquant, debounce logiciel (~20 ms), détection de clic simple, détection de 2 boutons pressés dans une fenêtre de 50 ms = "intention mur", masquage des boutons collés.
- `LedDriver` : couche bas niveau WS2812B. Maintient un buffer de trame, expose un `push()` atomique qui désactive les interruptions le temps strict du transfert. Indépendant de la sémantique du jeu.
- `LedAnimator` : couche haut niveau. Mappe (row, col) → indice LED. Gère les animations en machines à états locales (frame courante, durée, transition). Pilote `LedDriver` via son buffer.
- `MotionControl` : exécute des trajectoires XY (calcul des pas, pulses STEP/DIR via MCP23017, supervision fins de course, gestion ENABLE) et le servo. Vit dans une tâche FreeRTOS dédiée Core 0. Communique avec `GameController` par 2 queues (commandes entrantes, réponses sortantes : DONE / ERROR_<code>).
- `UartLink` : parsing des trames RPi en non-bloquant (assemblage progressif depuis le buffer série), file FIFO des commandes décodées, fonctions de sérialisation pour les trames sortantes (intentions, ACK, ERROR).
- `GameController` : FSM globale (cf. §2.4), orchestration. Lit les intentions de `ButtonMatrix`, les commandes UART de `UartLink`, dispatche vers `LedAnimator` et `MotionControl`. Gère mode démo et mode connecté.

**Justification :**

- Un découpage minimal (3 modules) ferait dégénérer le `GameController` en "fichier-monde" (UART + moteurs + FSM mélangés).
- Un découpage par couche d'abstraction (HAL/animations/protocol/game) demanderait des interfaces virtuelles C++ pour vraiment isoler — overhead injustifié sur ce projet.
- La séparation `LedDriver` / `LedAnimator` est **délibérée** : le driver gère le timing critique, l'animator décide *quoi* afficher. Cela permet de remplacer le driver (autre type de LED) ou de tester l'animator avec un driver mock.

### 2.4 Machine à états globale (`GameController`)

```
BOOT
  ├─ test I2C MCP23017 (write/read sur registre IODIRA)
  ├─ ping LedDriver (push d'une frame de test invisible)
  ├─ lecture initiale matrice (détection éventuels boutons collés)
  ├─ homing moteurs XY (recherche fins de course origine)
  ├─ succès complet → WAITING_RPI
  └─ échec d'une étape → ERROR (code spécifique, LED rouge fixe, attend reset)

WAITING_RPI
  ├─ envoie HELLO périodique sur UART (toutes les 200 ms)
  ├─ ACK reçu < 3 s → CONNECTED
  └─ timeout 3 s sans ACK → DEMO (état terminal jusqu'au reset)

DEMO
  ├─ animations LED autonomes (rainbow idle, démo de cycle de jeu factice)
  ├─ scan boutons actif : un clic déclenche une animation locale (feedback)
  ├─ aucune trame UART émise (à part éventuel debug)
  └─ état terminal : sortie uniquement par reset matériel

CONNECTED
  ├─ état neutre : LEDs reflètent le dernier ordre RPi (highlight, indicateur de tour)
  ├─ trame CMD_* reçue (PLACE_WALL, MOVE_PAWN, HIGHLIGHT, etc.) → traitement → EXECUTING
  └─ clic détecté par ButtonMatrix → BUTTON_INTENT_PENDING

(la surveillance KEEPALIVE — détection de perte UART — est active dans CONNECTED,
BUTTON_INTENT_PENDING et EXECUTING ; cf. §4 Règles transverses)

BUTTON_INTENT_PENDING
  ├─ intention envoyée au RPi (MOVE_REQUEST(row,col) ou WALL_REQUEST(h|v,row,col))
  ├─ flash doux sur la(les) case(s) cliquée(s) (feedback "en cours de validation")
  ├─ ACK + ordre d'animation → EXECUTING
  ├─ NACK (coup illégal) → flash rouge bref sur la case → CONNECTED
  ├─ timeout 500 ms → flash orange bref → CONNECTED, incrémente compteur timeouts consécutifs
  └─ 3 timeouts consécutifs → ERROR (ERR_UART_LOST suspecté)

EXECUTING
  ├─ une commande RPi est en cours d'exécution :
  │     animation LED (par LedAnimator) + éventuelle séquence MotionControl + servo
  ├─ scan boutons gelé (les clics sont ignorés, pas bufferisés)
  ├─ fin (DONE de MotionControl + animation terminée) → envoie DONE au RPi → CONNECTED
  └─ erreur hardware pendant l'exécution → ERROR (code spécifique)

ERROR (puits)
  ├─ entrée possible depuis n'importe quel état
  ├─ actions immédiates :
  │     - moteurs : stop pulses + désactivation A4988 via pin ENABLE (relâche couple)
  │     - servo : neutralisation (signal PWM neutre)
  │     - LED : pattern rouge distinct + clignotement codé indiquant le code d'erreur
  ├─ envoie ERR_<code> au RPi via UART (best effort)
  ├─ ne traite plus aucune commande UART entrante sauf CMD_RESET
  └─ sortie : CMD_RESET (reboot logiciel ESP.restart()) ou reset matériel → BOOT
```

**Décisions clés :**

- **Pas de transition DEMO ↔ CONNECTED à chaud.** La détection RPi se fait au boot uniquement. Toute perte UART en cours de partie → ERROR. Justification : moins de transitions = moins de chemins de code = moins de bugs résiduels. Branchement à chaud écarté pour la fiabilité.
- **`BUTTON_INTENT_PENDING` est un état distinct** de `CONNECTED` (pas un simple flag interne). Justification : transitions explicites, plus facile à débugger, permet un feedback visuel différencié pendant l'attente d'ACK.
- **Timeout ACK : flash orange + escalade.** Premier et second timeout = retour silencieux à `CONNECTED` avec flash orange (le joueur recliquera). 3e timeout consécutif = ERROR (ce n'est plus un hiccup, c'est une défaillance).

## 3. Stratégie d'erreurs hardware

**Principe : toute défaillance détectable → ERROR puits. Pas de récupération automatique.**

| Défaillance | Détection | Code |
|---|---|---|
| Moteur XY ne bouge pas (obstacle, perte de pas) | Timeout sur durée déplacement (théorique × 2) | `ERR_MOTOR_TIMEOUT` |
| Fin de course inattendu pendant trajectoire | Lecture switchs pendant le mouvement | `ERR_LIMIT_UNEXPECTED` |
| Échec homing au boot | Pas de switch après course max × 1.5 | `ERR_HOMING_FAILED` |
| MCP23017 muet (I2C) | NACK / timeout sur `Wire.endTransmission()` | `ERR_I2C_NACK` |
| ≥ 3 boutons collés simultanés | Compteur dans le scan matrice | `ERR_BUTTON_MATRIX` |
| Perte UART | 3 KEEPALIVE consécutifs manqués (3 s) | `ERR_UART_LOST` |
| Test I2C ou LED échoue au boot | Vérification dans BOOT | `ERR_BOOT_<sous-code>` |

**Cas particulier — bouton collé isolé** : 1 ou 2 boutons restés pressés > 5 s sont **masqués** par `ButtonMatrix` (exclus virtuellement de la matrice) sans déclencher ERROR. Robustesse : un bouton mécanique défaillant ne casse pas une partie. Au-delà de 3 boutons collés simultanés, on suspecte un court-circuit matrice et on bascule en ERROR.

**Limites assumées explicitement** (non détectables sans hardware additionnel hors scope) :

- Servo bloqué mécaniquement (pas de feedback de position SG90).
- Mur qui ne monte pas correctement (pas de capteur sur le mur).
- LED grillée (pas de feedback I/O sur WS2812B).

Ces cas sont gérés côté humain pendant la démo : si le défaut est visible, intervention manuelle.

## 4. Règles transverses (fiabilité)

- **Aucun `delay()`** dans la loop principale, dans `LedAnimator`, dans `UartLink`, dans `ButtonMatrix`, dans `GameController`. Seul `MotionControl` (tâche FreeRTOS dédiée) peut utiliser des délais bornés (`delayMicroseconds()` pour le timing pulse moteur).
- **Toute boucle d'attente bornée** par un timeout `millis()`. Aucun `while (condition)` sans condition de sortie temporelle.
- **Watchdog `esp_task_wdt` actif** sur Core 0 et Core 1, timeout 5 s. Chaque module doit "ravitailler" le watchdog en cédant régulièrement la main.
- **Codes d'erreur explicites** envoyés au RPi pour chaque défaillance — facilite le debug pendant la mise au point et les démos.
- **Trame KEEPALIVE unidirectionnelle (RPi → ESP32)** : le RPi envoie un KEEPALIVE toutes les 1 s, l'ESP32 surveille leur réception. Cette surveillance est active dans tous les états où l'ESP32 est censé être connecté au RPi : `CONNECTED`, `BUTTON_INTENT_PENDING` et `EXECUTING`. 3 KEEPALIVE consécutifs manqués → bascule en ERROR (`ERR_UART_LOST`) depuis n'importe lequel de ces trois états. (Le format exact de la trame est défini dans le spec protocole UART, hors scope ici.)

## 5. Paramètres temporels (récapitulatif)

| Paramètre | Valeur | Rationale |
|---|---|---|
| Debounce bouton | ≈20 ms | Pratique commune boutons mécaniques |
| Fenêtre détection 2 boutons simultanés | 50 ms | Compatible appui à deux mains |
| Timeout HELLO au boot (avant DEMO) | 3 s | Laisse le RPi démarrer Python |
| Période KEEPALIVE RPi → ESP32 | 1 s | Détection perte UART en ≤ 3 s |
| Seuil détection perte UART | 3 KEEPALIVE manqués (3 s) | Tolère un hiccup ponctuel |
| Timeout ACK après intention bouton | 500 ms | Couvre validation IA + réseau |
| Seuil escalade ERROR depuis BUTTON_INTENT_PENDING | 3 timeouts consécutifs | Distingue hiccup vs panne |
| Timeout watchdog ESP32 | 5 s | Marge confortable au-dessus du plus long traitement légitime |
| Seuil bouton collé (masquage) | 5 s pressé en continu | Plus long qu'un appui humain crédible |

## 6. Hors scope (specs ultérieurs)

Ce document fige uniquement l'architecture globale. Les sujets suivants seront traités séparément :

- **Protocole UART détaillé** : format exact des trames (binaire vs texte), encodage des commandes, mécanique ACK/NACK, gestion des collisions, framing/checksum. → spec dédié.
- **Implémentation par module** : interfaces précises de `ButtonMatrix`, calibration des moteurs (vitesse, accélération, micro-stepping), palette d'animations LED, mapping coordonnées plateau → indices LED. → un spec par sous-système.
- **Adaptation côté Python** : ajout d'une couche transport série dans `main.py` (mode console actuel préservé pour tests). → spec côté Python.
- **Vérifications hardware au premier branchement** : polarité condensateurs, comportement boot avec BOUTON1, toggle GPIO25 pour LED. → procédure hardware, pas un spec firmware.

## 7. Critères de succès du firmware (à atteindre dans l'implémentation)

- Une partie complète humain vs IA peut se jouer sans plantage du firmware.
- Au minimum 1 heure d'usage continu sans freeze ni reboot watchdog non sollicité.
- Toute défaillance hardware listée au §3 est correctement détectée et rapportée au RPi.
- Le mode DEMO fonctionne sans RPi connecté.
- Le firmware compile et flashe avec l'IDE Arduino standard sur ESP32 (pas d'ESP-IDF natif requis).
- Code lisible par un coéquipier ICAM 3A ne connaissant pas le projet (commentaires en français selon convention projet).
