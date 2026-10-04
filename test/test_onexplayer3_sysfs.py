import logging
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "py_modules"))
config = sys.modules.get("config", types.ModuleType("config"))
config.DEFAULT_BRIGHTNESS = 100
config.LED_PATH = "/nonexistent"
config.SOFTWARE_EFFECT_UPDATE_RATE = 30.0
config.logger = logging.getLogger("huesync-oxp3-test")
sys.modules["config"] = config

from devices.onexplayer3 import OneXPlayer3LEDDevice, OXP3_EFFECTS
from utils import Color, RGBMode


class OneXPlayer3Tests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name)
        attrs = {"brightness": "100", "max_brightness": "100",
                 "multi_intensity": "36 34 153", "multi_max_intensity": "100 100 100",
                 "multi_index": "red green blue", "enabled": "true", "effect": "unknown",
                 "effect_index": "monocolor " + " ".join(OXP3_EFFECTS.values()),
                 "speed": "5", "speed_range": "0-9"}
        for attr, value in attrs.items():
            (self.path / attr).write_text(value + "\n")
        patcher = patch("devices.onexplayer3.OXP3_LED_PATH", str(self.path))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.device = OneXPlayer3LEDDevice()

    def read(self, attr):
        return (self.path / attr).read_text().strip()

    def test_constructor_does_not_write_device_state(self):
        self.assertEqual(self.read("effect"), "unknown")
        self.assertEqual(self.read("multi_intensity"), "36 34 153")

    def test_solid_scaling_and_no_double_brightness(self):
        self.device.set_color(RGBMode.Solid, Color(64, 0, 0), brightness=25)
        self.assertEqual(self.read("multi_intensity"), "25 0 0")
        self.assertEqual(self.read("brightness"), "100")
        self.assertEqual(self.read("enabled"), "true")
        self.assertEqual(self.read("effect"), "monocolor")

    def test_disabled_and_reenabled(self):
        self.device.set_color(RGBMode.Disabled, Color(255, 0, 0))
        self.assertEqual(self.read("enabled"), "false")
        self.device.set_color(RGBMode.Solid, Color(255, 0, 0))
        self.assertEqual(self.read("enabled"), "true")
        self.assertEqual(self.read("multi_intensity"), "100 0 0")

    def test_black_solid_is_off(self):
        self.device.set_color(RGBMode.Solid, Color(0, 0, 0))
        self.assertEqual(self.read("enabled"), "false")

    def test_native_effect_brightness_speed_and_zero(self):
        for brightness in (0, 25, 100):
            with self.subTest(brightness=brightness):
                self.device.set_color(RGBMode.OXP_AURORA, Color(0, 0, 0), brightness=brightness, speed="high")
                self.assertEqual(self.read("brightness"), str(brightness))
                self.assertEqual(self.read("speed"), "9")
                self.assertEqual(self.read("effect"), "aurora")
                self.assertEqual(self.read("enabled"), "true" if brightness else "false")

    def test_preset_to_solid_replays_static_state(self):
        self.device.set_color(RGBMode.OXP_NEON, Color(0, 0, 0), brightness=25)
        self.device.set_color(RGBMode.Solid, Color(0, 255, 0))
        self.assertEqual(self.read("effect"), "monocolor")
        self.assertEqual(self.read("brightness"), "100")
        self.assertEqual(self.read("multi_intensity"), "0 100 0")

    def test_classic_preset_brightness(self):
        self.device.set_color(RGBMode.OXP_CLASSIC, Color(255, 255, 255), brightness=50)
        self.assertEqual(self.read("effect"), "monocolor")
        self.assertEqual(self.read("multi_intensity"), "36 9 0")

    def test_color_order_and_unequal_channel_maxima(self):
        (self.path / "multi_index").write_text("blue red green\n")
        (self.path / "multi_max_intensity").write_text("255 100 200\n")
        self.device.resume()
        self.device.set_color(RGBMode.Solid, Color(255, 128, 64))
        self.assertEqual(self.read("multi_intensity"), "64 100 100")

    def test_no_multi_max_intensity_uses_kernel_maximum(self):
        (self.path / "multi_max_intensity").unlink()
        (self.path / "max_brightness").write_text("255\n")
        self.device.resume()
        self.device.set_color(RGBMode.Solid, Color(12, 34, 56))
        self.assertEqual(self.read("multi_intensity"), "12 34 56")
        self.assertEqual(self.read("brightness"), "255")

    def test_only_advertises_present_presets(self):
        (self.path / "effect_index").write_text("monocolor neon\n")
        self.device.resume()
        modes = self.device.get_mode_capabilities()
        self.assertIn(RGBMode.OXP_NEON, modes)
        self.assertNotIn(RGBMode.OXP_AURORA, modes)
        with self.assertRaises(ValueError):
            self.device.set_color(RGBMode.OXP_AURORA, Color(0, 0, 0))

    def test_software_frames_do_not_rewrite_static_attributes(self):
        self.device._set_solid_color(Color(255, 0, 0))
        with patch.object(Path, "write_text", autospec=True, wraps=Path.write_text) as write:
            self.device._set_solid_color(Color(0, 255, 0))
            self.assertEqual([call.args[0].name for call in write.call_args_list], ["multi_intensity"])

    def test_resume_reapplies_state_changed_by_firmware(self):
        self.device._set_solid_color(Color(255, 0, 0))
        (self.path / "effect").write_text("aurora\n")
        (self.path / "enabled").write_text("false\n")
        self.device.resume()
        self.device._set_solid_color(Color(255, 0, 0))
        self.assertEqual(self.read("effect"), "monocolor")
        self.assertEqual(self.read("enabled"), "true")

    def test_missing_interface_fails_without_generic_hid_fallback(self):
        (self.path / "effect").unlink()
        with self.assertRaisesRegex(RuntimeError, "requires the hid-oxp"):
            self.device.set_color(RGBMode.Solid, Color(255, 0, 0))
        self.assertFalse(self.device.supports_software_fallback)

    def test_write_failure_propagates(self):
        with patch.object(Path, "write_text", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                self.device.set_color(RGBMode.Solid, Color(255, 0, 0))
        self.assertEqual(self.device._cache, {})

    def test_dmi_selection_is_specific(self):
        self.assertTrue(self.device.matches_dmi("ONE-NETBOOK", "ONEXPLAYER 3"))
        self.assertFalse(self.device.matches_dmi("ONE-NETBOOK", "ONEXPLAYER X1"))
        self.assertFalse(self.device.matches_dmi("OTHER", "ONEXPLAYER 3"))

    def test_only_one_zone_and_no_power_suspend_custom_controls(self):
        caps = self.device.get_device_capabilities()
        self.assertEqual(len(caps["zones"]), 1)
        self.assertFalse(caps["power_led"])
        self.assertFalse(caps["suspend_mode"])
        self.assertFalse(caps["custom_rgb"])


if __name__ == "__main__":
    unittest.main()
