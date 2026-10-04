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

from devices.onexplayer3 import OneXPlayer3LEDDevice, OXP3_EFFECTS, OXP3_ZONES
from utils import Color, RGBMode


class OneXPlayer3Tests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "oxp:rgb:left_joystick"
        attrs = {"brightness": "100", "max_brightness": "100",
                 "multi_intensity": "36 34 153", "multi_max_intensity": "100 100 100",
                 "multi_index": "red green blue", "enabled": "true", "effect": "unknown",
                 "effect_index": "monocolor " + " ".join(OXP3_EFFECTS.values()),
                 "speed": "5", "speed_range": "0-9"}
        for name, _ in OXP3_ZONES.values():
            path = self.root / ("oxp:rgb:" + name)
            path.mkdir()
            for attr, value in attrs.items():
                if name in ("guide_button", "top") and attr in ("enabled", "speed", "speed_range"):
                    continue
                (path / attr).write_text(value + "\n")
        patcher = patch("devices.onexplayer3.OXP3_LED_ROOT", str(self.root))
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
        with self.assertRaisesRegex(RuntimeError, "requires the Gen3"):
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

    def test_five_zones_and_no_power_suspend_custom_controls(self):
        caps = self.device.get_device_capabilities()
        self.assertEqual(len(caps["zones"]), 5)
        self.assertFalse(caps["power_led"])
        self.assertFalse(caps["suspend_mode"])
        self.assertFalse(caps["custom_rgb"])

    def test_independent_colors_and_disabled_zones(self):
        self.device.set_color(RGBMode.Solid, Color(255, 0, 0),
            zone_colors={"right_joystick": Color(0, 255, 0), "top": Color(0, 0, 255)},
            zone_enabled={"guide_button": False})
        self.assertEqual(self.read("multi_intensity"), "100 0 0")
        self.assertEqual((self.root / "oxp:rgb:right_joystick/multi_intensity").read_text().strip(), "0 100 0")
        self.assertEqual((self.root / "oxp:rgb:top/multi_intensity").read_text().strip(), "0 0 100")
        self.assertEqual((self.root / "oxp:rgb:guide_button/brightness").read_text().strip(), "0")

    def test_global_off_and_reenable_preserves_zone_choices(self):
        self.device.set_color(RGBMode.Solid, Color(255, 0, 0), zone_colors={"top": Color(0, 0, 255)})
        self.device.set_color(RGBMode.Disabled, Color(0, 0, 0))
        for name, _ in OXP3_ZONES.values():
            self.assertEqual((self.root / ("oxp:rgb:" + name) / "brightness").read_text().strip(), "0")
        self.device.set_color(RGBMode.Solid, Color(255, 0, 0))
        self.assertEqual((self.root / "oxp:rgb:top/multi_intensity").read_text().strip(), "0 0 100")
        self.assertEqual((self.root / "oxp:rgb:top/brightness").read_text().strip(), "100")

    def test_missing_named_zone_and_unknown_id_are_rejected(self):
        with self.assertRaises(ValueError):
            self.device.set_color(RGBMode.Solid, Color(255, 0, 0), zone_colors={"made_up": Color(0, 0, 0)})
        (self.root / "oxp:rgb:top/effect").unlink()
        self.device.resume()
        with self.assertRaisesRegex(RuntimeError, "Missing Gen3 RGB zone"):
            self.device.set_color(RGBMode.Solid, Color(255, 0, 0))

    def test_software_primary_frame_does_not_change_other_zones(self):
        self.device.set_color(RGBMode.Solid, Color(255, 0, 0), zone_colors={"top": Color(0, 0, 255)})
        self.device._set_solid_color(Color(0, 255, 0))
        self.assertEqual((self.root / "oxp:rgb:top/multi_intensity").read_text().strip(), "0 0 100")

    def test_old_aggregate_interface_is_not_treated_as_working(self):
        self.path.rename(self.root / "oxp:rgb:joystick_rings")
        with self.assertRaisesRegex(RuntimeError, "Gen3"):
            OneXPlayer3LEDDevice()

    def test_primary_slider_update_does_not_resend_unchanged_other_zones(self):
        colors = {zone: Color(0, 0, 255) for zone in OXP3_ZONES if zone != "primary"}
        self.device.set_color(RGBMode.Solid, Color(255, 0, 0), zone_colors=colors)
        with patch.object(Path, "write_text", autospec=True, wraps=Path.write_text) as write:
            self.device.set_color(RGBMode.Solid, Color(64, 64, 64), zone_colors=colors)
            paths = [call.args[0] for call in write.call_args_list]
            self.assertEqual(paths, [self.path / "multi_intensity"])

    def test_identical_profile_does_not_write_but_init_replays(self):
        self.device.set_color(RGBMode.Solid, Color(255, 0, 0))
        with patch.object(Path, "write_text", autospec=True, wraps=Path.write_text) as write:
            self.device.set_color(RGBMode.Solid, Color(255, 0, 0))
            self.assertEqual(write.call_count, 0)
            self.device.set_color(RGBMode.Solid, Color(255, 0, 0), init=True)
            self.assertGreater(write.call_count, 0)

    def test_zero_brightness_and_off_write_black_to_every_zone(self):
        self.device.set_color(RGBMode.Solid, Color(255, 0, 0))
        self.device.set_color(RGBMode.Disabled, Color(255, 0, 0))
        for name, _ in OXP3_ZONES.values():
            path = self.root / ("oxp:rgb:" + name)
            self.assertEqual((path / "multi_intensity").read_text().strip(), "0 0 0")
            self.assertEqual((path / "brightness").read_text().strip(), "0")
        self.device.set_color(RGBMode.Solid, Color(64, 64, 64))
        self.assertEqual(self.read("multi_intensity"), "25 25 25")
        self.assertEqual(self.read("brightness"), "100")
        self.assertEqual(self.read("enabled"), "true")

    def test_current_kernel_ranges_keep_low_brightness_unsaturated_white(self):
        for name, _ in OXP3_ZONES.values():
            (self.root / ("oxp:rgb:" + name) / "multi_max_intensity").write_text("255 255 255\n")
        self.device.resume()
        colors = {zone: Color(64, 64, 64) for zone in OXP3_ZONES if zone != "primary"}
        self.device.set_color(RGBMode.Solid, Color(64, 64, 64), zone_colors=colors, brightness=25)
        for name, _ in OXP3_ZONES.values():
            path = self.root / ("oxp:rgb:" + name)
            self.assertEqual((path / "multi_intensity").read_text().strip(), "64 64 64")
            self.assertEqual((path / "brightness").read_text().strip(), "100")


if __name__ == "__main__":
    unittest.main()
