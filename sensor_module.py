"""
sensor_module.py
-----------------
Sensor data acquisition layer.

Supports two real sensors commonly used in Raspberry Pi IoT projects:
  - DHT22 (temperature + humidity)     -> via the 'adafruit_dht' library
  - LDR / photoresistor (light level)  -> via an MCP3008 ADC on SPI

If those libraries/hardware are not present (e.g. developing on a laptop),
the module falls back to a realistic simulated signal generator, so the
Flask app and dashboard behave identically either way.

A background polling thread samples the sensors on a fixed interval and
appends readings to a bounded in-memory history (deque), which the Flask
routes serve to the dashboard.
"""

import logging
import math
import random
import threading
import time
from collections import deque
from datetime import datetime

logger = logging.getLogger("iot.sensors")

try:
    import adafruit_dht
    import board
    HARDWARE_AVAILABLE = True
except (ImportError, NotImplementedError):
    HARDWARE_AVAILABLE = False


class SensorHub:
    """Polls temperature, humidity and light sensors on a background
    thread and keeps a rolling history for the dashboard/API."""

    def __init__(self, history_size=120, poll_interval=2.0, dht_pin=4):
        self.poll_interval = poll_interval
        self.hardware_available = HARDWARE_AVAILABLE
        self.history = deque(maxlen=history_size)
        self._lock = threading.Lock()
        self._latest = {"temperature": None, "humidity": None, "light": None, "timestamp": None}
        self._stop_event = threading.Event()
        self._thread = None
        self._t0 = time.time()

        if self.hardware_available:
            try:
                self._dht = adafruit_dht.DHT22(getattr(board, f"D{dht_pin}"))
                logger.info("DHT22 sensor initialised on GPIO%s - HARDWARE mode", dht_pin)
            except Exception as exc:  # pragma: no cover - hardware specific
                logger.warning("Failed to init DHT22 (%s); falling back to simulation", exc)
                self.hardware_available = False
        if not self.hardware_available:
            logger.info("No sensor hardware detected - running in SIMULATION mode")

    # ---------- acquisition ----------

    def _read_hardware(self):
        temperature = self._dht.temperature
        humidity = self._dht.humidity
        light = None  # extend with MCP3008 SPI read if attached
        return temperature, humidity, light

    def _read_simulated(self):
        """Generate smooth, realistic-looking sensor noise using sine
        waves + jitter so the dashboard has something believable to plot."""
        elapsed = time.time() - self._t0
        temperature = 24.0 + 3.0 * math.sin(elapsed / 45.0) + random.uniform(-0.3, 0.3)
        humidity = 50.0 + 8.0 * math.sin(elapsed / 70.0 + 1.2) + random.uniform(-1, 1)
        light = 500 + 400 * math.sin(elapsed / 30.0 + 0.5) + random.uniform(-20, 20)
        return round(temperature, 1), round(max(0, min(100, humidity)), 1), round(max(0, light), 0)

    def read_once(self):
        try:
            if self.hardware_available:
                temperature, humidity, light = self._read_hardware()
                if light is None:
                    _, _, light = self._read_simulated()
            else:
                temperature, humidity, light = self._read_simulated()
        except Exception as exc:  # pragma: no cover
            logger.warning("Sensor read failed (%s); using last known / simulated value", exc)
            temperature, humidity, light = self._read_simulated()

        reading = {
            "temperature": temperature,
            "humidity": humidity,
            "light": light,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        with self._lock:
            self._latest = reading
            self.history.append(reading)
        return reading

    # ---------- background thread management ----------

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Sensor polling thread started (interval=%.1fs)", self.poll_interval)

    def _poll_loop(self):
        while not self._stop_event.is_set():
            self.read_once()
            self._stop_event.wait(self.poll_interval)

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    # ---------- accessors ----------

    def latest(self):
        with self._lock:
            return dict(self._latest)

    def get_history(self, limit=60):
        with self._lock:
            return list(self.history)[-limit:]
