
// byte ensures it takes 1 byte instead of standart 2 bytes unneccesarily
// If u change these numbers (For ECHO ONLY) u must change the interrupt reciever as well (PCMSK2)
const byte TRIG_1 = 8;
const byte ECHO_1 = 2;

const byte TRIG_2 = 9;
const byte ECHO_2 = 3;

const byte TRIG_3 = 10;
const byte ECHO_3 = 4;

const byte TRIG_4 = 11;
const byte ECHO_4 = 5;

const byte TRIG_5 = 12;
const byte ECHO_5 = 6;

const byte TRIG_6 = 13;
const byte ECHO_6 = 7;

// volatile used to say that this value can abruptly change
// Some times it might reject abrupt changes as accidental in default var types
volatile unsigned long startTime[6] = {0, 0, 0, 0, 0, 0};
volatile unsigned long endTime[6] = {0, 0, 0, 0, 0, 0};
volatile bool echoComplete[6] = {false, false, false, false, false, false};
volatile byte previousState = 0;

float distance[6] = {0, 0, 0, 0, 0, 0};

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

  pinMode(TRIG_5, OUTPUT);
  pinMode(ECHO_5, INPUT);

  pinMode(TRIG_6, OUTPUT);
  pinMode(ECHO_6, INPUT);

  for (byte i = 0; i < 6; i++) {
    digitalWrite(TRIG_1 + i, LOW);
  }

  noInterrupts();

  previousState = PIND;

  PCMSK2 |= (1 << PCINT18);
  PCMSK2 |= (1 << PCINT19);
  PCMSK2 |= (1 << PCINT20);
  PCMSK2 |= (1 << PCINT21);
  PCMSK2 |= (1 << PCINT22);
  PCMSK2 |= (1 << PCINT23);

  PCIFR |= (1 << PCIF2);
  PCICR |= (1 << PCIE2);

  interrupts();
}

void loop() {

  for (byte i = 0; i < 6; i++) {

    noInterrupts();

    echoComplete[i] = false;
    startTime[i] = 0;
    endTime[i] = 0;

    interrupts();

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

  for (byte i = 0; i < 6; i++) {

    byte pinMask = (1 << (i + 2));

    if (changedPins & pinMask) {

      if (currentState & pinMask) {
        startTime[i] = micros();
      }
      else {
        endTime[i] = micros();
        echoComplete[i] = true;
      }
    }
  }
}
