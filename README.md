Details:

This program is meant to run a AZ/EL mount for a telescope that runs on stepper motors, meant for automatically tracking aerial objects.

Currently supporting tracking for:

Aircraft through adsb

Satellites and planets and moons, which are availible through JPL Horisons

Requirements:

ESP-32 DEV board
An AZ/EL mount running on stepper motors
Firefox browser

How to use:

Configure config.txt, 

Configure mechanical parameters to suit your AZ/EL mount in main code

```
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
```

set up gpios like so

```
// Pin Definitions
#define AZ_STEP_PIN     18
#define AZ_DIR_PIN      19
#define ALT_STEP_PIN    21
#define ALT_DIR_PIN     22
#define EN_PIN          15  // Shared Enable Pin for both drivers
#define LED_PIN         5   // Built-in ESP32 LED (usually GPIO 2)

// Inputs
#define BTN_HOME_AZ     14 // Pin for Azimuth Homing Button has external 1kO pull-down
#define BTN_HOME_ALT    13 // Pin for Altitude Homing Button has external 1kO pull-down
#define FORCE_STOP_PIN  25 // Pin for Emergency Stop Button has external 1kO pull-down
```

compile actuareveeyespy.cpp to your esp32

monitor serial for the esp32 ip and edit accordily in the other python programs


