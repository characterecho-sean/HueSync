"""Exercise the driver's actual Gen3 packet and acknowledgment helpers without USB."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "kernel/hid-oxp/hid-oxp.c"


def function(source, name):
    match = re.search(r"static (?:int|bool|void) " + name + r"\([^;]+?\)\n\{", source)
    if match is None:
        raise AssertionError(f"Missing driver helper: {name}")
    depth = 1
    end = match.end()
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end]


class Gen3ProtocolTests(unittest.TestCase):
    def test_wire_format_zone_isolation_retry_and_late_ack(self):
        source = SOURCE.read_text()
        structs = "\n".join(re.search(r"struct " + name + r" \{.*?\} __packed;", source, re.S)[0]
                            for name in ("oxp_gen_2_event_header", "oxp_rgb_color", "oxp_gen_3_rgb_color_report"))
        helpers = "\n".join(function(source, name) for name in (
            "oxp_gen_3_property_out", "oxp_gen_3_rgb_property_out",
            "oxp_gen_3_rgb_fill_color", "oxp_gen_2_rgb_event"))
        harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <stddef.h>
typedef uint8_t u8;
#define __packed __attribute__((packed))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define OXP_FID_GEN2_STATUS_EVENT 0xb8
#define GEN2_MESSAGE_ID 0x3f
#define OXP_EFFECT_MONO_TRUE 0xfe
#define OXP_GEN2_RGB_ACK 0x20
#define READ_ONCE(x) (x)
#define scoped_guard(kind, lock) for (int once = 1; once; once = 0)
#define msecs_to_jiffies(x) (x)
static int system_dfl_wq;
struct oxp_hid_cfg {
    int rgb_reply_lock, oxp_mcu_init;
    bool rgb_reply_pending, gen2_work_initialized, suspended, removing;
    u8 rgb_reply_command, rgb_reply_zone;
};
struct oxp_rgb_led { struct oxp_hid_cfg *cfg; u8 zone; };
static u8 wire[64];
static int calls, failures, resets;
static void mod_delayed_work(int wq, int *work, int delay) {
    (void)wq; (void)work; (void)delay; resets++;
}
static int mcu_property_out(struct oxp_hid_cfg *cfg, u8 *header, size_t hs,
                            u8 *data, size_t ds, u8 *footer, size_t fs,
                            bool expect_ack) {
    (void)cfg;
    assert(expect_ack && hs + ds + fs <= 64);
    memset(wire, 0, 64);
    memcpy(wire, header, hs);
    memcpy(wire + hs, data, ds);
    memcpy(wire + 64 - fs, footer, fs);
    calls++;
    if (failures) { failures--; return -110; }
    return 0;
}
'''
        checks = r'''
int main(void) {
    struct oxp_hid_cfg cfg = { .gen2_work_initialized = true };
    struct oxp_rgb_led led = { .cfg = &cfg };
    struct oxp_gen_3_rgb_color_report color;
    assert(sizeof(color) == 59);
    const u8 zones[] = {1, 2, 7};
    for (size_t z = 0; z < 3; z++) {
        led.zone = zones[z]; calls = 0;
        oxp_gen_3_rgb_fill_color(&color, 0xfe, 0, 0x12, 0x34, 0x56);
        assert(oxp_gen_3_rgb_property_out(&led, (u8 *)&color, sizeof(color)) == 0);
        assert(calls == 1);
        const u8 header[] = {0xb8, 0x3f, 1, 0xfe, zones[z], 2};
        assert(memcmp(wire, header, sizeof(header)) == 0);
        for (int i = 0; i < 18; i++) {
            assert(wire[6 + i*3] == 0x12);
            assert(wire[7 + i*3] == 0x34);
            assert(wire[8 + i*3] == 0x56);
        }
        assert(wire[60] == 0x12 && wire[61] == 0x34);
        assert(wire[62] == 0x3f && wire[63] == 0xb8);
    }
    u8 status[] = {0xfd, 0, 2, 1, 5, 4};
    led.zone = 2; failures = 1; calls = 0;
    assert(oxp_gen_3_rgb_property_out(&led, status, sizeof(status)) == 0);
    assert(calls == 2 && wire[4] == 2 && wire[3] == 0xfd);
    failures = 2; calls = 0;
    assert(oxp_gen_3_rgb_property_out(&led, status, sizeof(status)) == -110);
    assert(calls == 2);
    struct oxp_gen_2_event_header reply = { .command = 0xfe, .zone = 2, .status = 0x20 };
    cfg.rgb_reply_pending = true; cfg.rgb_reply_command = 0xfe; cfg.rgb_reply_zone = 2;
    assert(oxp_gen_2_rgb_event(&cfg, &reply) && !cfg.rgb_reply_pending && resets == 0);
    cfg.rgb_reply_pending = true; cfg.rgb_reply_zone = 1;
    assert(oxp_gen_2_rgb_event(&cfg, &reply) && cfg.rgb_reply_pending && resets == 0);
    cfg.rgb_reply_pending = false;
    assert(oxp_gen_2_rgb_event(&cfg, &reply) && resets == 0);
    reply.status = 0;
    assert(oxp_gen_2_rgb_event(&cfg, &reply) && resets == 1);
    cfg.suspended = true;
    assert(oxp_gen_2_rgb_event(&cfg, &reply) && resets == 1);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "protocol.c").write_text(harness + structs + helpers + checks)
            build = subprocess.run(["gcc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-Wno-sign-compare",
                                    str(path / "protocol.c"), "-o", str(path / "protocol")],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(path / "protocol")], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
