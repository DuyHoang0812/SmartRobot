#!/usr/bin/env python3
"""Compare native wiring to the reference and inspect the built flash image without serial I/O."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
legacy = (ROOT / "ver2_6_esp32.ino").read_text()
board = (ROOT / "src/board.h").read_text()
for old, new in [
    ("IN1", "PIN_IN1"),
    ("IN2", "PIN_IN2"),
    ("IN3", "PIN_IN3"),
    ("IN4", "PIN_IN4"),
    ("TRIG_PIN", "PIN_TRIG"),
    ("ECHO_PIN", "PIN_ECHO"),
    ("SERVO1_PIN", "PIN_SERVO"),
    ("BUZZER_PIN", "PIN_BUZZER"),
    ("RELAY_PIN", "PIN_RELAY"),
]:
    original = int(re.search(rf"const int {old}\s*=\s*(\d+)", legacy).group(1))
    native = int(re.search(rf"#define {new}\s+(\d+)", board).group(1))
    assert original == native, f"GPIO mismatch: {old}"
image = (ROOT / ".pio/build/esp32dev/firmware.bin").read_bytes()
assert image[0] == 0xE9 and image[3] >> 4 == 2, "ESP image must declare physical flash 4MB"
assert len(image) < 0x300000, "Application exceeds partition"
print("All 9 GPIO mappings match reference; ESP image header declares 4MB, app fits 3MB partition")
