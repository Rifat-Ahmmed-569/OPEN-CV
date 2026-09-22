#include <Arduino.h>

#define TRIG A0
#define ECHO A1
#define CONTROL_PIN 6

const unsigned long COMMAND_TIMEOUT_MS = 2000UL;
unsigned long lastValidCommandMs = 0;

void setup() {
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  pinMode(CONTROL_PIN, OUTPUT);

  digitalWrite(CONTROL_PIN, LOW);

  Serial.begin(9600);
  lastValidCommandMs = millis();
}

void loop() {
  // Measure distance
  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);

  digitalWrite(TRIG, LOW);

  long duration = pulseIn(ECHO, HIGH);
  float distance = duration * 0.0343 / 2.0;

  // Send distance to Python
  Serial.println(distance);

  // Receive STOP / SAFE from Python
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "STOP") {
      digitalWrite(CONTROL_PIN, HIGH);
      lastValidCommandMs = millis();
    }
    else if (command == "SAFE") {
      digitalWrite(CONTROL_PIN, LOW);
      lastValidCommandMs = millis();
    }
  }

  // Safety timeout
  // If Python stops communicating, turn Pin 6 OFF.
  if (millis() - lastValidCommandMs > COMMAND_TIMEOUT_MS) {
    digitalWrite(CONTROL_PIN, LOW);
  }

  delay(100);
}