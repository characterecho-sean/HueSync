import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";
const dataUrl = source => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
async function transpile(path) {
  return ts.transpileModule(await readFile(new URL(path, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
  }).outputText;
}
const rgb = dataUrl(await transpile("../src/util/rgb.ts"));
const writer = dataUrl(await transpile("../src/util/latestValueWriter.ts"));
const zones = dataUrl((await transpile("../src/util/zoneSettings.ts")).replace('"./rgb"', JSON.stringify(rgb)));
const shims = {
  "../hooks": 'export const Setting = globalThis.rgbSetting; export class SettingsData {}',
  "@decky/api": 'export const call = (...args) => globalThis.rgbCall(...args)',
  "lodash": 'export const debounce = fn => fn',
  ".": 'export const Logger = { error() {}, warn() {}, info() {} }',
  "./const": 'export const RGBMode = { disabled: "disabled", custom: "custom" }',
  "./suspendPolicy": 'export const shouldHandleSuspendResume = () => false',
  "./profilePolicy": 'export const shouldPersistHardwareState = () => true',
  "./versionCache": 'export const getVersionCache = () => null; export const setVersionCache = () => {}; export const getStaleCache = () => null',
};
const { hsvToRgb } = await import(rgb);
globalThis.rgbSetting = { enableControl: true, ledEnabled: true, mode: "solid", hue: 0, saturation: 100, brightness: 100,
  red2: 0, green2: 0, blue2: 0, speed: "low", brightnessLevel: "high", appOverWrite: () => false,
  zoneSettings: {}, deviceCapabilities: { zones: [{ id: "primary" }, { id: "top" }] } };
for (const [index, name] of ["red", "green", "blue"].entries()) Object.defineProperty(rgbSetting, name, {
  get: () => hsvToRgb(rgbSetting.hue, rgbSetting.saturation, rgbSetting.brightness)[index],
});
let source = await transpile("../src/util/backend.ts");
source = source.replace(/from (["'])(.*?)\1/g, (match, quote, specifier) => {
  const url = specifier === "./latestValueWriter" ? writer : specifier === "./zoneSettings" ? zones : shims[specifier] ? dataUrl(shims[specifier]) : null;
  if (!url) throw Error(`Unexpected backend dependency: ${specifier}`);
  return `from ${JSON.stringify(url)}`;
});
const { Backend } = await import(dataUrl(source));
const nextTurn = () => new Promise(resolve => setImmediate(resolve));

test("brightness and saturation produce matching RGB values for primary and named zones", async () => {
  const calls = [];
  globalThis.rgbCall = async (...args) => { calls.push(args); return true; };
  rgbSetting.hue = 0; rgbSetting.saturation = 0; rgbSetting.brightness = 25;
  rgbSetting.zoneSettings = { top: { hue: 240, saturation: 0, brightness: 25, enabled: true } };
  Backend.applySettings();
  await Backend.colorWriter.flush();
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].slice(1, 5), ["solid", 64, 64, 64]);
  assert.deepEqual(calls[0][12], { top: { R: 64, G: 64, B: 64 } });
});

test("off replaces pending slider colors and is the last hardware request", async () => {
  const calls = [], gates = [];
  globalThis.rgbCall = (...args) => { calls.push(args); return new Promise(resolve => gates.push(resolve)); };
  Backend.applySettings(); await nextTurn();
  rgbSetting.brightness = 10; Backend.applySettings();
  rgbSetting.saturation = 100; Backend.applySettings();
  rgbSetting.enableControl = false;
  const off = Backend.turnOffLeds();
  // Delayed ordinary settings must not reenable RGB after control is disabled.
  Backend.applySettings();
  assert.equal(calls.length, 1);
  gates[0](true); await nextTurn();
  assert.equal(calls.length, 2);
  assert.equal(calls[1][1], "disabled");
  gates[1](true); await off;
  assert.equal(calls.length, 2);
});
