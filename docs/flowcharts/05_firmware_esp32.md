# Firmware ESP32 — bring-up et boucle de commandes

Le firmware tient dans **un seul sketch monolithique** :
[`firmware/src/bringup_l298n_complet.cpp`](../../firmware/src/bringup_l298n_complet.cpp).
Il est piloté à 100 % par commandes texte reçues sur deux canaux
interchangeables (USB-série et Wi-Fi TCP) et sert une seule logique de
dispatch via `traiter(cmd, Stream*)`.

Le firmware ne contient **aucune logique de jeu** : pas de matrice de
boutons, pas de validation de coup, pas de connaissance des règles
Quoridor. Il exécute uniquement des actions hardware (déplacement,
servo, LEDs) demandées par le Mac.

---

## Séquence de boot

```mermaid
flowchart TD
    POWER([Power-on / Reset]) --> LED_INIT[strip.begin<br/>setBrightness 102<br/>strip.clear + show]
    LED_INIT --> SERVO_INIT[servo.attach pin 4<br/>servo.write 180°<br/>= REPOS, sécurité mécanique]
    SERVO_INIT --> PIN_INIT[Init pins moteurs<br/>drivers OFF par défaut]
    PIN_INIT --> SERIAL_INIT[Serial.begin 115200]
    SERIAL_INIT --> WD_OFF[esp_task_wdt_deinit<br/>watchdog désactivé]
    WD_OFF --> HOME[homing_complet]

    HOME --> HOME_OK{HOME<br/>réussi ?}
    HOME_OK -->|Oui| AP[WiFi.softAP<br/>Quoridor-ESP32 / quoridor2026]
    HOME_OK -->|Non| HOME_FAIL[Drivers OFF<br/>attend HOME manuel via série]

    AP --> TCP[wifi_server.begin port 3333]
    TCP --> LOOP([Boucle principale])
    HOME_FAIL --> LOOP

    style POWER fill:#4CAF50,color:#fff
    style LOOP fill:#2196F3,color:#fff
    style LED_INIT fill:#FFD600
    style SERVO_INIT fill:#FF9800,color:#fff
    style HOME_FAIL fill:#f44336,color:#fff
```

**Garanties de sécurité au boot** :

1. Le servo est positionné à **180° (REPOS) en tout premier**, avant
   l'initialisation des moteurs. Évite qu'un piston levé bloque le
   chariot CoreXY.
2. Les drivers L298N sont **OFF par défaut** et n'activent les bobines
   que lors d'un mouvement demandé.
3. Le watchdog matériel ESP32 est désactivé (sketch monothread avec
   `delayMicroseconds` bloquants).

---

## Procédure HOME (par axe)

Le HOME se fait axe par axe : X d'abord, Y ensuite. Chaque axe utilise
le moteur CoreXY combiné de manière à ne bouger que sur cet axe.

```mermaid
flowchart TD
    START([HOME axe N]) --> CHECK{Capteur<br/>déjà LOW ?}
    CHECK -->|Oui| FREE[Libération 50 pas<br/>dans le sens opposé]
    CHECK -->|Non| APPROACH
    FREE --> APPROACH

    APPROACH[Approche pas à pas<br/>vers le capteur<br/>max 4000 pas]
    APPROACH --> TOUCHED{Capteur<br/>LOW ?}
    TOUCHED -->|Non, < 4000 pas| APPROACH
    TOUCHED -->|Oui| BACK[Recul 20 pas<br/>marge de sécurité]
    TOUCHED -->|Non, 4000 pas atteints| FAIL[Échec, drivers OFF]

    BACK --> OK([Axe N à 0])

    style START fill:#2196F3,color:#fff
    style OK fill:#4CAF50,color:#fff
    style FAIL fill:#f44336,color:#fff
```

**Convention CoreXY (validée machine)** :

| Mouvement | Action moteurs | Capteur |
|---|---|---|
| X pur | M1 et M2 en **sens opposés** | Pin 13 (`PIN_LIMIT_X`) |
| Y pur | M1 et M2 dans le **même sens** | Pin 18 (`PIN_LIMIT_Y`) |

Origine (0, 0) en bas-gauche après HOME complet, X croissant à droite,
Y croissant vers le haut. Voir
[`../hardware/calibration.md`](../hardware/calibration.md).

---

## Boucle principale `loop()`

```mermaid
flowchart TD
    LOOP([loop iteration]) --> NEW{Nouvelle<br/>connexion TCP ?}
    NEW -->|Oui| ACCEPT[Ferme ancien client<br/>accepte nouveau<br/>« dernier client gagne »]
    NEW -->|Non| SERIAL

    ACCEPT --> SERIAL{Char Serial<br/>dispo ?}
    SERIAL -->|Oui| READ_S[Accumule dans tampon_serie<br/>jusqu'au \\n]
    SERIAL -->|Non| WIFI

    READ_S --> DISP_S[traiter tampon_serie, Serial]
    DISP_S --> WIFI

    WIFI{Client TCP connecté<br/>avec char dispo ?}
    WIFI -->|Oui| READ_W[Accumule dans tampon_wifi<br/>jusqu'au \\n]
    WIFI -->|Non| WD

    READ_W --> DISP_W[traiter tampon_wifi, wifi_client]
    DISP_W --> WD

    WD{Client TCP silencieux<br/>plus de 30 s ?}
    WD -->|Oui| KILL[wifi_client.stop<br/>libère le socket]
    WD -->|Non| LOOP
    KILL --> LOOP

    style LOOP fill:#2196F3,color:#fff
    style DISP_S fill:#FF9800,color:#fff
    style DISP_W fill:#FF9800,color:#fff
    style KILL fill:#9E9E9E,color:#fff
```

**Politique « dernier client gagne »** : si un client TCP est déjà connecté
quand un nouveau arrive, l'ancien est fermé. Simplifie la gestion d'état
sans nécessiter de multi-client.

**Watchdog applicatif** : un client TCP silencieux pendant 30 s est
expulsé. Évite les sockets fantômes laissés par un client mal débranché.

---

## Cycle d'une commande `WALL`

```mermaid
sequenceDiagram
    participant MAC as Mac (webapp)
    participant FW as Firmware

    MAC->>FW: WALL H 2 3\n

    Note over FW: traiter() : parse + bornes [0..4]
    Note over FW: wall_lever('H', 2, 3)<br/>j = 4 - 2 = 2

    alt MURS_H[2][3] mesuré
        FW->>FW: goto_xy(x, y)<br/>déplacement CoreXY
        FW->>FW: servo.write(0°) + delay 400 ms<br/>LEVER
        FW->>FW: servo.write(180°) + delay 400 ms<br/>BAISSER
    else _NA
        Note over FW: saute (raised inchangé)
    end

    alt MURS_H[2][4] mesuré
        FW->>FW: goto_xy(x, y) + LEVER + BAISSER
    end

    FW->>MAC: WALL OK H 2 3 raised=2\n
```

Détail dans [`06_protocole.md`](06_protocole.md) (côté protocole) et
dans [`05_firmware.md`](../06_firmware.md) (textuel complet).

---

## Catalogue des commandes implémentées

| Commande | Effet | Détail |
|---|---|---|
| `PING` | Répond `PONG` | Handshake |
| `HOME` | Relance le homing | Réinitialise position connue |
| `STATUS` | Affiche état drivers + position + SPEED + DUTY + limits | Debug |
| `LIMITS` | Lecture instantanée des 2 capteurs | Debug |
| `LIMITS WATCH` | Lecture continue (Enter pour sortir) | Debug |
| `EN ON` / `EN OFF` | Active / coupe les 2 drivers | Sécurité manuelle |
| `GOTO <x> <y>` | Déplacement absolu en pas, [0..900] | Mouvement bas-niveau |
| `X F/B <n>`, `Y F/B <n>` | Axe pur, n pas, sens forward/backward | Mouvement bas-niveau |
| `M1 F/B <n>`, `M2 F/B <n>` | Moteur isolé, invalide la position connue | Debug câblage |
| `LEVER` / `BAISSER` | Servo 0° / 180° | Pose mur manuel |
| `SERVO <angle>` | Angle arbitraire [0..180] | Calibration servo |
| `SPEED <us>` | Délai entre pas [500..10000] | Tuning vitesse |
| `DUTY <pct>` | PWM driver [10..60] | Tuning couple |
| `WALL <H\|V> <r> <c>` | Lève un mur Quoridor | Cf. cycle ci-dessus |
| `MUR <H\|V> <i> <j>` | Va à la position physique du mur (sans lever) | Calibration positions |
| `TOUR`, `NEXT`, `STOP` | Parcours interactif des positions mesurées | Validation visuelle |
| `LIST` | Statut de remplissage des matrices `MURS_H`/`MURS_V` | Suivi calibration |
| `DEMO [N]` | N murs aléatoires parmi les mesurés, levée + redescente | Démonstration |
| `LED <idx> <r> <g> <b>` | Met à jour le pixel `idx` dans le buffer | Affichage |
| `LEDSHOW` | Push atomique vers la strip | Affichage |
| `LEDCLEAR` | Éteint toutes les LEDs | Affichage |
| `LEDBRIGHT <0..255>` | Modifie la luminosité globale | Affichage |
| `HELP` | Liste les commandes | Aide |

---

## Pinout (résumé)

| GPIO | Rôle |
|---|---|
| 14, 27, 26, 25 | M1 IN1..IN4 (L298N #1) |
| 33, 32 | M1 ENA, ENB (PWM) |
| 16, 17, 21, 22 | M2 IN1..IN4 (L298N #2) |
| 19, 23 | M2 ENA, ENB (PWM) |
| 13 | Fin de course X (`INPUT_PULLUP`) |
| 18 | Fin de course Y (`INPUT_PULLUP`) |
| 4 | Servo SG90 (pulse 500–2500 µs) |
| 15 | Strip WS2812B (36 LEDs) |

Détails complets : [`../hardware/pinout.md`](../hardware/pinout.md).

---

## Pourquoi ce sketch monolithique

- **Démarrage prévisible** : aucune dépendance à un système de fichiers,
  pas de mode init complexe, le code de chaque commande est dans la
  même unité de compilation.
- **Debug direct** : tout est accessible via le moniteur série.
- **Évolution sans recompilation des couches Python** : ajout d'une
  commande = ajout d'un cas dans `traiter()`, sans changement
  d'interface Mac.
- **Pas de FreeRTOS task** : monothread, `delayMicroseconds` bloquants.
  Suffit pour les besoins du Quoridor (un coup à la fois, pas de
  contrainte temps réel sub-milliseconde).

Pour les évolutions envisagées et écartées (multi-tâches, FSM boutons,
protocole CRC), voir [`../decisions.md`](../decisions.md).
