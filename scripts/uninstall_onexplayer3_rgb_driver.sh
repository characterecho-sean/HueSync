#!/usr/bin/env bash
set -euo pipefail
(( EUID == 0 )) || { echo 'Run with sudo' >&2; exit 1; }
(( $# == 0 )) || { echo 'Usage: uninstall_onexplayer3_rgb_driver.sh' >&2; exit 1; }
dkms remove -m oxp3-hid-rgb -v 0.1.0 --all
depmod -a
if command -v mkinitcpio >/dev/null; then
    mkinitcpio -P
elif command -v dracut >/dev/null; then
    dracut --regenerate-all --force
else
    echo 'Rebuild your initramfs before rebooting' >&2; exit 1
fi
echo 'Stock hid-oxp restored for the next boot. Reboot to activate it.'
echo 'HueSync five-zone RGB will require the corrected driver again.'
