// Sketch ultra minimal : active UNIQUEMENT le driver DRV8825 #2 (M2).
// But : permettre la calibration du Vref / mesure de courant sur le driver 2
// sans demarrer aucun mouvement, sans toucher au driver 1.
//
// Etat des pins apres boot :
//   M2_EN (GPIO 21) = LOW   -> driver 2 ACTIF (courant dispo dans les bobines)
//   M1_EN (GPIO 26) = HIGH  -> driver 1 OFF (securite)
//   STEP / DIR = LOW        -> aucun pas genere
//
// Usage :
//   pio run -e bringup_driver2_on -t upload
//   pio device monitor -e bringup_driver2_on
//
// Pour mesurer Vref :
//   Multimetre V= : pointe noire sur GND, pointe rouge sur la vis du potentiometre
//   du driver #2. Tourner doucement pour ajuster.
//   Formule DRV8825 + R100 : Vref = I_bobine x 0.5 (ex. 0.25 V = ~0.5 A).

#include <Arduino.h>

static constexpr uint8_t M1_EN   = 26;
static constexpr uint8_t M2_STEP = 16;
static constexpr uint8_t M2_DIR  = 17;
static constexpr uint8_t M2_EN   = 21;

void setup() {
  // Driver 1 hors tension par securite.
  pinMode(M1_EN, OUTPUT);
  digitalWrite(M1_EN, HIGH);

  // Driver 2 : STEP / DIR en niveau bas (pas de pulse), EN = LOW (driver actif).
  pinMode(M2_STEP, OUTPUT); digitalWrite(M2_STEP, LOW);
  pinMode(M2_DIR,  OUTPUT); digitalWrite(M2_DIR,  LOW);
  pinMode(M2_EN,   OUTPUT); digitalWrite(M2_EN,   LOW);

  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("=== Driver 2 (DRV8825 #2) ACTIF ===");
  Serial.println("M2 EN  = LOW  (GPIO 21) -> driver 2 ACTIF");
  Serial.println("M1 EN  = HIGH (GPIO 26) -> driver 1 OFF (securite)");
  Serial.println("STEP / DIR a LOW : aucun mouvement.");
  Serial.println();
  Serial.println("Calibre le Vref au tournevis + multimetre.");
  Serial.println("Reset (bouton EN de l'ESP32) ou autre upload pour sortir de cet etat.");
}

void loop() {
  // Rien. Les pins restent dans l'etat fixe par setup().
}
