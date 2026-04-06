from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)
CONFIG_PATH = Path("gpio.json")


class DummyGPIOController:
    def set_high(self, index: int):
        logger.debug("set_low:%i" % index)

    def set_low(self, index: int):
        logger.debug("set_high:%i" % index)

    def cleanup(self):
        logger.debug("cleanup")


class RaspberryPiGPIOController:
    def __init__(self, pins: list[int]):
        import RPi.GPIO as GPIO

        self.GPIO = GPIO
        self.pins = pins

        GPIO.setmode(GPIO.BCM)

        for pin in pins:
            GPIO.setup(pin, GPIO.OUT)

    def _check_index(self, index: int):
        if not 0 <= index < len(self.pins):
            raise IndexError(
                f"GPIO index {index} out of bounds "
                f"(valid: 0 to {len(self.pins) - 1})"
            )

    def set_high(self, index: int):
        self._check_index(index)
        self.GPIO.output(self.pins[index], self.GPIO.HIGH)
        logger.debug("set_high:%i" % index)

    def set_low(self, index: int):
        self._check_index(index)
        self.GPIO.output(self.pins[index], self.GPIO.LOW)
        logger.debug("set_low:%i" % index)

    def cleanup(self):
        self.GPIO.cleanup()
        logger.debug("cleanup")


def load_gpio_controller():
    if not CONFIG_PATH.exists():
        return DummyGPIOController()

    with CONFIG_PATH.open() as f:
        pins = json.load(f)

    if not isinstance(pins, list):
        raise ValueError("GPIO config must be a JSON list")

    return RaspberryPiGPIOController(pins)