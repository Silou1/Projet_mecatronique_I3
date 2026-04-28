# Plan 1 — Squelette firmware ESP32 + FSM globale + intégration FreeRTOS

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produire un firmware ESP32 minimal qui compile, flashe, boote, exécute la FSM globale complète (BOOT → WAITING_RPI → DEMO/CONNECTED → BUTTON_INTENT_PENDING → EXECUTING → ERROR), avec watchdog actif et tâche FreeRTOS moteurs branchée mais simulée. Les modules métier (scan boutons réel, driver WS2812B, moteurs A4988, protocole UART final) sont des stubs vérifiables qui seront remplacés dans les Plans 2-7.

**Architecture:** Sketch Arduino unique `arduino_quoridor.ino` orchestrant 6 modules (`ButtonMatrix`, `LedDriver`, `LedAnimator`, `MotionControl`, `UartLink`, `GameController`). Le `GameController` est l'unique propriétaire de la FSM. La loop principale (Core 1) appelle séquentiellement `UartLink.poll()`, `ButtonMatrix.poll()`, `GameController.tick()`, `LedAnimator.tick()`. La tâche FreeRTOS sur Core 0 héberge `MotionControl` et communique par 2 queues. UART en mode protocole texte simplifié (HELLO/ACK/KEEP/CMD/ERR) — sera remplacé par le vrai protocole binaire dans le Plan 3.

**Tech Stack:**
- Arduino IDE (cible "ESP32 Dev Module", Espressif ESP32 board package ≥ 2.0)
- ESP32-WROOM (Freenove)
- Bibliothèques système : `esp_task_wdt.h`, `freertos/FreeRTOS.h`, `freertos/queue.h`, `freertos/task.h`, `HardwareSerial.h`
- Aucune bibliothèque externe pour ce plan (FastLED, MCP23017 etc. arrivent dans les plans suivants)
- Test = procédure manuelle via Serial monitor à 115200 bauds (l'Arduino IDE n'a pas de framework de test embarqué — on valide chaque transition d'état en envoyant des commandes texte et observant la sortie série)

---

## Notes de contexte importantes

**Convention de test :** comme on est en embarqué Arduino sans framework de tests unitaires, chaque tâche se termine par une **procédure de test manuelle** : flasher, ouvrir Serial monitor, exécuter une séquence d'inputs et vérifier la sortie attendue. Les commits se font après vérification manuelle, pas après "passage de test automatique".

**Protocole texte temporaire (Plan 1 uniquement) :** chaque trame est une ligne ASCII terminée par `\n`. Format : `<TYPE> <args séparés par espaces>`. Exemples :

| Trame | Direction | Sens |
|---|---|---|
| `HELLO` | ESP32 → ordi | ESP32 demande la présence d'un maître |
| `HELLO_ACK` | ordi → ESP32 | l'ordi se déclare présent |
| `KEEP` | ordi → ESP32 | keepalive |
| `BTN <row> <col>` | ordi → ESP32 | simule un clic bouton (provisoire, remplacera ButtonMatrix réel) |
| `MOVE_REQ <row> <col>` | ESP32 → ordi | intention de déplacement |
| `WALL_REQ <h\|v> <row> <col>` | ESP32 → ordi | intention de mur |
| `ACK` | ordi → ESP32 | accord du maître sur la dernière intention |
| `NACK` | ordi → ESP32 | refus du maître |
| `CMD MOVE <row> <col>` | ordi → ESP32 | commande directe de déplacement |
| `DONE` | ESP32 → ordi | exécution terminée |
| `ERR <code>` | ESP32 → ordi | erreur (perd la connexion, reste en ERROR_STATE) |
| `RESET` | ordi → ESP32 | force un reboot logiciel |

**Renommage `ERROR` → `ERROR_STATE` :** `ERROR` est défini comme macro dans certains headers Arduino. On utilise `ERROR_STATE` pour éviter les collisions.

**Pin debug :** pour signaler visuellement les transitions d'état pendant le développement, on utilise la LED bleue intégrée Freenove (GPIO2). Les `Serial.println` restent la source de vérité pour les tests.

---

## File Structure

```
firmware/
└── arduino_quoridor/
    ├── arduino_quoridor.ino     // setup() + loop() + lancement tâche moteurs
    ├── Pins.h                   // mapping centralisé des pins PCB v2
    ├── ButtonMatrix.h           // API publique (stub plan 1)
    ├── ButtonMatrix.cpp         // stub : poll() vide, hasIntent() false
    ├── LedDriver.h              // API publique (stub plan 1)
    ├── LedDriver.cpp            // stub : init/setPixel/show debug par Serial
    ├── LedAnimator.h            // API publique (stub plan 1)
    ├── LedAnimator.cpp          // stub : enregistre l'animation demandée, tick() vide
    ├── MotionControl.h          // API + types Command, Result, queues exposées
    ├── MotionControl.cpp        // tâche FreeRTOS Core 0, simule un déplacement (delay 1 s)
    ├── UartLink.h               // API publique : init, poll, sendLine, tryReadLine
    ├── UartLink.cpp             // protocole texte ligne par ligne
    ├── GameController.h         // API + enum State
    └── GameController.cpp       // FSM complète, orchestration des modules
```

---

## Tâches

### Task 1 : Setup projet Arduino + sketch vide qui compile

**Files:**
- Create: `firmware/arduino_quoridor/arduino_quoridor.ino`
- Create: `firmware/arduino_quoridor/Pins.h`

- [ ] **Step 1.1: Créer l'arborescence et `Pins.h`**

```cpp
// firmware/arduino_quoridor/Pins.h
#ifndef PINS_H
#define PINS_H

// Mapping PCB v2 (cf. hardware/AUDIT_PCB_V2.md)
// Matrice boutons 6x6 — colonnes
constexpr int PIN_COL_0 = 0;
constexpr int PIN_COL_1 = 4;
constexpr int PIN_COL_2 = 16;
constexpr int PIN_COL_3 = 17;
constexpr int PIN_COL_4 = 5;
constexpr int PIN_COL_5 = 18;

// Matrice boutons 6x6 — lignes
constexpr int PIN_ROW_0 = 13;
constexpr int PIN_ROW_1 = 14;
constexpr int PIN_ROW_2 = 27;
constexpr int PIN_ROW_3 = 26;
constexpr int PIN_ROW_4 = 25;
constexpr int PIN_ROW_5 = 33;

// Periph
constexpr int PIN_LEDS_DATA = 27;   // partagé avec PIN_ROW_2 sur PCB v2 — accepté pour Plan 1
constexpr int PIN_SERVO    = 32;
constexpr int PIN_LED_DEBUG = 2;    // LED bleue intégrée Freenove

// I2C (MCP23017)
constexpr int PIN_I2C_SDA = 21;
constexpr int PIN_I2C_SCL = 22;
constexpr uint8_t MCP23017_ADDR = 0x20;

#endif
```

- [ ] **Step 1.2: Créer le sketch principal vide**

```cpp
// firmware/arduino_quoridor/arduino_quoridor.ino
#include <Arduino.h>
#include "Pins.h"

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("BOOT_START");
  pinMode(PIN_LED_DEBUG, OUTPUT);
}

void loop() {
  // vide pour l'instant
}
```

- [ ] **Step 1.3: Compiler dans Arduino IDE**

Ouvrir `firmware/arduino_quoridor/arduino_quoridor.ino` dans l'IDE Arduino. Sélectionner Outils → Type de carte → "ESP32 Dev Module". Compiler (Ctrl+R / Cmd+R).
Expected: compilation OK, aucune erreur.

- [ ] **Step 1.4: Flasher l'ESP32 (si carte branchée) ou skipper**

Si pas de carte sous la main : skipper le flash, on testera tout à la fin du plan.
Si carte branchée : sélectionner le bon port série, téléverser. Ouvrir Serial monitor à 115200 bauds.
Expected (si flashé): `BOOT_START` apparaît dans le moniteur, LED bleue intégrée éteinte.

- [ ] **Step 1.5: Commit**

```bash
git add firmware/arduino_quoridor/arduino_quoridor.ino firmware/arduino_quoridor/Pins.h
git commit -m "feat(firmware): squelette sketch + mapping pins PCB v2"
```

---

### Task 2 : Headers minimaux des 6 modules + linkage compile-only

**Files:**
- Create: `firmware/arduino_quoridor/ButtonMatrix.h`
- Create: `firmware/arduino_quoridor/ButtonMatrix.cpp`
- Create: `firmware/arduino_quoridor/LedDriver.h`
- Create: `firmware/arduino_quoridor/LedDriver.cpp`
- Create: `firmware/arduino_quoridor/LedAnimator.h`
- Create: `firmware/arduino_quoridor/LedAnimator.cpp`
- Create: `firmware/arduino_quoridor/MotionControl.h`
- Create: `firmware/arduino_quoridor/MotionControl.cpp`
- Create: `firmware/arduino_quoridor/UartLink.h`
- Create: `firmware/arduino_quoridor/UartLink.cpp`
- Create: `firmware/arduino_quoridor/GameController.h`
- Create: `firmware/arduino_quoridor/GameController.cpp`
- Modify: `firmware/arduino_quoridor/arduino_quoridor.ino`

L'objectif est d'avoir tous les headers en place avec leurs API publiques, et des `.cpp` minimaux (juste `Serial.println` au démarrage de chaque init). Le sketch principal initialise tous les modules dans `setup()`. Aucune logique métier encore.

- [ ] **Step 2.1: `ButtonMatrix.h` + `ButtonMatrix.cpp`**

```cpp
// ButtonMatrix.h
#ifndef BUTTON_MATRIX_H
#define BUTTON_MATRIX_H

#include <Arduino.h>

namespace ButtonMatrix {
  enum class IntentKind { NONE, MOVE, WALL_H, WALL_V };

  struct Intent {
    IntentKind kind;
    uint8_t row;
    uint8_t col;
  };

  void init();
  void poll();              // appelée en boucle dans loop()
  bool hasIntent();
  Intent takeIntent();      // consomme et retourne l'intention courante

  // utilisé par UartLink pour simuler un clic en plan 1 (sera retiré au plan 4)
  void injectMoveIntent(uint8_t row, uint8_t col);
  void injectWallIntent(bool horizontal, uint8_t row, uint8_t col);
}

#endif
```

```cpp
// ButtonMatrix.cpp
#include "ButtonMatrix.h"

namespace {
  ButtonMatrix::Intent _pending = { ButtonMatrix::IntentKind::NONE, 0, 0 };
  bool _hasPending = false;
}

void ButtonMatrix::init() {
  Serial.println("[ButtonMatrix] init (stub)");
}

void ButtonMatrix::poll() {
  // stub : pas de scan réel en plan 1
}

bool ButtonMatrix::hasIntent() {
  return _hasPending;
}

ButtonMatrix::Intent ButtonMatrix::takeIntent() {
  Intent out = _pending;
  _hasPending = false;
  _pending.kind = IntentKind::NONE;
  return out;
}

void ButtonMatrix::injectMoveIntent(uint8_t row, uint8_t col) {
  _pending = { IntentKind::MOVE, row, col };
  _hasPending = true;
}

void ButtonMatrix::injectWallIntent(bool horizontal, uint8_t row, uint8_t col) {
  _pending = { horizontal ? IntentKind::WALL_H : IntentKind::WALL_V, row, col };
  _hasPending = true;
}
```

- [ ] **Step 2.2: `LedDriver.h` + `LedDriver.cpp`**

```cpp
// LedDriver.h
#ifndef LED_DRIVER_H
#define LED_DRIVER_H

#include <Arduino.h>

namespace LedDriver {
  void init();
  void setPixel(uint8_t index, uint8_t r, uint8_t g, uint8_t b);
  void clear();
  void show();              // push atomique vers la chaîne LED (stub plan 1)
  bool selfTest();          // utilisé par BOOT
}

#endif
```

```cpp
// LedDriver.cpp
#include "LedDriver.h"

void LedDriver::init() {
  Serial.println("[LedDriver] init (stub)");
}

void LedDriver::setPixel(uint8_t index, uint8_t r, uint8_t g, uint8_t b) {
  // stub : log uniquement
  Serial.print("[LedDriver] setPixel "); Serial.print(index);
  Serial.print(" "); Serial.print(r);
  Serial.print(" "); Serial.print(g);
  Serial.print(" "); Serial.println(b);
}

void LedDriver::clear() {
  Serial.println("[LedDriver] clear");
}

void LedDriver::show() {
  // stub : pas de push WS2812B en plan 1
}

bool LedDriver::selfTest() {
  Serial.println("[LedDriver] selfTest -> OK (stub)");
  return true;
}
```

- [ ] **Step 2.3: `LedAnimator.h` + `LedAnimator.cpp`**

```cpp
// LedAnimator.h
#ifndef LED_ANIMATOR_H
#define LED_ANIMATOR_H

#include <Arduino.h>

namespace LedAnimator {
  enum class Pattern {
    OFF,
    DEMO_IDLE,
    PENDING_FLASH,    // flash doux sur la case en attente d'ACK
    NACK_FLASH,       // flash rouge bref
    TIMEOUT_FLASH,    // flash orange bref
    EXECUTING_SPINNER,
    ERROR_PATTERN
  };

  void init();
  void tick();
  void play(Pattern p);
}

#endif
```

```cpp
// LedAnimator.cpp
#include "LedAnimator.h"
#include "LedDriver.h"

namespace {
  LedAnimator::Pattern _current = LedAnimator::Pattern::OFF;
}

void LedAnimator::init() {
  Serial.println("[LedAnimator] init (stub)");
}

void LedAnimator::tick() {
  // stub : pas d'animation réelle en plan 1
}

void LedAnimator::play(Pattern p) {
  if (p != _current) {
    _current = p;
    Serial.print("[LedAnimator] play pattern=");
    Serial.println((int)p);
  }
}
```

- [ ] **Step 2.4: `MotionControl.h` + `MotionControl.cpp` (squelette de tâche FreeRTOS)**

```cpp
// MotionControl.h
#ifndef MOTION_CONTROL_H
#define MOTION_CONTROL_H

#include <Arduino.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

namespace MotionControl {
  enum class CommandKind { HOMING, MOVE_TO_WALL_SLOT, PUSH_WALL };

  struct Command {
    CommandKind kind;
    uint8_t row;
    uint8_t col;
    bool horizontal;        // utilisé pour MOVE_TO_WALL_SLOT
  };

  enum class ResultKind { DONE, ERR_MOTOR_TIMEOUT, ERR_LIMIT_UNEXPECTED, ERR_HOMING_FAILED, ERR_I2C_NACK };

  struct Result {
    ResultKind kind;
  };

  void init();
  bool postCommand(const Command& cmd);    // non bloquant ; renvoie false si queue pleine
  bool tryGetResult(Result& out);          // non bloquant
  bool selfTest();                         // utilisé par BOOT (test I2C)
}

#endif
```

```cpp
// MotionControl.cpp
#include "MotionControl.h"
#include "freertos/task.h"

namespace {
  QueueHandle_t _commandQueue = nullptr;
  QueueHandle_t _resultQueue  = nullptr;
  TaskHandle_t  _taskHandle   = nullptr;

  void motionTask(void* arg) {
    MotionControl::Command cmd;
    for (;;) {
      if (xQueueReceive(_commandQueue, &cmd, portMAX_DELAY) == pdTRUE) {
        Serial.print("[MotionControl] exec command kind=");
        Serial.println((int)cmd.kind);
        // simulation : 1 s d'attente puis DONE
        vTaskDelay(pdMS_TO_TICKS(1000));
        MotionControl::Result res = { MotionControl::ResultKind::DONE };
        xQueueSend(_resultQueue, &res, 0);
      }
    }
  }
}

void MotionControl::init() {
  Serial.println("[MotionControl] init (FreeRTOS task)");
  _commandQueue = xQueueCreate(4, sizeof(Command));
  _resultQueue  = xQueueCreate(4, sizeof(Result));
  // tâche pinnée sur Core 0 (la loop principale tourne sur Core 1)
  xTaskCreatePinnedToCore(motionTask, "motion", 4096, nullptr, 1, &_taskHandle, 0);
}

bool MotionControl::postCommand(const Command& cmd) {
  return xQueueSend(_commandQueue, &cmd, 0) == pdTRUE;
}

bool MotionControl::tryGetResult(Result& out) {
  return xQueueReceive(_resultQueue, &out, 0) == pdTRUE;
}

bool MotionControl::selfTest() {
  Serial.println("[MotionControl] selfTest -> OK (stub I2C)");
  return true;
}
```

- [ ] **Step 2.5: `UartLink.h` + `UartLink.cpp`**

```cpp
// UartLink.h
#ifndef UART_LINK_H
#define UART_LINK_H

#include <Arduino.h>

namespace UartLink {
  void init();
  void poll();                       // assemble les caractères entrants en lignes
  bool tryReadLine(String& out);     // récupère une ligne complète si dispo
  void sendLine(const String& line); // envoie une ligne terminée par \n
}

#endif
```

```cpp
// UartLink.cpp
#include "UartLink.h"

namespace {
  String _rxBuffer;
  String _pendingLine;
  bool _hasPending = false;
}

void UartLink::init() {
  // Serial déjà initialisé dans setup()
  Serial.println("[UartLink] init");
  _rxBuffer.reserve(64);
}

void UartLink::poll() {
  while (Serial.available() > 0 && !_hasPending) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      _pendingLine = _rxBuffer;
      _rxBuffer = "";
      _hasPending = true;
      break;
    }
    _rxBuffer += c;
    if (_rxBuffer.length() > 60) {
      // protection débordement : on jette
      _rxBuffer = "";
    }
  }
}

bool UartLink::tryReadLine(String& out) {
  if (!_hasPending) return false;
  out = _pendingLine;
  _hasPending = false;
  return true;
}

void UartLink::sendLine(const String& line) {
  Serial.print(line);
  Serial.print('\n');
}
```

- [ ] **Step 2.6: `GameController.h` + `GameController.cpp` (squelette vide)**

```cpp
// GameController.h
#ifndef GAME_CONTROLLER_H
#define GAME_CONTROLLER_H

#include <Arduino.h>

namespace GameController {
  enum class State {
    BOOT,
    WAITING_RPI,
    DEMO,
    CONNECTED,
    BUTTON_INTENT_PENDING,
    EXECUTING,
    ERROR_STATE
  };

  void init();
  void tick();          // appelée à chaque itération de loop()
  State currentState();
}

#endif
```

```cpp
// GameController.cpp
#include "GameController.h"

namespace {
  GameController::State _state = GameController::State::BOOT;
}

void GameController::init() {
  Serial.println("[GameController] init");
  _state = State::BOOT;
}

void GameController::tick() {
  // sera implémentée tâche par tâche
}

GameController::State GameController::currentState() {
  return _state;
}
```

- [ ] **Step 2.7: Brancher tous les modules dans le sketch principal**

Remplacer entièrement `arduino_quoridor.ino` :

```cpp
#include <Arduino.h>
#include "Pins.h"
#include "ButtonMatrix.h"
#include "LedDriver.h"
#include "LedAnimator.h"
#include "MotionControl.h"
#include "UartLink.h"
#include "GameController.h"

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("BOOT_START");
  pinMode(PIN_LED_DEBUG, OUTPUT);

  UartLink::init();
  LedDriver::init();
  LedAnimator::init();
  ButtonMatrix::init();
  MotionControl::init();
  GameController::init();

  Serial.println("SETUP_DONE");
}

void loop() {
  UartLink::poll();
  ButtonMatrix::poll();
  GameController::tick();
  LedAnimator::tick();
}
```

- [ ] **Step 2.8: Compiler**

Compiler dans Arduino IDE.
Expected: compilation OK. Si erreurs de linkage type "undefined reference", vérifier que tous les `.cpp` sont bien dans le même dossier que le `.ino`.

- [ ] **Step 2.9: Test (si carte branchée)**

Flasher, ouvrir Serial monitor 115200.
Expected output:
```
BOOT_START
[UartLink] init
[LedDriver] init (stub)
[LedAnimator] init (stub)
[ButtonMatrix] init (stub)
[MotionControl] init (FreeRTOS task)
[GameController] init
SETUP_DONE
```

- [ ] **Step 2.10: Commit**

```bash
git add firmware/arduino_quoridor/
git commit -m "feat(firmware): headers et stubs des 6 modules + integration sketch"
```

---

### Task 3 : FSM — état BOOT + transition vers WAITING_RPI

**Files:**
- Modify: `firmware/arduino_quoridor/GameController.cpp`

L'état BOOT exécute les self-tests (LedDriver, MotionControl) puis lance le homing. Tout étant en stub pour ce plan, les self-tests retournent OK et BOOT transitionne immédiatement vers WAITING_RPI. On ajoute une petite temporisation pour observer la trace au Serial.

- [ ] **Step 3.1: Implémenter BOOT dans `GameController.cpp`**

Remplacer le contenu de `GameController.cpp` :

```cpp
#include "GameController.h"
#include "LedDriver.h"
#include "MotionControl.h"
#include "UartLink.h"

namespace {
  GameController::State _state = GameController::State::BOOT;
  unsigned long _stateEnteredMs = 0;

  void enterState(GameController::State s) {
    _state = s;
    _stateEnteredMs = millis();
    Serial.print("[GameController] -> state ");
    Serial.println((int)s);
  }

  void tickBoot() {
    // self-tests successifs
    if (!LedDriver::selfTest()) {
      Serial.println("[GameController] BOOT_FAILED LedDriver");
      enterState(GameController::State::ERROR_STATE);
      return;
    }
    if (!MotionControl::selfTest()) {
      Serial.println("[GameController] BOOT_FAILED I2C/MotionControl");
      enterState(GameController::State::ERROR_STATE);
      return;
    }
    // homing : poste une commande HOMING et attend DONE
    MotionControl::Command cmd = { MotionControl::CommandKind::HOMING, 0, 0, false };
    if (!MotionControl::postCommand(cmd)) {
      enterState(GameController::State::ERROR_STATE);
      return;
    }
    // on attend la réponse de la tâche moteurs (bornée à 10 s)
    MotionControl::Result res;
    unsigned long start = millis();
    while (millis() - start < 10000) {
      if (MotionControl::tryGetResult(res)) {
        if (res.kind == MotionControl::ResultKind::DONE) {
          enterState(GameController::State::WAITING_RPI);
        } else {
          Serial.println("[GameController] BOOT_FAILED homing");
          enterState(GameController::State::ERROR_STATE);
        }
        return;
      }
      delay(10);  // toléré uniquement pendant BOOT, jamais ailleurs
    }
    Serial.println("[GameController] BOOT_FAILED homing_timeout");
    enterState(GameController::State::ERROR_STATE);
  }
}

void GameController::init() {
  Serial.println("[GameController] init");
  enterState(State::BOOT);
}

void GameController::tick() {
  switch (_state) {
    case State::BOOT:
      tickBoot();
      break;
    default:
      break;
  }
}

GameController::State GameController::currentState() {
  return _state;
}
```

- [ ] **Step 3.2: Compiler**

Expected: compilation OK.

- [ ] **Step 3.3: Test (si carte branchée)**

Flasher, ouvrir Serial monitor.
Expected output (la simulation MotionControl prend 1 s) :
```
BOOT_START
... [tous les init] ...
SETUP_DONE
[GameController] -> state 0           // BOOT
[LedDriver] selfTest -> OK (stub)
[MotionControl] selfTest -> OK (stub I2C)
[MotionControl] exec command kind=0   // HOMING
... 1 s plus tard ...
[GameController] -> state 1           // WAITING_RPI
```

- [ ] **Step 3.4: Commit**

```bash
git add firmware/arduino_quoridor/GameController.cpp
git commit -m "feat(firmware): FSM etat BOOT avec self-tests et homing"
```

---

### Task 4 : États WAITING_RPI / DEMO / CONNECTED + transitions

**Files:**
- Modify: `firmware/arduino_quoridor/GameController.cpp`

WAITING_RPI envoie `HELLO` toutes les 200 ms et attend `HELLO_ACK` pendant 3 s. Si reçu → CONNECTED. Sinon → DEMO (terminal).

- [ ] **Step 4.1: Ajouter les transitions WAITING_RPI**

Dans `GameController.cpp`, ajouter dans le namespace anonyme :

```cpp
  unsigned long _lastHelloMs = 0;
  static constexpr unsigned long HELLO_PERIOD_MS  = 200;
  static constexpr unsigned long HELLO_TIMEOUT_MS = 3000;

  void tickWaitingRpi() {
    // émission HELLO périodique
    if (millis() - _lastHelloMs >= HELLO_PERIOD_MS) {
      UartLink::sendLine("HELLO");
      _lastHelloMs = millis();
    }
    // ACK reçu ?
    String line;
    if (UartLink::tryReadLine(line)) {
      if (line == "HELLO_ACK") {
        enterState(GameController::State::CONNECTED);
        return;
      }
      // autres lignes ignorées en WAITING_RPI
    }
    // timeout total ?
    if (millis() - _stateEnteredMs >= HELLO_TIMEOUT_MS) {
      enterState(GameController::State::DEMO);
    }
  }

  void tickDemo() {
    // drainer les lignes UART entrantes pour ne pas saturer le buffer interne
    // (DEMO ne traite aucune trame, mais on consomme pour libérer UartLink)
    String drained;
    while (UartLink::tryReadLine(drained)) {
      // ignoré : DEMO est terminal jusqu'au reset
    }
    // émission tick de vie toutes les 500 ms
    static unsigned long _lastDemoMs = 0;
    if (millis() - _lastDemoMs >= 500) {
      Serial.println("[GameController] DEMO tick");
      digitalWrite(2, !digitalRead(2));   // toggle LED debug
      _lastDemoMs = millis();
    }
  }

  void tickConnected() {
    // sera complétée tâche 5 + 6
  }
```

Ajouter les cas dans le `switch` de `tick()` :

```cpp
void GameController::tick() {
  switch (_state) {
    case State::BOOT:        tickBoot();        break;
    case State::WAITING_RPI: tickWaitingRpi();  break;
    case State::DEMO:        tickDemo();        break;
    case State::CONNECTED:   tickConnected();   break;
    default: break;
  }
}
```

- [ ] **Step 4.2: Compiler**

Expected: compilation OK.

- [ ] **Step 4.3: Test cas DEMO (si carte branchée)**

Flasher, ouvrir Serial monitor mais NE RIEN ENVOYER.
Expected: après les transitions BOOT, on voit `HELLO` répétés ~15 fois puis transition vers DEMO, puis `[GameController] DEMO tick` toutes les 500 ms et clignotement LED bleue.

- [ ] **Step 4.4: Test cas CONNECTED (si carte branchée)**

Reset l'ESP32 (bouton EN). Pendant les 3 s qui suivent BOOT, taper `HELLO_ACK` + Entrée dans le Serial monitor.
Expected: transition `-> state 3` (CONNECTED), plus de `HELLO`, LED debug ne clignote plus.

- [ ] **Step 4.5: Commit**

```bash
git add firmware/arduino_quoridor/GameController.cpp
git commit -m "feat(firmware): FSM etats WAITING_RPI et DEMO"
```

---

### Task 5 : CONNECTED — surveillance KEEPALIVE + bascule ERROR_STATE

**Files:**
- Modify: `firmware/arduino_quoridor/GameController.cpp`

Une fois en CONNECTED, on surveille la réception de `KEEP` (toléré aussi par d'autres trames qui réinitialisent le timer). 3 s sans aucune trame entrante → bascule ERROR_STATE avec code `ERR_UART_LOST`.

- [ ] **Step 5.1: Ajouter compteur KEEPALIVE et état ERROR_STATE**

Dans le namespace anonyme :

```cpp
  unsigned long _lastUartActivityMs = 0;
  static constexpr unsigned long UART_TIMEOUT_MS = 3000;

  void resetUartActivity() {
    _lastUartActivityMs = millis();
  }

  void enterError(const char* code) {
    Serial.print("[GameController] ENTER ERROR code=");
    Serial.println(code);
    // actions de sécurité (stubs en plan 1)
    // - moteurs : on pose un fanion en mémoire (le vrai stop sera fait au plan 7)
    // - servo : idem
    LedAnimator::play(LedAnimator::Pattern::ERROR_PATTERN);
    String msg = "ERR ";
    msg += code;
    UartLink::sendLine(msg);
    enterState(GameController::State::ERROR_STATE);
  }
```

(Inclure `LedAnimator.h` en haut de `GameController.cpp` si pas déjà fait.)

Modifier `tickConnected` :

```cpp
  void tickConnected() {
    // surveillance KEEPALIVE
    if (millis() - _lastUartActivityMs >= UART_TIMEOUT_MS) {
      enterError("UART_LOST");
      return;
    }
    // lecture trames entrantes
    String line;
    if (UartLink::tryReadLine(line)) {
      resetUartActivity();
      if (line == "KEEP") {
        // rien à faire, juste reset l'activité (déjà fait)
      } else {
        // autres trames seront traitées dans la tâche 6
        Serial.print("[GameController] CONNECTED rx unhandled: ");
        Serial.println(line);
      }
    }
  }
```

Initialiser `_lastUartActivityMs` au moment d'entrer en CONNECTED. Modifier `tickWaitingRpi` :

```cpp
      if (line == "HELLO_ACK") {
        resetUartActivity();
        enterState(GameController::State::CONNECTED);
        return;
      }
```

Ajouter le cas ERROR_STATE dans `tick()` :

```cpp
  void tickError() {
    // attente CMD_RESET ou reset matériel
    String line;
    if (UartLink::tryReadLine(line)) {
      if (line == "RESET") {
        Serial.println("[GameController] RESET requested");
        delay(100);
        ESP.restart();
      }
    }
  }
```

```cpp
void GameController::tick() {
  switch (_state) {
    case State::BOOT:         tickBoot();         break;
    case State::WAITING_RPI:  tickWaitingRpi();   break;
    case State::DEMO:         tickDemo();         break;
    case State::CONNECTED:    tickConnected();    break;
    case State::ERROR_STATE:  tickError();        break;
    default: break;
  }
}
```

- [ ] **Step 5.2: Compiler**

Expected: compilation OK.

- [ ] **Step 5.3: Test perte UART (si carte branchée)**

Flasher, taper `HELLO_ACK` pendant les 3 s post-boot pour entrer en CONNECTED. Ensuite **ne plus rien taper**.
Expected: après 3 s sans activité, message `[GameController] ENTER ERROR code=UART_LOST` et transition vers ERROR_STATE.

- [ ] **Step 5.4: Test KEEPALIVE maintient CONNECTED (si carte branchée)**

Reset, `HELLO_ACK`, puis taper `KEEP` toutes les ~2 s pendant 10 s.
Expected: l'ESP32 reste en CONNECTED, pas d'ERROR.

- [ ] **Step 5.5: Test RESET depuis ERROR (si carte branchée)**

Depuis ERROR_STATE, taper `RESET`.
Expected: `[GameController] RESET requested` puis nouveau `BOOT_START` (l'ESP32 reboote).

- [ ] **Step 5.6: Commit**

```bash
git add firmware/arduino_quoridor/GameController.cpp
git commit -m "feat(firmware): surveillance KEEPALIVE + transition ERROR + RESET"
```

---

### Task 6 : BUTTON_INTENT_PENDING — émission intention + ACK/NACK/timeout + escalade

**Files:**
- Modify: `firmware/arduino_quoridor/GameController.cpp`

Un clic bouton (simulé via `BTN <r> <c>` reçu sur UART qui appelle `ButtonMatrix::injectMoveIntent`) déclenche l'émission d'une intention `MOVE_REQ`/`WALL_REQ` et la transition vers BUTTON_INTENT_PENDING. Là on attend `ACK`, `NACK` ou un timeout 500 ms. 3 timeouts consécutifs → ERROR.

- [ ] **Step 6.1: Étendre `tickConnected` pour gérer `BTN` simulé et les intentions**

Inclure `ButtonMatrix.h` en haut de `GameController.cpp` s'il ne l'est pas déjà. Compléter `tickConnected` :

```cpp
  uint8_t _consecutiveTimeouts = 0;
  static constexpr uint8_t MAX_CONSECUTIVE_TIMEOUTS = 3;
  static constexpr unsigned long INTENT_ACK_TIMEOUT_MS = 500;

  void emitIntent(const ButtonMatrix::Intent& intent) {
    String msg;
    switch (intent.kind) {
      case ButtonMatrix::IntentKind::MOVE:
        msg = "MOVE_REQ "; msg += intent.row; msg += " "; msg += intent.col;
        break;
      case ButtonMatrix::IntentKind::WALL_H:
        msg = "WALL_REQ h "; msg += intent.row; msg += " "; msg += intent.col;
        break;
      case ButtonMatrix::IntentKind::WALL_V:
        msg = "WALL_REQ v "; msg += intent.row; msg += " "; msg += intent.col;
        break;
      default:
        return;
    }
    UartLink::sendLine(msg);
    LedAnimator::play(LedAnimator::Pattern::PENDING_FLASH);
    enterState(GameController::State::BUTTON_INTENT_PENDING);
  }

  void tickConnected() {
    if (millis() - _lastUartActivityMs >= UART_TIMEOUT_MS) {
      enterError("UART_LOST");
      return;
    }
    String line;
    if (UartLink::tryReadLine(line)) {
      resetUartActivity();
      if (line == "KEEP") {
        // rien
      } else if (line.startsWith("BTN ")) {
        // simulation d'un clic — sera retiré au plan 4 quand ButtonMatrix sera réel
        int sp1 = line.indexOf(' ', 4);
        int row = line.substring(4, sp1).toInt();
        int col = line.substring(sp1 + 1).toInt();
        ButtonMatrix::injectMoveIntent((uint8_t)row, (uint8_t)col);
      } else if (line.startsWith("CMD ")) {
        // sera traitée tâche 7
        Serial.print("[GameController] CMD recue (sera traitee tache 7): ");
        Serial.println(line);
      } else {
        Serial.print("[GameController] CONNECTED rx unhandled: ");
        Serial.println(line);
      }
    }
    // intention bouton ?
    if (ButtonMatrix::hasIntent()) {
      emitIntent(ButtonMatrix::takeIntent());
    }
  }

  void tickIntentPending() {
    if (millis() - _lastUartActivityMs >= UART_TIMEOUT_MS) {
      enterError("UART_LOST");
      return;
    }
    String line;
    if (UartLink::tryReadLine(line)) {
      resetUartActivity();
      if (line == "ACK") {
        _consecutiveTimeouts = 0;
        // pour le plan 1, on enchaîne directement EXECUTING (sera affiné tâche 7)
        enterState(GameController::State::EXECUTING);
        return;
      }
      if (line == "NACK") {
        _consecutiveTimeouts = 0;
        LedAnimator::play(LedAnimator::Pattern::NACK_FLASH);
        enterState(GameController::State::CONNECTED);
        return;
      }
      if (line == "KEEP") {
        // toléré pendant l'attente, ne quitte pas l'état
        return;
      }
      Serial.print("[GameController] INTENT_PENDING rx unhandled: ");
      Serial.println(line);
    }
    // timeout 500 ms ?
    if (millis() - _stateEnteredMs >= INTENT_ACK_TIMEOUT_MS) {
      _consecutiveTimeouts++;
      Serial.print("[GameController] intent timeout (consecutive=");
      Serial.print(_consecutiveTimeouts); Serial.println(")");
      LedAnimator::play(LedAnimator::Pattern::TIMEOUT_FLASH);
      if (_consecutiveTimeouts >= MAX_CONSECUTIVE_TIMEOUTS) {
        enterError("UART_LOST");
        return;
      }
      enterState(GameController::State::CONNECTED);
    }
  }
```

Ajouter le cas dans `tick()` :

```cpp
    case State::BUTTON_INTENT_PENDING: tickIntentPending(); break;
```

- [ ] **Step 6.2: Compiler**

Expected: compilation OK.

- [ ] **Step 6.3: Test ACK (si carte branchée)**

Flasher, `HELLO_ACK`, `BTN 3 4` (simule clic), puis rapidement `ACK`.
Expected:
```
... CONNECTED ...
[GameController] -> state 4   // BUTTON_INTENT_PENDING
MOVE_REQ 3 4                  // émis sur UART
[LedAnimator] play pattern=2  // PENDING_FLASH
... ACK reçu ...
[GameController] -> state 5   // EXECUTING
```

- [ ] **Step 6.4: Test NACK**

Reset, `HELLO_ACK`, `BTN 1 1`, puis `NACK`.
Expected: retour CONNECTED avec `[LedAnimator] play pattern=3` (NACK_FLASH).

- [ ] **Step 6.5: Test timeout simple**

Reset, `HELLO_ACK`, `BTN 0 0`, **ne rien envoyer pendant 600 ms**.
Expected: `intent timeout (consecutive=1)` puis retour CONNECTED, pattern TIMEOUT_FLASH.

- [ ] **Step 6.6: Test escalade ERROR après 3 timeouts**

Reset, `HELLO_ACK`, puis 3 fois de suite : `BTN x y`, attendre 600 ms (sans répondre).
Important : entre chaque clic, taper `KEEP` pour ne pas que ce soit l'UART_LOST de fond qui déclenche l'ERROR.
Expected au 3e timeout : `ENTER ERROR code=UART_LOST`.

- [ ] **Step 6.7: Commit**

```bash
git add firmware/arduino_quoridor/GameController.cpp
git commit -m "feat(firmware): FSM BUTTON_INTENT_PENDING avec ACK/NACK/timeout + escalade"
```

---

### Task 7 : EXECUTING — orchestration MotionControl + sortie DONE

**Files:**
- Modify: `firmware/arduino_quoridor/GameController.cpp`

Quand on entre en EXECUTING (depuis ACK ou depuis une commande `CMD ...`), on poste une commande sur la queue MotionControl et on attend le résultat. Pendant ce temps, le scan boutons est gelé (en plan 1, ButtonMatrix est de toute façon stub, donc rien à geler ; on consigne juste l'intention de geler — la mécanique réelle sera ajoutée au plan 4). Sur DONE → envoie `DONE` au RPi → retour CONNECTED. Sur erreur moteur → ERROR.

- [ ] **Step 7.1: Implémenter `tickExecuting` et entrée depuis CMD**

Ajouter dans le namespace anonyme :

```cpp
  bool _waitingMotion = false;

  void enterExecutingWithCommand(const MotionControl::Command& cmd) {
    if (!MotionControl::postCommand(cmd)) {
      enterError("MOTION_QUEUE_FULL");
      return;
    }
    _waitingMotion = true;
    LedAnimator::play(LedAnimator::Pattern::EXECUTING_SPINNER);
    enterState(GameController::State::EXECUTING);
  }

  void tickExecuting() {
    if (millis() - _lastUartActivityMs >= UART_TIMEOUT_MS) {
      enterError("UART_LOST");
      return;
    }
    // KEEPALIVE peut arriver
    String line;
    if (UartLink::tryReadLine(line)) {
      resetUartActivity();
      // les autres trames sont ignorées pendant EXECUTING
    }
    // résultat moteur ?
    MotionControl::Result res;
    if (_waitingMotion && MotionControl::tryGetResult(res)) {
      _waitingMotion = false;
      switch (res.kind) {
        case MotionControl::ResultKind::DONE:
          UartLink::sendLine("DONE");
          enterState(GameController::State::CONNECTED);
          break;
        case MotionControl::ResultKind::ERR_MOTOR_TIMEOUT:
          enterError("MOTOR_TIMEOUT");
          break;
        case MotionControl::ResultKind::ERR_LIMIT_UNEXPECTED:
          enterError("LIMIT_UNEXPECTED");
          break;
        case MotionControl::ResultKind::ERR_HOMING_FAILED:
          enterError("HOMING_FAILED");
          break;
        case MotionControl::ResultKind::ERR_I2C_NACK:
          enterError("I2C_NACK");
          break;
      }
    }
  }
```

Modifier la branche ACK de `tickIntentPending` pour utiliser une vraie commande :

```cpp
      if (line == "ACK") {
        _consecutiveTimeouts = 0;
        MotionControl::Command cmd = { MotionControl::CommandKind::MOVE_TO_WALL_SLOT, 0, 0, false };
        enterExecutingWithCommand(cmd);
        return;
      }
```

Modifier la branche `CMD` de `tickConnected` pour traiter `CMD MOVE <r> <c>` :

```cpp
      } else if (line.startsWith("CMD MOVE ")) {
        int sp1 = line.indexOf(' ', 9);
        int row = line.substring(9, sp1).toInt();
        int col = line.substring(sp1 + 1).toInt();
        MotionControl::Command cmd = { MotionControl::CommandKind::MOVE_TO_WALL_SLOT,
                                       (uint8_t)row, (uint8_t)col, false };
        enterExecutingWithCommand(cmd);
      } else if (line.startsWith("CMD ")) {
        Serial.print("[GameController] CMD non-impl: "); Serial.println(line);
      }
```

Ajouter dans `tick()` :

```cpp
    case State::EXECUTING: tickExecuting(); break;
```

- [ ] **Step 7.2: Compiler**

Expected: compilation OK.

- [ ] **Step 7.3: Test cycle ACK → EXECUTING → DONE → CONNECTED**

Flasher, `HELLO_ACK`, `BTN 2 3`, `ACK`. Attendre 1 s.
Expected:
```
[GameController] -> state 4              // BUTTON_INTENT_PENDING
MOVE_REQ 2 3
ACK reçu
[MotionControl] exec command kind=1
[LedAnimator] play pattern=5             // EXECUTING_SPINNER
[GameController] -> state 5              // EXECUTING
... 1 s plus tard ...
DONE                                     // émis sur UART
[GameController] -> state 3              // CONNECTED
```

- [ ] **Step 7.4: Test commande directe CMD MOVE**

Reset, `HELLO_ACK`, `CMD MOVE 4 5`. Attendre 1 s.
Expected: pareil mais sans passage par BUTTON_INTENT_PENDING.

- [ ] **Step 7.5: Commit**

```bash
git add firmware/arduino_quoridor/GameController.cpp
git commit -m "feat(firmware): FSM EXECUTING avec orchestration MotionControl"
```

---

### Task 8 : Watchdog ESP32 sur les deux cœurs

**Files:**
- Modify: `firmware/arduino_quoridor/arduino_quoridor.ino`
- Modify: `firmware/arduino_quoridor/MotionControl.cpp`

Activation du watchdog avec timeout 5 s. La loop principale (Core 1) et la tâche moteurs (Core 0) sont enregistrées et doivent appeler `esp_task_wdt_reset()` à chaque itération. Si une tâche freeze > 5 s, l'ESP32 reboote → BOOT propre.

- [ ] **Step 8.1: Activer le watchdog dans `setup()`**

Modifier `arduino_quoridor.ino` :

```cpp
#include <Arduino.h>
#include "esp_task_wdt.h"
#include "Pins.h"
#include "ButtonMatrix.h"
#include "LedDriver.h"
#include "LedAnimator.h"
#include "MotionControl.h"
#include "UartLink.h"
#include "GameController.h"

static constexpr uint32_t WDT_TIMEOUT_S = 5;

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("BOOT_START");
  pinMode(PIN_LED_DEBUG, OUTPUT);

  // watchdog 5 s pour les deux coeurs
  esp_task_wdt_init(WDT_TIMEOUT_S, true);   // panic on timeout
  esp_task_wdt_add(NULL);                   // enregistre la tâche courante (loopTask Core 1)

  UartLink::init();
  LedDriver::init();
  LedAnimator::init();
  ButtonMatrix::init();
  MotionControl::init();
  GameController::init();

  Serial.println("SETUP_DONE");
}

void loop() {
  esp_task_wdt_reset();
  UartLink::poll();
  ButtonMatrix::poll();
  GameController::tick();
  LedAnimator::tick();
}
```

- [ ] **Step 8.2: Enregistrer la tâche moteurs au watchdog**

Modifier `MotionControl.cpp`, dans `motionTask` :

```cpp
  void motionTask(void* arg) {
    esp_task_wdt_add(NULL);                  // enregistre cette tâche
    MotionControl::Command cmd;
    for (;;) {
      esp_task_wdt_reset();
      if (xQueueReceive(_commandQueue, &cmd, pdMS_TO_TICKS(500)) == pdTRUE) {
        Serial.print("[MotionControl] exec command kind=");
        Serial.println((int)cmd.kind);
        // simulation découpée pour ne pas dépasser le watchdog
        for (int i = 0; i < 10; ++i) {
          esp_task_wdt_reset();
          vTaskDelay(pdMS_TO_TICKS(100));
        }
        MotionControl::Result res = { MotionControl::ResultKind::DONE };
        xQueueSend(_resultQueue, &res, 0);
      }
    }
  }
```

(Inclure `#include "esp_task_wdt.h"` en haut du fichier.)

- [ ] **Step 8.3: Compiler**

Expected: compilation OK.

- [ ] **Step 8.4: Test fonctionnement normal (si carte branchée)**

Flasher. Faire les tests précédents (BOOT, WAITING_RPI, CONNECTED, BUTTON_INTENT_PENDING, EXECUTING).
Expected: aucun reboot intempestif. Le watchdog ne se déclenche jamais en fonctionnement nominal.

- [ ] **Step 8.5: Test du watchdog (provocation contrôlée)**

Pour vérifier qu'il fonctionne, ajouter temporairement dans `tickDemo` un `delay(7000);` (7 s, > timeout watchdog). Compiler, flasher, laisser entrer en DEMO.
Expected: au bout de ~5 s, l'ESP32 reboote spontanément, on revoit `BOOT_START`. **Retirer le `delay` après le test, ne pas commit.**

- [ ] **Step 8.6: Commit**

```bash
git add firmware/arduino_quoridor/arduino_quoridor.ino firmware/arduino_quoridor/MotionControl.cpp
git commit -m "feat(firmware): watchdog ESP32 sur loop principale et tache moteurs"
```

---

### Task 9 : Test d'intégration complet — parcours nominal et chemins d'erreur

**Files:** aucun fichier modifié (tâche de validation pure).

Cette tâche n'écrit pas de code ; elle exécute une procédure de validation manuelle complète et vérifie que le firmware se comporte conformément au spec. À faire dès que la PCB est branchable, ou avec un ESP32 nu.

- [ ] **Step 9.1: Préparer**

Brancher l'ESP32 par USB. Ouvrir Serial monitor à 115200 bauds, fin de ligne = "Newline" (pas "Both NL & CR"). Avoir le spec sous la main pour comparer.

- [ ] **Step 9.2: Scénario 1 — boot nominal vers DEMO**

Reset l'ESP32. Ne rien taper.
Expected:
- `BOOT_START`
- traces d'init des 6 modules
- `SETUP_DONE`
- transition BOOT → WAITING_RPI (après ~1 s, le temps du homing simulé)
- 15 émissions de `HELLO` espacées de 200 ms
- transition WAITING_RPI → DEMO
- `DEMO tick` toutes les 500 ms, LED bleue clignote
- état stable, jamais d'ERROR

- [ ] **Step 9.3: Scénario 2 — boot nominal vers CONNECTED**

Reset. Pendant les 3 s post-BOOT, taper `HELLO_ACK`. Ensuite taper `KEEP` toutes les 2 s pendant 30 s.
Expected: transition vers CONNECTED, pas de bascule ERROR. Stabilité parfaite.

- [ ] **Step 9.4: Scénario 3 — cycle de jeu simulé complet**

Depuis CONNECTED, en envoyant `KEEP` régulièrement :
1. `BTN 2 3` → MOVE_REQ émis, BUTTON_INTENT_PENDING
2. `ACK` → EXECUTING, DONE émis 1 s plus tard, retour CONNECTED
3. `BTN 1 1` → MOVE_REQ
4. `NACK` → retour CONNECTED, pattern NACK_FLASH
5. `CMD MOVE 4 4` → EXECUTING direct, DONE 1 s plus tard, retour CONNECTED

Expected: toutes les transitions conformes, LED debug ne clignote pas pendant CONNECTED.

- [ ] **Step 9.5: Scénario 4 — perte UART en CONNECTED**

Depuis CONNECTED, ne rien envoyer pendant 4 s.
Expected: après 3 s exactement, `ENTER ERROR code=UART_LOST`, transition vers ERROR_STATE, `ERR UART_LOST` émis.

- [ ] **Step 9.6: Scénario 5 — escalade timeout intent**

Reset, `HELLO_ACK`. Puis 3 fois : `BTN x y` puis attendre 600 ms en envoyant un seul `KEEP` au milieu.
Expected: 3 timeouts consécutifs comptés, au 3e bascule vers ERROR_STATE.

- [ ] **Step 9.7: Scénario 6 — récupération depuis ERROR**

Depuis ERROR_STATE, taper `RESET`.
Expected: reboot complet, retour à `BOOT_START`.

- [ ] **Step 9.8: Vérifier la couverture du spec**

Cocher chaque état et chaque transition listés dans `2026-04-28-firmware-esp32-architecture-globale-design.md` §2.4. Tous doivent avoir été observés dans les scénarios 2-7.

- [ ] **Step 9.9: Si carte non disponible : noter l'item bloquant**

Créer un fichier `firmware/arduino_quoridor/TESTS_PENDING.md` avec la liste des scénarios non joués (à faire dès réception PCB) :

```markdown
# Tests d'intégration en attente de hardware

Le firmware compile et a passé une revue manuelle du code, mais les
scénarios 1 à 6 du Plan 1 (Task 9) n'ont pas été exécutés sur cible.

À faire dès qu'un ESP32 (PCB v2 ou DevKit nu) est disponible.
```

- [ ] **Step 9.10: Commit**

Si scénarios joués avec succès :
```bash
git commit --allow-empty -m "test(firmware): plan 1 valide en bout-en-bout sur cible"
```

Si tests reportés :
```bash
git add firmware/arduino_quoridor/TESTS_PENDING.md
git commit -m "test(firmware): plan 1 compile, tests cible reportes (carte indisponible)"
```

---

## Critères de succès du plan 1

- [ ] Le firmware compile sans warning bloquant dans Arduino IDE
- [ ] Les 6 modules existent en stub avec API publique cohérente
- [ ] La FSM globale `GameController` implémente les 7 états et toutes les transitions du spec §2.4
- [ ] Le watchdog est actif sur les deux cœurs et ne se déclenche pas en fonctionnement nominal
- [ ] Tous les scénarios de la Task 9 passent (ou sont consignés comme "en attente hardware")
- [ ] Aucun usage de `delay()` dans la loop principale (sauf BOOT bornée)
- [ ] Toutes les boucles d'attente sont bornées par un timeout

## Hors scope du plan 1 (sera traité dans les plans suivants)

- Scan réel de la matrice de boutons (Plan 4)
- Driver WS2812B fonctionnel et animations LED (Plans 5 et 6)
- Pilotage réel des moteurs A4988 + servo SG90 + homing physique (Plan 7)
- Protocole UART binaire final avec checksum (Plan 2 + Plan 3)
- Adaptation côté Python `main.py` pour piloter le firmware (Plan 8)
- Mode boutons collés (sera ajouté quand ButtonMatrix sera réel — Plan 4)

## Notes pour la reprise

Si tu reprends ce plan dans une session future, le point d'entrée est `firmware/arduino_quoridor/arduino_quoridor.ino`. La FSM est entièrement dans `GameController.cpp`. Le protocole texte temporaire est documenté en haut de ce fichier de plan dans la section "Notes de contexte importantes". Les commandes UART simulant le RPi pour les tests sont les mêmes qui seront remplacées au plan 3 par le vrai protocole binaire.
