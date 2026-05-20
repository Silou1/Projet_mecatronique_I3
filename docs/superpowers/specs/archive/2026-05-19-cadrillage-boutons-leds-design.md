# Spec — Cadrillage boutons + driver LEDs (PCB v2)

> ⚠️ **STATUT : DRAFT EN PAUSE — 2026-05-19**
>
> L'équipe abandonne la PCB v2 et reprend tout le hardware à zéro. Toute la partie hardware de ce spec (MCP23017 @ 0x20, GPIO 21/22 I2C, GPIO 32 LED, GPIO map §2.4, refonte `Pins.h` §7, schéma PCB §2) est désormais **potentiellement obsolète** et doit être révisée quand le nouveau hardware sera figé.
>
> **Sections qui restent valides quel que soit le hardware retenu** : §4 (FSM B séquentielle, états IDLE/WAITING_2ND/RELEASING, fenêtre 500 ms, anti-cascade, compatibilité usage simultané), §5.4 (catalogue des patterns LED), §6.1 (API publique de `ButtonMatrix`). Ces décisions sont des choix UX/firmware, pas hardware.
>
> Ne pas commiter, ne pas implémenter avant relecture par Silouane après le nouveau câblage.

> Date : 2026-05-19
> Statut : draft (en pause hardware)
> Phases ciblées : P11.1 (driver matrice boutons), P11.2 (driver LEDs WS2812B)
> Prérequis : nouveau hardware figé (PCB v2 abandonnée)

## 1. Contexte et motivation

Le firmware actuel utilise des stubs ([ButtonMatrix.cpp](../../../firmware/src/ButtonMatrix.cpp), [LedDriver.cpp](../../../firmware/src/LedDriver.cpp)) qui se contentent de logguer. Le mapping de [Pins.h](../../../firmware/src/Pins.h) reflète une ancienne version du design où la matrice 6×6 était câblée directement sur 12 GPIO de l'ESP32, avec un conflit GPIO27 partagé entre `PIN_ROW_2` et `PIN_LEDS_DATA`.

Le design hardware a été retravaillé. La PCB v2 (commandée 2026-04-28, schéma EasyEDA du 2026-02-16, source : NotebookLM `ESP32 Mechatronic Stepper Control PCB Schematic`, id `a4d40652-f03a-45d4-b376-3b508d5c3097`) introduit deux changements majeurs :

1. **Les 36 boutons (matrice 6×6) passent par un expander I2C MCP23017** au lieu des GPIO directs. L'ESP32 ne consomme plus que 2 broches (GPIO 21 SDA + GPIO 22 SCL).
2. **Les 36 LEDs WS2812B passent sur GPIO 32** (avec une résistance série R1 = 470 Ω) au lieu de GPIO 27, supprimant le conflit avec la matrice.

Ce spec décrit le design firmware pour exploiter cette nouvelle topologie et fixe le modèle d'interaction utilisateur retenu (séquentiel, voir §4).

## 2. Architecture hardware (synthèse pour le firmware)

### 2.1 Matrice de boutons

- **36 boutons physiques**, un sous chaque case du plateau 6×6.
- **12 fils sortants** : 6 lignes (axe X) + 6 colonnes (axe Y).
- Câblage matrice **classique sans diodes anti-fantôme** : chaque bouton ferme un contact entre une ligne et une colonne.
- Les 12 fils arrivent sur deux connecteurs femelles du PCB :
  - **H3 (Boutonhor)** : connecté au Port B du MCP23017. 8 broches physiques sur le connecteur (`GPB0..GPB7` côté MCP23017). **Seules `GPB0..GPB5` sont utilisées** (6 lignes). `GPB6` et `GPB7` restent non câblées au tapis (broches du connecteur libres).
  - **H4 (Boutonver)** : connecté au Port A du MCP23017. 8 broches physiques (`GPA0..GPA7`). **Seules `GPA0..GPA5` sont utilisées** (6 colonnes). `GPA6` et `GPA7` restent libres.

### 2.2 MCP23017 (U6)

- **Adresse I2C** : `0x20` (les pins A0/A1/A2 sont à GND sur le schéma).
- **Bus I2C** : SDA = ESP32 GPIO 21, SCL = ESP32 GPIO 22.
- ⚠️ **Broches INTA (20) et INTB (19) NON CÂBLÉES** vers l'ESP32. Le firmware n'a pas accès à l'interruption hardware du MCP23017 et **DOIT** procéder par **polling I2C cyclique**. Le rapport final mentionne un mode "interruption" qui n'est pas reflété dans le schéma du PCB v2 ; le firmware ignore cette mention et reste en polling.
- **Pull-ups internes** du MCP23017 utilisés sur les 6 colonnes (lecture active LOW lorsque le bouton est pressé). Pas de résistances externes nécessaires.

### 2.3 LEDs WS2812B

- **36 LEDs** en chaîne série (une par case du plateau 6×6).
- **Pin data principale** : ESP32 **GPIO 32**, avec **R1 = 470 Ω en série** sur la ligne data avant le connecteur H1.
- Alimentation 5 V centralisée sur H1, conversion interne 12 V → 5 V.
- ⚠️ **Pas de level shifter 3.3 V → 5 V** sur le PCB. La data est pilotée à 3.3 V (sortie ESP32) avec seulement R1 en série. Le seuil `VIH` typique des WS2812B est ≈ 3.5 V (= 0.7 × VCC). Marge négative théorique → **risque de non-pilotage** selon le batch des LEDs. À valider au premier branchement (P10). Mitigation possible si besoin : alimenter les LEDs en 4.0–4.3 V (abaisse le seuil) ou ajouter un AHCT125 externe en cas d'échec.
- **4 lignes "Supp" supplémentaires** câblées sur H1 (Supp1 = GPIO 25, Supp2 = GPIO 26, Supp3 = GPIO 23, Supp4 = GPIO 19). Réserve hardware non utilisée par ce spec ; le firmware initial laisse ces GPIO en `INPUT` au boot.

### 2.4 GPIO map ESP32 (vue d'ensemble)

| GPIO | Usage | Spec | Remarque |
|---|---|---|---|
| 1 (TX) | UART RPi | hors scope | |
| 3 (RX) | UART RPi | hors scope | |
| 21 | I2C SDA (MCP23017) | **utilisé par ce spec** | |
| 22 | I2C SCL (MCP23017) | **utilisé par ce spec** | |
| 32 | LED data WS2812B | **utilisé par ce spec** | via R1 470 Ω |
| 25, 26, 23, 19 | LED Supp1–4 | réservé, INPUT au boot | non câblé au ruban en P11.2 |
| 33 | Servo | hors scope | |
| 18 / 5 / 13 / 12 / 14 | DIR / STEP / MS1 / MS2 / MS3 moteur 1 | hors scope | GPIO 5 et 12 = strapping |
| 17 / 16 / 27 / 2 / 4 | DIR / STEP / MS1 / MS2 / MS3 moteur 2 | hors scope | GPIO 2 = strapping |
| 34, 35, 36, 39 | non utilisés | INPUT (input-only) | |

### 2.5 Ambiguïté connue (à lever en P10)

NotebookLM signale que certaines étiquettes `Bouton7` à `Bouton12` apparaissent à la fois sur les ports du MCP23017 ET sur des GPIO ESP32 (15, 14, 27, 26, 25, 33). C'est probablement un résidu d'un ancien routage avant le passage au MCP23017. **Le firmware n'utilise jamais ces GPIO pour lire des boutons** ; il dépend exclusivement du bus I2C. Si une connexion parasite existe physiquement sur la PCB, elle est ignorée. À valider visuellement au premier branchement (voir §9).

## 3. Driver matrice boutons (P11.1)

### 3.1 Schéma logique

```
ESP32 ────── I2C 100 kHz ──── MCP23017 @ 0x20
                                │
                                ├── Port B (GPB0..GPB5) ──── 6 lignes (drive output)
                                └── Port A (GPA0..GPA5) ──── 6 colonnes (input + pull-up)
                                                                    │
                                                                    └── tapis 36 boutons
```

### 3.2 Configuration MCP23017 au démarrage

1. Init bus I2C ESP32 (100 kHz, SDA = 21, SCL = 22).
2. Vérifier la présence du MCP23017 à `0x20` (ping → si échec : `LedAnimator::ERROR_PATTERN` + UART log).
3. Configurer le MCP23017 :
   - **Port B (GPB0..GPB5)** : `IODIRB` = sorties (mais maintenues HIGH au repos via `OLATB`). Au scan, chaque ligne sera tirée LOW à tour de rôle pour la durée du sample, les autres restant HIGH.
   - **Port A (GPA0..GPA5)** : `IODIRA` = entrées. `GPPUA` = pull-ups activés. Lecture active LOW.
   - `IPOLA` = 0 (pas d'inversion logique côté registre ; l'inversion est faite en logiciel pour clarté).
4. Démarrer la tâche de polling (voir §3.3).

### 3.3 Algorithme de scan (polling I2C)

```
Boucle de polling, période 20 ms (50 Hz) :
  pour chaque ligne r de 0 à 5 :
    écrire OLATB tel que GPBr = 0, GPB[autres] = 1
    attendre 100 µs (settling)
    lire GPIOA → 6 bits
    pour chaque colonne c où GPAc = 0 :
      marquer (r, c) appuyé dans ce scan
  restaurer OLATB = 0b00111111 (toutes lignes HIGH au repos)
  appliquer debounce sur la matrice 6×6 (voir §3.4)
  alimenter la FSM B (voir §4)
```

Durée d'un scan complet : ≤ 8 ms (6 itérations × ~1.3 ms I2C). Compatible avec la période de polling 20 ms (taux d'occupation ≈ 40 % de la fenêtre, marge pour le reste du firmware).

### 3.4 Debounce logiciel

- Buffer circulaire de 3 scans consécutifs par bouton (3 × 20 ms = 60 ms).
- Un bouton est considéré « pressé stable » s'il est marqué pressé sur les 3 derniers scans.
- Un bouton est considéré « relâché stable » s'il est marqué relâché sur les 3 derniers scans.
- Permet de filtrer les rebonds mécaniques typiques (1–10 ms) sans perception de latence (60 ms < 100 ms cible CDCF).

### 3.5 Robustesse multi-appuis (rappel hardware)

- **2 appuis stables simultanés** sur la matrice 6×6 sans diodes : aucun risque de ghosting (démonstration : ghosting requiert ≥ 3 appuis aux coins d'un rectangle).
- **3 appuis stables ou plus simultanés** : ghosting possible. Le driver n'émet pas de nouvel évènement d'appui tant que le nombre de boutons « pressés stables » est supérieur à 2 ; la FSM `WAITING_2ND` traite alors ce cas comme une annulation (voir §4.3).

## 4. Modèle d'interaction utilisateur — FSM B séquentielle

### 4.1 Principe retenu

Le joueur **n'appuie pas simultanément** sur 2 boutons pour placer un mur. Il appuie **séquentiellement** sur les 2 cases du mur, dans une fenêtre temporelle bornée. Le driver `ButtonMatrix` encapsule entièrement cette logique et n'expose au reste du firmware qu'un `Intent` déjà désambiguïsé.

Raisons du choix séquentiel sur simultané :
- Élimine le ghosting (1 seul appui actif à la fois enregistré comme stable).
- Plus accessible (pas de dextérité 2 doigts requise).
- Feedback visuel intermédiaire possible (LED `PENDING_FLASH` sur la 1ʳᵉ case).
- Annulation naturelle par timeout.
- Impact firmware minimal : un état FSM supplémentaire dans `ButtonMatrix`, aucun changement hardware, aucun changement protocole UART, aucun changement moteur Python.

**Compatibilité usage simultané** : la FSM B accepte naturellement le cas où le joueur garde le 1ᵉʳ bouton enfoncé en appuyant sur le 2ᵉ (ancien geste « option A »). Tant que les deux boutons sont stables simultanément (60 ms) et adjacents, l'évènement « 2ᵉ case adjacente pressée » se déclenche et l'`Intent WALL` est émis. Les deux gestes (séquentiel vrai et simultané) produisent donc le même résultat — pas de rééducation des joueurs habitués à l'ancien modèle.

### 4.2 États internes du driver

```
┌─────────┐    1ʳᵉ case pressée stable     ┌──────────────┐
│  IDLE   │ ──────────────────────────────▶│ WAITING_2ND  │
└─────────┘                                 └──────────────┘
     ▲                                           │  │  │
     │                                           │  │  │
     │   tous les boutons relâchés stables       │  │  │
     │                                           │  │  │
┌───────────┐                                    │  │  │  2ᵉ adjacente pressée
│ RELEASING │◀───────────────────────────────────┘  │  │  → Intent WALL
└───────────┘   timeout 500 ms sans 2ᵉ appui        │  │
     ▲          → Intent MOVE                       │  │
     │                                              │  │
     │◀─────────────────────────────────────────────┘  │
     │   2ᵉ non-adjacente OU > 2 appuis stables        │
     │   → NACK_FLASH, pas d'intent                    │
     │                                                 │
     │◀────────────────────────────────────────────────┘
```

### 4.3 Définition formelle

Dans toute cette table, « appui stable » signifie « bouton marqué comme `pressé stable` au sens du debounce §3.4 » (3 scans consécutifs = ~60 ms).

| Évènement | État source | État cible | Action |
|---|---|---|---|
| Appui stable sur `(r, c)` (alors qu'aucun bouton n'était stable précédemment) | `IDLE` | `WAITING_2ND` | Mémoriser `(r, c)`, démarrer minuteur 500 ms, `LedAnimator::playPendingFlash(r, c)` |
| Apparition d'un 2ᵉ appui stable sur `(r', c')` adjacent à `(r, c)` (`|Δr| + |Δc| = 1`) | `WAITING_2ND` | `RELEASING` | Émettre `Intent{kind = WALL_H ou WALL_V, …}`, stopper minuteur, `LedAnimator::play(OFF)` |
| Apparition d'un 2ᵉ appui stable non-adjacent, OU passage à > 2 appuis stables détectés | `WAITING_2ND` | `RELEASING` | `LedAnimator::play(NACK_FLASH)`, stopper minuteur, pas d'intent émis |
| Minuteur 500 ms expiré sans 2ᵉ appui stable | `WAITING_2ND` | `RELEASING` | Émettre `Intent{kind = MOVE, row = r, col = c}`, `LedAnimator::play(OFF)` |
| Tous les boutons sont relâchés stables | `RELEASING` | `IDLE` | (aucune action ; ré-armement de la FSM) |

État `RELEASING` (verrou anti-rebond logique) : empêche un re-déclenchement immédiat d'un nouveau cycle tant que le joueur n'a pas relâché tous les boutons. Sans cet état, un joueur qui garde le doigt enfoncé après émission d'un `Intent MOVE` (timeout) provoquerait une cascade d'`Intent MOVE` identiques.

### 4.4 Détermination de l'orientation du mur

Pour 2 cases adjacentes `(r1, c1)` et `(r2, c2)` :
- Si `r1 == r2` (cases côte à côte sur la même ligne) → **mur vertical** entre elles. `Intent{kind = WALL_V, row = min(r1, r2), col = min(c1, c2)}`.
- Si `c1 == c2` (cases l'une au-dessus de l'autre) → **mur horizontal** entre elles. `Intent{kind = WALL_H, row = min(r1, r2), col = min(c1, c2)}`.

Le mapping `(row, col)` retenu doit correspondre exactement à la convention `Wall = (orientation, ligne, colonne, longueur=2)` de [quoridor_engine/core.py:50](../../../quoridor_engine/core.py) (coin haut-gauche du mur). Tests unitaires firmware à prévoir pour les 4 directions × 4 coins du plateau.

### 4.5 Constantes paramétrables

```cpp
namespace ButtonMatrixConfig {
  constexpr uint32_t POLL_PERIOD_MS = 20;          // §3.3
  constexpr uint8_t  DEBOUNCE_SAMPLES = 3;         // §3.4
  constexpr uint32_t SECOND_PRESS_WINDOW_MS = 500; // §4 (ajustable après tests UX)
}
```

`SECOND_PRESS_WINDOW_MS` est délibérément exposée pour permettre un ajustement rapide après les tests utilisateurs (P11 ou P13). Valeurs envisagées : 300 ms (plus réactif, plus exigeant) à 800 ms (plus permissif, plus lent).

## 5. Driver LEDs WS2812B (P11.2)

### 5.1 Bibliothèque

**FastLED 3.6+** (ou plus récente disponible sur PlatformIO). Choisie pour :
- Support natif ESP32 + WS2812B.
- API simple `FastLED.show()` + `leds[i].setRGB(r, g, b)`.
- Bufferisation en RAM (36 LEDs × 3 octets = 108 octets, négligeable).

Ajouter à `firmware/platformio.ini` :
```ini
lib_deps =
    fastled/FastLED@^3.6.0
```

### 5.2 Initialisation

```cpp
constexpr uint8_t LED_DATA_PIN = 32;
constexpr uint8_t LED_COUNT = 36;
CRGB leds[LED_COUNT];

void LedDriver::init() {
  FastLED.addLeds<WS2812B, LED_DATA_PIN, GRB>(leds, LED_COUNT);
  FastLED.setBrightness(64);   // 25 %, à calibrer P11.2 selon visibilité plateau
  FastLED.clear();
  FastLED.show();
}
```

Brightness initiale à 25 % :
- Limite la conso à ~0.18 A pour 36 LEDs blanches (vs 0.72 A à 100 %), réduit la chauffe.
- Suffisant en pratique sous plateau bois fin / diffuseur translucide.
- Calibrable sur place lors des tests P11.2.

### 5.3 Mapping case → index LED

Le mapping linéaire dépend du sens physique de soudure du ruban (à confirmer visuellement avec Jean au premier branchement). Hypothèse par défaut : **scan en serpentin** (ligne 0 gauche→droite, ligne 1 droite→gauche, etc.) pour minimiser la longueur de soudure. À documenter dans `LedDriver.cpp` par une fonction explicite :

```cpp
uint8_t LedDriver::caseToLedIndex(uint8_t row, uint8_t col) {
  if (row % 2 == 0) {
    return row * 6 + col;          // ligne paire : gauche→droite
  } else {
    return row * 6 + (5 - col);    // ligne impaire : droite→gauche
  }
}
```

Si Jean confirme un autre câblage (rangées indépendantes ou ordre fixe), la fonction sera ajustée. Test de validation P11.2 : allumer les LEDs `(0,0)`, `(0,5)`, `(5,0)`, `(5,5)` une par une et confirmer visuellement.

### 5.4 Animations requises (alignées sur [LedAnimator.h](../../../firmware/src/LedAnimator.h))

| Pattern | Comportement | Déclencheur FSM |
|---|---|---|
| `OFF` | Toutes éteintes | État `IDLE` du driver boutons |
| `DEMO_IDLE` | Slow rainbow doux sur 36 LEDs, 1 cycle / 4 s | État `GameController::DEMO` |
| `PENDING_FLASH` | LED `(r, c)` clignote bleu 2 Hz | État `WAITING_2ND` du driver boutons |
| `NACK_FLASH` | Toutes LEDs rouge 200 ms puis OFF | Intent rejeté (multi-appui ou non-adjacent), ou NACK reçu du Python |
| `TIMEOUT_FLASH` | LED `(r, c)` orange 300 ms puis OFF | Timeout UART en `BUTTON_INTENT_PENDING` |
| `EXECUTING_SPINNER` | Anneau tournant blanc sur le contour 6×6 | État `GameController::EXECUTING` (ordre IA en cours) |
| `ERROR_PATTERN` | Pulsation rouge lente sur les 36 LEDs | État `GameController::ERROR_STATE` |

`LedAnimator::tick()` est appelé à chaque itération de `loop()` ; il met à jour les LEDs en interne sans bloquer.

## 6. API firmware proposée

### 6.1 `ButtonMatrix.h` — interface élargie

L'enum `IntentKind` et la struct `Intent` actuels ([ButtonMatrix.h:7-13](../../../firmware/src/ButtonMatrix.h#L7-L13)) sont conservés. La fonction `init()` prend désormais un paramètre optionnel `bool useStubMode` pour faciliter les tests en l'absence de PCB.

```cpp
namespace ButtonMatrix {
  enum class IntentKind { NONE, MOVE, WALL_H, WALL_V };
  struct Intent { IntentKind kind; uint8_t row; uint8_t col; };

  // Initialise le driver. Si mcp23017 absent à 0x20, le driver
  // retourne false et reste en mode stub (les fonctions inject*
  // continuent à fonctionner pour les tests P9.4).
  bool init();

  // À appeler à chaque itération de loop() ; effectue le polling
  // I2C selon POLL_PERIOD_MS et fait avancer la FSM B en interne.
  void poll();

  // Vrai si un Intent désambiguïsé est prêt à être consommé.
  bool hasIntent();

  // Consomme l'Intent courant (state→NONE après).
  Intent takeIntent();

  // Hooks d'injection pour P9.4 (conservés pour compatibilité tests).
  void injectMoveIntent(uint8_t row, uint8_t col);
  void injectWallIntent(bool horizontal, uint8_t row, uint8_t col);
}
```

Garanties contractuelles :
- `poll()` ne bloque jamais plus de 10 ms (durée d'un scan complet I2C).
- Un appel à `takeIntent()` après `hasIntent() == true` retourne toujours un `Intent` cohérent (jamais d'`IntentKind::NONE`).
- La FSM interne (`IDLE` / `WAITING_2ND` / `RELEASING`, voir §4.2) est invisible depuis l'extérieur.

### 6.2 `LedDriver.h` et `LedAnimator.h` — signatures existantes conservées

Les interfaces actuelles ([LedDriver.h](../../../firmware/src/LedDriver.h), [LedAnimator.h](../../../firmware/src/LedAnimator.h)) sont conservées telles quelles. Seules les implémentations changent. Ajout d'une seule fonction publique dans `LedAnimator` :

```cpp
namespace LedAnimator {
  // Existe déjà : play(Pattern), init(), tick()
  // Ajout :
  void playPendingFlash(uint8_t row, uint8_t col);  // §5.4 PENDING_FLASH
}
```

## 7. Refonte de `Pins.h`

Le fichier [Pins.h](../../../firmware/src/Pins.h) actuel est entièrement obsolète. Refonte proposée :

```cpp
#ifndef PINS_H
#define PINS_H

// Mapping PCB v2 (cf. docs/superpowers/specs/2026-05-19-cadrillage-boutons-leds-design.md)

// === Bus I2C : boutons via MCP23017 (U6) ===
constexpr int PIN_I2C_SDA = 21;
constexpr int PIN_I2C_SCL = 22;
constexpr uint8_t MCP23017_ADDR = 0x20;

// === LEDs WS2812B (chaîne principale, R1 = 470Ω en série) ===
constexpr int PIN_LEDS_DATA = 32;
constexpr int LED_COUNT = 36;

// === Servo ===
constexpr int PIN_SERVO = 33;

// === Réserves hardware (LEDs Supp1-4, non utilisées par le firmware initial) ===
// GPIO 25, 26, 23, 19 -- laissées en INPUT au boot

#endif
```

Suppressions :
- `PIN_COL_0..5`, `PIN_ROW_0..5` (ancienne matrice GPIO direct) → remplacés par I2C.
- `PIN_LED_DEBUG = 2` (GPIO 2 est désormais MS2_2 driver moteur 2, strapping). Si besoin de debug visuel, utiliser la LED bleue intégrée à la Freenove DevKit en P10 uniquement, retirer en prod.
- `PIN_SERVO` change de 32 → 33 (corrigé selon PCB v2).
- `PIN_LEDS_DATA` change de 27 → 32 (corrigé selon PCB v2).

## 8. Critères d'acceptation (tests de validation P11.1 + P11.2)

### 8.1 Boutons (P11.1)

1. **Présence MCP23017** : à l'init, le firmware détecte le MCP23017 à `0x20` et log `BTN: MCP23017 OK`. Si absent : log `BTN: MCP23017 missing -> stub mode` et continue.
2. **Détection individuelle** : presser chacun des 36 boutons un par un. Pour chaque bouton, le firmware émet un `Intent{kind = MOVE, row, col}` correct (vérifié via log UART).
3. **Anti-rebond** : un appui rapide (<60 ms) est ignoré ; un appui normal (>100 ms) est détecté une seule fois (pas de doublon).
4. **Mur horizontal** : presser `(2, 1)` puis `(2, 2)` dans la fenêtre 500 ms → émettre `Intent{WALL_V, row=2, col=1}`. Vérifier les 4 directions et les 4 coins du plateau.
5. **Mur vertical** : presser `(1, 3)` puis `(2, 3)` dans la fenêtre 500 ms → émettre `Intent{WALL_H, row=1, col=3}`.
6. **Timeout déplacement** : presser `(0, 0)` seul, attendre 600 ms → émettre `Intent{MOVE, row=0, col=0}`.
7. **Annulation non-adjacent** : presser `(0, 0)` puis `(3, 4)` dans la fenêtre → `NACK_FLASH` sur les LEDs, pas d'intent émis.
8. **Annulation > 2 appuis** : presser 3 boutons simultanés (formant un rectangle) → `NACK_FLASH`, pas d'intent émis.
9. **Pas de blocage UART** : pendant la fenêtre 500 ms, l'ESP32 répond toujours à un `PING` du RPi en <100 ms.
10. **Anti-cascade `RELEASING`** : presser `(0, 0)` et garder le doigt enfoncé pendant 2 s → un seul `Intent MOVE` émis (sur timeout), pas de cascade. Aucun nouvel `Intent` jusqu'au relâchement complet.
11. **Compatibilité usage simultané** : presser `(2, 1)` puis sans le relâcher presser `(2, 2)` dans la fenêtre → émettre `Intent{WALL_V, row=2, col=1}` (équivalent au test 4).

### 8.2 LEDs (P11.2)

1. **Mapping LED ↔ case** : allumer successivement `(0,0)`, `(0,5)`, `(5,0)`, `(5,5)` et confirmer visuellement la position.
2. **Pattern `DEMO_IDLE`** : visible et fluide en `GameController::DEMO`.
3. **Pattern `PENDING_FLASH`** : visible sur la 1ʳᵉ case du mur pendant la fenêtre 500 ms.
4. **Pattern `EXECUTING_SPINNER`** : tourne pendant l'exécution d'un coup IA.
5. **Pattern `NACK_FLASH`** : 200 ms rouge sur réception d'un NACK.
6. **Pattern `ERROR_PATTERN`** : pulsation rouge lente en `ERROR_STATE`.
7. **Niveau logique** : si les LEDs ne s'allument pas du tout malgré le code OK, vérifier le risque level shifter (§2.3) : essayer d'abaisser le 5V LEDs à 4.2 V ou ajouter un AHCT125 entre GPIO 32 et le ruban.

### 8.3 Tests joueur (P13)

- **Fenêtre 500 ms ajustable** : tester 300 / 500 / 800 ms avec 3 joueurs différents pour valider la valeur retenue.
- **Apprentissage** : un joueur naïf comprend-il l'interaction mur (1ʳᵉ case + 2ᵉ case adjacente) sans explication, juste avec le retour visuel ? Note libre.

## 9. Risques et points à valider au premier branchement PCB (P10)

| Risque | Probabilité | Mitigation |
|---|---|---|
| Level shifter manquant → WS2812B ne reçoivent pas la data | Moyenne | Tester `setPixel(0, 255, 0, 0)`. Si KO, abaisser VCC LEDs à 4.2 V ou ajouter AHCT125 en air-wired. |
| Routage parasite "Bouton7-12" sur GPIO ESP32 directs (§2.5) | Faible | Vérifier au multimètre : continuité entre GPIO 15/14/27/26/25/33 et les broches concernées du MCP23017. Si parasitage, dégager le GPIO problématique côté firmware moteur. |
| MCP23017 non détecté à 0x20 | Faible | Vérifier A0/A1/A2 à GND, soudures du MCP, présence pull-ups SDA/SCL externes (sur le PCB ou ajout). |
| GPIO 2/5/12 (strapping) tirés au mauvais niveau au boot | Faible | Vérifier que MS1_1/MS2_1/MS2_2 ne forcent pas un niveau interdit pendant le reset. Si problème, refaire le séquencement d'init firmware. |
| WS2812B Supp1-4 effectivement câblés sur le tapis (au lieu de réserve) | Très faible | Le user a confirmé "réserve" en discussion équipe le 2026-05-19. Si finalement câblées, le spec sera étendu et `LedDriver::caseToLedIndex` adapté. |

## 10. Hors scope (volontairement exclu)

- Drivers moteurs (MCP23017 sort A4988 + Nema 17) → P11.3 / P11.4, spec séparé à venir.
- Driver servo → P11.5.
- Toute modification du protocole UART → conservé tel quel ([06_protocole_uart.md](../../06_protocole_uart.md)).
- Toute modification du moteur Python → conservé tel quel.
- Bouton "annuler" physique séparé → pas dans le hardware.
- Mode interruption hardware MCP23017 → impossible (INT non câblées sur PCB v2).
- Mise à jour des animations [LedAnimator.h](../../../firmware/src/LedAnimator.h) avec de nouveaux patterns → ce spec se limite aux patterns déjà énumérés.

## 11. Sources

- Rapport final équipe Quoridor : NotebookLM `Automating Quoridor: A Mechatronic AI Strategy Board Game` (id `d504110b-3a17-4289-8671-ed6382757a09`).
- Schéma PCB v2 EasyEDA 2026-02-16 : NotebookLM `ESP32 Mechatronic Stepper Control PCB Schematic` (id `a4d40652-f03a-45d4-b376-3b508d5c3097`).
- Datasheet ESP32 : NotebookLM `ESP32 Development Board Pinout Reference Map` (id `7d0bccd1-df3f-456d-99a0-1192766043ba`).
- Discussion équipe Silouane ↔ collègues, 2026-05-19 (validation modèle B séquentiel, Supp1-4 en réserve).
