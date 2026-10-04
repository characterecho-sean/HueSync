"""ONEXPLAYER 3 Gen3 RGB zones through the corrected hid-oxp LED ABI."""
from pathlib import Path
import threading

from utils import Color, RGBMode, RGBModeCapabilities

from .generic import GenericLEDDevice

OXP3_LED_ROOT = "/sys/class/leds"
OXP3_ZONES = {
    "primary": ("left_joystick", "Left joystick"),
    "right_joystick": ("right_joystick", "Right joystick"),
    "guide_button": ("guide_button", "G button"),
    "top": ("top", "Top lighting"),
    "controller_connector": ("controller_connector", "Controller connector"),
}
OXP3_EFFECTS = {
    RGBMode.OXP_MONSTER_WOKE: "monster_woke",
    RGBMode.OXP_FLOWING: "flowing_light",
    RGBMode.OXP_SUNSET: "sunset_afterglow",
    RGBMode.OXP_NEON: "neon",
    RGBMode.OXP_DREAMY: "dreamy",
    RGBMode.OXP_CYBERPUNK: "cyberpunk",
    RGBMode.OXP_COLORFUL: "colorful",
    RGBMode.OXP_AURORA: "aurora",
    RGBMode.OXP_SUN: "warm_sun",
}


class OneXPlayer3LEDDevice(GenericLEDDevice):
    REQUIRED = ("brightness", "max_brightness", "multi_intensity", "multi_index",
                "enabled", "effect", "effect_index", "speed", "speed_range")

    def __init__(self):
        # GenericLEDDevice calls our exact-path detector, avoiding unrelated LEDs.
        super().__init__()
        self._lock = threading.RLock()
        self._cache = {}
        self._identity = None
        self._require_interface()
        self._zone_colors = {}
        self._zone_enabled = {}

    @staticmethod
    def matches_dmi(vendor, product):
        return vendor in ("ONE-NETBOOK", "ONE-NETBOOK TECHNOLOGY CO., LTD.") and product == "ONEXPLAYER 3"

    def _detect_sysfs_led_path(self):
        path = Path(OXP3_LED_ROOT) / "oxp:rgb:left_joystick"
        self._sysfs_led_path = str(path) if all((path / attr).is_file() for attr in self.REQUIRED) else None
        return self._sysfs_led_path

    def _read(self, attr):
        return (Path(self._sysfs_led_path) / attr).read_text().strip()

    def _require_interface(self):
        if not self._detect_sysfs_led_path():
            raise RuntimeError("ONEXPLAYER 3 RGB requires the Gen3 hid-oxp update; install kernel/hid-oxp and reboot")
        stat = Path(self._sysfs_led_path).stat()
        identity = (stat.st_dev, stat.st_ino)
        if identity == self._identity:
            return
        self._cache.clear()
        self._zones = {}
        for zone, (name, _) in OXP3_ZONES.items():
            path = Path(OXP3_LED_ROOT) / ("oxp:rgb:" + name)
            attrs = self.REQUIRED if zone in ("primary", "right_joystick", "controller_connector") else ("brightness", "max_brightness", "multi_intensity", "multi_index", "effect", "effect_index")
            if not all((path / attr).is_file() for attr in attrs):
                raise RuntimeError(f"Missing Gen3 RGB zone: {name}; install the driver update and reboot")
            self._zones[zone] = path
        self._channels = self._read("multi_index").split()
        if len(self._channels) != 3 or set(self._channels) != {"red", "green", "blue"}:
            raise RuntimeError("Unexpected oxp RGB channel layout")
        self._maximum = int(self._read("max_brightness"))
        maxima_path = Path(self._sysfs_led_path) / "multi_max_intensity"
        self._maxima = ([int(v) for v in maxima_path.read_text().split()] if maxima_path.exists()
                        else [self._maximum] * 3)
        if self._maximum <= 0 or len(self._maxima) != 3 or any(v <= 0 for v in self._maxima):
            raise RuntimeError("Invalid oxp RGB brightness/intensity range")
        self._speed_min, self._speed_max = map(int, self._read("speed_range").split("-"))
        if not 0 <= self._speed_min <= self._speed_max:
            raise RuntimeError("Invalid oxp RGB speed range")
        self._effects = set(self._read("effect_index").split())
        if "monocolor" not in self._effects:
            raise RuntimeError("oxp RGB interface lacks monocolor support")
        self._identity = identity

    def _write(self, attr, value):
        value = str(value)
        if self._cache.get(attr) == value:
            return
        try:
            (Path(self._sysfs_led_path) / attr).write_text(value + "\n")
        except OSError:
            self._cache.clear()
            raise
        self._cache[attr] = value

    def _set_zone_solid(self, zone, color, enabled=True):
        path = self._zones[zone]
        maximum = int((path / "max_brightness").read_text())
        channels = (path / "multi_index").read_text().split()
        if len(channels) != 3 or set(channels) != {"red", "green", "blue"}:
            raise RuntimeError(f"Unexpected RGB channel layout in {zone}")
        maxima_path = path / "multi_max_intensity"
        maxima = list(map(int, maxima_path.read_text().split())) if maxima_path.exists() else [maximum] * 3
        if maximum <= 0 or len(maxima) != 3 or any(v <= 0 for v in maxima):
            raise RuntimeError(f"Invalid RGB ranges in {zone}")
        values = {"red": color.R, "green": color.G, "blue": color.B}
        intensity = " ".join(str(round(values[name] * limit / 255)) for name, limit in zip(channels, maxima))
        on = enabled and any(values.values())
        writes = [("multi_intensity", intensity), ("brightness", maximum if on else 0), ("effect", "monocolor")]
        if (path / "enabled").exists():
            writes.append(("enabled", "true" if on else "false"))
        for attr, value in writes:
            key = (zone, attr)
            if self._cache.get(key) == str(value):
                continue
            try:
                (path / attr).write_text(str(value) + "\n")
            except OSError:
                self._cache.clear()
                raise
            self._cache[key] = str(value)

    @property
    def supports_software_fallback(self):
        # A failed kernel write must reach the plugin, never silently use raw HID.
        return False

    @property
    def hardware_supported_modes(self):
        self._require_interface()
        return [RGBMode.Disabled, RGBMode.Solid, RGBMode.OXP_CLASSIC] + [
            mode for mode, effect in OXP3_EFFECTS.items() if effect in self._effects]

    def _set_solid_color(self, color):
        with self._lock:
            self._require_interface()
            self._set_zone_solid("primary", color)
            self._current_color = color

    def _set_hardware_color(self, mode=None, color=None, color2=None, init=False,
                            brightness=None, speed=None, **kwargs):
        with self._lock:
            self._require_interface()
            # Replay complete settings on a UI/native transaction or resume.
            self._cache.clear()
            if mode == RGBMode.Disabled:
                self._write("brightness", 0)
                self._write("enabled", "false")
            elif mode == RGBMode.Solid:
                self._set_solid_color(color)
            elif mode == RGBMode.OXP_CLASSIC:
                percent = 100 if brightness is None else max(0, min(100, brightness))
                self._set_solid_color(Color(*(round(v * percent / 100) for v in (183, 48, 0))))
            else:
                effect = OXP3_EFFECTS.get(mode)
                if effect not in self._effects:
                    raise ValueError(f"Unsupported ONEXPLAYER 3 hardware effect: {mode}")
                percent = 100 if brightness is None else max(0, min(100, brightness))
                fraction = {"low": 0, "medium": .5, "high": 1}.get(speed or "medium", .5)
                self._write("brightness", round(self._maximum * percent / 100))
                self._write("effect", effect)
                self._write("speed", round(self._speed_min + fraction * (self._speed_max - self._speed_min)))
                self._write("enabled", "true" if percent > 0 else "false")
            self._current_mode = mode

    def set_color(self, *args, zone_colors=None, zone_enabled=None, **kwargs):
        self._require_interface()
        mode = kwargs.get("mode", args[0] if args else None) or self._current_mode
        if mode in OXP3_EFFECTS and OXP3_EFFECTS[mode] not in self._effects:
            raise ValueError(f"Unsupported ONEXPLAYER 3 hardware effect: {mode}")
        unknown = (set(zone_colors or {}) | set(zone_enabled or {})) - set(OXP3_ZONES)
        if unknown:
            raise ValueError(f"Unknown ONEXPLAYER 3 RGB zones: {sorted(unknown)}")
        self.stop_effects()
        with self._lock:
            self._cache.clear()
            self._zone_colors.update(zone_colors or {})
            self._zone_enabled.update(zone_enabled or {})
            for zone in OXP3_ZONES:
                if zone == "primary":
                    continue
                # Unconfigured zones follow the requested main color on first use.
                color = self._zone_colors.get(zone, kwargs.get("color", args[1] if len(args) > 1 else None))
                if mode == RGBMode.Disabled:
                    self._set_zone_solid(zone, Color(0, 0, 0), enabled=False)
                elif color is not None:
                    self._set_zone_solid(zone, color, enabled=self._zone_enabled.get(zone, True))
        return super().set_color(*args, **kwargs)

    def get_mode_capabilities(self):
        capabilities = super().get_mode_capabilities()
        for mode in self.hardware_supported_modes:
            if mode in OXP3_EFFECTS or mode == RGBMode.OXP_CLASSIC:
                capabilities[mode] = RGBModeCapabilities(mode=mode, color=False,
                    brightness=True, speed=mode in OXP3_EFFECTS)
        for capability in capabilities.values():
            capability.zones = list(OXP3_ZONES)
        return capabilities

    def get_device_capabilities(self):
        return {"zones": [{"id": zone, "name_key": "ZONE_PRIMARY_NAME", "name": label}
                          for zone, (_, label) in OXP3_ZONES.items()],
                "power_led": False, "suspend_mode": False, "custom_rgb": False}

    def suspend(self, settings=None):
        self.stop_effects()
        with self._lock:
            self._cache.clear()

    def resume(self, settings=None):
        # HueSync reapplies the selected profile after resume; don't trust old writes.
        with self._lock:
            self._identity = None
            self._cache.clear()
