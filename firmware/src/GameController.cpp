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

  bool _waitingMotion = false;
  uint8_t _currentCmdAckSeq = 0;

  void enterState(GameController::State s) {
    _state = s;
    _stateEnteredMs = millis();
    UartLink::logf("FSM", "-> state %d", (int)s);
  }

  void resetUartActivity() {
    _lastUartActivityMs = millis();
  }

  void enterError(const char* code) {
    UartLink::logf("FSM", "ENTER ERROR code=%s", code);
    LedAnimator::play(LedAnimator::Pattern::ERROR_PATTERN);
    // Si on etait en train de traiter une CMD (state EXECUTING), respondCmdErr
    // sinon emitSpontaneousErr.
    if (_state == GameController::State::EXECUTING) {
      UartLink::respondCmdErr(_currentCmdAckSeq, code);
    } else {
      UartLink::emitSpontaneousErr(code);
    }
    enterState(GameController::State::ERROR_STATE);
  }

  void emitIntent(const ButtonMatrix::Intent& intent) {
    char args[16];
    const char* type = "MOVE_REQ";
    switch (intent.kind) {
      case ButtonMatrix::IntentKind::MOVE:
        type = "MOVE_REQ";
        snprintf(args, sizeof(args), "%d %d", intent.row, intent.col);
        break;
      case ButtonMatrix::IntentKind::WALL_H:
        type = "WALL_REQ";
        snprintf(args, sizeof(args), "h %d %d", intent.row, intent.col);
        break;
      case ButtonMatrix::IntentKind::WALL_V:
        type = "WALL_REQ";
        snprintf(args, sizeof(args), "v %d %d", intent.row, intent.col);
        break;
      default:
        return;
    }
    UartLink::sendFrame(type, args);
    LedAnimator::play(LedAnimator::Pattern::PENDING_FLASH);
    enterState(GameController::State::BUTTON_INTENT_PENDING);
  }

  void enterExecutingWithCommand(const MotionControl::Command& cmd) {
    if (!MotionControl::postCommand(cmd)) {
      enterError("MOTION_QUEUE_FULL");
      return;
    }
    _waitingMotion = true;
    LedAnimator::play(LedAnimator::Pattern::EXECUTING_SPINNER);
    enterState(GameController::State::EXECUTING);
  }

  void tickBoot() {
    if (!LedDriver::selfTest()) {
      UartLink::log("FSM", "BOOT_FAILED LedDriver");
      enterState(GameController::State::ERROR_STATE);
      return;
    }
    if (!MotionControl::selfTest()) {
      UartLink::log("FSM", "BOOT_FAILED I2C/MotionControl");
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
          UartLink::log("FSM", "BOOT_FAILED homing");
          enterState(GameController::State::ERROR_STATE);
        }
        return;
      }
      delay(10);
    }
    UartLink::log("FSM", "BOOT_FAILED homing_timeout");
    enterState(GameController::State::ERROR_STATE);
  }

  void tickWaitingRpi() {
    if (millis() - _lastHelloMs >= HELLO_PERIOD_MS) {
      UartLink::sendFrame("HELLO", "", -1, UartLink::PROTOCOL_VERSION);
      _lastHelloMs = millis();
    }
    UartLink::Frame f;
    if (UartLink::tryGetFrame(f)) {
      if (strcmp(f.type, "HELLO_ACK") == 0) {
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
    UartLink::Frame drained;
    while (UartLink::tryGetFrame(drained)) {
      // ignore
    }
    static unsigned long _lastDemoMs = 0;
    if (millis() - _lastDemoMs >= 500) {
      UartLink::log("FSM", "DEMO tick");
      digitalWrite(2, !digitalRead(2));
      _lastDemoMs = millis();
    }
  }

  void tickConnected() {
    if (millis() - _lastUartActivityMs >= UART_TIMEOUT_MS) {
      enterError("UART_LOST");
      return;
    }
    UartLink::Frame f;
    if (UartLink::tryGetFrame(f)) {
      resetUartActivity();
      if (strcmp(f.type, "KEEPALIVE") == 0) {
        // KEEPALIVE : juste reset activite
      } else if (strcmp(f.type, "MOVE_REQ") == 0) {
        // Trame d'injection test convertie en MOVE_REQ par UartLink (cf. sec 4.6)
        // Args = "row col"
        int row = 0, col = 0;
        sscanf(f.args, "%d %d", &row, &col);
        ButtonMatrix::injectMoveIntent((uint8_t)row, (uint8_t)col);
      } else if (strcmp(f.type, "CMD") == 0 && strncmp(f.args, "MOVE ", 5) == 0) {
        int row = 0, col = 0;
        sscanf(f.args + 5, "%d %d", &row, &col);
        MotionControl::Command cmd = { MotionControl::CommandKind::MOVE_TO_WALL_SLOT,
                                       (uint8_t)row, (uint8_t)col, false };
        _currentCmdAckSeq = f.seq;
        enterExecutingWithCommand(cmd);
      } else if (strcmp(f.type, "CMD") == 0 && strncmp(f.args, "WALL ", 5) == 0) {
        UartLink::logf("FSM", "CMD WALL stub: %s", f.args + 5);
        UartLink::respondCmdDone(f.seq);
      } else if (strcmp(f.type, "CMD") == 0 && strncmp(f.args, "GAMEOVER ", 9) == 0) {
        UartLink::logf("FSM", "CMD GAMEOVER stub: %s", f.args + 9);
        UartLink::respondCmdDone(f.seq);
      } else if (strcmp(f.type, "CMD") == 0) {
        UartLink::logf("FSM", "CMD non-impl: %s", f.args);
      } else if (strcmp(f.type, "CMD_RESET") == 0) {
        // Reset hors etat ERROR : ignore (le RESET n'est traite qu'en ERROR)
      } else {
        UartLink::logf("FSM", "CONNECTED rx unhandled: %s", f.type);
      }
    }
    if (ButtonMatrix::hasIntent()) {
      emitIntent(ButtonMatrix::takeIntent());
    }
  }

  void tickIntentPending() {
    if (millis() - _lastUartActivityMs >= UART_TIMEOUT_MS) {
      enterError("UART_LOST");
      return;
    }
    UartLink::Frame f;
    if (UartLink::tryGetFrame(f)) {
      resetUartActivity();
      if (strcmp(f.type, "ACK") == 0) {
        _consecutiveTimeouts = 0;
        MotionControl::Command cmd = { MotionControl::CommandKind::MOVE_TO_WALL_SLOT, 0, 0, false };
        _currentCmdAckSeq = f.ack >= 0 ? (uint8_t)f.ack : 0;
        enterExecutingWithCommand(cmd);
        return;
      }
      if (strcmp(f.type, "NACK") == 0) {
        _consecutiveTimeouts = 0;
        LedAnimator::play(LedAnimator::Pattern::NACK_FLASH);
        enterState(GameController::State::CONNECTED);
        return;
      }
      if (strcmp(f.type, "KEEPALIVE") == 0) {
        return;
      }
      UartLink::logf("FSM", "INTENT_PENDING rx unhandled: %s", f.type);
    }
    if (millis() - _stateEnteredMs >= INTENT_ACK_TIMEOUT_MS) {
      _consecutiveTimeouts++;
      UartLink::logf("FSM", "intent timeout consecutive=%d", _consecutiveTimeouts);
      LedAnimator::play(LedAnimator::Pattern::TIMEOUT_FLASH);
      if (_consecutiveTimeouts >= MAX_CONSECUTIVE_TIMEOUTS) {
        enterError("UART_LOST");
        return;
      }
      enterState(GameController::State::CONNECTED);
    }
  }

  void tickExecuting() {
    if (millis() - _lastUartActivityMs >= UART_TIMEOUT_MS) {
      enterError("UART_LOST");
      return;
    }
    UartLink::Frame f;
    if (UartLink::tryGetFrame(f)) {
      resetUartActivity();
      // Toutes trames (sauf erreurs) sont ignorees pendant EXECUTING
    }
    MotionControl::Result res;
    if (_waitingMotion && MotionControl::tryGetResult(res)) {
      _waitingMotion = false;
      switch (res.kind) {
        case MotionControl::ResultKind::DONE:
          UartLink::respondCmdDone(_currentCmdAckSeq);
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

  void tickError() {
    UartLink::Frame f;
    if (UartLink::tryGetFrame(f)) {
      if (strcmp(f.type, "CMD_RESET") == 0) {
        UartLink::log("FSM", "RESET requested");
        UartLink::clearErrState();
        delay(100);
        ESP.restart();
      }
    }
  }
}

void GameController::init() {
  UartLink::log("FSM", "init");
  enterState(State::BOOT);
}

void GameController::tick() {
  switch (_state) {
    case State::BOOT:                  tickBoot();          break;
    case State::WAITING_RPI:           tickWaitingRpi();    break;
    case State::DEMO:                  tickDemo();          break;
    case State::CONNECTED:             tickConnected();     break;
    case State::BUTTON_INTENT_PENDING: tickIntentPending(); break;
    case State::EXECUTING:             tickExecuting();     break;
    case State::ERROR_STATE:           tickError();         break;
    default: break;
  }
}

GameController::State GameController::currentState() {
  return _state;
}
