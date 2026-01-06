#include <Arduino.h>
#include <WiFi.h>
#include <AccelStepper.h>
#include <SPIFFS.h>

/* =========================================================================
   USER CONFIGURATION
   ========================================================================= */

String ssid;
String password;
const int serverPort = 10000;

// Pin Definitions
#define AZ_STEP_PIN     18
#define AZ_DIR_PIN      19
#define ALT_STEP_PIN    21
#define ALT_DIR_PIN     22
#define EN_PIN          15  // Shared Enable Pin for both drivers
#define LED_PIN         5   // Built-in ESP32 LED (usually GPIO 2)

// Inputs
#define BTN_HOME_AZ     14 // Pin for Azimuth Homing Button has external pull-down
#define BTN_HOME_ALT    13 // Pin for Altitude Homing Button has external pull-down
#define FORCE_STOP_PIN  25 // Pin for Emergency Stop Button has external pull-down

// Mechanical Specs
const float AZ_RATIO  = 5.75;
const float ALT_RATIO = 8.0;
const int MICROSTEPS  = 2; 

const float AZ_STEPS_PER_DEG  = (200.0 * MICROSTEPS * AZ_RATIO) / 360.0;
const float ALT_STEPS_PER_DEG = (200.0 * MICROSTEPS * ALT_RATIO) / 360.0;

const float ALT_MAX = 54.0;
const float ALT_MIN = -50.0;

const float MAX_SPEED = 1800.0;
const float ACCELERATION = 240.0; 

/* =========================================================================
   GLOBALS & OBJECTS
   ========================================================================= */

WiFiServer server(serverPort);
AccelStepper azStepper(AccelStepper::DRIVER, AZ_STEP_PIN, AZ_DIR_PIN);
AccelStepper altStepper(AccelStepper::DRIVER, ALT_STEP_PIN, ALT_DIR_PIN);

bool isEmergencyStopped = false;
bool azHomed = false;
bool altHomed = false;
String inputBuffer = "";

/* ==== NEW: timeout handling ==== */
unsigned long lastPacketTime = 0;           // when we last got a valid position
const unsigned long POSITION_TIMEOUT = 5000UL;  // 5 seconds

/*declare custom functions*/
void setAzimuthTarget(float targetDeg);
void setAltitudeTarget(float targetDeg);
void processPacket(String packet);


/* =========================================================================
   CORE FUNCTIONS
   ========================================================================= */

void setAzimuthTarget(float targetDeg) {
  while (targetDeg >= 360) targetDeg -= 360;
  while (targetDeg < 0)    targetDeg += 360;
  long currentSteps = azStepper.currentPosition();
  float currentDegRaw = currentSteps / AZ_STEPS_PER_DEG;
  float diff = targetDeg - (currentDegRaw - (360.0 * floor(currentDegRaw/360.0)));
  if (diff < -180) diff += 360;
  if (diff > 180)  diff -= 360;
  azStepper.moveTo(currentSteps + (diff * AZ_STEPS_PER_DEG));
}

void setAltitudeTarget(float targetDeg) {
  if (targetDeg > ALT_MAX) targetDeg = ALT_MAX;
  if (targetDeg < ALT_MIN) targetDeg = ALT_MIN;
  altStepper.moveTo(targetDeg * ALT_STEPS_PER_DEG);
}

void processPacket(String packet) {
  packet.trim();
  int azIndex = packet.indexOf("AZ:");
  int altIndex = packet.indexOf("ALT:");
  if (azIndex != -1 && altIndex != -1) {
    float newAz = packet.substring(azIndex + 3, altIndex).toFloat();
    float newAlt = packet.substring(altIndex + 4).toFloat();
    if (!isEmergencyStopped) {
      setAzimuthTarget(newAz);
      setAltitudeTarget(newAlt);
      //Serial.printf("Targeting -> AZ: %.3f, ALT: %.3f\n", newAz, newAlt);
      Serial.printf("[WiFi] RSSI: %d dBm, Channel: %d\n", WiFi.RSSI(), WiFi.channel());

      /* ==== UPDATE timeout timer every time we get a good packet ==== */
      lastPacketTime = millis();
    }
  }
}

/* =========================================================================
   SETUP
   ========================================================================= */

void setup() {
  Serial.begin(115200);

  // Initialize SPIFFS
  if (!SPIFFS.begin(true)) {
    Serial.println("SPIFFS Mount Failed");
    return;
  }

  // Load config
  File file = SPIFFS.open("/config.txt", "r");
  if (!file) {
    Serial.println("Failed to open config file");
    return;
  }
  while (file.available()) {
    String line = file.readStringUntil('\n');
    line.trim();
    if (line.startsWith("ssid=")) {
      ssid = line.substring(5);
    } else if (line.startsWith("password=")) {
      password = line.substring(9);
    }
  }
  file.close();

  // Set Pins to INPUT (not INPUT_PULLUP) because you are using external pull-downs
  pinMode(BTN_HOME_AZ, INPUT);
  pinMode(BTN_HOME_ALT, INPUT);
  pinMode(FORCE_STOP_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, HIGH); // Disable motors for manual movement

  azStepper.setMaxSpeed(MAX_SPEED);
  azStepper.setAcceleration(ACCELERATION);
  altStepper.setMaxSpeed(MAX_SPEED);
  altStepper.setAcceleration(ACCELERATION);

  // WiFi Connection
  WiFi.setAutoReconnect(true);
  Serial.print("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected!");
  Serial.print("ESP32 IP Address: ");
  Serial.println(WiFi.localIP());
  server.begin();

  // Homing Phase
  unsigned long lastBlink = 0;
  bool ledState = false;

  Serial.println("SYSTEM READY: Move telescope manually to North/Level, then press buttons.");

  while (!azHomed || !altHomed) {
    if (millis() - lastBlink > 300) {
      ledState = !ledState;
      digitalWrite(LED_PIN, ledState);
      lastBlink = millis();
    }

    if (!azHomed && digitalRead(BTN_HOME_AZ) == HIGH) {
      delay(200);
      azStepper.setCurrentPosition(0);
      azHomed = true;
      Serial.println(">> Azimuth (North) set.");
    }

    if (!altHomed && digitalRead(BTN_HOME_ALT) == HIGH) {
      delay(200);
      altStepper.setCurrentPosition(0);
      altHomed = true;
      Serial.println(">> Altitude (Level) set.");
    }

    if (digitalRead(FORCE_STOP_PIN) == HIGH) {
      Serial.println("Force Stop active! Homing halted.");
      digitalWrite(LED_PIN, LOW);
      while(1); 
    }
  }

  digitalWrite(EN_PIN, LOW);
  digitalWrite(LED_PIN, HIGH);
  Serial.println("Motors locked. Listening for socket data...");

  /* Initialise timeout timer – we consider the system "fresh" after homing */
  lastPacketTime = millis();
}

/* =========================================================================
   MAIN LOOP
   ========================================================================= */

void loop() {
  // 1. Safety Check (HIGH = Stop triggered)
  if (digitalRead(FORCE_STOP_PIN) == HIGH) {
    isEmergencyStopped = true;
    digitalWrite(EN_PIN, HIGH);
    digitalWrite(LED_PIN, LOW);
  }

  if (isEmergencyStopped) return;
  
  // 2. Continuous Motor Step Update
  azStepper.run();
  altStepper.run();

  // 3. Socket Client Handling
  static WiFiClient client;
  if (!client || !client.connected()) {
    client = server.available();
    if (client) {
      inputBuffer = "";
      client.flush();
      Serial.println("Python script connected.");
      // Optional: immediately enable motors when client connects
      lastPacketTime = millis();
    }
  }

  if (client && client.connected()) {
    while (client.available() > 0) {
      azStepper.run();
      altStepper.run();

      char c = client.read();
      if (c == '\n') {
        processPacket(inputBuffer);
        inputBuffer = "";
      } else if (c != '\r') {
        inputBuffer += c;
      }
    }
  }
}