#include "LedAnimator.h"
#include "LedDriver.h"

namespace {
  LedAnimator::Pattern _current = LedAnimator::Pattern::OFF;
}

void LedAnimator::init() {
  Serial.println("[LedAnimator] init (stub)");
}

void LedAnimator::tick() {
  // stub : pas d'animation reelle en plan 1
}

void LedAnimator::play(Pattern p) {
  if (p != _current) {
    _current = p;
    Serial.print("[LedAnimator] play pattern=");
    Serial.println((int)p);
  }
}
