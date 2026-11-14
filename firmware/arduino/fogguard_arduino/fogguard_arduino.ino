/*
 * ==============================================================================
 * Project: FogGuard — IoT Obstacle Detection & Traffic Management System
 * Module: Arduino Sensor & Traffic Signal Controller
 * Target: Arduino Uno / Mega / Nano
 * 
 * Hardware Configuration:
 * - 6x HC-SR04 Ultrasonic Sensors
 *   - S1 (Front Left): Trig Pin 2, Echo Pin 3
 *   - S2 (Front Center Left): Trig Pin 4, Echo Pin 5
 *   - S3 (Front Center Right): Trig Pin 6, Echo Pin 7
 *   - S4 (Front Right): Trig Pin 8, Echo Pin 9
 *   - S5 (Left Side): Trig Pin 10, Echo Pin 11
 *   - S6 (Right Side): Trig Pin 12, Echo Pin 13
 * 
 * - 3x Traffic Signal LEDs:
 *   - Red LED: Pin A0
 *   - Yellow LED: Pin A1
 *   - Green LED: Pin A2
 * 
 * - Communication with ESP32:
 *   - Hardware Serial (TX -> ESP32 RX2, RX <- ESP32 TX2) at 115200 baud
 * ==============================================================================
 */

#include <Arduino.h>

// Sensor Pin Definitions
const int SENSOR_COUNT = 6;
const int TRIG_PINS[SENSOR_COUNT] = {2, 4, 6, 8, 10, 12};
const int ECHO_PINS[SENSOR_COUNT] = {3, 5, 7, 9, 11, 13};
const char* SENSOR_IDS[SENSOR_COUNT] = {"S1", "S2", "S3", "S4", "S5", "S6"};
const char* SENSOR_ZONES[SENSOR_COUNT] = {
  "front_left", "front_center_left", "front_center_right", 
  "front_right", "left_side", "right_side"
};

// Traffic Signal Pins
const int PIN_LED_RED = A0;
const int PIN_LED_YELLOW = A1;
const int PIN_LED_GREEN = A2;

// Traffic Signal Timing (in seconds)
const unsigned long DURATION_RED = 30;
const unsigned long DURATION_GREEN = 25;
const unsigned long DURATION_YELLOW = 5;

// Timing State
enum TrafficState { STATE_RED, STATE_GREEN, STATE_YELLOW };
TrafficState currentTrafficState = STATE_RED;
unsigned long stateStartTime = 0;

// Sensor reading interval
unsigned long lastReadTime = 0;
const unsigned long READ_INTERVAL_MS = 500; // Read sensors every 500ms

// Maximum valid distance (cm)
const float MAX_DISTANCE_CM = 400.0;
const float CAUTION_THRESHOLD_CM = 150.0;

// Measures distance with HC-SR04 ultrasonic sensor (returns cm, or -1 if timeout)
float readDistanceCM(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  // 30ms timeout covers up to ~500cm
  unsigned long duration = pulseIn(echoPin, HIGH, 30000);
  if (duration == 0) {
    return -1.0; // Out of range or no echo
  }
  // Speed of sound: 343 m/s = 0.0343 cm/microsecond. Round-trip: / 2.0
  float distance = (duration * 0.0343) / 2.0;
  if (distance > MAX_DISTANCE_CM || distance < 2.0) {
    return -1.0;
  }
  return distance;
}

void setTrafficSignal(TrafficState state) {
  digitalWrite(PIN_LED_RED, state == STATE_RED ? HIGH : LOW);
  digitalWrite(PIN_LED_YELLOW, state == STATE_YELLOW ? HIGH : LOW);
  digitalWrite(PIN_LED_GREEN, state == STATE_GREEN ? HIGH : LOW);
}

const char* getTrafficStateName(TrafficState state) {
  switch (state) {
    case STATE_RED: return "RED";
    case STATE_YELLOW: return "YELLOW";
    case STATE_GREEN: return "GREEN";
    default: return "UNKNOWN";
  }
}

unsigned long getTrafficStateDuration(TrafficState state) {
  switch (state) {
    case STATE_RED: return DURATION_RED;
    case STATE_YELLOW: return DURATION_YELLOW;
    case STATE_GREEN: return DURATION_GREEN;
    default: return 0;
  }
}

void updateTrafficSignal() {
  unsigned long elapsedSec = (millis() - stateStartTime) / 1000;
  unsigned long currentDuration = getTrafficStateDuration(currentTrafficState);

  if (elapsedSec >= currentDuration) {
    // Transition to next state: RED -> GREEN -> YELLOW -> RED
    switch (currentTrafficState) {
      case STATE_RED:
        currentTrafficState = STATE_GREEN;
        break;
      case STATE_GREEN:
        currentTrafficState = STATE_YELLOW;
        break;
      case STATE_YELLOW:
        currentTrafficState = STATE_RED;
        break;
    }
    stateStartTime = millis();
    setTrafficSignal(currentTrafficState);
  }
}

void setup() {
  Serial.begin(115200);

  // Initialize Ultrasonic Pins
  for (int i = 0; i < SENSOR_COUNT; i++) {
    pinMode(TRIG_PINS[i], OUTPUT);
    pinMode(ECHO_PINS[i], INPUT);
    digitalWrite(TRIG_PINS[i], LOW);
  }

  // Initialize Traffic LED Pins
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);

  // Start with RED state
  stateStartTime = millis();
  setTrafficSignal(currentTrafficState);
}

void loop() {
  // Update traffic light state machine
  updateTrafficSignal();

  // Periodic sensor reading and UART transmission to ESP32
  unsigned long now = millis();
  if (now - lastReadTime >= READ_INTERVAL_MS) {
    lastReadTime = now;

    // Build compact JSON-line packet for ESP32
    // Format:
    // {"traffic":"RED","dur":30,"sensors":[{"id":"S1","zone":"front_left","dist":45.2,"det":true},...]}
    Serial.print("{\"traffic\":\"");
    Serial.print(getTrafficStateName(currentTrafficState));
    Serial.print("\",\"dur\":");
    Serial.print(getTrafficStateDuration(currentTrafficState));
    Serial.print(",\"sensors\":[");

    for (int i = 0; i < SENSOR_COUNT; i++) {
      float dist = readDistanceCM(TRIG_PINS[i], ECHO_PINS[i]);
      bool detected = (dist > 0 && dist <= CAUTION_THRESHOLD_CM);

      if (i > 0) Serial.print(",");
      Serial.print("{\"id\":\"");
      Serial.print(SENSOR_IDS[i]);
      Serial.print("\",\"zone\":\"");
      Serial.print(SENSOR_ZONES[i]);
      Serial.print("\",\"dist\":");
      if (dist > 0) {
        Serial.print(dist, 1);
      } else {
        Serial.print("null");
      }
      Serial.print(",\"det\":");
      Serial.print(detected ? "true" : "false");
      Serial.print("}");

      delay(10); // Short settle time between ultrasonic bursts
    }

    Serial.println("]}");
  }
}
