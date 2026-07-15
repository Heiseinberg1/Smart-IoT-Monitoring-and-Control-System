# IOT-CTRL &mdash; Smart IoT Monitoring & Control System

A Raspberry Pi-ready IoT project combining **Python, GPIO, Flask, sensor
acquisition, LED control, a live web dashboard, and core networking
concepts** in one cohesive system.

Runs in two modes automatically, no code changes needed:

| Mode | When | Sensor data | LED output |
|---|---|---|---|
| **Hardware** | Running on a Raspberry Pi with `RPi.GPIO` + `adafruit_dht` installed and wired | Real DHT22 readings | Real GPIO pins |
| **Simulation** | Running anywhere else (laptop, classroom PC) | Realistic generated signal | In-memory simulated state |

This means you can build and demo the entire dashboard on a laptop, then
deploy the identical code to a Pi with real hardware attached.

## 1. Architecture

```
 Browser (client)                     Raspberry Pi (server)
 ┌───────────────────┐   HTTP GET     ┌───────────────────────────┐
 │  dashboard.html    │ ─────────────▶│  Flask app (app.py)        │
 │  + dashboard.js     │◀───JSON──────│   ├── /api/sensors/*        │
 │  (polls every 2s)   │               │   ├── /api/leds/*           │
 │                      │  HTTP POST   │   └── /api/system/status    │
 │  LED toggle switch   │ ─────────────▶│                             │
 └───────────────────┘               │  sensor_module.py (thread) │
                                       │  gpio_controller.py       │
                                       └───────────────────────────┘
```

- **Server**: Flask process bound to `0.0.0.0:5000`, so it's reachable by
  any device on the same network, not just `localhost`.
- **Client**: the dashboard is plain HTML/CSS/JS. It never talks to GPIO
  directly &mdash; it only calls the REST API, exactly like a phone app
  or a second browser tab would.
- **Background thread**: sensors are sampled every 2 seconds independent
  of any client being connected, and kept in a bounded history buffer.
- **Actuator commands**: turning an LED on/off is an HTTP `POST` that
  changes server-side state and returns the new state as JSON &mdash;
  the standard REST pattern for controlling IoT devices.

## 2. Hardware wiring (optional &mdash; for a real Raspberry Pi)

| Component | Pi GPIO (BCM) | Notes |
|---|---|---|
| Red LED (+resistor ~330Ω) | GPIO 17 | Cathode to GND |
| Green LED (+resistor ~330Ω) | GPIO 27 | Cathode to GND |
| Blue LED (+resistor ~330Ω) | GPIO 22 | Cathode to GND |
| DHT22 data pin | GPIO 4 | Add a 10kΩ pull-up between data and 3.3V |

Change pin numbers in `LED_PINS` (`app.py`) or `dht_pin` (`SensorHub`) to
match your own wiring.

## 3. Setup

```bash
# 1. Clone / copy this folder onto your machine or Raspberry Pi
cd iot_system

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# 3. Install core dependencies
pip install -r requirements.txt

# 4. (Raspberry Pi only) install hardware libraries
pip install -r requirements-hardware.txt

# 5. Run the server
python app.py
```

Then open:
- `http://localhost:5000` on the same machine, or
- `http://<pi-ip-address>:5000` from any phone/laptop on the same Wi-Fi

Find your Pi's IP with `hostname -I`.

## 4. REST API reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/sensors/latest` | Most recent temperature/humidity/light reading |
| GET | `/api/sensors/history?limit=60` | Rolling history for charting |
| GET | `/api/leds` | State of every configured LED/output pin |
| POST | `/api/leds/<pin>/toggle` | Flip an LED's current state |
| POST | `/api/leds/<pin>/set` | Body: `{"state": true}` &mdash; set explicit state |
| GET | `/api/leds/history` | Recent switching events |
| GET | `/api/system/status` | Server uptime, request count, client IP, mode |

Example:
```bash
curl -X POST http://localhost:5000/api/leds/17/set \
     -H "Content-Type: application/json" \
     -d '{"state": true}'
```

## 5. Project structure

```
iot_system/
├── app.py                  # Flask server & REST API routes
├── gpio_controller.py      # GPIO abstraction (hardware + simulation)
├── sensor_module.py        # Sensor polling thread (hardware + simulation)
├── requirements.txt
├── requirements-hardware.txt
├── templates/
│   └── dashboard.html      # Web dashboard markup
└── static/
    ├── css/style.css       # Control-panel visual design
    └── js/dashboard.js     # Polling, chart rendering, LED switches
```

## 6. Concepts this project demonstrates

- **Python programming**: OOP design (`GPIOController`, `SensorHub`),
  threading, exception handling, hardware/software fallback patterns.
- **GPIO**: digital output control for LEDs/relays, sensor input wiring.
- **Flask web server**: routing, JSON responses, request handling,
  serving static assets and templates.
- **Sensor data acquisition**: background polling thread, bounded
  history buffer, graceful degradation when hardware is unavailable.
- **LED control**: REST-style actuator commands (`toggle`/`set`),
  server-side state tracking, event history.
- **Web dashboard**: live-updating UI built with vanilla HTML/CSS/JS
  and a dependency-free canvas chart.
- **Networking concepts**: client-server model, HTTP GET vs POST
  semantics, JSON as a wire format, polling vs push, binding
  `0.0.0.0` for LAN reachability, ports, and basic request telemetry.

## 7. Extending the project

- Swap polling for **Server-Sent Events** or **WebSockets** for true
  push updates instead of 2-second polling.
- Add **authentication** (Flask-Login) before exposing this beyond a
  trusted LAN.
- Persist sensor history to **SQLite** instead of in-memory `deque`.
- Add **email/SMS alerts** (e.g. via a webhook) when a sensor threshold
  is crossed.
- Containerize with **Docker** for consistent deployment across Pi
  models.
