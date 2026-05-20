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
  void tick();          // appelee a chaque iteration de loop()
  State currentState();
}

#endif
