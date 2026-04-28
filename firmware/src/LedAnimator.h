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
