# Firmware ESP32

Architecture du firmware ESP32 et référence des commandes série.

> **Code source** : [`firmware/src/bringup_l298n_complet.cpp`](../firmware/src/bringup_l298n_complet.cpp)

---

## Vue d'ensemble

- **Cible** : ESP32-WROOM (Freenove DevKit).
- **Sketch unique** : `firmware/src/bringup_l298n_complet.cpp` — monolithique, pas de split `.h/.cpp`.
- **Architecture** : monothread (boucle Arduino classique). Les mouvements moteurs bloquent volontairement
  via `delayMicroseconds` — pas de RTOS.
- **Watchdog matériel** : désactivé (les délais de mouvement dépassent les seuils matériels par défaut).
- **Stack** : Arduino C++ via PlatformIO.

---

## Compilation et flash

```bash
# Depuis la racine du dépôt ou depuis firmware/
pio run                      # compiler le sketch de production

pio run -t upload            # compiler + flasher l'ESP32 connecté en USB-C

pio device monitor -b 115200 # moniteur série (terminateur LF)
```

PlatformIO est installé dans `~/.platformio/penv`. CLI uniquement — aucune extension Cursor/VS Code requise.

---

## Mapping GPIO

| Fonction | GPIO |
|---|---|
| M1 (L298N #1) — IN1, IN2, IN3, IN4, ENA, ENB | 14, 27, 26, 25, 33, 32 |
| M2 (L298N #2) — IN1, IN2, IN3, IN4, ENA, ENB | 16, 17, 21, 22, 19, 23 |
| Capteur fin de course X | 13 (INPUT_PULLUP) |
| Capteur fin de course Y | 18 (INPUT_PULLUP) |
| Servo SG90 (signal) | 4 |

Conventions méchaniques (validées machine) :
- **X pur** : M1 et M2 tournent en **sens opposés**.
- **Y pur** : M1 et M2 tournent dans le **même sens**.
- **Servo 180°** = repos (piston bas) ; **Servo 0°** = mur levé.

Calibration et détail des courses : voir [`docs/hardware/calibration.md`](hardware/calibration.md).

---

## Architecture du sketch

### Setup (au boot, dans l'ordre strict)

1. **Servo positionné à 180° en tout premier** — sécurité mécanique : évite qu'un piston levé
   bloque le déplacement CoreXY pendant le homing.
2. Init des pins moteurs — drivers L298N désactivés par défaut, PWM coupé.
3. `Serial.begin(115200)`.
4. Activation des drivers (PWM à la valeur `DUTY` par défaut).
5. **HOME automatique** — axe X (capteur GPIO 13), puis axe Y (capteur GPIO 18).
   Voir [`docs/hardware/calibration.md`](hardware/calibration.md) pour le détail de la séquence.
6. Affichage de l'aide en série, entrée dans la boucle de commandes.

### Loop

Lecture série ligne par ligne (terminateur `\n`, `\r` ignoré). Chaque ligne est passée
à `traiter(String s)` qui parse les tokens et dispatche vers le handler correspondant.

Il n'y a qu'un seul parseur — les commandes debug et les commandes webapp cohabitent
dans la même boucle (voir [Cohabitation des modes](#cohabitation-des-deux-modes)).

---

## Comportement HOME

Résumé de la séquence (détail complet dans [`docs/hardware/calibration.md`](hardware/calibration.md)) :

1. HOME X : M1 et M2 en sens opposés, avance jusqu'à capteur GPIO 13 LOW.
2. Recul de 20 pas.
3. HOME Y : M1 et M2 même sens, avance jusqu'à capteur GPIO 18 LOW.
4. Recul de 20 pas.
5. Origine `(0, 0)` établie — toutes les coordonnées GOTO sont relatives à ce point.

**En cas d'échec** (capteur non atteint en 4 000 pas) : drivers coupés, message d'erreur
en série. La commande `HOME` relancera la séquence complète.

---

## Commandes série supportées

Format : texte ASCII, terminé par `\n`. Tokens séparés par des espaces. Commandes en MAJUSCULES.

### Mode debug / manuel

| Commande | Effet |
|---|---|
| `HOME` | Relance le homing complet (X puis Y) |
| `GOTO <x> <y>` | Déplacement absolu en pas depuis l'origine ; bornes 0..900 |
| `X F <n>` / `X B <n>` | Axe X pur, n pas forward / backward |
| `Y F <n>` / `Y B <n>` | Axe Y pur, n pas forward / backward |
| `M1 F <n>` / `M1 B <n>` | Moteur M1 seul — debug uniquement, **invalide la position courante** |
| `M2 F <n>` / `M2 B <n>` | Moteur M2 seul — debug uniquement, **invalide la position courante** |
| `LEVER` | Servo à 0° (mur levé) |
| `BAISSER` | Servo à 180° (mur baissé = position repos) |
| `SERVO <angle>` | Angle arbitraire 0..180° |
| `LIMITS` | Lecture instantanée des fins de course X et Y |
| `LIMITS WATCH` | Lecture continue des fins de course (appuyer sur Enter pour sortir) |
| `EN ON` / `EN OFF` | Active / coupe les deux drivers L298N |
| `SPEED <us>` | Délai entre deux pas en µs (bornes 500..10 000, défaut 10 000) |
| `DUTY <pct>` | Rapport cyclique PWM en % (bornes 10..60, défaut 40) |
| `STATUS` | État actuel : drivers, position, paramètres, état des capteurs |
| `LIST` | Taux de remplissage des matrices `MURS_H` et `MURS_V` |
| `TOUR` / `NEXT` / `STOP` | Tournée de validation des positions mesurées |
| `DEMO [N]` | N murs aléatoires parmi les positions mesurées, levée + redescente (défaut 10) |
| `HELP` | Affiche l'aide en série |

### Mode webapp

| Commande | Réponse série |
|---|---|
| `PING` | `PONG` |
| `WALL <H\|V> <row> <col>` | `WALL OK <H\|V> <r> <c> raised=<n>` ou `WALL ERR <raison>` |

Pour la sémantique complète du protocole webapp, voir [`docs/07_protocole.md`](07_protocole.md).

### Cohabitation des deux modes

Le sketch ne distingue pas les deux modes — un seul parseur traite toutes les commandes.
Il est possible d'ouvrir un moniteur série (`pio device monitor`) et de taper des commandes
de debug (ex. `STATUS`, `LIMITS`) pendant que la webapp envoie des commandes `WALL`.
Utile pour intercaler du diagnostic sans interrompre la session webapp.

---

## Plan d'ajout Wi-Fi (phase 5 — prévu, non implémenté à ce jour)

L'ESP32-WROOM dispose du Wi-Fi natif. La phase 5 prévoit :

- Activer le mode AP avec SSID `Quoridor-ESP32` et un mot de passe défini en constante.
- Démarrer un serveur TCP (ou WebSocket) acceptant les mêmes commandes texte que la liaison
  série (`PING`, `WALL`, etc.).
- Introduire une couche d'abstraction interne (`Comm`) pour découpler lecture/écriture
  de la couche commande — le parseur actuel restera inchangé.
- Maintenir le canal série actif en parallèle (mode debug + fallback démo).

Détails d'implémentation : spec phase 5 à venir.
