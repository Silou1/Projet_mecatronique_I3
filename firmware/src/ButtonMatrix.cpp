#include "ButtonMatrix.h"

namespace {
  ButtonMatrix::Intent _pending = { ButtonMatrix::IntentKind::NONE, 0, 0 };
  bool _hasPending = false;
}

void ButtonMatrix::init() {
  Serial.println("[ButtonMatrix] init (stub)");
}

void ButtonMatrix::poll() {
  // stub : pas de scan reel en plan 1
}

bool ButtonMatrix::hasIntent() {
  return _hasPending;
}

ButtonMatrix::Intent ButtonMatrix::takeIntent() {
  Intent out = _pending;
  _hasPending = false;
  _pending.kind = IntentKind::NONE;
  return out;
}

void ButtonMatrix::injectMoveIntent(uint8_t row, uint8_t col) {
  _pending = { IntentKind::MOVE, row, col };
  _hasPending = true;
}

void ButtonMatrix::injectWallIntent(bool horizontal, uint8_t row, uint8_t col) {
  _pending = { horizontal ? IntentKind::WALL_H : IntentKind::WALL_V, row, col };
  _hasPending = true;
}
