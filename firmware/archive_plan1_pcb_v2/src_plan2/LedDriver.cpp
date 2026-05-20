#include "LedDriver.h"
#include "UartLink.h"

void LedDriver::init() {
  UartLink::log("LED", "init (stub)");
}

void LedDriver::setPixel(uint8_t index, uint8_t r, uint8_t g, uint8_t b) {
  // stub : log uniquement
  UartLink::logf("LED", "setPixel %d %d %d %d", index, r, g, b);
}

void LedDriver::clear() {
  UartLink::log("LED", "clear");
}

void LedDriver::show() {
  // stub : pas de push WS2812B en plan 1
}

bool LedDriver::selfTest() {
  UartLink::log("LED", "selfTest -> OK (stub)");
  return true;
}
