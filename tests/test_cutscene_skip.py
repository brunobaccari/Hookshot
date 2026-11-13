"""Game-free checks of the authored skip permission hook; the game owns confirmation and completion."""
import argparse
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUN_ALL_ARGS = ["--cc", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import oot_patches


class CutsceneSkipPatchTests(unittest.TestCase):
    def source(self, body):
        return ('#include "a64.h"\nvoid before(Ctx *c) {\n' + body + '\n}\n'
                + oot_patches.CUTSCENE_HEAD + body + '\n}\n'
                + 'void after(Ctx *c) {\n' + body + '\n}\n')

    def setUp(self):
        self.body = (oot_patches.CUTSCENE_ANCHOR
                     + "    c->x[8]=recomp_load64(c,c->x[0] + 0);\n"
                     + "    c->x[8]=recomp_load64(c,c->x[8] + 40);\n"
                     + oot_patches.CUTSCENE_CALL
                     + "    if (runtime_lock) c->x[1] = 0;\n"
                     + "    native_update_and_confirm(c);\n")

    def test_changes_only_authored_permission_in_target_function(self):
        source = self.source(self.body)
        patched = oot_patches.patch_cutscene_skip(source)
        expected = source.replace(
            oot_patches.CUTSCENE_HEAD + self.body,
            oot_patches.CUTSCENE_HEAD + self.body.replace(
                oot_patches.CUTSCENE_ANCHOR,
                oot_patches.CUTSCENE_ANCHOR + oot_patches.CUTSCENE_HOOK), 1)
        expected = expected.replace(
            '#include "a64.h"\n',
            '#include "a64.h"\nextern uint64_t hos_oot_cutscene_skip_allowed(uint64_t native_allowed);\n', 1)
        self.assertEqual(patched, expected)
        self.assertEqual(oot_patches.patch_cutscene_skip(patched), patched)
        self.assertEqual(patched.count(oot_patches.CUTSCENE_HOOK), 1)

    def test_coexists_with_native_opening_hooks(self):
        source = (self.source(self.body)
                  + oot_patches.OPENING_REQUEST_HEAD + "\n}\n"
                  + oot_patches.OPENING_TIMELINE_HEAD + "\n}\n"
                  + oot_patches.OPENING_QUERY_HEAD + "\n}\n"
                  + oot_patches.CUTSCENE_TIMELINE_HEAD + oot_patches.CUTSCENE_TIMELINE_PREFIX
                  + oot_patches.CUTSCENE_TIMELINE_BRANCH + oot_patches.CUTSCENE_TIMELINE_READY + "\n}\n")
        for opening_first in (False, True):
            patched = oot_patches.patch_opening(source) if opening_first else source
            patched = oot_patches.patch_cutscene_skip(patched)
            patched = oot_patches.patch_cutscene_skip_timeline(patched)
            if not opening_first:
                patched = oot_patches.patch_opening(patched)
            self.assertEqual(patched.count(oot_patches.CUTSCENE_HOOK), 1)
            self.assertEqual(patched.count(oot_patches.CUTSCENE_TIMELINE_ALLOW), 1)
            for hook in (oot_patches.OPENING_REQUEST, oot_patches.OPENING_TIMELINE, oot_patches.OPENING_QUERY):
                self.assertEqual(patched.count(hook), 1)
            self.assertEqual(oot_patches.patch_opening(patched), patched)
            self.assertEqual(oot_patches.patch_cutscene_skip(patched), patched)
            self.assertEqual(oot_patches.patch_cutscene_skip_timeline(patched), patched)

    def test_rejects_missing_or_ambiguous_target_and_instruction_context(self):
        for anchor in (oot_patches.CUTSCENE_ANCHOR, oot_patches.CUTSCENE_CALL):
            for copies in (0, 2):
                with self.subTest(anchor=anchor, copies=copies):
                    self.assertIsNone(oot_patches.patch_cutscene_skip(
                        self.source(self.body.replace(anchor, anchor * copies))))
        source = self.source(self.body)
        self.assertIsNone(oot_patches.patch_cutscene_skip(source.replace(oot_patches.CUTSCENE_HEAD, "")))
        self.assertIsNone(oot_patches.patch_cutscene_skip(source + oot_patches.CUTSCENE_HEAD + "\n}\n"))
        self.assertIsNone(oot_patches.patch_cutscene_skip(oot_patches.CUTSCENE_HEAD + self.body))


class TimelineCutsceneSkipPatchTests(unittest.TestCase):
    def source(self, body):
        return ('#include "a64.h"\nvoid before(Ctx *c) {\n' + body + '\n}\n'
                + oot_patches.CUTSCENE_TIMELINE_HEAD + body + '\n}\n'
                + 'void after(Ctx *c) {\n' + body + '\n}\n')

    def setUp(self):
        self.body = (oot_patches.CUTSCENE_TIMELINE_PREFIX + oot_patches.CUTSCENE_TIMELINE_BRANCH
                     + "    native_disabled_path(c);\n" + oot_patches.CUTSCENE_TIMELINE_READY
                     + "    native_readiness_and_completion(c);\n")

    def test_overrides_only_authored_branch_and_preserves_readiness(self):
        source = self.source(self.body)
        patched = oot_patches.patch_cutscene_skip_timeline(source)
        expected = source.replace(
            oot_patches.CUTSCENE_TIMELINE_HEAD + self.body,
            oot_patches.CUTSCENE_TIMELINE_HEAD + self.body.replace(
                oot_patches.CUTSCENE_TIMELINE_BRANCH, oot_patches.CUTSCENE_TIMELINE_ALLOW), 1)
        expected = expected.replace(
            '#include "a64.h"\n',
            '#include "a64.h"\nextern uint64_t hos_oot_cutscene_skip_allowed(uint64_t native_allowed);\n', 1)
        self.assertEqual(patched, expected)
        self.assertEqual(oot_patches.patch_cutscene_skip_timeline(patched), patched)

    def test_rejects_missing_ambiguous_or_partially_patched_context(self):
        for anchor in (oot_patches.CUTSCENE_TIMELINE_PREFIX, oot_patches.CUTSCENE_TIMELINE_BRANCH,
                       oot_patches.CUTSCENE_TIMELINE_READY):
            for copies in (0, 2):
                with self.subTest(anchor=anchor, copies=copies):
                    self.assertIsNone(oot_patches.patch_cutscene_skip_timeline(
                        self.source(self.body.replace(anchor, anchor * copies))))
        source = self.source(self.body)
        self.assertIsNone(oot_patches.patch_cutscene_skip_timeline(
            source.replace(oot_patches.CUTSCENE_TIMELINE_HEAD, "")))
        self.assertIsNone(oot_patches.patch_cutscene_skip_timeline(
            source + oot_patches.CUTSCENE_TIMELINE_HEAD + "\n}\n"))
        self.assertIsNone(oot_patches.patch_cutscene_skip_timeline(
            oot_patches.CUTSCENE_TIMELINE_HEAD + self.body))
        self.assertIsNone(oot_patches.patch_cutscene_skip_timeline(self.source(
            self.body + oot_patches.CUTSCENE_TIMELINE_ALLOW)))


class MenuWiringTests(unittest.TestCase):
    def test_off_by_default_and_native_skip_control(self):
        header = (ROOT / "gpu/vk/vk_menu.h").read_text(encoding="utf-8")
        menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
        replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")
        self.assertIn("int allow_cutscene_skip = 0;", header)
        self.assertIn('{TAB_GAMEPLAY, "Skip cutscenes (Experimental)", &opts.allow_cutscene_skip, 0, 1, 1, tx_onoff,', menu)
        self.assertIn('"skip_unskippable_cutscenes"', menu)
        self.assertIn("Can skip the opening movie.", menu)
        self.assertIn("It may overlap dialogue; some conversations and chest sequences remain unsupported.", menu)
        self.assertIn("if (id == HOS_OPT_ALLOW_CUTSCENE_SKIP) return menu_allow_cutscene_skip();", replay)
        self.assertEqual(menu.count("cutscene_skip_now.store(opts.allow_cutscene_skip, std::memory_order_relaxed);"), 2)
        self.assertIn("int menu_allow_cutscene_skip() { return cutscene_skip_now.load(std::memory_order_relaxed); }", menu)


def check_host(cc):
    fixture = r'''
#include <assert.h>
#include <stdint.h>
static int menu, calls;
int rx_option(int id, int otherwise) {
    assert(id == 56 && otherwise == 0);
    ++calls;
    return menu;
}
uint64_t hos_oot_cutscene_skip_allowed(uint64_t native_allowed);
int main(void) {
    assert(hos_oot_cutscene_skip_allowed(0) == 0);
    assert(hos_oot_cutscene_skip_allowed(1) == 1);
    menu = 1;
    assert(hos_oot_cutscene_skip_allowed(0) == 1);
    assert(hos_oot_cutscene_skip_allowed(1) == 1);
    menu = 0;
    assert(hos_oot_cutscene_skip_allowed(0) == 0);
    menu = -1;
    assert(hos_oot_cutscene_skip_allowed(0) == 0);
    assert(calls == 6);
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="cutscene-skip-") as tmp:
        source = Path(tmp) / "fixture.c"
        exe = Path(tmp) / ("fixture.exe" if sys.platform == "win32" else "fixture")
        source.write_text(fixture, encoding="utf-8")
        subprocess.run([cc, "-x", "c", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(ROOT / "host" / "oot_cutscene_skip.c"), str(source), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


def check_timeline_branch(cc):
    # The lifted branch, join and readiness block, with native calls isolated from the rest of the player.
    body = ("    goto L_80ac87c8;\n" + oot_patches.CUTSCENE_TIMELINE_PREFIX + oot_patches.CUTSCENE_TIMELINE_BRANCH
            + "    { uint64_t _r = ((uint64_t)0 | ((uint64_t)(uint32_t)(((uint32_t)((uint64_t)0)) << 0))); _r &= 0xFFFFFFFFULL; c->x[8] = _r; }\n"
            + "L_80ac87dc:;\n"
            + "    c->x[9]=recomp_load64(c,c->x[0] + 0);\n"
            + "    { uint64_t _r = c->x[8] & 0x1ULL; _r &= 0xFFFFFFFFULL; c->x[1] = _r; }\n"
            + "    c->x[9]=recomp_load64(c,c->x[9] + 40);\n"
            + "{ uint64_t _t = c->x[9]; c->x[30] = 0x80ac87ecULL; A64_ICALL(c, _t); }\n"
            + "    return;\n" + oot_patches.CUTSCENE_TIMELINE_READY
            + "    { uint64_t _r = ((uint64_t)0 | ((uint64_t)(uint32_t)(((uint32_t)(c->x[0])) << 0))); _r &= 0xFFFFFFFFULL; c->x[8] = _r; }\n"
            + "    { uint64_t _r = ((uint64_t)0 | ((c->x[20]) << 0)); c->x[0] = _r; }\n"
            + "{ A64_POLL(c); goto L_80ac87dc; }\n")
    header = r'''
#include <assert.h>
#include <stdint.h>
typedef struct { uint64_t x[32]; } Ctx;
#define A64_NOESC
#define A64_POLL(c) ((void)(c))
static uint64_t recomp_load64(Ctx *, uint64_t);
static uint64_t recomp_load8(Ctx *, uint64_t);
static void f_83b60640(Ctx *);
static void fixture_setter(Ctx *, uint64_t);
#define A64_ICALL(c, t) fixture_setter(c, t)
'''
    fixture = r'''
enum { EVENT=0x100, RESOURCE=0x500, CONTROLLER=0xa00, VTABLE=0xb00 };
static int native_allowed, ready, option, readiness_calls, setter_calls, allowed;
int rx_option(int id, int otherwise) { assert(id==56 && otherwise==0); return option; }
static uint64_t recomp_load64(Ctx *c, uint64_t a) {
    (void)c;
    if (a==EVENT+16) return RESOURCE;
    if (a==EVENT+32) return CONTROLLER;
    if (a==CONTROLLER) return VTABLE;
    assert(a==VTABLE+40); return 0x1234;
}
static uint64_t recomp_load8(Ctx *c, uint64_t a) {
    (void)c; assert(a==RESOURCE+955); return 0xa1 | (native_allowed<<2);
}
static void f_83b60640(Ctx *c) {
    assert(c->x[0]==CONTROLLER); ++readiness_calls; c->x[0]=(uint64_t)ready;
}
static void fixture_setter(Ctx *c, uint64_t target) {
    assert(target==0x1234 && c->x[0]==CONTROLLER); ++setter_calls; allowed=(int)c->x[1];
}
int main(void) {
    int cases=0;
    for (option=-1; option<=1; ++option)
        for (native_allowed=0; native_allowed<=1; ++native_allowed)
            for (ready=0; ready<=1; ++ready) {
                Ctx c={0}; c.x[19]=EVENT;
                readiness_calls=setter_calls=0; allowed=-1;
                f_80ac8650(&c);
                assert(readiness_calls==(native_allowed || option>0));
                assert(setter_calls==1);
                assert(allowed==((native_allowed || option>0) && ready));
                ++cases;
            }
    assert(cases==12); return 0;
}
'''
    source = '#include "a64.h"\n' + oot_patches.CUTSCENE_TIMELINE_HEAD + body + "\n}\n"
    patched = oot_patches.patch_cutscene_skip_timeline(source)
    assert patched is not None
    with tempfile.TemporaryDirectory(prefix="cutscene-timeline-") as tmp:
        folder = Path(tmp)
        (folder / "a64.h").write_text(header, encoding="utf-8")
        path = folder / "fixture.c"
        path.write_text(patched + fixture, encoding="utf-8")
        exe = folder / ("fixture.exe" if sys.platform == "win32" else "fixture")
        subprocess.run([cc, "-x", "c", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(ROOT / "host" / "oot_cutscene_skip.c"), str(path), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    check_host(args.cc)
    check_timeline_branch(args.cc)
    unittest.main(argv=[sys.argv[0]])
