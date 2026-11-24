#include <Arduino.h>
#include <ESP_I2S.h>
#include <LittleFS.h>
#include <Stepper.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

const int sensorPins[] = {1, 2, 6, 8};
constexpr int stepsPerRevolution = 2048;
constexpr float openingTurns = 2.0f;  // Measured from closed to fully open.
constexpr int openingSteps = static_cast<int>(openingTurns * stepsPerRevolution + 0.5f);
static_assert(openingSteps > 0, "openingTurns must specify at least one step.");
constexpr int openingRpm = 8;
constexpr int closingRpm = 8;  // Start slower under the closing load.
constexpr unsigned long stepIntervalAtOneRpmUs = 60000000UL / stepsPerRevolution;
constexpr unsigned long sensorIntervalMs = 100;
// false: bloom with a mix of light and shade. true: require exactly 2 shaded.
const bool requireTwoAndTwo = false;
const size_t sensorCount = sizeof(sensorPins) / sizeof(sensorPins[0]);
const int shadeThreshold = 40;
const int lightThreshold = 60;
const int minCalibrationSpan = 12;
const unsigned long shadeHoldMs = 2000;  // Set to 5000 for five seconds.

const int sampleRate = 16000;
const int volumeDivisor = 12;  // Larger values make playback quieter.
const size_t framesPerBuffer = 256;

Stepper motor(stepsPerRevolution, 16, 5, 18, 17);
I2SClass audio;
File clip;
int litReading[sensorCount];
int shadedReading[sensorCount];
bool sensorShaded[sensorCount] = {};
bool sensorUsable[sensorCount] = {};
int activeSensorCount = 0;
bool calibrationOk = false;
// Step zero is the physically closed position at startup.
int motorPositionSteps = 0;
int targetPositionSteps = 0;
unsigned long lastMotorStepUs = 0;
unsigned long lastSensorReadMs = 0;
int pendingShadedCount = -1;
unsigned long countStableSinceMs = 0;

void sampleCalibration(int averages[], int noiseRanges[]) {
  const int sampleCount = 50;
  int sums[sensorCount] = {};
  int lows[sensorCount] = {};
  int highs[sensorCount] = {};

  for (int sample = 0; sample < sampleCount; ++sample) {
    for (size_t i = 0; i < sensorCount; ++i) {
      const int reading = analogRead(sensorPins[i]);
      sums[i] += reading;
      if (sample == 0 || reading < lows[i]) {
        lows[i] = reading;
      }
      if (sample == 0 || reading > highs[i]) {
        highs[i] = reading;
      }
    }
    delay(20);
  }

  for (size_t i = 0; i < sensorCount; ++i) {
    averages[i] = (sums[i] + sampleCount / 2) / sampleCount;
    noiseRanges[i] = highs[i] - lows[i];
  }
}

bool calibrateSensors() {
  int litNoise[sensorCount];
  int shadedNoise[sensorCount];

  Serial.println("Step 1: Leave all sensors in normal light. Sampling in 3 s.");
  delay(3000);
  sampleCalibration(litReading, litNoise);

  Serial.println("Step 2: Shade all sensors as you would during use. Sampling in 5 s.");
  delay(5000);
  sampleCalibration(shadedReading, shadedNoise);

  activeSensorCount = 0;
  for (size_t i = 0; i < sensorCount; ++i) {
    const int span = litReading[i] - shadedReading[i];
    const int noise = max(litNoise[i], shadedNoise[i]);
    sensorUsable[i] = span >= minCalibrationSpan && span > 2 * noise;
    activeSensorCount += sensorUsable[i];
    Serial.printf("GPIO%d: light=%d shade=%d span=%d noise=%d%s\n",
                  sensorPins[i], litReading[i], shadedReading[i], span, noise,
                  sensorUsable[i] ? "" : "  WEAK SIGNAL (ignored)");
  }

  if (activeSensorCount < static_cast<int>(sensorCount) - 1) {
    Serial.println("Too few usable sensors. Flower stays closed.");
    return false;
  }

  Serial.printf("Calibration done. Using %d of %d sensors.\n",
                activeSensorCount, static_cast<int>(sensorCount));
  return true;
}

int readShadedCount() {
  int shadedCount = 0;
  for (size_t i = 0; i < sensorCount; ++i) {
    if (!sensorUsable[i]) {
      continue;
    }

    const int raw = analogRead(sensorPins[i]);
    const int span = litReading[i] - shadedReading[i];
    const int percent = 100 * (raw - shadedReading[i]) / span;

    // In the middle band, retain the previous classification.
    if (percent <= shadeThreshold) {
      sensorShaded[i] = true;
    } else if (percent >= lightThreshold) {
      sensorShaded[i] = false;
    }

    shadedCount += sensorShaded[i];
    Serial.printf("GPIO%d=%d %s  ", sensorPins[i], raw,
                  sensorShaded[i] ? "shade" : "light");
  }
  Serial.printf("| shaded: %d/%d\n", shadedCount, activeSensorCount);
  return shadedCount;
}

void playAudio(void *) {
  int16_t mono[framesPerBuffer];
  int16_t stereo[framesPerBuffer * 2];

  while (true) {
    size_t bytesRead = clip.read(reinterpret_cast<uint8_t *>(mono), sizeof(mono));
    if (bytesRead == 0 && clip.seek(0)) {
      bytesRead = clip.read(reinterpret_cast<uint8_t *>(mono), sizeof(mono));
    }

    if (bytesRead == 0 || bytesRead % sizeof(mono[0]) != 0) {
      Serial.println("Could not read /sound.pcm.");
      break;
    }

    const size_t frames = bytesRead / sizeof(mono[0]);
    for (size_t i = 0; i < frames; ++i) {
      const int16_t sample = mono[i] / volumeDivisor;
      stereo[2 * i] = sample;
      stereo[2 * i + 1] = sample;
    }

    const size_t outputBytes = frames * 2 * sizeof(stereo[0]);
    if (audio.write(reinterpret_cast<uint8_t *>(stereo), outputBytes) != outputBytes) {
      Serial.println("I2S write failed.");
      break;
    }
  }

  clip.close();
  audio.end();
  vTaskDelete(nullptr);
}

void startAudio() {
  if (!LittleFS.begin()) {
    Serial.println("LittleFS mount failed.");
    return;
  }

  clip = LittleFS.open("/sound.pcm", "r");
  if (!clip || clip.size() == 0 || clip.size() % sizeof(int16_t) != 0) {
    Serial.println("Missing or invalid /sound.pcm.");
    clip.close();
    return;
  }

  audio.setPins(9, 10, 11);  // BCLK, LRC, DIN
  if (!audio.begin(I2S_MODE_STD, sampleRate, I2S_DATA_BIT_WIDTH_16BIT,
                   I2S_SLOT_MODE_STEREO)) {
    Serial.println("I2S setup failed.");
    clip.close();
    return;
  }

  // The I2S write blocks while its buffers drain. The stepper can run meanwhile.
  if (xTaskCreate(playAudio, "audio", 6144, nullptr, 2, nullptr) != pdPASS) {
    Serial.println("Could not start the audio task.");
    clip.close();
    audio.end();
  }
}

void setup() {
  Serial.begin(9600);
  motor.setSpeed(closingRpm);
  calibrationOk = calibrateSensors();
  startAudio();
}

void updateBloomTarget(unsigned long now) {
  const int shadedCount = readShadedCount();
  if (shadedCount != pendingShadedCount) {
    pendingShadedCount = shadedCount;
    countStableSinceMs = now;
  }

  if (now - countStableSinceMs < shadeHoldMs) {
    return;
  }

  const bool mixedLight = shadedCount > 0 && shadedCount < activeSensorCount;
  const bool shouldBloom = mixedLight && (!requireTwoAndTwo || shadedCount == 2);
  const int requestedPosition = shouldBloom ? openingSteps : 0;
  if (targetPositionSteps != requestedPosition) {
    targetPositionSteps = requestedPosition;
    motor.setSpeed(shouldBloom ? openingRpm : closingRpm);
    Serial.println(shouldBloom ? "Opening flower" : "Closing flower");
  }
}

void advanceMotor() {
  const int rpm = targetPositionSteps == 0 ? closingRpm : openingRpm;
  const unsigned long motorStepIntervalUs = stepIntervalAtOneRpmUs / rpm;
  if (motorPositionSteps == targetPositionSteps ||
      micros() - lastMotorStepUs < motorStepIntervalUs) {
    return;
  }

  if (motorPositionSteps < targetPositionSteps) {
    motor.step(-1);
    ++motorPositionSteps;
  } else {
    motor.step(1);
    --motorPositionSteps;
  }
  lastMotorStepUs = micros();
}

void loop() {
  if (!calibrationOk) {
    delay(1000);
    return;
  }

  const unsigned long now = millis();
  if (now - lastSensorReadMs >= sensorIntervalMs) {
    lastSensorReadMs = now;
    updateBloomTarget(now);
  }

  advanceMotor();
  delay(1);
}
