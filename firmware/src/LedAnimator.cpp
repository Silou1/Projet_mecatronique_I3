#include "LedAnimator.h"
#include "LedDriver.h"
#include "UartLink.h"

namespace {
  LedAnimator::Pattern _current = LedAnimator::Pattern::OFF;
}

void LedAnimator::init() {
  UartLink::log("ANIM", "init (stub)");
}

void LedAnimator::tick() {
  // stub : pas d'animation reelle en plan 1
}

void LedAnimator::play(Pattern p) {
  if (p != _current) {
    _current = p;
    UartLink::logf("ANIM", "play pattern=%d", (int)p);
  }
}
