import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

async function transpile(url) {
  const source = await readFile(url, "utf8");
  return ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
}
const rgb = `data:text/javascript;base64,${Buffer.from(await transpile(new URL("../src/util/rgb.ts", import.meta.url))).toString("base64")}`;
const source = (await transpile(new URL("../src/util/zoneSettings.ts", import.meta.url))).replace('"./rgb"', JSON.stringify(rgb));
const { copyZoneSettings, zoneSettingsToColors } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

test("zone HSV settings survive profile copies without sharing mutable state", () => {
  const settings = { top: { hue: 240, saturation: 100, brightness: 50, enabled: true } };
  const snapshot = copyZoneSettings(settings);
  settings.top.brightness = 0;
  assert.equal(snapshot.top.brightness, 50);
  assert.deepEqual(copyZoneSettings(undefined), {});
});

test("each advertised zone reaches the backend with independent brightness and enable state", () => {
  const result = zoneSettingsToColors(["right_joystick", "top", "guide_button", "controller_connector"], {
    right_joystick: { hue: 120, saturation: 100, brightness: 100, enabled: true },
    top: { hue: 240, saturation: 100, brightness: 50, enabled: true },
    guide_button: { hue: 0, saturation: 0, brightness: 25, enabled: false },
  });
  assert.deepEqual(result.colors.right_joystick, { r: 0, g: 255, b: 0 });
  assert.deepEqual(result.colors.top, { r: 0, g: 0, b: 128 });
  assert.deepEqual(result.colors.guide_button, { r: 64, g: 64, b: 64 });
  assert.equal(result.enabled.guide_button, false);
  assert.deepEqual(result.colors.controller_connector, { r: 255, g: 0, b: 0 });
  assert.equal(result.enabled.controller_connector, true);
});

test("unadvertised zone settings are not sent to a different device", () => {
  assert.deepEqual(zoneSettingsToColors([], { top: { hue: 0, saturation: 100, brightness: 100, enabled: true } }), { colors: {}, enabled: {} });
});
