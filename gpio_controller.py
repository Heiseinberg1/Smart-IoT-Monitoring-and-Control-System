"""
gpio_controller.py
-------------------
Hardware abstraction layer for GPIO output control (LEDs / relays).

On a real Raspberry Pi this uses RPi.GPIO. On any other machine (your
laptop, a CI runner, a classroom PC with no Pi attached) it transparently
falls back to an in-memory simulation so the whole system - Flask server,
dashboard, API - can be developed and demoed without hardware.

Usage:
    gpio = GPIOController()
    gpio.setup_pin(17, "Living Room LED")
    gpio.set_pin(17, True)
    state = gpio.get_pin(17)
"""

import logging
import time

logger = logging.getLogger("iot.gpio")

try:
    import RPi.GPIO as RPi_GPIO
    HARDWARE_AVAILABLE = True
except (ImportError, RuntimeError):
    HARDWARE_AVAILABLE = False


class GPIOController:
    """Controls digital output pins (LEDs/relays) with automatic
    hardware/simulation fallback."""

    def __init__(self, mode="BCM"):
        self.hardware_available = HARDWARE_AVAILABLE
        self._pins = {}          # pin -> {"label": str, "state": bool}
        self._history = []       # list of {pin, state, ts} events

        if self.hardware_available:
            RPi_GPIO.setmode(RPi_GPIO.BCM if mode == "BCM" else RPi_GPIO.BOARD)
            RPi_GPIO.setwarnings(False)
            logger.info("RPi.GPIO detected - running in HARDWARE mode")
        else:
            logger.info("RPi.GPIO not available - running in SIMULATION mode")

    def setup_pin(self, pin, label="LED"):
        """Register a pin as a digital output, defaulting to OFF."""
        if self.hardware_available:
            RPi_GPIO.setup(pin, RPi_GPIO.OUT)
            RPi_GPIO.output(pin, RPi_GPIO.LOW)
        self._pins[pin] = {"label": label, "state": False}
        logger.info("Configured pin %s (%s) as OUTPUT", pin, label)

    def set_pin(self, pin, state: bool):
        """Drive a pin HIGH (True) or LOW (False)."""
        if pin not in self._pins:
            raise KeyError(f"Pin {pin} has not been set up")

        if self.hardware_available:
            RPi_GPIO.output(pin, RPi_GPIO.HIGH if state else RPi_GPIO.LOW)

        self._pins[pin]["state"] = bool(state)
        self._history.append({
            "pin": pin,
            "label": self._pins[pin]["label"],
            "state": bool(state),
            "ts": time.time(),
        })
        self._history = self._history[-200:]  # keep it bounded
        logger.info("Pin %s (%s) -> %s", pin, self._pins[pin]["label"], "ON" if state else "OFF")
        return self._pins[pin]

    def toggle_pin(self, pin):
        current = self.get_pin(pin)["state"]
        return self.set_pin(pin, not current)

    def get_pin(self, pin):
        if pin not in self._pins:
            raise KeyError(f"Pin {pin} has not been set up")
        return self._pins[pin]

    def get_all_pins(self):
        return {pin: dict(info) for pin, info in self._pins.items()}

    def get_history(self, limit=50):
        return self._history[-limit:]

    def cleanup(self):
        if self.hardware_available:
            RPi_GPIO.cleanup()
        logger.info("GPIO cleaned up")
