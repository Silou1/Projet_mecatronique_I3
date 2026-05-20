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
    bool horizontal;        // utilise pour MOVE_TO_WALL_SLOT
  };

  enum class ResultKind { DONE, ERR_MOTOR_TIMEOUT, ERR_LIMIT_UNEXPECTED, ERR_HOMING_FAILED, ERR_I2C_NACK };

  struct Result {
    ResultKind kind;
  };

  void init();
  bool postCommand(const Command& cmd);    // non bloquant ; renvoie false si queue pleine
  bool tryGetResult(Result& out);          // non bloquant
  bool selfTest();                         // utilise par BOOT (test I2C)
}

#endif
