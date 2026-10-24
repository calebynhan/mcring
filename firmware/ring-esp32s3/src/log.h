#pragma once
#include <Arduino.h>
#define LOGI(tag, fmt, ...) Serial.printf("[%8lu] I %s: " fmt "\n", (unsigned long)millis(), tag, ##__VA_ARGS__)
#define LOGW(tag, fmt, ...) Serial.printf("[%8lu] W %s: " fmt "\n", (unsigned long)millis(), tag, ##__VA_ARGS__)
#define LOGE(tag, fmt, ...) Serial.printf("[%8lu] E %s: " fmt "\n", (unsigned long)millis(), tag, ##__VA_ARGS__)
#if CORE_DEBUG_LEVEL >= 4
#define LOGD(tag, fmt, ...) Serial.printf("[%8lu] D %s: " fmt "\n", (unsigned long)millis(), tag, ##__VA_ARGS__)
#else
#define LOGD(tag, fmt, ...) do {} while (0)
#endif
