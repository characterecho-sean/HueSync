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
  - ONEXPLAYER 3 (Gen3 `hid-oxp` DKMS update; five-zone hardware testing pending)
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

The original test using the stock `oxp:rgb:joystick_rings` interface failed on
hardware: HueSync accepted changes, but the LEDs did not change. The installed
CachyOS `7.2.9-1-cachyos-deckify` driver uses the older RGB protocol and does not
expose this model's auxiliary zones.

This fork includes a corrected `hid-oxp` DKMS driver in
[`kernel/hid-oxp`](kernel/hid-oxp/README.md). It uses the published Gen3 driver
fixes and the OXP3 zone addresses from OneXConsole. HueSync exposes five
independent color, saturation, brightness and on/off controls:

| HueSync area | Firmware zone | Kernel LED name |
| --- | --- | --- |
| Left joystick (primary effect controls) | 1 | `oxp:rgb:left_joystick` |
| Right joystick | 2 | `oxp:rgb:right_joystick` |
| G button | 5 | `oxp:rgb:guide_button` |
| Top lighting | 6 | `oxp:rgb:top` |
| Controller connector | 7 | `oxp:rgb:controller_connector` |

The mode selector applies to the left joystick. Other zones retain their own
solid colors while the primary runs a software effect or a OneX preset. All
zones turn off with the main lighting switch; individual choices are restored
when it is turned back on. HSV brightness is applied once. Native preset
brightness is limited to firmware steps. Software effects have a low refresh
rate because the reviewed HID transport waits 200 ms between commands; use
native presets for smooth firmware animations. Extra zones are saved per profile,
including separate AC/battery profiles. A custom animation editor is not
exposed for this device.

The backend requires all five corrected LED interfaces and reports a driver
update dependency if only the old aggregate interface exists. It never uses
legacy OneX HID initialization or writes EC registers. The kernel driver
includes the reviewed controller lifecycle/acknowledgment fixes required by
the Gen3 RGB implementation; its source and local delta are provided for review.

For a local build and installation from this fork (DKMS, GCC and matching
kernel headers must already be installed):

```bash
git submodule update --init --recursive
pnpm install --frozen-lockfile
pnpm test
pnpm build
sudo bash scripts/install_onexplayer3_test.sh
# Reboot through the Steam/KDE power menu.
```

The installer stages the DKMS driver, rebuilds the initramfs, installs the local
HueSync build and restarts Decky. It requires an ONEXPLAYER 3 and retains any
previous plugin under `/var/lib/huesync-test/`. It does not unload or rebind the
live HID driver. Reboot to activate the new kernel module; HueSync cannot use
the five-zone backend before that reboot.

Software tests and a module build with extra compiler warnings pass on
`7.2.9-1-cachyos-deckify`. **The corrected implementation still needs physical
validation on this device.** After reboot, check red/green/blue and low/high
brightness on each zone, individual off/on, and the global switch. Test a
primary native preset and speed, suspend/resume, and the drawer/keyboard
buttons. Sysfs read-back alone is not proof of a physical LED change.

To remove the replacement kernel module, run
`sudo bash scripts/uninstall_onexplayer3_rgb_driver.sh` and reboot. Restore the
previous HueSync plugin from the printed backup path if needed.

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
