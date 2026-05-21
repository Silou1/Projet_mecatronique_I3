# Firmware ESP32 — bring-up CoreXY

Ce document détaille le firmware actif sur l'ESP32-WROOM : `firmware/src/bringup_l298n_complet.cpp`. Ce sketch unique combine pilotage CoreXY (2 moteurs pas à pas via L298N), servo de placement des murs, et lecture des fins de course. Validé sur breadboard le 2026-05-20 après l'abandon de la PCB v2.

---

## Vue d'ensemble du sketch

```mermaid
flowchart LR
    subgraph FIRM["bringup_l298n_complet.cpp"]
        SETUP["setup()<br/>boot auto"]
        LOOP["loop()<br/>lecture série"]
        SETUP --> LOOP
    end

    subgraph BLOCKS["Modules logiques"]
        MOT["Pilotage moteurs<br/>(IN1..4 + ENA/ENB PWM)"]
        SRV["Pilotage servo<br/>(ESP32Servo)"]
        CAP["Lecture capteurs<br/>(INPUT_PULLUP)"]
        PARSE["Parsing commandes<br/>(GOTO, MUR H/V, ...)"]
        MAT["Matrices murs<br/>(30 H + 30 V)"]
    end

    LOOP --> PARSE
    PARSE --> MOT
    PARSE --> SRV
    PARSE --> CAP
    PARSE --> MAT

    style FIRM fill:#FF9800,color:#fff
```

---

## Séquence de boot automatique

Au reset de l'ESP32, le firmware exécute une séquence rigoureuse en plaçant la sécurité mécanique en premier (servo retracté) avant d'activer les moteurs.

```mermaid
flowchart TD
    BOOT(["Reset / power-on"]) --> S1["1. Servo → 180°<br/>(repos, piston bas)"]
    S1 --> S2["2. Init pins moteurs<br/>(IN1..4, ENA/ENB PWM = 0)"]
    S2 --> S3["3. Init pins capteurs<br/>(INPUT_PULLUP, actifs LOW)"]
    S3 --> S4["4. Désactivation watchdog<br/>(esp_task_wdt_deinit)"]
    S4 --> S5["5. Serial.begin(115200)<br/>Affichage header config"]
    S5 --> S6["6. Activation drivers L298N<br/>(PWM = DUTY_DEFAUT, 40%)"]
    S6 --> S7["7. HOME automatique<br/>(homing X puis Y)"]
    S7 --> S8{"HOME<br/>réussi ?"}
    S8 -->|Oui| READY["Origine (0, 0) établie<br/>position_connue = true"]
    S8 -->|Non| FAIL["Drivers OFF<br/>(sécurité mécanique)"]
    READY --> WAIT(["loop() : attente<br/>commandes série"])
    FAIL --> WAIT

    style BOOT fill:#4CAF50,color:#fff
    style S1 fill:#FFEB3B,color:#000
    style FAIL fill:#f44336,color:#fff
    style READY fill:#81C784,color:#000
    style WAIT fill:#2196F3,color:#fff
```

> **Sécurité critique** : le servo est mis à 180° (piston rétracté) **avant** toute activation des moteurs, pour éviter qu'un mur déjà levé n'entre en collision avec le chariot pendant le homing.

---

## Procédure HOME (homing CoreXY)

Le homing établit l'origine (0, 0) du chariot en se déplaçant vers les fins de course X- puis Y-, en exploitant la **convention CoreXY** : combiner les sens de rotation des deux moteurs pour obtenir un mouvement axial pur.

```mermaid
flowchart TD
    HOME_START(["HOME"]) --> AXE_X["HOME axe X"]

    AXE_X --> X_PRECHK{"Capteur X<br/>déjà LOW ?"}
    X_PRECHK -->|Oui| X_FREE["Libération :<br/>50 pas vers X+<br/>(M1 et M2 sens opposés)"]
    X_PRECHK -->|Non| X_APPROACH
    X_FREE --> X_APPROACH

    X_APPROACH["Approche vers X- :<br/>1 pas à la fois<br/>(M1 et M2 sens opposés)"]
    X_APPROACH --> X_READ{"Capteur X<br/>= LOW ?"}
    X_READ -->|Non| X_LIMIT{"Pas max<br/>4000 atteint ?"}
    X_LIMIT -->|Non| X_APPROACH
    X_LIMIT -->|Oui| HOME_FAIL(["Échec HOME<br/>timeout"])
    X_READ -->|Oui| X_BACK["Recul 20 pas<br/>(libère le capteur)"]
    X_BACK --> AXE_Y

    AXE_Y["HOME axe Y"]
    AXE_Y --> Y_PRECHK{"Capteur Y<br/>déjà LOW ?"}
    Y_PRECHK -->|Oui| Y_FREE["Libération :<br/>50 pas vers Y+<br/>(M1 et M2 même sens)"]
    Y_PRECHK -->|Non| Y_APPROACH
    Y_FREE --> Y_APPROACH

    Y_APPROACH["Approche vers Y- :<br/>1 pas à la fois<br/>(M1 et M2 même sens)"]
    Y_APPROACH --> Y_READ{"Capteur Y<br/>= LOW ?"}
    Y_READ -->|Non| Y_LIMIT{"Pas max<br/>4000 atteint ?"}
    Y_LIMIT -->|Non| Y_APPROACH
    Y_LIMIT -->|Oui| HOME_FAIL
    Y_READ -->|Oui| Y_BACK["Recul 20 pas"]
    Y_BACK --> ORIGIN(["Origine (0, 0) établie"])

    style HOME_START fill:#FF9800,color:#fff
    style ORIGIN fill:#4CAF50,color:#fff
    style HOME_FAIL fill:#f44336,color:#fff
```

> **Convention CoreXY** mesurée et validée sur la machine :
> - **X pur** : M1 et M2 tournent en **sens opposés** → chariot bouge horizontalement seul
> - **Y pur** : M1 et M2 tournent en **même sens** → chariot bouge verticalement seul
> - **Calibration** : 100 pas full-step = 2 cm. 1 cm = 50 pas, 1 mm = 5 pas.

---

## Boucle principale et commandes série

Une fois le HOME validé, la boucle `loop()` lit le port série caractère par caractère. À chaque saut de ligne, elle dispatche vers le handler de la commande.

```mermaid
flowchart TD
    LOOP_START(["loop()"]) --> READ{"Caractère<br/>dispo ?"}
    READ -->|Non| READ
    READ -->|Oui| BUFFER["Accumule dans<br/>tampon_serie (max 64 chars)"]
    BUFFER --> EOL{"CR / LF<br/>reçu ?"}
    EOL -->|Non| READ
    EOL -->|Oui| DISPATCH

    DISPATCH{"Commande ?"}

    DISPATCH -->|"HOME"| CMD_HOME["Relance homing complet"]
    DISPATCH -->|"GOTO x y"| CMD_GOTO["Déplacement absolu<br/>(bornes 0..900 pas)"]
    DISPATCH -->|"X F/B n"| CMD_X["Axe X pur, n pas"]
    DISPATCH -->|"Y F/B n"| CMD_Y["Axe Y pur, n pas"]
    DISPATCH -->|"LEVER"| CMD_LEVER["Servo → 0°<br/>(mur levé)"]
    DISPATCH -->|"BAISSER"| CMD_BAISSER["Servo → 180°<br/>(piston bas)"]
    DISPATCH -->|"MUR H/V i j"| CMD_MUR["Lookup matrice + GOTO"]
    DISPATCH -->|"TOUR"| CMD_TOUR["Parcourir tous murs<br/>mesurés (NEXT/STOP)"]
    DISPATCH -->|"LIMITS"| CMD_LIM["Lecture capteurs X et Y"]
    DISPATCH -->|"EN ON/OFF"| CMD_EN["Active/coupe drivers"]
    DISPATCH -->|"SPEED us"| CMD_SPEED["Délai inter-pas"]
    DISPATCH -->|"DUTY %"| CMD_DUTY["PWM moteurs<br/>(10..60%)"]
    DISPATCH -->|"STATUS"| CMD_STAT["Position, drivers,<br/>capteurs, etc."]
    DISPATCH -->|"HELP"| CMD_HELP["Affiche aide"]

    CMD_HOME --> ACK["Affichage 'OK' / 'KO'"]
    CMD_GOTO --> ACK
    CMD_X --> ACK
    CMD_Y --> ACK
    CMD_LEVER --> ACK
    CMD_BAISSER --> ACK
    CMD_MUR --> ACK
    CMD_TOUR --> ACK
    CMD_LIM --> ACK
    CMD_EN --> ACK
    CMD_SPEED --> ACK
    CMD_DUTY --> ACK
    CMD_STAT --> ACK
    CMD_HELP --> ACK

    ACK --> READ

    style LOOP_START fill:#2196F3,color:#fff
    style DISPATCH fill:#9C27B0,color:#fff
```

---

## Cycle de placement d'un mur

Le mécanisme exploite les matrices `MURS_H` (30 positions horizontales) et `MURS_V` (30 positions verticales) — un total de 60 positions de murs sur le plateau 6×6 — pré-mesurées en pas depuis l'origine.

```mermaid
flowchart TD
    WALL_REQ(["Commande<br/>MUR H i j  ou  MUR V i j"]) --> LOOKUP["Lookup dans<br/>MURS_H[i][j] ou MURS_V[i][j]"]

    LOOKUP --> CHECK{"Position<br/>mesurée ?"}
    CHECK -->|Non| ERR(["Refusé : position non<br/>encore calibrée"])
    CHECK -->|Oui| MOVE["GOTO x_mur y_mur<br/>(déplacement absolu CoreXY)"]

    MOVE --> ARRIVED["Chariot positionné<br/>sous l'emplacement du mur"]
    ARRIVED --> LIFT["LEVER : servo → 0°<br/>(piston pousse le mur vers le haut)"]
    LIFT --> WAIT_USER{"Mur en place<br/>sur le plateau ?"}
    WAIT_USER -->|En attente| LOWER["BAISSER : servo → 180°<br/>(piston redescend)"]
    LOWER --> DONE(["Cycle terminé,<br/>chariot libre"])

    style WALL_REQ fill:#FF9800,color:#fff
    style DONE fill:#4CAF50,color:#fff
    style ERR fill:#f44336,color:#fff
```

> **Convention servo** : 180° = repos (piston rétracté), 0° = mur levé. Cette convention est mémorisée pour la sécurité : à tout reset, le servo retourne en 180°, donc aucun risque de collision pendant le HOME.

---

## Pins utilisées et contraintes

| Élément | Pins | Rôle |
|---|---|---|
| **Moteur 1 (L298N #1)** | 14, 27, 26, 25 | IN1..4 (phases) |
| Moteur 1 PWM | 33, 32 | ENA, ENB |
| **Moteur 2 (L298N #2)** | 16, 17, 21, 22 | IN1..4 (phases) |
| Moteur 2 PWM | 19, 23 | ENA, ENB |
| **Fin de course X** | 13 | INPUT_PULLUP, actif LOW |
| **Fin de course Y** | 18 | INPUT_PULLUP, actif LOW |
| **Servo SG90** | 4 | PWM (alim 5V externe) |
| **UART0** | TX/RX (USB) | 115200 bauds — debug + futur dialogue avec RPi |

**Limites de sécurité** :
- `PAS_MAX = 10 000` pas par commande
- `GOTO_MAX = 900` pas (limite plateau)
- `HOME_PAS_MAX = 4 000` pas (timeout homing)
- `DUTY` plage 10..60 % (au-delà : risque thermique L298N)
- Drivers coupés au boot **et** si HOME échoue
- Mouvements X/Y refusés si drivers OFF

---

> **Note évolutive** : ce sketch est un firmware de **bring-up validé**. La prochaine étape (Plan P11) consiste à le refactoriser pour qu'il dialogue avec le RPi via le protocole UART Plan 2 (cf. `06_protocole_uart.md`), au lieu de répondre à des commandes texte saisies au monitor série.
