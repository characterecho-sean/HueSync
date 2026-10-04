import { hsvToRgb } from "./rgb";

export interface ZoneSetting {
  hue: number;
  saturation: number;
  brightness: number;
  enabled: boolean;
}

export const defaultZoneSetting: ZoneSetting = { hue: 0, saturation: 100, brightness: 100, enabled: true };

export function copyZoneSettings(zones: Record<string, ZoneSetting> = {}): Record<string, ZoneSetting> {
  return Object.fromEntries(Object.entries(zones).map(([id, setting]) => [id, { ...setting }]));
}

export function zoneSettingsToColors(ids: string[], settings: Record<string, ZoneSetting>) {
  const colors: Record<string, { r: number; g: number; b: number }> = {};
  const enabled: Record<string, boolean> = {};
  for (const id of ids) {
    const setting = settings[id] ?? defaultZoneSetting;
    const [r, g, b] = hsvToRgb(setting.hue, setting.saturation, setting.brightness);
    colors[id] = { r, g, b };
    enabled[id] = setting.enabled;
  }
  return { colors, enabled };
}
