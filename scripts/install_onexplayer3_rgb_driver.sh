#!/usr/bin/env bash
# Stage the corrected hid-oxp for the next boot. Never unbind a live controller.
set -euo pipefail
(( EUID == 0 )) || { echo 'Run with sudo' >&2; exit 1; }
(( $# == 0 )) || { echo 'Usage: install_onexplayer3_rgb_driver.sh' >&2; exit 1; }
[[ $(cat /sys/class/dmi/id/product_name) == 'ONEXPLAYER 3' &&
   $(cat /sys/class/dmi/id/sys_vendor) == 'ONE-NETBOOK' ]] || {
    echo 'This installer targets ONEXPLAYER 3 only' >&2; exit 1;
}
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../kernel/hid-oxp" && pwd)
module=oxp3-hid-rgb
version=0.1.0
kernel=$(uname -r)
for program in dkms make gcc depmod; do
    command -v "$program" >/dev/null || { echo "Missing dependency: $program" >&2; exit 1; }
done
test -f "/lib/modules/$kernel/build/Makefile" || { echo "Install headers for $kernel" >&2; exit 1; }
# A replacement module must also be present in any initramfs that includes hid-oxp.
if command -v mkinitcpio >/dev/null; then
    initramfs_tool=mkinitcpio
elif command -v dracut >/dev/null; then
    initramfs_tool=dracut
else
    echo 'No supported initramfs tool (mkinitcpio or dracut) found' >&2; exit 1
fi
rollback_driver=false
rebuild_initramfs() {
    if [[ $initramfs_tool == mkinitcpio ]]; then
        mkinitcpio -P
    else
        dracut --regenerate-all --force
    fi
}
cleanup() {
    result=$?
    trap - EXIT
    if (( result != 0 )) && "$rollback_driver"; then
        echo 'Driver staging failed; restoring the stock module for this kernel' >&2
        dkms remove -m "$module" -v "$version" -k "$kernel" || true
        depmod -a "$kernel" || true
        rebuild_initramfs || echo 'Initramfs recovery failed; fix it before rebooting' >&2
    fi
    exit "$result"
}
trap cleanup EXIT
if [[ -e "/usr/src/$module-$version" ]]; then
    cmp "$source_dir/hid-oxp.c" "/usr/src/$module-$version/hid-oxp.c" &&
    cmp "$source_dir/hid-ids.h" "/usr/src/$module-$version/hid-ids.h" &&
    cmp "$source_dir/dkms.conf" "/usr/src/$module-$version/dkms.conf" || {
        echo 'A different build has the same DKMS version; remove it before retrying' >&2; exit 1;
    }
else
    install -d -m 0755 "/usr/src/$module-$version"
    install -m 0644 "$source_dir"/{hid-oxp.c,hid-ids.h,Makefile,dkms.conf} "/usr/src/$module-$version/"
fi
if [[ -z $(dkms status -m "$module" -v "$version") ]]; then
    dkms add -m "$module" -v "$version"
fi
if [[ $(dkms status -m "$module" -v "$version" -k "$kernel") != *installed* ]]; then
    rollback_driver=true
    dkms install -m "$module" -v "$version" -k "$kernel"
fi
depmod -a "$kernel"
selected=$(modinfo -k "$kernel" -n hid_oxp)
[[ $selected == */updates/dkms/hid-oxp.ko* ]] || {
    echo "DKMS driver is not selected: $selected" >&2; exit 1;
}
[[ $(modinfo -k "$kernel" -F version hid_oxp) == "$version" ]] || {
    echo 'Unexpected hid-oxp version selected' >&2; exit 1;
}
rebuild_initramfs
rollback_driver=false
echo 'Gen3 RGB driver staged. Reboot to activate it; the live driver was left bound.'
echo "Rollback: sudo bash $(dirname -- "${BASH_SOURCE[0]}")/uninstall_onexplayer3_rgb_driver.sh"
