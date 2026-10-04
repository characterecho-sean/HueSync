#!/usr/bin/env bash
# Install this local HueSync build, keeping any existing plugin for recovery.
set -euo pipefail
if (( EUID != 0 )); then echo 'Run with sudo: install_onexplayer3_test.sh'; exit 1; fi
if (( $# )); then echo 'Usage: install_onexplayer3_test.sh'; exit 1; fi
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $(cat /sys/class/dmi/id/product_name) != 'ONEXPLAYER 3' ]] ||
   [[ $(cat /sys/class/dmi/id/sys_vendor) != 'ONE-NETBOOK' ]]; then
    echo 'This test installer targets the evaluated ONEXPLAYER 3' >&2; exit 1
fi
for file in dist/index.js main.py plugin.json package.json py_modules/lib_hid/__init__.py py_modules/serial/__init__.py; do
    test -f "$source_dir/$file" || { echo "Incomplete local build: $file" >&2; exit 1; }
done
test -n "${SUDO_USER:-}" && test "$SUDO_USER" != root || {
    echo 'Run sudo from your desktop user account' >&2; exit 1;
}
desktop_dir=$(getent passwd "$SUDO_USER" | cut -d: -f6)
plugin_parent="$desktop_dir/homebrew/plugins"
test -d "$plugin_parent" || { echo 'Decky plugin directory not found' >&2; exit 1; }
systemctl is-active --quiet plugin_loader.service || {
    echo 'Decky plugin_loader.service is not running' >&2; exit 1;
}
plugin_dir="$plugin_parent/HueSync"
test ! -L "$plugin_dir" || { echo 'Refusing to replace a plugin symlink' >&2; exit 1; }
install -d -m 0755 /var/lib/huesync-test
work_dir=$(mktemp -d /var/lib/huesync-test/onexplayer3-XXXXXXXX)
stage="$work_dir/staged"
backup="$work_dir/HueSync.previous"
mkdir "$stage"
old_moved=false
new_moved=false
service_stopped=false
cleanup() {
    result=$?
    trap - EXIT
    if (( result != 0 )); then
        if "$new_moved"; then rm -rf -- "$plugin_dir"; fi
        if "$old_moved"; then mv -- "$backup" "$plugin_dir"; fi
        echo 'Test installation failed; previous plugin restored where available' >&2
    fi
    if "$service_stopped"; then
        systemctl start plugin_loader.service || result=1
    fi
    exit "$result"
}
trap cleanup EXIT
# Stage outside Decky's watched plugin directory and omit Git/cache metadata.
tar -C "$source_dir" --exclude=.git --exclude=__pycache__ --exclude='*.pyc' \
    -cf - dist backend py_modules main.py plugin.json package.json README.md LICENSE | tar -C "$stage" -xf -
driver_ready=false
if [[ -r /sys/module/hid_oxp/version ]] &&
   [[ $(cat /sys/module/hid_oxp/version) == 0.1.0 ]] &&
   cmp -s "$source_dir/kernel/hid-oxp/hid-oxp.c" /usr/src/oxp3-hid-rgb-0.1.0/hid-oxp.c; then
    driver_ready=true
else
    bash "$source_dir/scripts/install_onexplayer3_rgb_driver.sh"
fi
systemctl stop plugin_loader.service
service_stopped=true
if test -e "$plugin_dir"; then
    mv -- "$plugin_dir" "$backup"
    old_moved=true
fi
mv -- "$stage" "$plugin_dir"
new_moved=true
systemctl start plugin_loader.service
systemctl is-active --quiet plugin_loader.service
service_stopped=false
echo "Local ONEXPLAYER 3 HueSync build installed: $plugin_dir"
if "$old_moved"; then echo "Previous plugin saved: $backup"; fi
if "$driver_ready"; then
    echo 'Active RGB driver matches. Plugin update is ready; no reboot is needed.'
else
    echo 'Reboot, then enable HueSync RGB control in Gaming Mode and test each of the five zones.'
fi
