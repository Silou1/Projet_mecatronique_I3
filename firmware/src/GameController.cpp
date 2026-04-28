#include "GameController.h"
#include "LedDriver.h"
#include "LedAnimator.h"
#include "MotionControl.h"
#include "UartLink.h"

namespace {
  GameController::State _state = GameController::State::BOOT;
  unsigned long _stateEnteredMs = 0;

  unsigned long _lastHelloMs = 0;
  static constexpr unsigned long HELLO_PERIOD_MS  = 200;
  static constexpr unsigned long HELLO_TIMEOUT_MS = 3000;

  unsigned long _lastUartActivityMs = 0;
  static constexpr unsigned long UART_TIMEOUT_MS = 3000;

  void enterState(GameController::State s) {
    _state = s;
    _stateEnteredMs = millis();
    Serial.print("[GameController] -> state ");
    Serial.println((int)s);
  }

  void resetUartActivity() {
    _lastUartActivityMs = millis();
  }

  void enterError(const char* code) {
    Serial.print("[GameController] ENTER ERROR code=");
    Serial.println(code);
    // actions de securite (stubs en plan 1)
    // - moteurs : on pose un fanion en memoire (le vrai stop sera fait au plan 7)
    // - servo : idem
    LedAnimator::play(LedAnimator::Pattern::ERROR_PATTERN);
    String msg = "ERR ";
    msg += code;
    UartLink::sendLine(msg);
    enterState(GameController::State::ERROR_STATE);
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
    // on attend la reponse de la tache moteurs (bornee a 10 s)
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
      delay(10);  // tolere uniquement pendant BOOT, jamais ailleurs
    }
    Serial.println("[GameController] BOOT_FAILED homing_timeout");
    enterState(GameController::State::ERROR_STATE);
  }

  void tickWaitingRpi() {
    // emission HELLO periodique
    if (millis() - _lastHelloMs >= HELLO_PERIOD_MS) {
      UartLink::sendLine("HELLO");
      _lastHelloMs = millis();
    }
    // ACK recu ?
    String line;
    if (UartLink::tryReadLine(line)) {
      if (line == "HELLO_ACK") {
        resetUartActivity();
        enterState(GameController::State::CONNECTED);
        return;
      }
      // autres lignes ignorees en WAITING_RPI
    }
    // timeout total ?
    if (millis() - _stateEnteredMs >= HELLO_TIMEOUT_MS) {
      enterState(GameController::State::DEMO);
    }
  }

  void tickDemo() {
    // drainer les lignes UART entrantes pour ne pas saturer le buffer interne
    String drained;
    while (UartLink::tryReadLine(drained)) {
      // ignore : DEMO est terminal jusqu'au reset
    }
    // emission tick de vie toutes les 500 ms
    static unsigned long _lastDemoMs = 0;
    if (millis() - _lastDemoMs >= 500) {
      Serial.println("[GameController] DEMO tick");
      digitalWrite(2, !digitalRead(2));   // toggle LED debug
      _lastDemoMs = millis();
    }
  }

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
        // rien a faire, juste reset l'activite (deja fait)
      } else {
        // autres trames seront traitees Task 6
        Serial.print("[GameController] CONNECTED rx unhandled: ");
        Serial.println(line);
      }
    }
  }

  void tickError() {
    // attente CMD_RESET ou reset materiel
    String line;
    if (UartLink::tryReadLine(line)) {
      if (line == "RESET") {
        Serial.println("[GameController] RESET requested");
        delay(100);
        ESP.restart();
      }
    }
  }
}

void GameController::init() {
  Serial.println("[GameController] init");
  enterState(State::BOOT);
}

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

GameController::State GameController::currentState() {
  return _state;
}
