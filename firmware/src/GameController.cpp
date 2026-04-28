#include "GameController.h"
#include "ButtonMatrix.h"
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

  uint8_t _consecutiveTimeouts = 0;
  static constexpr uint8_t MAX_CONSECUTIVE_TIMEOUTS = 3;
  static constexpr unsigned long INTENT_ACK_TIMEOUT_MS = 500;

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
    LedAnimator::play(LedAnimator::Pattern::ERROR_PATTERN);
    String msg = "ERR ";
    msg += code;
    UartLink::sendLine(msg);
    enterState(GameController::State::ERROR_STATE);
  }

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

  void tickBoot() {
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
    MotionControl::Command cmd = { MotionControl::CommandKind::HOMING, 0, 0, false };
    if (!MotionControl::postCommand(cmd)) {
      enterState(GameController::State::ERROR_STATE);
      return;
    }
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
      delay(10);
    }
    Serial.println("[GameController] BOOT_FAILED homing_timeout");
    enterState(GameController::State::ERROR_STATE);
  }

  void tickWaitingRpi() {
    if (millis() - _lastHelloMs >= HELLO_PERIOD_MS) {
      UartLink::sendLine("HELLO");
      _lastHelloMs = millis();
    }
    String line;
    if (UartLink::tryReadLine(line)) {
      if (line == "HELLO_ACK") {
        resetUartActivity();
        enterState(GameController::State::CONNECTED);
        return;
      }
    }
    if (millis() - _stateEnteredMs >= HELLO_TIMEOUT_MS) {
      enterState(GameController::State::DEMO);
    }
  }

  void tickDemo() {
    String drained;
    while (UartLink::tryReadLine(drained)) {
      // ignore : DEMO est terminal
    }
    static unsigned long _lastDemoMs = 0;
    if (millis() - _lastDemoMs >= 500) {
      Serial.println("[GameController] DEMO tick");
      digitalWrite(2, !digitalRead(2));
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
        // rien
      } else if (line.startsWith("BTN ")) {
        // simulation d'un clic -- sera retire au plan 4 quand ButtonMatrix sera reel
        int sp1 = line.indexOf(' ', 4);
        int row = line.substring(4, sp1).toInt();
        int col = line.substring(sp1 + 1).toInt();
        ButtonMatrix::injectMoveIntent((uint8_t)row, (uint8_t)col);
      } else if (line.startsWith("CMD ")) {
        // sera traitee Task 7
        Serial.print("[GameController] CMD recue (sera traitee Task 7): ");
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
        // pour le plan 1, on enchaine directement EXECUTING (sera affine Task 7)
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
        // tolere pendant l'attente, ne quitte pas l'etat
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

  void tickError() {
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
    case State::BOOT:                  tickBoot();          break;
    case State::WAITING_RPI:           tickWaitingRpi();    break;
    case State::DEMO:                  tickDemo();          break;
    case State::CONNECTED:             tickConnected();     break;
    case State::BUTTON_INTENT_PENDING: tickIntentPending(); break;
    case State::ERROR_STATE:           tickError();         break;
    default: break;
  }
}

GameController::State GameController::currentState() {
  return _state;
}
