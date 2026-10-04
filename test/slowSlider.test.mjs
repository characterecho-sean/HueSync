import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const url = source => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const react = url(`export function useRef(value) {
  const hooks = globalThis.sliderHooks;
  return hooks.refs[hooks.refIndex++] ??= { current: value };
}
export function useEffect(callback) {
  const hooks = globalThis.sliderHooks;
  if (!hooks.mounted) hooks.cleanups.push(callback());
}`);
const decky = url(`export const SliderField = "SliderField";`);
const source = await readFile(new URL("../src/components/SlowSliderField.tsx", import.meta.url), "utf8");
let { outputText } = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020,
  jsx: ts.JsxEmit.React, jsxFactory: "globalThis.sliderElement",
} });
outputText = outputText.replace('"react"', JSON.stringify(react)).replace('"@decky/ui"', JSON.stringify(decky));
const { SlowSliderField } = await import(url(outputText));

function withSlider(run) {
  const originalSet = globalThis.setTimeout, originalClear = globalThis.clearTimeout;
  const timers = new Map();
  let timer = 0;
  globalThis.setTimeout = callback => { timers.set(++timer, callback); return timer; };
  globalThis.clearTimeout = id => timers.delete(id);
  globalThis.sliderHooks = { refs: [], refIndex: 0, cleanups: [], mounted: false };
  globalThis.sliderElement = (type, props) => ({ type, props });
  const render = props => {
    sliderHooks.refIndex = 0;
    const component = SlowSliderField(Object.freeze(props));
    sliderHooks.mounted = true;
    return component.props;
  };
  const flush = () => { const pending = [...timers.values()]; timers.clear(); pending.forEach(callback => callback()); };
  const unmount = () => sliderHooks.cleanups.forEach(cleanup => cleanup?.());
  try { run({ render, flush, unmount, timers }); }
  finally { globalThis.setTimeout = originalSet; globalThis.clearTimeout = originalClear; }
}

test("opening RGB controls never commits their initial values", () => withSlider(({ render, flush }) => {
  const changes = [];
  render({ value: 84, onChangeEnd: value => changes.push(value) });
  flush();
  assert.deepEqual(changes, []);
}));

test("rapid slider input commits only the latest value with the latest HSV callback", () => withSlider(({ render, flush }) => {
  const previews = [], commits = [];
  const slider = render({ value: 84, onChange: value => previews.push(value), onChangeEnd: () => { throw Error("stale callback"); } });
  slider.onChange(70); slider.onChange(50); slider.onChange(0);
  render({ value: 0, onChangeEnd: value => commits.push({ saturation: value, brightness: 25 }) });
  flush();
  assert.deepEqual(previews, [70, 50, 0]);
  assert.deepEqual(commits, [{ saturation: 0, brightness: 25 }]);
}));

test("closing the panel cancels an outstanding slider commit", () => withSlider(({ render, unmount, flush }) => {
  const commits = [];
  render({ value: 100, onChangeEnd: value => commits.push(value) }).onChange(10);
  unmount(); flush();
  assert.deepEqual(commits, []);
}));
