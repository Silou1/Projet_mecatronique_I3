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
