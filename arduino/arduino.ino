
// byte ensures it takes 1 byte instead of standart 2 bytes unneccesarily
// If u change these numbers (For ECHO ONLY) u must change the interrupt reciever as well (PCMSK2)
const byte TRIG_1 = 9;
const byte ECHO_1 = 2;

const byte TRIG_2 = 10;
const byte ECHO_2 = 3;

const byte TRIG_3 = 11;
const byte ECHO_3 = 4;

const byte TRIG_4 = 12;
const byte ECHO_4 = 5;

// volatile used to say that this value can abruptly change
// Some times it might reject abrupt changes as accidental in default var types
volatile unsigned long startTime[4] = {0, 0, 0, 0};
volatile unsigned long endTime[4] = {0, 0, 0, 0};
volatile bool echoComplete[4] = {false, false, false, false};
volatile byte previousState = 0;

float distance[4] = {0, 0, 0, 0};

void setup() {
  Serial.begin(115200);

  pinMode(TRIG_1, OUTPUT);
  pinMode(ECHO_1, INPUT);

  pinMode(TRIG_2, OUTPUT);
  pinMode(ECHO_2, INPUT);

  pinMode(TRIG_3, OUTPUT);
  pinMode(ECHO_3, INPUT);

  pinMode(TRIG_4, OUTPUT);
  pinMode(ECHO_4, INPUT);

  digitalWrite(TRIG_1, LOW);
  digitalWrite(TRIG_2, LOW);
  digitalWrite(TRIG_3, LOW);
  digitalWrite(TRIG_4, LOW);

  noInterrupts();

  previousState = PIND;

  PCMSK2 |= (1 << PCINT18);
  PCMSK2 |= (1 << PCINT19);
  PCMSK2 |= (1 << PCINT20);
  PCMSK2 |= (1 << PCINT21);

  PCIFR |= (1 << PCIF2);  // To remove any interrupts that are incomplete
  PCICR |= (1 << PCIE2);  // Restart interrupt

  interrupts();
}

void loop() {

  for (byte i = 0; i < 4; i++) {

    digitalWrite(TRIG_1 + i, LOW);
    delayMicroseconds(2);

    digitalWrite(TRIG_1 + i, HIGH);
    delayMicroseconds(10);

    digitalWrite(TRIG_1 + i, LOW);

    unsigned long triggerTime = micros();

    while (!echoComplete[i] && micros() - triggerTime < 25000UL) {
    }

    noInterrupts();

    bool completed = echoComplete[i];
    unsigned long start = startTime[i];
    unsigned long end = endTime[i];

    echoComplete[i] = false;

    interrupts();

    if (completed) {

      unsigned long duration = end - start;

      distance[i] = duration / 58.0;

      Serial.print("Sensor ");
      Serial.print(i + 1);
      Serial.print(": ");
      Serial.print(distance[i]);
      Serial.println(" cm");

    }
    else {
      Serial.print("Sensor ");
      Serial.print(i + 1);
      Serial.println(": No Echo");
    }

    delay(30);
  }
}

ISR(PCINT2_vect) {

  byte currentState = PIND;

  byte changedPins = currentState ^ previousState;

  previousState = currentState;

  // SENSOR 1 - D2
  if (changedPins & (1 << 2)) {

    if (currentState & (1 << 2)) {
      startTime[0] = micros();
    }
    else {
      endTime[0] = micros();
      echoComplete[0] = true;
    }
  }

  // SENSOR 2 - D3
  if (changedPins & (1 << 3)) {

    if (currentState & (1 << 3)) {
      startTime[1] = micros();
    }
    else {
      endTime[1] = micros();
      echoComplete[1] = true;
    }
  }

  // SENSOR 3 - D4
  if (changedPins & (1 << 4)) {

    if (currentState & (1 << 4)) {
      startTime[2] = micros();
    }
    else {
      endTime[2] = micros();
      echoComplete[2] = true;
    }
  }

  // SENSOR 4 - D5
  if (changedPins & (1 << 5)) {

    if (currentState & (1 << 5)) {
      startTime[3] = micros();
    }
    else {
      endTime[3] = micros();
      echoComplete[3] = true;
    }
  }
}
