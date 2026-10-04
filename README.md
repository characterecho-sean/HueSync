English | [简体中文](./README_cn.md)
# HueSync
[![](https://img.shields.io/github/downloads/honjow/HueSync/total.svg)](https://gitHub.com/honjow/HueSync/releases) [![](https://img.shields.io/github/downloads/honjow/HueSync/latest/total)](https://github.com/honjow/HueSync/releases/latest) [![](https://img.shields.io/github/v/release/honjow/HueSync)](https://github.com/honjow/HueSync/releases/latest)

Plugin for [decky-loader](https://github.com/SteamDeckHomebrew/decky-loader)

LED controller for handheld devices

|                           |
| ------------------------- |
| ![](./screenshot/HueSync.jpg) |

## Supported Devices
### Directly Supported
- AYANEO
  - AIR/Pro/1S
  - 2/2S
  - GEEK/1S
- GPD
  - Win 4 (Support by [pyWinControls](https://github.com/pelrun/pyWinControls))
- OneXPlayer
  - OneXFly
  - X1
  - ONEXPLAYER 3 (kernel `hid-oxp` RGB interface; hardware testing pending)
- Aokzoe
  - A1
  - A2
- ROG
  - Ally/X
  - Xbox Ally/X
- MSI
  - Claw
  - Claw 8
  - Claw 7
- Lenovo
  - Legion Go S
  - Legion Go/2

### Additional Support
Support for more Ayaneo devices through [ayaneo-platform](https://github.com/ShadowBlip/ayaneo-platform), can be obtained by installing the dkms module through [AUR](https://aur.archlinux.org/packages/ayaneo-platform-dkms-git). The latest ChimeraOS comes with it.

- AYANEO
  - AIR/Pro/1S
  - 2/2S
  - GEEK/1S
  - AIR Plus
  - SLIDE

Similarly, Support for Ayn devices through [ayn-platform](https://github.com/ShadowBlip/ayn-platform),  [AUR](https://aur.archlinux.org/packages/ayn-platform-dkms-git)
- AYN
  - Loki Max

## Custom RGB Effects

### ONEXPLAYER 3

ONEXPLAYER 3 uses `/sys/class/leds/oxp:rgb:joystick_rings` from the kernel's
`hid-oxp` driver. HueSync controls both joystick rings as one primary zone:
solid color, off, numeric brightness, software effects and the OneX hardware
presets listed by the driver. Native presets also support animation speed.
The backend reads channel order and value ranges from sysfs and uses the
existing HueSync controls. Hardware preset brightness may change in steps,
depending on the controller firmware.

This model never falls back to generic OneX HID initialization, which can
rewrite button mappings. If the required kernel RGB interface is missing,
HueSync reports that dependency instead. It does not add EC, button mapping,
rumble, power LED or per-ring controls. Custom multizone editing and auxiliary
LEDs are not exposed on this kernel.

The interface was inspected on an ONEXPLAYER 3 running CachyOS kernel
`7.2.3-3-cachyos-deckify`: RGB order `red green blue`, brightness/intensity
maxima `100`, speed range `0-9`, and the OneX presets including `monocolor`.
Software checks cover this layout, reordered channels, different ranges,
brightness zero, failures and reconnection. Physical RGB behavior is pending
testing with the built plugin.

For a local test build from this fork:

```bash
git submodule update --init --recursive
pnpm install --frozen-lockfile
pnpm test
pnpm build
sudo bash scripts/install_onexplayer3_test.sh
```

The test installer copies the local build into your Decky plugin directory,
retains any previous HueSync plugin under `/var/lib/huesync-test/`, and restarts
Decky. It leaves other plugins and user settings intact. In Gaming Mode, enable
RGB control in HueSync and check red/green/blue, brightness, off/on, native
presets and speed. Confirm the drawer and keyboard buttons still work, then
check color restoration after suspend/resume. Sysfs read-back alone is not
proof of a physical LED change; report the observed colors/effects.

Some devices support advanced custom RGB effects with multi-frame animations and individual zone color control.

### Supported Devices

- **MSI Claw Series** - Hardware-accelerated for smoother animations
- **ASUS ROG Ally / Ally X** - Software animation engine
- **AYANEO Devices** - Software animation engine

These devices have commands to set individual LED zone colors, which makes custom effects possible. MSI devices use hardware animation interface, while ROG Ally and AYANEO use software algorithms to smoothly interpolate between keyframes.

### Editor Interfaces

**MSI Claw**  
![MSI Custom Editor](./screenshot/msi_custom_editor.png)

**ASUS ROG Ally**  
![Ally Custom Editor](./screenshot/ally_custom_editor.png)

**AYANEO**  
![AyaNeo Custom Editor](./screenshot/ayaneo_custom_editor.png)

## One-step Installation
```
curl -L https://raw.githubusercontent.com/honjow/huesync/main/install.sh | sh
```
