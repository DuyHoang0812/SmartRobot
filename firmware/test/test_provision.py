"""Provisioning validation tests only: no device I/O or motor/sensor emulation."""

import importlib.util
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("provision", ROOT / "tools/provision.py")
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)


class ProvisionTests(unittest.TestCase):
    def config(self):
        return {
            "wifi_ssid": "unit-test",
            "wifi_password": "",
            "backend_url": "https://robot.example.test/api/v1/devices",
            "device_id": "test-device",
            "device_secret": "unit-test-only-" + "x" * 50,
        }

    def test_defaults_are_unarmed(self):
        rows = provision.rows_from_config(self.config(), ROOT)
        values = {r[0]: r[3] for r in rows}
        self.assertEqual(values["motors_on"], 0)
        self.assertEqual(values["blind_manual"], 0)
        self.assertEqual(values["relay_console"], 0)

    def test_http_requires_private_numeric_ip_and_explicit_opt_in(self):
        for url, allow in [
            ("http://192.168.1.10:8000", False),
            ("http://8.8.8.8", True),
            ("http://example.test", True),
        ]:
            with self.assertRaises(ValueError):
                provision.rows_from_config(
                    self.config()
                    | {"backend_url": url + "/api/v1/devices", "allow_http_lan": allow},
                    ROOT,
                )
        provision.rows_from_config(
            self.config()
            | {
                "backend_url": "http://192.168.1.10:8000/api/v1/devices",
                "allow_http_lan": True,
            },
            ROOT,
        )

    def test_secret_header_injection_and_unknown_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            provision.rows_from_config(
                self.config() | {"device_secret": "x" * 64 + "\r\nBad: header"}, ROOT
            )
        with self.assertRaises(ValueError):
            provision.rows_from_config(self.config() | {"gpio_in1": 4}, ROOT)

    def test_blind_motion_and_timeout_limits(self):
        for field, value in [
            ("blind_manual_max_ms", 500),
            ("http_timeout_ms", 1000),
            ("full_speed", True),
            ("left_motor_percent", 49),
            ("right_motor_percent", 151),
            ("right_motor_percent", 83.55),
            ("right_motor_percent", float("nan")),
            ("right_motor_percent", True),
            ("auto_clearance_cm", 14),
            ("auto_backup_ms", 401),
            ("auto_turn_left_ms", 99),
            ("auto_turn_right_ms", 1201),
        ]:
            with self.assertRaises(ValueError):
                provision.rows_from_config(self.config() | {field: value}, ROOT)

    def test_motor_trim_and_auto_defaults_and_nvs_types(self):
        values = {
            r[0]: (r[2], r[3]) for r in provision.rows_from_config(self.config(), ROOT)
        }
        self.assertEqual(values["left_pct10"], ("u32", 1000))
        self.assertEqual(values["right_pct10"], ("u32", 835))
        self.assertEqual(values["auto_clear"], ("u32", 15))
        self.assertEqual(values["auto_back_ms"], ("u32", 400))
        self.assertEqual(values["trim_rev"], ("u8", 16))
        self.assertEqual(values["auto_rev"], ("u8", 10))

    def test_official_nvs_generator_produces_private_image_without_leaking_values(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            config = folder / "test.json"
            config.write_text(json.dumps(self.config()))
            out = folder / "test.bin"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/provision.py"),
                    str(config),
                    "--out",
                    str(out),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(out.stat().st_size, 65536)
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
            self.assertNotIn(
                self.config()["device_secret"], result.stdout + result.stderr
            )
            self.assertEqual(list(folder.glob("*.csv")), [])


if __name__ == "__main__":
    unittest.main()
