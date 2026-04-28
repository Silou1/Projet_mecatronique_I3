#include <Arduino.h>
#include "Pins.h"
#include "ButtonMatrix.h"
#include "LedDriver.h"
#include "LedAnimator.h"
#include "MotionControl.h"
#include "UartLink.h"
#include "GameController.h"

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("BOOT_START");
  pinMode(PIN_LED_DEBUG, OUTPUT);

  UartLink::init();
  LedDriver::init();
  LedAnimator::init();
  ButtonMatrix::init();
  MotionControl::init();
  GameController::init();

  Serial.println("SETUP_DONE");
}

void loop() {
  UartLink::poll();
  ButtonMatrix::poll();
  GameController::tick();
  LedAnimator::tick();
}
