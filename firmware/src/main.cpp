#include <Arduino.h>
#include "Pins.h"

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("BOOT_START");
  pinMode(PIN_LED_DEBUG, OUTPUT);
}

void loop() {
  // vide pour l'instant (sera complete par la Task 2)
}
