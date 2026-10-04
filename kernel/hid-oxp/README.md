# ONEXPLAYER 3 Gen3 HID driver

This standalone GPL-2.0-or-later driver replaces `hid-oxp` through DKMS.
HueSync's BSD license does not apply to this kernel directory.

## Provenance

- Upstream base: https://github.com/torvalds/linux/blob/master/drivers/hid/hid-oxp.c
  Retrieved 2026-10-04; SHA-256 `0d33ecddcfc58c486361cf7d33187c7c34499c8903d3d574b4f6a4916ebdd855`.
- Andrei Aldea's reviewed 15-patch series, September 10, 2026:
  https://lore-kernel.gnuweeb.org/linux-input/20260910032115.28669-1-andrei1998%40gmail.com/
  Downloaded thread mbox.gz SHA-256 `74679f058fe0b819b32565d1a71268683ccb714ec83863cd8b36d1836a3db37f`.
  The signed patches are attributed to Andrei Aldea and reviewed by Derek J. Clark.
- The base already used `cancel_delayed_work_sync` in remove; patch 08 was
  adapted only for that existing spelling. All 15 source patches applied.
- Gen3 protocol: https://lists.openwall.net/linux-kernel/2026/09/10/269
- Auxiliary zones: https://lkml.iu.edu/2609.1/06237.html

The local changes after that series are recorded verbatim in
`onexplayer3-zones.patch`: separate left/right/connector ring devices, per-zone
status routing, preserve the selected effect/speed during queued brightness
updates, prevent continuous color frames from indefinitely delaying output,
ignore late/unmatched RGB acknowledgments as reset signals, label zone 6 as Top according to OneXConsole's OXP3 configuration,
and add module version 0.1.0. `hid-ids.h` contains only the four upstream IDs
needed for standalone compilation.

OneXConsole's OXP3 `rgbPartitionList`, from the previously extracted
`onex_reverse/extracted/background.js`, identifies addresses 1 (left stick),
2 (right stick), 5 (G key), 6 (Top), and 7 (Controller Connector). No zone
addresses beyond that list are probed. The reviewed patch's `rear_logo` name
for address 6 is replaced with the vendor's `top` name.

## Protocol and lifecycle

Gen3 uses 64-byte B8/3f/01 output reports, explicitly addressed zones, and a
59-byte solid-color payload (18 RGB triplets plus the final red/green bytes).
RGB writes require a matching command/zone acknowledgment and retry once.
Configuration lives on the matched vendor interface 2. Pending work is
quiesced on suspend/removal and valid RGB state is restored on resume.
The series also supplies X2-family three-page button-map and controller
initialization fixes; the complete driver changes should be reviewed together.

The legacy aggregate LED remains for older supported controllers. The installer
is restricted to exact ONEXPLAYER 3 DMI; X2 Mini Pro is not tested here.

## Build, installation and recovery

```bash
make -C /lib/modules/$(uname -r)/build M="$PWD" W=1 modules
sudo bash ../../scripts/install_onexplayer3_rgb_driver.sh
```

Use the repository's test installer to stage both HueSync and the driver.
Installation leaves the live driver bound. **Reboot is required.** Rebuilding
the initramfs ensures the replacement is used even if the driver loads early.
Module build validation: `7.2.9-1-cachyos-deckify`, GCC 16.2.1, `W=1`.
Physical RGB/controller validation remains pending.

```bash
modinfo -F version hid_oxp
ls /sys/class/leds/oxp:rgb:*
sudo journalctl -k -b --grep='hid-oxp|RGB' --no-pager
```

Expected module version: 0.1.0; five named LED devices. Kernel log errors or
sysfs success cannot replace observing the physical LEDs.

Rollback without live driver removal:

```bash
sudo bash ../../scripts/uninstall_onexplayer3_rgb_driver.sh
# Reboot to return to the stock kernel driver.
```

DKMS restores the stock driver from its saved original module. Plugin backup
paths are printed by `install_onexplayer3_test.sh` and live outside Decky's
watched plugin directory.
