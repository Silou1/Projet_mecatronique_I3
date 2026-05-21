// Sketch de validation complete LED - regroupe les 5 phases de bring-up
// hardware en un seul flash. Enchaine en boucle, sans commande serie.
//
// Phases (s'enchaine automatiquement, defile en boucle) :
//   1. LED 0 fixe blanc     -> valide GPIO 15 + lib NeoPixel + cablage DIN
//   2. 4 coins du strip     -> identifie orientation physique du serpentin
//   3. Chenillard 0 -> 35   -> visualise le sens du serpentin
//   4. 4 coins grille engine -> valide formule engine_to_strip_index
//   5. Positions de depart  -> J1 bleu (5,3) + J2 rouge (0,3) Quoridor
//
// Les phases impriment leurs messages sur le serial 115200 baud.
//
// Flash   : pio run -e bringup_led_check -t upload
// Monitor : pio device monitor

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

#define LED_PIN     15
#define LED_COUNT   36
#define PHASE_HOLD  3000   // ms entre phases statiques
#define STEP_MS     250    // ms par pas pour le chenillard

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// Port C++ de webapp.leds.engine_to_strip_index (formule de production).
int engine_to_strip_index(int row, int col) {
  int row_phys = 5 - row;
  if (row_phys % 2 == 0) {
    return row_phys * 6 + col;
  }
  return row_phys * 6 + (5 - col);
}

static void phase_intro(const char* nom) {
  Serial.println();
  Serial.print("=== Phase : "); Serial.println(nom);
  strip.clear();
  strip.show();
  delay(300);
}

static void phase_hello() {
  phase_intro("1/5 LED 0 fixe blanc");
  strip.setPixelColor(0, strip.Color(255, 255, 255));
  strip.show();
  delay(PHASE_HOLD);
}

static void phase_corners() {
  phase_intro("2/5 coins strip - LED 0 rouge / 5 vert / 30 bleu / 35 jaune");
  strip.setPixelColor(0,  strip.Color(255, 0,   0));
  strip.setPixelColor(5,  strip.Color(0,   255, 0));
  strip.setPixelColor(30, strip.Color(0,   0,   255));
  strip.setPixelColor(35, strip.Color(255, 255, 0));
  strip.show();
  delay(PHASE_HOLD);
}

static void phase_serpentin() {
  phase_intro("3/5 chenillard sequentiel 0 -> 35");
  for (int i = 0; i < LED_COUNT; i++) {
    strip.clear();
    strip.setPixelColor(i, strip.Color(255, 255, 255));
    strip.show();
    Serial.print("LED "); Serial.println(i);
    delay(STEP_MS);
  }
  strip.clear();
  strip.show();
  delay(500);
}

static void phase_mapping() {
  phase_intro("4/5 mapping engine - rouge HG / vert HD / bleu BG / jaune BD");
  int idx_00 = engine_to_strip_index(0, 0);  // haut-gauche
  int idx_05 = engine_to_strip_index(0, 5);  // haut-droit
  int idx_50 = engine_to_strip_index(5, 0);  // bas-gauche
  int idx_55 = engine_to_strip_index(5, 5);  // bas-droit
  Serial.print("(0,0) HG -> LED "); Serial.println(idx_00);
  Serial.print("(0,5) HD -> LED "); Serial.println(idx_05);
  Serial.print("(5,0) BG -> LED "); Serial.println(idx_50);
  Serial.print("(5,5) BD -> LED "); Serial.println(idx_55);
  strip.setPixelColor(idx_00, strip.Color(255, 0,   0));
  strip.setPixelColor(idx_05, strip.Color(0,   255, 0));
  strip.setPixelColor(idx_50, strip.Color(0,   0,   255));
  strip.setPixelColor(idx_55, strip.Color(255, 255, 0));
  strip.show();
  delay(PHASE_HOLD);
}

static void phase_pions() {
  phase_intro("5/5 positions depart - J1 bleu (5,3) / J2 rouge (0,3)");
  int idx_j1 = engine_to_strip_index(5, 3);
  int idx_j2 = engine_to_strip_index(0, 3);
  Serial.print("J1 humain (5,3) -> LED "); Serial.println(idx_j1);
  Serial.print("J2 IA     (0,3) -> LED "); Serial.println(idx_j2);
  strip.setPixelColor(idx_j1, strip.Color(0,   0,   255));  // bleu
  strip.setPixelColor(idx_j2, strip.Color(255, 0,   0));    // rouge
  strip.show();
  delay(PHASE_HOLD);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("=== bringup_led_check : validation complete LED (5 phases) ===");

  strip.begin();
  strip.setBrightness(102);  // 40 %
  strip.clear();
  strip.show();
}

void loop() {
  phase_hello();
  phase_corners();
  phase_serpentin();
  phase_mapping();
  phase_pions();

  Serial.println();
  Serial.println("--- Cycle complet, on recommence ---");
  delay(1500);
}
