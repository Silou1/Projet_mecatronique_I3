#include "MotionControl.h"
#include "esp_task_wdt.h"
#include "freertos/task.h"

namespace {
  QueueHandle_t _commandQueue = nullptr;
  QueueHandle_t _resultQueue  = nullptr;
  TaskHandle_t  _taskHandle   = nullptr;

  void motionTask(void* arg) {
    esp_task_wdt_add(NULL);                  // enregistre cette tache au watchdog
    MotionControl::Command cmd;
    for (;;) {
      esp_task_wdt_reset();
      if (xQueueReceive(_commandQueue, &cmd, pdMS_TO_TICKS(500)) == pdTRUE) {
        Serial.print("[MotionControl] exec command kind=");
        Serial.println((int)cmd.kind);
        // simulation decoupee pour ne pas depasser le watchdog
        for (int i = 0; i < 10; ++i) {
          esp_task_wdt_reset();
          vTaskDelay(pdMS_TO_TICKS(100));
        }
        MotionControl::Result res = { MotionControl::ResultKind::DONE };
        xQueueSend(_resultQueue, &res, 0);
      }
    }
  }
}

void MotionControl::init() {
  Serial.println("[MotionControl] init (FreeRTOS task)");
  _commandQueue = xQueueCreate(4, sizeof(Command));
  _resultQueue  = xQueueCreate(4, sizeof(Result));
  // tache pinnee sur Core 0 (la loop principale tourne sur Core 1)
  xTaskCreatePinnedToCore(motionTask, "motion", 4096, nullptr, 1, &_taskHandle, 0);
}

bool MotionControl::postCommand(const Command& cmd) {
  return xQueueSend(_commandQueue, &cmd, 0) == pdTRUE;
}

bool MotionControl::tryGetResult(Result& out) {
  return xQueueReceive(_resultQueue, &out, 0) == pdTRUE;
}

bool MotionControl::selfTest() {
  Serial.println("[MotionControl] selfTest -> OK (stub I2C)");
  return true;
}
