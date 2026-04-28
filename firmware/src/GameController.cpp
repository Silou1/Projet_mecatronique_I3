#include "GameController.h"

namespace {
  GameController::State _state = GameController::State::BOOT;
}

void GameController::init() {
  Serial.println("[GameController] init");
  _state = State::BOOT;
}

void GameController::tick() {
  // sera implementee tache par tache
}

GameController::State GameController::currentState() {
  return _state;
}
