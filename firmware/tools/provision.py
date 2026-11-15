#!/usr/bin/env python3
"""Generate a private NVS configuration image. Never connects to or flashes an ESP32."""

import argparse
import csv
import ipaddress
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def rows_from_config(config, directory):
    allowed = {
        "wifi_ssid",
        "wifi_password",
        "backend_url",
        "device_id",
        "device_secret",
        "ca_file",
        "ntp_server",
        "allow_http_lan",
        "motors_enabled",
        "allow_blind_manual",
        "blind_manual_max_ms",
        "full_speed",
        "slow_speed",
        "turn_speed",
        "http_timeout_ms",
        "relay_console",
    }
    if not isinstance(config, dict) or set(config) - allowed:
        raise ValueError("Unknown configuration fields")
    strings = [
        ("ssid", "wifi_ssid", 1, 32),
        ("wifi_pass", "wifi_password", 0, 64),
        ("base_url", "backend_url", 20, 255),
        ("device_id", "device_id", 3, 128),
        ("secret", "device_secret", 32, 128),
    ]
    rows = [["robot", "namespace", "", ""]]
    for key, name, low, high in strings:
        value = config.get(name)
        if not isinstance(value, str) or not low <= len(value.encode()) <= high or "\0" in value:
            raise ValueError(f"Missing/invalid {name}; values are intentionally not echoed")
        rows.append([key, "data", "string", value])
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{3,128}", config["device_id"]):
        raise ValueError("Invalid Device ID")
    if not re.fullmatch(r"[!-~]{32,128}", config["device_secret"]):
        raise ValueError("Invalid device secret header characters")
    url = urlsplit(config["backend_url"])
    if (
        url.path != "/api/v1/devices"
        or url.query
        or url.fragment
        or url.username
        or url.password
        or not url.hostname
        or any(x in config["backend_url"] for x in "\r\n ")
    ):
        raise ValueError("Backend URL must end in /api/v1/devices, without credentials/query")
    if url.scheme != "https":
        if url.scheme != "http" or config.get("allow_http_lan") is not True:
            raise ValueError("HTTPS required unless allow_http_lan is explicitly enabled")
        addr = ipaddress.IPv4Address(url.hostname)
        if not any(
            addr in ipaddress.IPv4Network(net)
            for net in ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16"]
        ):
            raise ValueError("HTTP accepts only a numeric private LAN IPv4 address")
    if config.get("wifi_password") and len(config["wifi_password"].encode()) < 8:
        raise ValueError("Wi-Fi password must be empty for an open AP or at least 8 bytes")
    for key, name in [
        ("allow_http", "allow_http_lan"),
        ("motors_on", "motors_enabled"),
        ("blind_manual", "allow_blind_manual"),
        ("relay_console", "relay_console"),
    ]:
        value = config.get(name, False)
        if type(value) is not bool:
            raise ValueError(f"{name} must be a boolean")
        rows.append([key, "data", "u8", int(value)])
    for key, name, default, low, high in [
        ("full_speed", "full_speed", 75, 1, 255),
        ("slow_speed", "slow_speed", 30, 1, 255),
        ("turn_speed", "turn_speed", 75, 1, 255),
        ("blind_ms", "blind_manual_max_ms", 300, 50, 400),
        ("http_ms", "http_timeout_ms", 250, 50, 400),
    ]:
        value = config.get(name, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"Invalid {name}")
        rows.append([key, "data", "u8" if high == 255 else "u32", value])
    if config.get("slow_speed", 30) > config.get("full_speed", 75):
        raise ValueError("slow_speed must not exceed full_speed")
    ntp = config.get("ntp_server", "pool.ntp.org")
    if not isinstance(ntp, str) or not re.fullmatch(r"[A-Za-z0-9.:-]{1,127}", ntp):
        raise ValueError("Invalid NTP server")
    rows.append(["ntp", "data", "string", ntp])
    if config.get("ca_file"):
        ca = (directory / config["ca_file"]).read_text()
        if "-----BEGIN CERTIFICATE-----" not in ca or len(ca.encode()) > 3900:
            raise ValueError("CA must be a PEM certificate, at most 3900 bytes")
        rows.append(["ca_pem", "data", "string", ca])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", nargs="?", type=Path, default=ROOT / "device.local.json")
    parser.add_argument("--out", type=Path, default=ROOT / "secrets" / "robot_cfg.bin")
    parser.add_argument("--idf-python", type=Path)
    args = parser.parse_args()
    csv_path = None
    os.umask(0o077)
    try:
        rows = rows_from_config(json.loads(args.config.read_text()), args.config.resolve().parent)
        core = Path(os.environ.get("PLATFORMIO_CORE_DIR", Path.home() / ".platformio"))
        python = args.idf_python or core / "penv" / ".espidf-6.1.0" / "bin" / "python"
        if not python.is_file():
            raise ValueError(
                "Run pio run first, or provide --idf-python for the ESP-IDF environment"
            )
        args.out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(
            "w", newline="", suffix=".csv", dir=args.out.parent, delete=False
        ) as file:
            csv_path = Path(file.name)
            writer = csv.writer(file)
            writer.writerow(["key", "type", "encoding", "value"])
            writer.writerows(rows)
        result = subprocess.run(
            [
                str(python),
                "-m",
                "esp_idf_nvs_partition_gen",
                "generate",
                str(csv_path),
                str(args.out.resolve()),
                "0x10000",
            ],
            capture_output=True,
        )
        if result.returncode:
            raise ValueError("NVS generation failed; output suppressed to protect credentials")
        args.out.chmod(0o600)
        print("Private NVS image generated (0600). No device was flashed.")
    except (ValueError, OSError, KeyError, TypeError):
        parser.exit(
            1,
            "Invalid/missing provisioning configuration; no credentials were printed. "
            "Check README.\n",
        )
    finally:
        if csv_path:
            csv_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
