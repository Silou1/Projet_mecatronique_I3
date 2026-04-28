#include <Arduino.h>
#include "esp_task_wdt.h"
#include "Pins.h"
#include "ButtonMatrix.h"
#include "LedDriver.h"
#include "LedAnimator.h"
#include "MotionControl.h"
#include "UartLink.h"
#include "GameController.h"

static constexpr uint32_t WDT_TIMEOUT_S = 5;

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("BOOT_START");
  pinMode(PIN_LED_DEBUG, OUTPUT);

  // watchdog 5 s pour les deux coeurs
  esp_task_wdt_init(WDT_TIMEOUT_S, true);   // panic on timeout
  esp_task_wdt_add(NULL);                   // enregistre la tache courante (loopTask Core 1)

  UartLink::init();
  LedDriver::init();
  LedAnimator::init();
  ButtonMatrix::init();
  MotionControl::init();
  GameController::init();

  Serial.println("SETUP_DONE");
}

void loop() {
  esp_task_wdt_reset();
  UartLink::poll();
  ButtonMatrix::poll();
  GameController::tick();
  LedAnimator::tick();
}
