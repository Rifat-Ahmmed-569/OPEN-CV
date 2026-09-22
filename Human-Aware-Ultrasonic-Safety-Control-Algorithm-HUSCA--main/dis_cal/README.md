# Human Detection + Arduino Safety System

This project combines:

- OpenCV-based human detection from the local camera
- HC-SR04 ultrasonic distance readings from an Arduino Uno
- Python logic that decides between SAFE and STOP
- Serial commands sent back to the Arduino to drive output pin 6

## Hardware

- Arduino Uno
- HC-SR04 ultrasonic sensor
  - TRIG -> A0
  - ECHO -> A1
- Control output
  - Arduino pin 6 -> control signal

## Serial configuration

- Port: /dev/ttyACM0
- Baud: 9600

The Arduino continuously sends a numeric distance value in centimeters over the same USB serial connection. Python reads that stream and ignores any non-numeric lines. Python then sends either `SAFE` or `STOP` back to the Arduino, one line at a time.

## Important

PlatformIO Serial Monitor and the Python application must not access /dev/ttyACM0 at the same time. Close the Serial Monitor before running the Python program.

## Build and upload Arduino firmware

From the project root:

```bash
platformio run -e uno -t upload
```

## Run Python application

Install dependencies:

```bash
python3 -m pip install -r python/requirements.txt
```

Run the app:

```bash
python3 python/main.py
```

Press `q` to quit the camera window.

## Safety logic

- No person detected -> `SAFE`
- Person detected and distance >= 60.96 cm -> `SAFE`
- Person detected and distance < 60.96 cm -> `STOP`

The Arduino converts:

- `STOP` -> pin 6 HIGH
- `SAFE` -> pin 6 LOW

## Notes

- The ultrasonic distance logic is kept in the Arduino sketch and remains compatible with the existing 9600 baud numeric stream.
- The Python program reads distance values asynchronously in a background thread so the camera window stays responsive.
- Commands are only sent when the state changes to avoid serial spam.
