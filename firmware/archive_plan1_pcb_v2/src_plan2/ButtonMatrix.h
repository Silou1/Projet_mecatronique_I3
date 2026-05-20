#ifndef BUTTON_MATRIX_H
#define BUTTON_MATRIX_H

#include <Arduino.h>

namespace ButtonMatrix {
  enum class IntentKind { NONE, MOVE, WALL_H, WALL_V };

  struct Intent {
    IntentKind kind;
    uint8_t row;
    uint8_t col;
  };

  void init();
  void poll();              // appelee en boucle dans loop()
  bool hasIntent();
  Intent takeIntent();      // consomme et retourne l'intention courante

  // utilise par UartLink pour simuler un clic en plan 1 (sera retire au plan 4)
  void injectMoveIntent(uint8_t row, uint8_t col);
  void injectWallIntent(bool horizontal, uint8_t row, uint8_t col);
}

#endif
