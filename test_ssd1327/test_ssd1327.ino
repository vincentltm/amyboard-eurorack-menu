#include <Arduino.h>
#include <Wire.h>

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n\n====================================");
  Serial.println("=== FULL ESP32-S3 I2C BUS SCANNER ===");
  Serial.println("====================================");

  int candidate_sda[] = {41, 20, 4, 8, 1, 17, 3, 5, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19, 38, 39, 40, 42};
  int candidate_scl[] = {42, 21, 5, 9, 2, 18, 4, 6, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20, 39, 40, 41, 43};

  int total_found = 0;

  for (size_t i = 0; i < sizeof(candidate_sda)/sizeof(candidate_sda[0]); i++) {
    int sda = candidate_sda[i];
    int scl = candidate_scl[i];
    if (sda == scl) continue;

    Wire.end();
    delay(20);
    Wire.begin(sda, scl);
    delay(20);

    bool header_printed = false;
    for (uint8_t addr = 1; addr < 127; addr++) {
      Wire.beginTransmission(addr);
      uint8_t err = Wire.endTransmission();
      if (err == 0) {
        if (!header_printed) {
          Serial.printf("\n--> BUS FOUND on SDA=GPIO%d, SCL=GPIO%d:\n", sda, scl);
          header_printed = true;
        }
        Serial.printf("    [0x%02X] Device detected!\n", addr);
        total_found++;
      }
    }
  }

  Serial.println("\n------------------------------------");
  if (total_found == 0) {
    Serial.println("NO I2C DEVICES RESPONDED ON TESTED PINS.");
  } else {
    Serial.printf("TOTAL I2C DEVICES DETECTED: %d\n", total_found);
  }
  Serial.println("====================================\n");
}

void loop() {
  delay(1000);
}
