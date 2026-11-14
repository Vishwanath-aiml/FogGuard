/*
 * ==============================================================================
 * Project: FogGuard — IoT Obstacle Detection & Traffic Management System
 * Module: High-Performance Interrupt-Driven (PCINT) Sensor & Traffic Controller
 * Target: Arduino Uno / Nano (ATmega328P)
 * Based on: Vishwanath-aiml/FogGuard Pin Change Interrupt architecture
 * 
 * Key Advantages over blocking pulseIn():
 * - Zero blocking latency: captures ECHO rising/falling edges via PCINT2 hardware ISR
 * - Non-blocking round-robin ultrasonic state machine
 * - Immediate CPU availability for traffic light FSM and serial telemetry streaming
 * - High telemetry refresh rate (~10-15 Hz) ideal for real-time 3D cuboid projection
 * 
 * Hardware Pin Allocation:
 * - 4x HC-SR04 Ultrasonic Sensors:
 *   - S1 (Front Left):   TRIG Pin 9,  ECHO Pin 2 (PCINT18 / Port D2)
 *   - S2 (Front Center): TRIG Pin 10, ECHO Pin 3 (PCINT19 / Port D3)
 *   - S3 (Front Right):  TRIG Pin 11, ECHO Pin 4 (PCINT20 / Port D4)
 *   - S4 (Roof Center):  TRIG Pin 12, ECHO Pin 5 (PCINT21 / Port D5)
 * 
 * - 3x Traffic Signal LEDs:
 *   - Red LED:    Pin A0
 *   - Yellow LED: Pin A1
 *   - Green LED:  Pin A2
 * 
 * - Communication with ESP32 Gateway:
 *   - Hardware Serial 0 (TX Pin 1 -> ESP32 RX2 GPIO 16, RX Pin 0 <- ESP32 TX2 GPIO 17)
 *   - Baud Rate: 115200
 * ==============================================================================
 */

#include <Arduino.h>

// ─── Sensor Pin Definitions ──────────────────────────────────────────────────
const uint8_t SENSOR_COUNT = 4;

const uint8_t TRIG_PINS[SENSOR_COUNT] = {9, 10, 11, 12};
const uint8_t ECHO_PINS[SENSOR_COUNT] = {2, 3, 4, 5};   // Port D pins 2..5

const char* SENSOR_IDS[SENSOR_COUNT] = {"S1", "S2", "S3", "S4"};
const char* SENSOR_ZONES[SENSOR_COUNT] = {
  "front_left",
  "front_center",
  "front_right",
  "roof_center"
};

// ─── Traffic Signal Definitions ──────────────────────────────────────────────
const uint8_t PIN_LED_RED    = A0;
const uint8_t PIN_LED_YELLOW = A1;
const uint8_t PIN_LED_GREEN  = A2;

const unsigned long DURATION_RED    = 30; // Seconds
const unsigned long DURATION_GREEN  = 25; // Seconds
const unsigned long DURATION_YELLOW = 5;  // Seconds

enum TrafficState { STATE_RED, STATE_GREEN, STATE_YELLOW };
TrafficState currentTrafficState = STATE_RED;
unsigned long trafficStateStartTime = 0;

// ─── Distance & Detection Thresholds ─────────────────────────────────────────
const float MAX_DISTANCE_CM       = 400.0;
const float MIN_DISTANCE_CM       = 2.0;
const float CAUTION_THRESHOLD_CM  = 150.0;
const unsigned long ECHO_TIMEOUT_US = 25000; // ~428 cm maximum echo window

// ─── Non-Blocking Interrupt Storage ─────────────────────────────────────────
volatile unsigned long echoStartTime[SENSOR_COUNT] = {0, 0, 0, 0};
volatile unsigned long echoEndTime[SENSOR_COUNT]   = {0, 0, 0, 0};
volatile bool echoReceived[SENSOR_COUNT]           = {false, false, false, false};
volatile bool echoMeasuring[SENSOR_COUNT]          = {false, false, false, false};
volatile uint8_t previousPinDState                 = 0;

// Filtered calculated distances
float currentDistances[SENSOR_COUNT] = {-1.0, -1.0, -1.0, -1.0};
bool  obstacleDetected[SENSOR_COUNT] = {false, false, false, false};

// ─── Round-Robin Sensor Sequencer ────────────────────────────────────────────
uint8_t currentSensorIndex = 0;
unsigned long triggerTime = 0;
const unsigned long SENSOR_STEP_INTERVAL_MS = 25; // Stagger sensors to prevent crosstalk
unsigned long lastTelemetryBroadcast = 0;
const unsigned long TELEMETRY_INTERVAL_MS   = 100; // Broadcast to ESP32 at 10 Hz

// ─── Pin Change Interrupt Service Routine for Port D (D0-D7) ─────────────────
ISR(PCINT2_vect) {
  uint8_t currentPinD = PIND;
  uint8_t changedPins = currentPinD ^ previousPinDState;
  unsigned long now = micros();

  // Check D2 (Echo 1 - S1)
  if (changedPins & (1 << PIND2)) {
    if (currentPinD & (1 << PIND2)) {
      echoStartTime[0] = now;
      echoMeasuring[0] = true;
    } else if (echoMeasuring[0]) {
      echoEndTime[0] = now;
      echoReceived[0] = true;
      echoMeasuring[0] = false;
    }
  }

  // Check D3 (Echo 2 - S2)
  if (changedPins & (1 << PIND3)) {
    if (currentPinD & (1 << PIND3)) {
      echoStartTime[1] = now;
      echoMeasuring[1] = true;
    } else if (echoMeasuring[1]) {
      echoEndTime[1] = now;
      echoReceived[1] = true;
      echoMeasuring[1] = false;
    }
  }

  // Check D4 (Echo 3 - S3)
  if (changedPins & (1 << PIND4)) {
    if (currentPinD & (1 << PIND4)) {
      echoStartTime[2] = now;
      echoMeasuring[2] = true;
    } else if (echoMeasuring[2]) {
      echoEndTime[2] = now;
      echoReceived[2] = true;
      echoMeasuring[2] = false;
    }
  }

  // Check D5 (Echo 4 - S4)
  if (changedPins & (1 << PIND5)) {
    if (currentPinD & (1 << PIND5)) {
      echoStartTime[3] = now;
      echoMeasuring[3] = true;
    } else if (echoMeasuring[3]) {
      echoEndTime[3] = now;
      echoReceived[3] = true;
      echoMeasuring[3] = false;
    }
  }

  previousPinDState = currentPinD;
}

// ─── Ultrasonic Pulse Trigger ────────────────────────────────────────────────
void triggerSensor(uint8_t index) {
  // Clear measurement flags atomically
  cli();
  echoReceived[index]  = false;
  echoMeasuring[index] = false;
  echoStartTime[index] = 0;
  echoEndTime[index]   = 0;
  sei();

  // Emit 10us trigger pulse
  digitalWrite(TRIG_PINS[index], LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PINS[index], HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PINS[index], LOW);

  triggerTime = millis();
}

// ─── Process Last Triggered Sensor Distance ──────────────────────────────────
void processSensorResult(uint8_t index) {
  unsigned long start, end;
  bool received;

  cli();
  start = echoStartTime[index];
  end = echoEndTime[index];
  received = echoReceived[index];
  echoReceived[index] = false;
  sei();

  if (received && (end > start)) {
    unsigned long pulseDuration = end - start;
    if (pulseDuration <= ECHO_TIMEOUT_US) {
      // Speed of sound: 0.0343 cm/us / 2
      float dist = (float)pulseDuration * 0.0343 / 2.0;
      if (dist >= MIN_DISTANCE_CM && dist <= MAX_DISTANCE_CM) {
        currentDistances[index] = dist;
        obstacleDetected[index] = (dist <= CAUTION_THRESHOLD_CM);
        return;
      }
    }
  }

  // If no echo received within timeout or out of valid range
  currentDistances[index] = -1.0;
  obstacleDetected[index] = false;
}

// ─── Traffic Signal Controller ───────────────────────────────────────────────
void setTrafficLeds(TrafficState state) {
  digitalWrite(PIN_LED_RED,    state == STATE_RED    ? HIGH : LOW);
  digitalWrite(PIN_LED_YELLOW, state == STATE_YELLOW ? HIGH : LOW);
  digitalWrite(PIN_LED_GREEN,  state == STATE_GREEN  ? HIGH : LOW);
}

const char* getTrafficStateName(TrafficState state) {
  switch (state) {
    case STATE_RED:    return "RED";
    case STATE_YELLOW: return "YELLOW";
    case STATE_GREEN:  return "GREEN";
    default:           return "UNKNOWN";
  }
}

unsigned long getTrafficStateDuration(TrafficState state) {
  switch (state) {
    case STATE_RED:    return DURATION_RED;
    case STATE_YELLOW: return DURATION_YELLOW;
    case STATE_GREEN:  return DURATION_GREEN;
    default:           return 0;
  }
}

void updateTrafficSignal() {
  unsigned long elapsedSec = (millis() - trafficStateStartTime) / 1000;
  unsigned long currentDuration = getTrafficStateDuration(currentTrafficState);

  if (elapsedSec >= currentDuration) {
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
    trafficStateStartTime = millis();
    setTrafficLeds(currentTrafficState);
  }
}

// ─── Send Serial JSON Telemetry to ESP32 ─────────────────────────────────────
void broadcastTelemetry() {
  // Compact JSON line string formatted for FogGuard ESP32 gateway
  Serial.print("{\"traffic\":\"");
  Serial.print(getTrafficStateName(currentTrafficState));
  Serial.print("\",\"dur\":");
  Serial.print(getTrafficStateDuration(currentTrafficState));
  Serial.print(",\"sensors\":[");

  for (uint8_t i = 0; i < SENSOR_COUNT; i++) {
    if (i > 0) Serial.print(",");
    Serial.print("{\"id\":\"");
    Serial.print(SENSOR_IDS[i]);
    Serial.print("\",\"zone\":\"");
    Serial.print(SENSOR_ZONES[i]);
    Serial.print("\",\"dist\":");
    if (currentDistances[i] > 0) {
      Serial.print(currentDistances[i], 1);
    } else {
      Serial.print("null");
    }
    Serial.print(",\"det\":");
    Serial.print(obstacleDetected[i] ? "true" : "false");
    Serial.print("}");
  }

  Serial.println("]}");
}

// ─── Arduino Setup ───────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  // Initialize Ultrasonic Pins
  for (uint8_t i = 0; i < SENSOR_COUNT; i++) {
    pinMode(TRIG_PINS[i], OUTPUT);
    digitalWrite(TRIG_PINS[i], LOW);
    pinMode(ECHO_PINS[i], INPUT);
  }

  // Initialize Traffic LED Pins
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);

  // Record initial pin state on Port D
  previousPinDState = PIND;

  // Configure Pin Change Interrupts on Pins D2, D3, D4, D5 (PCINT18..PCINT21)
  // 1. Enable PCINT Group 2 (Port D, D0-D7)
  PCICR |= (1 << PCIE2);

  // 2. Unmask PCINT18 (D2), PCINT19 (D3), PCINT20 (D4), PCINT21 (D5)
  PCMSK2 |= (1 << PCINT18) | (1 << PCINT19) | (1 << PCINT20) | (1 << PCINT21);

  // Initialize traffic state
  trafficStateStartTime = millis();
  setTrafficLeds(currentTrafficState);

  // Trigger first sensor
  triggerSensor(0);
}

// ─── Main Non-Blocking Loop ──────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // 1. Service Traffic Signal State Machine
  updateTrafficSignal();

  // 2. Round-Robin Sensor Sequencer
  if (now - triggerTime >= SENSOR_STEP_INTERVAL_MS) {
    // Process results of previously triggered sensor
    processSensorResult(currentSensorIndex);

    // Advance to next sensor
    currentSensorIndex = (currentSensorIndex + 1) % SENSOR_COUNT;

    // Trigger next sensor
    triggerSensor(currentSensorIndex);
  }

  // 3. Periodic High-Speed Telemetry Transmission to ESP32
  if (now - lastTelemetryBroadcast >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryBroadcast = now;
    broadcastTelemetry();
  }
}
