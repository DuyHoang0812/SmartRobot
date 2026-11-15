#!/usr/bin/env python3
"""Validate firmware JSON serializers against Pydantic schemas; no hardware emulation."""

import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "backend"))
from app.schemas.devices import AckInput, TelemetryInput  # noqa: E402

result = subprocess.run(
    [str(root / "firmware/.pio/host/protocol_test"), "--contract-json"],
    check=True,
    capture_output=True,
    text=True,
)
data = json.loads(result.stdout)
for status in ["RECEIVED", "APPLIED", "REJECTED", "FAILED"]:
    ack = AckInput.model_validate(data[status])
    assert ack.status.value == status
sample = TelemetryInput.model_validate(data["telemetry"])
assert sample.distance_cm is None and sample.obstacle_status.value == "SENSOR_ERROR"
print("Firmware ACK/telemetry JSON validated against actual backend Pydantic schemas")
