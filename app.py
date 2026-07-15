"""
app.py
------
Smart IoT Monitoring & Control System - Flask web server.

Architecture (networking concepts in play):
  - This process is an HTTP SERVER. Any device on the same LAN can be a
    CLIENT by browsing to http://<this-machine's-IP>:5000
  - The dashboard (HTML/JS) is the CLIENT: it polls the JSON REST API
    every few seconds (client-initiated HTTP GET) to refresh sensor
    readings - a simple, firewall-friendly alternative to WebSockets.
  - LED control uses HTTP POST requests: the client sends a state change,
    the server applies it via GPIO and returns the new state as JSON,
    which is the standard REST "command" pattern for IoT actuators.
  - Binding host="0.0.0.0" (vs "127.0.0.1") is what makes the server
    reachable from other devices on the network, not just the same
    machine - the single most common gotcha in student IoT projects.

Run:
    python app.py
Then visit:
    http://localhost:5000            (same machine)
    http://<pi-ip-address>:5000      (any device on the LAN)
"""

import logging
import time

from flask import Flask, jsonify, render_template, request

from gpio_controller import GPIOController
from sensor_module import SensorHub

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("iot.app")

app = Flask(__name__)

# ---------------------------------------------------------------------
# Device configuration - map logical devices to GPIO pins.
# Change these to match your actual wiring on a real Raspberry Pi.
# ---------------------------------------------------------------------
LED_PINS = {
    17: "Red LED (Alert)",
    27: "Green LED (Status)",
    22: "Blue LED (Accent)",
}

gpio = GPIOController(mode="BCM")
for pin, label in LED_PINS.items():
    gpio.setup_pin(pin, label)

sensors = SensorHub(history_size=120, poll_interval=2.0)
sensors.start()

SERVER_START_TIME = time.time()
request_counter = {"count": 0}


@app.before_request
def _count_requests():
    request_counter["count"] += 1


# ----------------------------- Web dashboard -----------------------------

@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        led_pins=LED_PINS,
        hardware_mode=gpio.hardware_available,
        sensor_hardware_mode=sensors.hardware_available,
    )


# ----------------------------- REST API: sensors -----------------------------

@app.route("/api/sensors/latest")
def api_sensors_latest():
    """Current snapshot of all sensor readings."""
    return jsonify(sensors.latest())


@app.route("/api/sensors/history")
def api_sensors_history():
    """Rolling history for charting. ?limit=60 (default) controls length."""
    limit = request.args.get("limit", default=60, type=int)
    return jsonify(sensors.get_history(limit=limit))


# ----------------------------- REST API: LEDs / actuators -----------------------------

@app.route("/api/leds")
def api_leds_list():
    """State of every configured output pin."""
    return jsonify(gpio.get_all_pins())


@app.route("/api/leds/<int:pin>/toggle", methods=["POST"])
def api_led_toggle(pin):
    try:
        new_state = gpio.toggle_pin(pin)
        return jsonify(new_state)
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404


@app.route("/api/leds/<int:pin>/set", methods=["POST"])
def api_led_set(pin):
    body = request.get_json(silent=True) or {}
    if "state" not in body:
        return jsonify({"error": "Request body must include boolean 'state'"}), 400
    try:
        new_state = gpio.set_pin(pin, bool(body["state"]))
        return jsonify(new_state)
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404


@app.route("/api/leds/history")
def api_led_history():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify(gpio.get_history(limit=limit))


# ----------------------------- REST API: system / networking status -----------------------------

@app.route("/api/system/status")
def api_system_status():
    """Server health + basic networking telemetry, shown in the dashboard's
    status strip to make the client-server relationship visible."""
    uptime = time.time() - SERVER_START_TIME
    return jsonify({
        "uptime_seconds": round(uptime, 1),
        "requests_served": request_counter["count"],
        "client_ip": request.remote_addr,
        "gpio_mode": "hardware" if gpio.hardware_available else "simulated",
        "sensor_mode": "hardware" if sensors.hardware_available else "simulated",
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })


if __name__ == "__main__":
    try:
        # host="0.0.0.0" -> reachable from other devices on the LAN
        # debug=True     -> auto-reload during development only
        app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    finally:
        sensors.stop()
        gpio.cleanup()
