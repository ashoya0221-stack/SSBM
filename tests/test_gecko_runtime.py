"""Execute emitted PPC bytes with modeled game calls, not a full Dolphin test."""

import json
import struct
import unittest

from tools.build_gecko import ROOT, FUNCTIONS, build, c2, data_words

try:
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_PPC32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import (UC_PPC_REG_0, UC_PPC_REG_PC, UC_PPC_REG_LR,
                                   UC_PPC_REG_MSR, UC_PPC_REG_FPR0)
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


SETTINGS = json.loads((ROOT / "config/restoration.json").read_text())


class Runtime:
    BASE = 0x81200000
    STOP = 0x817FF000
    STACK = 0x81700000
    MH = 0x80400000
    CH = 0x80400100
    A = 0x80400200
    B = 0x80400300

    def __init__(self, force_combo=False):
        self.text, self.code, self.symbols, _ = build(SETTINGS, force_combo)
        self.u = Uc(UC_ARCH_PPC, UC_MODE_PPC32 | UC_MODE_BIG_ENDIAN)
        self.u.mem_map(0x80000000, 0x1800000)
        self.u.mem_write(self.BASE, self.code)
        self.u.reg_write(UC_PPC_REG_MSR, 0x2000)  # enable floating-point instructions
        self.hands = {27: self.MH, 28: self.CH}
        self.frames_remaining = {}
        self.damage = {self.A: 0, self.B: 0}
        self.pummels, self.throws, self.cuts = [], [], []
        self.throw_data = {}
        self.moves = []
        self.sounds, self.events = [], []
        self.invocation = 0
        self.rng = 3
        for i, obj in enumerate((self.MH, self.CH, self.A, self.B)):
            fp = 0x80500000 + i * 0x10000
            self.write(obj + 0x2C, fp)
            self.write(fp + 4, 27 + i if i < 2 else 0)
            self.write(fp + 0x10, 341)
            self.write(fp + 0x1844, 0x3F800000)
            if i < 2:
                data = 0x80550000 + i * 0x10000
                self.write(fp + 0x10C, data)
                self.write(data + 0xC, 0x80600000 + i * 0x10000)
        self.write(self.fp(self.CH) + 0x10, 384)
        self.write(self.fp(self.CH) + 0x2250, 380)
        self.u.hook_add(UC_HOOK_CODE, self.game_call)

    def read(self, address):
        return struct.unpack(">I", self.u.mem_read(address, 4))[0]

    def write(self, address, value):
        self.u.mem_write(address, struct.pack(">I", value))

    def fp(self, obj):
        return self.read(obj + 0x2C)

    def set_frame(self, obj, frame):
        self.u.mem_write(self.fp(obj) + 0x894, struct.pack(">f", frame))

    def frame(self, obj):
        return struct.unpack(">f", self.u.mem_read(self.fp(obj) + 0x894, 4))[0]

    def reg(self, index):
        return self.u.reg_read(UC_PPC_REG_0 + index)

    def game_call(self, u, address, _size, _data):
        reverse = {value: name for name, value in FUNCTIONS.items()}
        if address not in reverse:
            return
        name = reverse[address]
        a, b = self.reg(3), self.reg(4)
        self.events.append((self.invocation, name, a, b))
        result = 0
        if name == "GET_HAND":
            result = self.hands.get(a, 0)
        elif name == "RANDI":
            result = self.rng % a
        elif name == "CHANGE_STATE":
            self.write(self.fp(a) + 0x10, b)
            self.set_frame(a, 0)
        elif name == "ANIM_REMAINING":
            result = int(self.frames_remaining.get(a, True))
        elif name in ("MASTER_MOVE", "CRAZY_MOVE"):
            pos = self.reg(5)
            self.moves.append((a, b, struct.unpack(">3f", self.u.mem_read(pos, 12))))
        elif name == "INIT_GRAB":
            fp = a
            self.u.mem_write(fp + 0x1A68, struct.pack(">H", b))
            for offset, index in ((0x2190, 5), (0x2194, 6), (0x2198, 7)):
                self.write(fp + offset, self.reg(index))
            byte = self.u.mem_read(fp + 0x221E, 1)[0]
            self.u.mem_write(fp + 0x221E, bytes([byte | 2]))
        elif name == "SET_GRAB_MASK":
            self.u.mem_write(a + 0x1A6A, struct.pack(">H", b))
        elif name == "SET_THROW_DATA":
            ptr = self.read(b + 8)
            self.throw_data[a] = self.read(ptr) & 0x7FFFFF
        elif name == "CREATE_HITBOX":
            ptr = self.read(b + 8)
            damage = self.read(ptr) & 0x3FF
            element = (self.read(ptr + 16) >> 18) & 31
            only_victim = bool(self.read(ptr + 20) & 0x80000)
            target = self.read(self.fp(a) + 0x1A58)
            self.pummels.append((a, target, damage, element, only_victim))
            # The real ftColl damage scan excludes Catch (8); the v1 harness
            # incorrectly awarded damage to that element and hid the MH bug.
            if target in self.damage and element != 8 and only_victim:
                self.damage[target] += damage
        elif name == "PLAY_SFX":
            self.sounds.append((a, b, self.reg(5), self.reg(6)))
        elif name == "BOSS_LAUGH":
            self.sounds.append((self.fp(a), "laugh", 127, 64))
        elif name == "ANIM_SEEK":
            bits = u.reg_read(UC_PPC_REG_FPR0 + 1)
            frame = struct.unpack(">d", struct.pack(">Q", bits))[0]
            self.set_frame(a, frame)
        elif name == "APPLY_THROW":
            self.damage[b] += self.throw_data[a]
            self.throws.append((a, b, self.throw_data[a]))
        elif name == "CAPTURE_CUT":
            self.cuts.append(a)
            self.write(self.fp(a) + 0x1A58, 0)
        elif name in ("MASTER_IDLE", "CRAZY_IDLE"):
            self.write(self.fp(a) + 0x10, 341)
        elif name not in ("ANIM_INIT", "ANIM_EVALUATE", "CLEAR_HITBOXES",
                           "MH_THROWN", "CH_THROWN", "LAUNCH_VICTIM"):
            raise AssertionError(f"unexpected unmodeled call: {name}")
        # Game calls may destroy all volatile GPRs; emitted code must obey the ABI.
        for index in range(4, 13):
            u.reg_write(UC_PPC_REG_0 + index, 0xDEAD0000 + index)
        for index in range(14):
            u.reg_write(UC_PPC_REG_FPR0 + index, 0x4008000000000000)
        u.reg_write(UC_PPC_REG_0 + 3, result)
        u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))

    def invoke(self, label, obj, arg4=0):
        self.invocation += 1
        self.u.reg_write(UC_PPC_REG_0 + 1, self.STACK)
        self.u.reg_write(UC_PPC_REG_0 + 3, obj)
        self.u.reg_write(UC_PPC_REG_0 + 4, arg4)
        saved = {i: 0x12340000 + i for i in range(26, 32)}
        for i, value in saved.items():
            self.u.reg_write(UC_PPC_REG_0 + i, value)
        self.u.reg_write(UC_PPC_REG_LR, self.STOP)
        self.u.emu_start(self.BASE + self.symbols[label], self.STOP, count=20000)
        if self.u.reg_read(UC_PPC_REG_PC) != self.STOP:
            raise AssertionError("PPC routine did not return within instruction budget")
        for i, value in saved.items():
            if self.reg(i) != value:
                raise AssertionError(f"nonvolatile register r{i} was corrupted")
        if self.reg(1) != self.STACK:
            raise AssertionError("stack pointer was not restored")

    def capture(self, hand, target):
        self.write(self.fp(hand) + 0x1A58, target)
        self.write(self.fp(target) + 0x1A58, hand)
        self.u.mem_write(self.fp(target) + 0x221E, b"\x80")
        self.invoke("on_grab", hand)

    def run_hook(self, index, register_values, stack_vector=None):
        lines = self.text.splitlines()
        hooks = []
        cursor = 2
        while lines[cursor].startswith("C2"):
            head, count = (int(x, 16) for x in lines[cursor].split())
            words = [int(word, 16) for line in lines[cursor+1:cursor+1+count]
                     for word in line.split()]
            hooks.append((0x80000000 | (head & 0x1FFFFFF), words))
            cursor += count + 1
        address, words = hooks[index]
        base = self.BASE + 0x10000 * (index + 1)
        last = base + 4 * (len(words) - 1)
        words[-1] = 0x48000000 | ((address + 4 - last) & 0x3FFFFFC)
        self.u.mem_write(base, struct.pack(">" + "I" * len(words), *words))
        self.u.reg_write(UC_PPC_REG_0 + 1, self.STACK)
        for i, value in register_values.items():
            self.u.reg_write(UC_PPC_REG_0 + i, value)
        self.u.reg_write(UC_PPC_REG_LR, self.STOP)
        if stack_vector:
            offset, vector = stack_vector
            self.u.mem_write(self.STACK + offset, struct.pack(">3f", *vector))
            # The original caller loads f0 with the vector's Z before the hook.
            self.u.reg_write(UC_PPC_REG_FPR0,
                             struct.unpack(">Q", struct.pack(">d", vector[2]))[0])
        self.u.emu_start(base, address + 4, count=20000)
        if self.u.reg_read(UC_PPC_REG_PC) != address + 4:
            raise AssertionError("hook did not return to the original instruction stream")
        if self.reg(1) != self.STACK:
            raise AssertionError("hook corrupted stack pointer")

    def finish_grab(self):
        self.frames_remaining = {self.MH: False, self.CH: False}
        self.invoke("tag_anim", self.MH)
        self.frames_remaining = {}

    def squeeze_frame(self, frame, ch_frame=None):
        self.set_frame(self.MH, frame)
        self.set_frame(self.CH, frame if ch_frame is None else ch_frame)
        self.invoke("tag_anim", self.MH)
        self.invoke("tag_anim", self.CH)


class EncodingTests(unittest.TestCase):
    def test_native_damage_and_own_victim_filter(self):
        words = data_words(SETTINGS)
        self.assertEqual(words["PUMMEL_DATA_MH"][0] & 1023, 6)
        self.assertEqual(words["PUMMEL_DATA_MH"][4] >> 18 & 31, 0)
        self.assertEqual(words["PUMMEL_DATA_CH"][0] & 1023, 7)
        self.assertEqual(words["PUMMEL_DATA_CH"][4] >> 18 & 31, 15)
        self.assertEqual(words["PUMMEL_DATA_CH"][5], 0x80000)

    def test_grab_radius_and_native_sound_command(self):
        words = data_words(SETTINGS)
        self.assertEqual(words["GRAB_DATA_MH"][:4],
                         [0x0800000F, 0x44000000, 156, 0x7F40])
        self.assertEqual(words["GRAB_DATA_MH"][6] >> 16, 24 * 256)
        self.assertEqual(words["GRAB_DATA_CH"][2] >> 16, 24 * 256)

    def test_default_dolphin_code_list_capacity(self):
        for forced in (False, True):
            code, *_ = build(SETTINGS, forced)
            self.assertLessEqual(len(code.splitlines()) * 8, 3256)

    def test_c2_branch_back_slot_and_line_count(self):
        for count in (1, 2, 3):
            lines = c2(0x80100000, b"\x60\x00\x00\x00" * count)
            self.assertEqual(int(lines[0].split()[1], 16), len(lines) - 1)
            self.assertTrue(lines[-1].endswith("00000000"))


@unittest.skipUnless(AVAILABLE, "install requirements-dev.txt to execute PPC tests")
class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.r = Runtime()

    def test_pair_starts_correct_distinct_actions_and_callbacks(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 385)
        self.assertEqual(r.read(r.fp(r.CH) + 0x10), 380)
        self.assertEqual(r.read(r.fp(r.MH) + 0x2198), 0x801550D8)
        self.assertEqual(r.read(r.fp(r.CH) + 0x2198), 0x8015AB94)

    def test_real_selector_hook_has_four_choices_and_preserves_other_groups(self):
        r = self.r
        for rng in range(4):
            r.rng = rng
            r.run_hook(0, {3: 377, 27: 5, 29: r.fp(r.CH)})
            self.assertEqual(r.reg(3), 377 + rng)
        r.run_hook(0, {3: 359, 27: 3, 29: r.fp(r.CH)})
        self.assertEqual(r.reg(3), 359)
        del r.hands[27]
        r.run_hook(0, {3: 377, 27: 5, 29: r.fp(r.CH)})
        self.assertEqual(r.reg(3), 343)

    def test_real_movement_hooks_pass_original_stack_vectors(self):
        r = self.r
        r.run_hook(1, {31: r.CH}, (0x24, (-44.0, 30.0, 0.0)))
        r.run_hook(2, {28: r.MH}, (0x2C, (44.0, 30.0, 0.0)))
        self.assertEqual(r.moves[0], (r.CH, 0x8015A114, (-44.0, 30.0, 0.0)))
        self.assertEqual(r.moves[1], (r.MH, r.BASE + 0x30000 + r.symbols["start_pair"],
                                    (44.0, 30.0, 0.0)))

    def test_combo_test_variant_always_selects_restored_move(self):
        r = Runtime(force_combo=True)
        for rng in range(4):
            r.rng = rng
            r.run_hook(0, {3: 377, 27: 5, 29: r.fp(r.CH)})
            self.assertEqual(r.reg(3), 380)

    def test_two_independent_victims_five_hits_and_both_throws(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        r.capture(r.MH, r.A)
        r.capture(r.CH, r.B)
        r.finish_grab()
        for frame in range(SETTINGS["throw_frame"] + 1):
            r.squeeze_frame(frame)
        self.assertEqual([(a, b, d) for a, b, d in r.throws],
                         [(r.MH, r.A, 12), (r.CH, r.B, 16)])
        self.assertEqual(r.damage[r.A], 42)
        self.assertEqual(r.damage[r.B], 51)  # engine's flower DOT is separate
        self.assertEqual(len(r.pummels), 10)
        self.assertTrue(all(p[4] for p in r.pummels))
        self.assertTrue(all(p[1] == (r.A if p[0] == r.MH else r.B) for p in r.pummels))
        self.assertEqual(r.read(r.fp(r.MH) + 0x1A58), 0)
        self.assertEqual(r.read(r.fp(r.CH) + 0x1A58), 0)
        for name, count in (("CREATE_HITBOX", 10), ("APPLY_THROW", 2)):
            events = [e for e in r.events if e[1] == name]
            self.assertEqual(len(events), count)
            for mh, ch in zip(events[::2], events[1::2]):
                self.assertEqual(mh[0], ch[0], "both hands must act in the same callback")
                self.assertEqual((mh[2], ch[2]), (r.MH, r.CH))
        self.assertEqual([s[1] for s in r.sounds], ["laugh"] + [0x4E212] * 5 + [9])
        self.assertTrue(all(s[2:] == (127, 64) for s in r.sounds))

    def test_whiff_recovers_both_hands(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        r.finish_grab()
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 387)
        self.assertEqual(r.read(r.fp(r.CH) + 0x10), 382)
        r.frames_remaining = {r.MH: False, r.CH: False}
        r.invoke("tag_anim", r.MH)
        r.invoke("tag_anim", r.CH)
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 341)
        self.assertEqual(r.read(r.fp(r.CH) + 0x10), 341)

    def test_one_whiff_does_not_release_other_hands_victim(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        r.capture(r.MH, r.A)
        r.finish_grab()
        self.assertEqual(r.read(r.fp(r.CH) + 0x10), 381)
        for frame in range(SETTINGS["throw_frame"] + 1):
            r.squeeze_frame(frame)
        self.assertEqual(r.throws, [(r.MH, r.A, 12)])
        self.assertEqual(r.cuts, [])

    def test_other_hand_captures_alone_and_both_finish_together(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        r.capture(r.CH, r.B)
        r.finish_grab()
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 386)
        for frame in range(SETTINGS["throw_frame"] + 1):
            r.squeeze_frame(frame)
        self.assertEqual(r.throws, [(r.CH, r.B, 16)])
        r.frames_remaining = {r.MH: False, r.CH: True}
        r.squeeze_frame(330)
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 386)
        r.frames_remaining[r.CH] = False
        r.squeeze_frame(331)
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 341)
        self.assertEqual(r.read(r.fp(r.CH) + 0x10), 341)

    def test_grab_completion_waits_for_both_hands(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        r.capture(r.MH, r.A)
        r.frames_remaining = {r.MH: False, r.CH: True}
        r.invoke("tag_anim", r.MH)
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 385)
        r.finish_grab()
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 386)
        self.assertEqual(r.read(r.fp(r.CH) + 0x10), 381)

    def test_animation_frame_drives_events_despite_duplicate_or_secondary_callbacks(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        r.capture(r.MH, r.A)
        r.capture(r.CH, r.B)
        r.finish_grab()
        r.squeeze_frame(48)
        for _ in range(7):
            r.invoke("tag_anim", r.CH)
            r.invoke("tag_anim", r.MH)
        self.assertEqual(r.pummels, [])
        r.squeeze_frame(49)
        for _ in range(7):
            r.invoke("tag_anim", r.MH)
        self.assertEqual(len(r.pummels), 2)
        # Integer frame may jump over an event due to animation speed changes.
        r.squeeze_frame(80)
        self.assertEqual(len(r.pummels), 4)

    def test_repair_partner_pose_drift_without_repeating_damage(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        r.capture(r.MH, r.A)
        r.capture(r.CH, r.B)
        r.finish_grab()
        r.squeeze_frame(49, ch_frame=54)
        self.assertEqual(r.frame(r.CH), 49)
        self.assertEqual(len(r.pummels), 2)

    def test_partner_death_releases_held_victim_and_recovers(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        r.capture(r.MH, r.A)
        r.capture(r.CH, r.B)
        r.write(r.fp(r.CH) + 0x10, 385)  # CH's actual death state
        r.invoke("tag_anim", r.MH)
        self.assertEqual(r.cuts, [r.B, r.A])
        self.assertEqual(r.u.mem_read(r.fp(r.A) + 0x221E, 1), b"\0")
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 341)
        self.assertEqual(r.read(r.fp(r.CH) + 0x10), 385)

    def test_reciprocal_owner_check_prevents_stealing_other_capture(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        r.write(r.fp(r.MH) + 0x1A58, r.B)
        r.write(r.fp(r.B) + 0x1A58, r.CH)
        r.finish_grab()
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 387)
        self.assertEqual(r.cuts, [])

    def test_missing_partner_recovers(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        del r.hands[28]
        r.invoke("tag_anim", r.MH)
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 341)

    def test_animation_that_never_finishes_has_bounded_recovery(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        for ticks in range(1, 401):
            r.invoke("tag_anim", r.MH)
            if r.read(r.fp(r.MH) + 0x10) == 341:
                break
        self.assertLessEqual(ticks, 380)

    def test_stalled_squeeze_releases_both_without_a_throw(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        r.capture(r.MH, r.A)
        r.capture(r.CH, r.B)
        r.finish_grab()
        for _ in range(900):
            r.invoke("tag_anim", r.MH)
        self.assertEqual(r.cuts, [r.B, r.A])
        self.assertEqual(r.throws, [])
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 341)
        self.assertEqual(r.read(r.fp(r.CH) + 0x10), 341)


if __name__ == "__main__":
    unittest.main()
