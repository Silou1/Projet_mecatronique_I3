#include "GameController.h"
#include "LedDriver.h"
#include "MotionControl.h"
// UartLink.h sera inclus en Task 4 quand on emettra HELLO depuis WAITING_RPI

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
