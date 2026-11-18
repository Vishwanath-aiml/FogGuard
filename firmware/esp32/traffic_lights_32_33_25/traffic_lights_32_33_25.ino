/*
 * FogGuard standalone ESP32 traffic-light controller
 *
 * Working ESP32 output mapping:
 *   Red    -> GPIO 32
 *   Yellow -> GPIO 33
 *   Green  -> GPIO 25
 *
 * GPIO 34 was not used because it is input-only on standard ESP32
 * Dev Modules and cannot drive an LED.
 */

#include <Arduino.h>

#define RED_LED_PIN 32
#define YELLOW_LED_PIN 33
#define GREEN_LED_PIN 25

enum TrafficState {
  TRAFFIC_RED,
  TRAFFIC_GREEN,
  TRAFFIC_YELLOW
};

const unsigned long RED_DURATION_MS = 30000;
const unsigned long GREEN_DURATION_MS = 25000;
const unsigned long YELLOW_DURATION_MS = 5000;

TrafficState currentState = TRAFFIC_RED;
unsigned long stateStartedAt = 0;

void setTrafficLights(TrafficState state) {
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(YELLOW_LED_PIN, LOW);
  digitalWrite(GREEN_LED_PIN, LOW);

  switch (state) {
    case TRAFFIC_RED:
      digitalWrite(RED_LED_PIN, HIGH);
      break;
    case TRAFFIC_GREEN:
      digitalWrite(GREEN_LED_PIN, HIGH);
      break;
    case TRAFFIC_YELLOW:
      digitalWrite(YELLOW_LED_PIN, HIGH);
      break;
  }
}

unsigned long getStateDurationMs(TrafficState state) {
  switch (state) {
    case TRAFFIC_RED:
      return RED_DURATION_MS;
    case TRAFFIC_GREEN:
      return GREEN_DURATION_MS;
    case TRAFFIC_YELLOW:
      return YELLOW_DURATION_MS;
  }
  return 0;
}

void setup() {
  Serial.begin(115200);

  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(YELLOW_LED_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);

  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(YELLOW_LED_PIN, LOW);
  digitalWrite(GREEN_LED_PIN, LOW);

  stateStartedAt = millis();
  setTrafficLights(currentState);

  Serial.println("FogGuard traffic lights: R=32 Y=33 G=25");
  Serial.println("GPIO 34 is input-only and cannot drive the green LED.");
}

void loop() {
  if (millis() - stateStartedAt >= getStateDurationMs(currentState)) {
    stateStartedAt = millis();

    switch (currentState) {
      case TRAFFIC_RED:
        currentState = TRAFFIC_GREEN;
        break;
      case TRAFFIC_GREEN:
        currentState = TRAFFIC_YELLOW;
        break;
      case TRAFFIC_YELLOW:
        currentState = TRAFFIC_RED;
        break;
    }

    setTrafficLights(currentState);
  }
}
