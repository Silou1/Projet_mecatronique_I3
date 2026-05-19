// Sketch de test : capteur de fin de course - bring-up breadboard.
// Cible : ESP32-WROOM (Freenove DevKit)
//
// Cablage :
//   - Une borne du switch -> GPIO 13 de l'ESP32
//   - Autre borne du switch -> GND
//   - Pull-up interne ESP32 active (pas de resistance externe necessaire)
//
// Lecture :
//   - LOW  = switch presse
//   - HIGH = switch relache
//
// Sortie : moniteur serie 115200 baud, affichage uniquement aux transitions.

#include <Arduino.h>

static constexpr uint8_t PIN_LIMIT = 13;

static int dernier_etat = -1;

void setup() {
  Serial.begin(115200);
  delay(500);  // laisse au moniteur le temps de s'ouvrir apres flash
  pinMode(PIN_LIMIT, INPUT_PULLUP);

  Serial.println();
  Serial.println("=== Test fin de course - GPIO 13 ===");
  Serial.println("Pull-up interne actif. Appui -> LOW. Relachement -> HIGH.");
  Serial.println("Etat initial :");
}

void loop() {
  int etat = digitalRead(PIN_LIMIT);
  if (etat != dernier_etat) {
    Serial.print("  LIMIT = ");
    Serial.println(etat == LOW ? "LOW  (presse)" : "HIGH (relache)");
    dernier_etat = etat;
  }
  delay(20);  // 50 Hz, lecture stable sans rebond
}
