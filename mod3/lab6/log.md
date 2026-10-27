## 10/15

### 1:50pm
Cleared the protoboard from the previous project, got a photoresistor, and connected the ESP32 to the protoboard and to the laptop.

- RPi IP address is `10.67.65.142`
- Decided to send data from the ESP32 to the RPi over WiFi using UDP

### 1:55pm
Found an example script in the Arduino IDE for sending data from the ESP32 over WiFi using UDP.

- Set up a simple UDP server on the RPi to test the connection

### 2:00pm
Measured the photoresistor's resistance range to be between 3k and 20k ohms.

- Explored how to produce audio through the interface/monitor
- Started testing dummy data transfer from ESP32 to RPi; debugging connection not being found
- Realized we needed to register the MAC address on the Yale wireless registry; found a script and waited for it to register

### 2:15pm
While waiting for the MAC address to register, tested whether a connection was possible on YaleGuest (data transfer isn't possible) → we were able to connect.

- Meanwhile, started ideating the audio/visual mechanism for representing the photoresistor measurements
- Idea: depending on the photoresistor readings, play a given audio file at different speeds
  - e.g. at 3k ohms play at 0.2x speed, at 20k ohms play at 5x speed, etc.

### 2:22pm
Started wiring the circuit, no hiccups.

- Measurements read correctly on the ESP32, ranging between 800 and 3000 ohms (due to voltage difference)

### 2:30pm
Started coding the audio transformation; registration still pending.

- Found a YouTube video and ran a script to pull the audio file directly from the video link
- Debugged audio errors on the monitor
- Realized the monitors have no speakers → pivoted to visual output
- Connection still not working (for the entire class — everyone who registered their MAC address today); working on the visual part now

### 2:50pm
Finished the Pac-Man code using dummy values.

---

## 10/17

### 4:50pm
Verified the connection was working.

- Connected the ESP32 to the RPi and SSH'd into the RPi to set up `.ino` scripts and one-time installations

### 6:00pm
Finalized submission. Was unable to debug the slow packet-sending issue.
