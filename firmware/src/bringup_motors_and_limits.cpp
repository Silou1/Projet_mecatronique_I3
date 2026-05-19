// Sketch de test : CoreXY (2 moteurs NEMA17 via L298N) + 2 fins de course par axe.
// Cible : ESP32-WROOM (Freenove DevKit). Etend bringup_motor1_l298n + bringup_limit_switch.
//
// ARCHITECTURE CoreXY (convention propre a CETTE machine, validee 2026-05-20) :
//   - Les 2 moteurs sont couples. M1 seul ou M2 seul -> mouvement diagonal.
//   - Mouvement X pur : M1 et M2 sens OPPOSES. (Capteur 1 = fin de course axe X.)
//   - Mouvement Y pur : M1 et M2 MEME sens.   (Capteur 2 = fin de course axe Y.)
//   (Inverse de la convention CoreXY "standard" -- depend du routage des courroies.)
//
// Cablage :
//
//   Moteur 1 (L298N #1)
//     IN1 -> GPIO 14   IN2 -> GPIO 27   IN3 -> GPIO 26   IN4 -> GPIO 25
//     ENA -> GPIO 33   ENB -> GPIO 32
//
//   Moteur 2 (L298N #2)
//     IN1 -> GPIO 16   IN2 -> GPIO 17   IN3 -> GPIO 21   IN4 -> GPIO 22
//     ENA -> GPIO 19   ENB -> GPIO 23
//
//   Capteur 1 (fin de course axe X) : entre GPIO 13 et GND (INPUT_PULLUP)
//   Capteur 2 (fin de course axe Y) : entre GPIO 18 et GND (INPUT_PULLUP)
//
//   Convention NEMA17 (StepperOnline) :
//     OUT1/OUT2 -> bobine A (noir/vert)
//     OUT3/OUT4 -> bobine B (rouge/bleu)
//
//   Alim 12V partagee, masses communes (ESP32 + alim + 2 L298N).
//   Jumpers ENA/ENB des 2 L298N RETIRES (PWM depuis ESP). Jumper 5V_EN en place.
//
// ATTENTION : le L298N n'a pas de regulation de courant interne.
//             Tester regulierement la temperature des deux drivers.
//             Si trop chaud -> couper et baisser DUTY.
//
// Commandes serie (115200 baud) :
//   M1 F/B <n>    moteur 1 SEUL (debug, mouvement DIAGONAL en CoreXY) (1..10000)
//   M2 F/B <n>    moteur 2 SEUL (debug, mouvement DIAGONAL)
//   X F/B <n>     axe X pur (M1 et M2 sens opposes)
//   Y F/B <n>     axe Y pur (M1 et M2 meme sens)
//   LIMITS        lecture instantanee L1/L2
//   LIMITS WATCH  affichage en continu des transitions (Enter pour sortir)
//   EN ON         active les deux drivers
//   EN OFF        coupe les deux drivers (etat boot)
//   SPEED <us>    delai entre pas en us (500..10000, defaut 8000)
//   DUTY <pct>    PWM en % (10..60, defaut 60) - applique aux 2 moteurs
//   HOME          home axe X (Capteur 1) puis axe Y (Capteur 2), recul de 20 pas
//   STATUS        etat courant
//   HELP          cette aide
//
// HOME : pendant le mouvement vers le switch, lecture du capteur a chaque pas.
//        Pour M1/M2/X/Y F/B manuels : PAS de safety stop (operateur en controle).

#include <Arduino.h>
#include "esp_task_wdt.h"

// ============================================================================
// Pins
// ============================================================================

static constexpr uint8_t PIN_LIMIT_1 = 13;
static constexpr uint8_t PIN_LIMIT_2 = 18;

struct Moteur {
  const char* nom;
  uint8_t in1, in2, in3, in4;
  uint8_t ena, enb;
  int phase_courante;
};

static Moteur M1 = { "M1", 14, 27, 26, 25, 33, 32, 0 };
static Moteur M2 = { "M2", 16, 17, 21, 22, 19, 23, 0 };

// ============================================================================
// Parametres
// ============================================================================

static constexpr uint32_t SPEED_DEFAUT_US = 8000;
static constexpr uint32_t SPEED_MIN_US    = 500;
static constexpr uint32_t SPEED_MAX_US    = 10000;
static constexpr uint32_t PAS_MAX         = 10000;

static constexpr uint8_t  DUTY_DEFAUT_PCT = 60;
static constexpr uint8_t  DUTY_MIN_PCT    = 10;
static constexpr uint8_t  DUTY_MAX_PCT    = 60;

static constexpr uint32_t HOME_PAS_MAX    = 4000;  // garde-fou anti-runaway
static constexpr uint32_t HOME_RECUL_PAS  = 20;    // recul apres detection
static constexpr uint32_t HOME_LIBERATION = 50;    // recul si switch deja LOW

// Sequence full-step 4 phases : (IN1, IN2, IN3, IN4)
static const uint8_t SEQUENCE[4][4] = {
  {1, 0, 1, 0},
  {0, 1, 1, 0},
  {0, 1, 0, 1},
  {1, 0, 0, 1}
};

static uint32_t demi_periode_us = SPEED_DEFAUT_US;
static uint8_t  duty_pct        = DUTY_DEFAUT_PCT;
static bool     driver_actif    = false;
static String   tampon_serie;

// ============================================================================
// Helpers moteur
// ============================================================================

static uint8_t duty_to_pwm(uint8_t pct) {
  uint32_t v = (uint32_t)pct * 255 / 100;
  return (uint8_t)(v > 255 ? 255 : v);
}

static void couper_phases(const Moteur& m) {
  digitalWrite(m.in1, LOW);
  digitalWrite(m.in2, LOW);
  digitalWrite(m.in3, LOW);
  digitalWrite(m.in4, LOW);
}

static void appliquer_phase(const Moteur& m, int idx) {
  digitalWrite(m.in1, SEQUENCE[idx][0] ? HIGH : LOW);
  digitalWrite(m.in2, SEQUENCE[idx][1] ? HIGH : LOW);
  digitalWrite(m.in3, SEQUENCE[idx][2] ? HIGH : LOW);
  digitalWrite(m.in4, SEQUENCE[idx][3] ? HIGH : LOW);
}

static void appliquer_pwm(const Moteur& m, uint8_t pwm) {
  analogWrite(m.ena, pwm);
  analogWrite(m.enb, pwm);
}

static void activer_drivers(bool actif) {
  driver_actif = actif;
  if (actif) {
    uint8_t pwm = duty_to_pwm(duty_pct);
    appliquer_pwm(M1, pwm);
    appliquer_pwm(M2, pwm);
    appliquer_phase(M1, M1.phase_courante);
    appliquer_phase(M2, M2.phase_courante);
  } else {
    appliquer_pwm(M1, 0);
    appliquer_pwm(M2, 0);
    couper_phases(M1);
    couper_phases(M2);
  }
}

static void faire_un_pas(Moteur& m, bool sens_forward) {
  m.phase_courante = (m.phase_courante + (sens_forward ? 1 : 3)) & 3;
  appliquer_phase(m, m.phase_courante);
  delayMicroseconds(demi_periode_us);
}

static void executer_pas(Moteur& m, uint32_t nb_pas, bool sens_forward) {
  for (uint32_t i = 0; i < nb_pas; ++i) {
    faire_un_pas(m, sens_forward);
    if ((i & 0x3F) == 0) yield();
  }
}

// ============================================================================
// Mouvements coordonnes CoreXY
// ============================================================================
//
// Cinematique CoreXY (convention propre a cette machine, validee 2026-05-20) :
//   X pur : M1 et M2 sens OPPOSES   (Capteur 1)
//   Y pur : M1 et M2 MEME sens      (Capteur 2)
//
// Convention sens validee :
//   X backward (M1 B + M2 F) -> approche Capteur 1 (homing X)
//   Y backward (M1 B + M2 B) -> approche Capteur 2 (homing Y)

static void faire_un_pas_coordonne(bool m1_forward, bool m2_forward) {
  M1.phase_courante = (M1.phase_courante + (m1_forward ? 1 : 3)) & 3;
  M2.phase_courante = (M2.phase_courante + (m2_forward ? 1 : 3)) & 3;
  appliquer_phase(M1, M1.phase_courante);
  appliquer_phase(M2, M2.phase_courante);
  delayMicroseconds(demi_periode_us);
}

static void executer_axe_X(uint32_t nb_pas, bool forward) {
  // X = M1 et M2 sens opposes (cette machine)
  for (uint32_t i = 0; i < nb_pas; ++i) {
    faire_un_pas_coordonne(forward, !forward);
    if ((i & 0x3F) == 0) yield();
  }
}

static void executer_axe_Y(uint32_t nb_pas, bool forward) {
  // Y = M1 et M2 meme sens (cette machine)
  for (uint32_t i = 0; i < nb_pas; ++i) {
    faire_un_pas_coordonne(forward, forward);
    if ((i & 0x3F) == 0) yield();
  }
}

// ============================================================================
// Homing CoreXY
// ============================================================================

// Homing d'un axe. Le mouvement est coordonne (2 moteurs en meme temps).
//   nom        : "X" ou "Y" (pour les logs)
//   pin_limit  : capteur correspondant
//   m1_fwd_vers_switch, m2_fwd_vers_switch : sens de chaque moteur pour
//       aller VERS le switch. Le recul applique les sens inverses.
//
// Retourne true si le switch a ete touche et le chariot recule, false si
// le garde-fou HOME_PAS_MAX est atteint sans contact.
static bool homing_axe(const char* nom,
                       uint8_t pin_limit,
                       bool m1_fwd_vers_switch,
                       bool m2_fwd_vers_switch) {
  Serial.print("HOME ");
  Serial.print(nom);
  Serial.println(" ...");

  // Si deja sur le switch : recul en sens inverse pour le liberer.
  if (digitalRead(pin_limit) == LOW) {
    Serial.print("  switch deja LOW, recul de ");
    Serial.print(HOME_LIBERATION);
    Serial.println(" pas pour liberer");
    for (uint32_t i = 0; i < HOME_LIBERATION; ++i) {
      faire_un_pas_coordonne(!m1_fwd_vers_switch, !m2_fwd_vers_switch);
      if ((i & 0x3F) == 0) yield();
    }
    if (digitalRead(pin_limit) == LOW) {
      Serial.println("  ERREUR : switch toujours LOW apres liberation");
      Serial.println("           -> verifier cablage / convention de sens");
      return false;
    }
  }

  // Avance vers le switch jusqu'a detection ou garde-fou.
  for (uint32_t i = 0; i < HOME_PAS_MAX; ++i) {
    if (digitalRead(pin_limit) == LOW) {
      Serial.print("  contact apres ");
      Serial.print(i);
      Serial.println(" pas");
      // Recul pour liberer le switch
      for (uint32_t j = 0; j < HOME_RECUL_PAS; ++j) {
        faire_un_pas_coordonne(!m1_fwd_vers_switch, !m2_fwd_vers_switch);
        if ((j & 0x3F) == 0) yield();
      }
      Serial.print("  axe ");
      Serial.print(nom);
      Serial.println(" origine etablie");
      return true;
    }
    faire_un_pas_coordonne(m1_fwd_vers_switch, m2_fwd_vers_switch);
    if ((i & 0x3F) == 0) yield();
  }

  Serial.print("  ERREUR : ");
  Serial.print(HOME_PAS_MAX);
  Serial.println(" pas sans toucher le switch -> abandon");
  return false;
}

static void executer_home() {
  if (!driver_actif) {
    Serial.println("Driver OFF. Tape 'EN ON' d'abord.");
    return;
  }

  // Convention validee 2026-05-20 sur cette machine :
  //   axe X- (vers Capteur 1) : M1 backward + M2 forward  (sens opposes)
  //   axe Y- (vers Capteur 2) : M1 backward + M2 backward (meme sens)
  bool ok_x = homing_axe("X", PIN_LIMIT_1, /*m1*/ false, /*m2*/ true);
  bool ok_y = homing_axe("Y", PIN_LIMIT_2, /*m1*/ false, /*m2*/ false);

  if (ok_x && ok_y) {
    Serial.println("HOME OK : chariot a l'origine (X=0, Y=0)");
  } else {
    Serial.println("HOME ECHEC (voir messages ci-dessus)");
  }
}

// ============================================================================
// LIMITS
// ============================================================================

static void lire_limits_une_fois() {
  int l1 = digitalRead(PIN_LIMIT_1);
  int l2 = digitalRead(PIN_LIMIT_2);
  Serial.print("L1=");
  Serial.print(l1 == LOW ? "LOW " : "HIGH");
  Serial.print("  L2=");
  Serial.println(l2 == LOW ? "LOW " : "HIGH");
}

static void watch_limits() {
  Serial.println("LIMITS WATCH : appuie sur Enter pour sortir");
  int dernier_l1 = -1;
  int dernier_l2 = -1;
  while (true) {
    int l1 = digitalRead(PIN_LIMIT_1);
    int l2 = digitalRead(PIN_LIMIT_2);
    if (l1 != dernier_l1 || l2 != dernier_l2) {
      Serial.print("  L1=");
      Serial.print(l1 == LOW ? "LOW " : "HIGH");
      Serial.print("  L2=");
      Serial.println(l2 == LOW ? "LOW " : "HIGH");
      dernier_l1 = l1;
      dernier_l2 = l2;
    }
    // Sortie sur Enter (ligne vide)
    if (Serial.available()) {
      char c = (char)Serial.read();
      if (c == '\n' || c == '\r') {
        Serial.println("WATCH stop");
        // Vider le reste du buffer pour eviter d'avaler la commande suivante
        while (Serial.available()) Serial.read();
        return;
      }
    }
    delay(20);  // 50 Hz
  }
}

// ============================================================================
// Parser serie
// ============================================================================

static void afficher_aide() {
  Serial.println("Commandes :");
  Serial.println("  M1 F/B <n>            moteur 1 SEUL - debug (diagonale en CoreXY)");
  Serial.println("  M2 F/B <n>            moteur 2 SEUL - debug (diagonale)");
  Serial.println("  X F <n> | X B <n>     axe X pur (M1 et M2 sens opposes)");
  Serial.println("  Y F <n> | Y B <n>     axe Y pur (M1 et M2 meme sens)");
  Serial.println("  LIMITS                lecture instantanee L1/L2");
  Serial.println("  LIMITS WATCH          affichage continu (Enter pour sortir)");
  Serial.println("  EN ON | EN OFF        active / coupe les 2 drivers");
  Serial.println("  SPEED <us>            delai inter-pas (500..10000, defaut 8000)");
  Serial.println("  DUTY <pct>            PWM (10..60, defaut 60)");
  Serial.println("  HOME                  homing axe X (Capteur 1) puis axe Y (Capteur 2)");
  Serial.println("  STATUS                etat courant");
  Serial.println("  HELP                  cette aide");
}

static void afficher_status() {
  Serial.print("  EN     : ");
  Serial.println(driver_actif ? "ON" : "OFF");
  Serial.print("  SPEED  : ");
  Serial.print(demi_periode_us);
  Serial.print(" us  (~");
  Serial.print(1000000UL / demi_periode_us);
  Serial.println(" pas/s)");
  Serial.print("  DUTY   : ");
  Serial.print(duty_pct);
  Serial.println(" %");
  Serial.print("  M1 phase=");
  Serial.print(M1.phase_courante);
  Serial.print("   M2 phase=");
  Serial.println(M2.phase_courante);
  lire_limits_une_fois();
}

static bool parser_moteur(const String& s) {
  // s commence par "M1 " ou "M2 ", deja en majuscule, deja trim.
  if (s.length() < 5) return false;
  Moteur* m;
  if (s.startsWith("M1 ")) {
    m = &M1;
  } else if (s.startsWith("M2 ")) {
    m = &M2;
  } else {
    return false;
  }
  char sens = s.charAt(3);
  if ((sens != 'F' && sens != 'B') || s.charAt(4) != ' ') return false;
  long n = s.substring(5).toInt();
  if (n <= 0 || n > (long)PAS_MAX) {
    Serial.print("N hors limite [1..");
    Serial.print(PAS_MAX);
    Serial.println("]");
    return true;
  }
  if (!driver_actif) {
    Serial.println("Driver OFF. Tape 'EN ON' d'abord.");
    return true;
  }
  bool forward = (sens == 'F');
  Serial.print(m->nom);
  Serial.print(forward ? " F " : " B ");
  Serial.print(n);
  Serial.print(" pas a ");
  Serial.print(demi_periode_us);
  Serial.println(" us ...");
  executer_pas(*m, (uint32_t)n, forward);
  Serial.println("done");
  return true;
}

// X F <n>, X B <n>, Y F <n>, Y B <n>
static bool parser_axe(const String& s) {
  if (s.length() < 5) return false;
  char axe = s.charAt(0);
  if (axe != 'X' && axe != 'Y') return false;
  if (s.charAt(1) != ' ') return false;
  char sens = s.charAt(2);
  if ((sens != 'F' && sens != 'B') || s.charAt(3) != ' ') return false;
  long n = s.substring(4).toInt();
  if (n <= 0 || n > (long)PAS_MAX) {
    Serial.print("N hors limite [1..");
    Serial.print(PAS_MAX);
    Serial.println("]");
    return true;
  }
  if (!driver_actif) {
    Serial.println("Driver OFF. Tape 'EN ON' d'abord.");
    return true;
  }
  bool forward = (sens == 'F');
  Serial.print(axe);
  Serial.print(forward ? " F " : " B ");
  Serial.print(n);
  Serial.print(" pas a ");
  Serial.print(demi_periode_us);
  Serial.println(" us ...");
  if (axe == 'X') executer_axe_X((uint32_t)n, forward);
  else            executer_axe_Y((uint32_t)n, forward);
  Serial.println("done");
  return true;
}

static void traiter(String s) {
  s.trim();
  s.toUpperCase();
  if (s.length() == 0) return;

  if (s == "HELP")   { afficher_aide();    return; }
  if (s == "STATUS") { afficher_status();  return; }
  if (s == "HOME")   { executer_home();    return; }

  if (s == "EN ON")  { activer_drivers(true);  Serial.println("drivers ON");  return; }
  if (s == "EN OFF") { activer_drivers(false); Serial.println("drivers OFF"); return; }

  if (s == "LIMITS")       { lire_limits_une_fois(); return; }
  if (s == "LIMITS WATCH") { watch_limits();         return; }

  if (s.startsWith("SPEED ")) {
    long v = s.substring(6).toInt();
    if (v < (long)SPEED_MIN_US || v > (long)SPEED_MAX_US) {
      Serial.print("SPEED hors limite [");
      Serial.print(SPEED_MIN_US);
      Serial.print("..");
      Serial.print(SPEED_MAX_US);
      Serial.println("] us");
      return;
    }
    demi_periode_us = (uint32_t)v;
    Serial.print("SPEED = ");
    Serial.print(demi_periode_us);
    Serial.println(" us");
    return;
  }

  if (s.startsWith("DUTY ")) {
    long v = s.substring(5).toInt();
    if (v < (long)DUTY_MIN_PCT || v > (long)DUTY_MAX_PCT) {
      Serial.print("DUTY hors limite [");
      Serial.print(DUTY_MIN_PCT);
      Serial.print("..");
      Serial.print(DUTY_MAX_PCT);
      Serial.println("] %");
      return;
    }
    duty_pct = (uint8_t)v;
    if (driver_actif) {
      uint8_t pwm = duty_to_pwm(duty_pct);
      appliquer_pwm(M1, pwm);
      appliquer_pwm(M2, pwm);
    }
    Serial.print("DUTY = ");
    Serial.print(duty_pct);
    Serial.println(" %");
    return;
  }

  if (s.startsWith("M1 ") || s.startsWith("M2 ")) {
    if (parser_moteur(s)) return;
  }

  if (s.startsWith("X ") || s.startsWith("Y ")) {
    if (parser_axe(s)) return;
  }

  Serial.print("Commande inconnue : '");
  Serial.print(s);
  Serial.println("' - tape HELP");
}

// ============================================================================
// Setup / loop
// ============================================================================

static void init_moteur(const Moteur& m) {
  pinMode(m.in1, OUTPUT);
  pinMode(m.in2, OUTPUT);
  pinMode(m.in3, OUTPUT);
  pinMode(m.in4, OUTPUT);
  pinMode(m.ena, OUTPUT);
  pinMode(m.enb, OUTPUT);
  couper_phases(m);
  analogWrite(m.ena, 0);
  analogWrite(m.enb, 0);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  esp_task_wdt_deinit();

  init_moteur(M1);
  init_moteur(M2);

  pinMode(PIN_LIMIT_1, INPUT_PULLUP);
  pinMode(PIN_LIMIT_2, INPUT_PULLUP);

  Serial.println();
  Serial.println("=== Bring-up moteurs + fins de course ===");
  Serial.println("M1 L298N : IN1=14 IN2=27 IN3=26 IN4=25 ENA=33 ENB=32");
  Serial.println("M2 L298N : IN1=16 IN2=17 IN3=21 IN4=22 ENA=19 ENB=23");
  Serial.println("LIMIT 1 : GPIO 13      LIMIT 2 : GPIO 18");
  Serial.println("Drivers DESACTIVES au boot. Tape 'EN ON' pour activer.");
  Serial.print("SPEED ");
  Serial.print(demi_periode_us);
  Serial.print(" us  DUTY ");
  Serial.print(duty_pct);
  Serial.println(" %");
  Serial.println("ATTENTION : touche les deux L298N regulierement (anti-surchauffe).");
  Serial.println();
  afficher_aide();
  Serial.println();
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      traiter(tampon_serie);
      tampon_serie = "";
    } else {
      tampon_serie += c;
      if (tampon_serie.length() > 64) {
        tampon_serie = "";
        Serial.println("Ligne trop longue, ignoree.");
      }
    }
  }
}
