#ifndef LED_DRIVER_H
#define LED_DRIVER_H

#include <Arduino.h>

namespace LedDriver {
  void init();
  void setPixel(uint8_t index, uint8_t r, uint8_t g, uint8_t b);
  void clear();
  void show();              // push atomique vers la chaine LED (stub plan 1)
  bool selfTest();          // utilise par BOOT
}

#endif
