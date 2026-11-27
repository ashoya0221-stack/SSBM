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

    def __init__(self, force_combo=False, manual=False):
        self.manual = manual
        self.text, self.code, self.symbols, _ = build(SETTINGS, force_combo, manual)
        self.u = Uc(UC_ARCH_PPC, UC_MODE_PPC32 | UC_MODE_BIG_ENDIAN)
        self.u.mem_map(0x80000000, 0x1800000)
        self.u.mem_write(self.BASE, self.code)
        self.u.reg_write(UC_PPC_REG_MSR, 0x2000)  # enable floating-point instructions
        self.hands = {27: self.MH, 28: self.CH}
        self.frames_remaining = {}
        self.damage = {self.A: 0, self.B: 0}
        self.pummels, self.throws, self.cuts = [], [], []
        self.throw_data = {}
        self.throw_angles = {}
        self.moves = []
        self.sounds, self.events = [], []
        self.invocation = 0
        self.hitboxes, self.hit_once = {}, set()
        self.hit_generation = 0
        self.grounded = set()
        self.impacts, self.launches, self.allocations = [], [], []
        self.attachments = []
        self.follow_calls = []
        self.nametag_positions = {}
        self.joints = {}
        self.installed_hooks = set()
        self.flowers, self.hit_effects = [], []
        self.rng = 3
        for i, obj in enumerate((self.MH, self.CH, self.A, self.B)):
            fp = 0x80500000 + i * 0x10000
            self.write(obj + 0x2C, fp)
            self.write(fp + 4, 27 + i if i < 2 else 0)
            self.write(fp + 0x0C, (i + 2) % 4)
            self.write(fp + 0x10, 341)
            self.write(fp + 0x1844, 0x3F800000)
            self.write(fp + 0x38, 0x3F800000)
            if i < 2:
                data = 0x80550000 + i * 0x10000
                self.write(fp + 0x10C, data)
                attrs = 0x80640000 + i * 0x1000
                self.write(data + 4, attrs)
                self.u.mem_write(attrs + 0x13C, struct.pack(">2f", 44, 30))
                self.write(data + 0xC, 0x80600000 + i * 0x10000)
                parts, joint = 0x80620000 + i * 0x1000, 0x80650000 + i * 0x100
                self.write(fp + 0x5E8, parts)
                self.write(parts + 0x120, joint)
                self.joints[joint] = (25.0 if i == 0 else -25.0, 50.0, 0.0)
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
        elif name == "ATTACH_VICTIM":
            self.attachments.append((a, b))
        elif name == "CAPTURE_FOLLOW":
            self.follow_calls.append(a)
        elif name == "PLAYER_SET_SLOT_POS":
            position = struct.unpack(">3f", u.mem_read(self.reg(5), 12))
            self.nametag_positions[(a, b)] = position
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
            self.throw_angles[a] = self.read(ptr + 4) >> 23
        elif name == "CREATE_HITBOX":
            if not self.manual:
                raise AssertionError("v4 pummels must not depend on spatial hitboxes")
            ptr = self.read(b + 8)
            assert self.read(ptr + 16) == 0x00200007  # catch, never a pummel
            self.write(self.fp(a) + 0x914, 1)
        elif name == "RESET_HIT_VICTIMS":
            assert self.manual
        elif name == "CLEAR_HITBOXES":
            self.hitboxes.pop(a, None)
            self.write(self.fp(a) + 0x914, 0)
        elif name == "PLAY_SFX":
            self.sounds.append((a, b, self.reg(5), self.reg(6)))
        elif name == "BOSS_LAUGH":
            self.sounds.append((self.fp(a), "laugh", 127, 64))
        elif name == "TAKE_DAMAGE":
            target = next(obj for obj in self.damage if self.fp(obj) == a)
            bits = u.reg_read(UC_PPC_REG_FPR0 + 1)
            damage = struct.unpack(">d", struct.pack(">Q", bits))[0]
            hand = self.read(a + 0x1A58)
            assert hand in (self.MH, self.CH)
            element = 15 if hand == self.CH else 0
            self.damage[target] += damage
            self.pummels.append((hand, target, damage, element, True))
        elif name == "RECORD_HIT":
            assert self.read(self.fp(b) + 0x1A58) == a
        elif name == "APPLY_FLOWER":
            assert b == 7  # US 1.00 ABI uses an integer, not f1.
            self.flowers.append((a, b))
        elif name == "HIT_EFFECT":
            position = struct.unpack(">3f", u.mem_read(b, 12))
            self.hit_effects.append((a, position, self.reg(5)))
        elif name == "ANIM_SEEK":
            bits = u.reg_read(UC_PPC_REG_FPR0 + 1)
            frame = struct.unpack(">d", struct.pack(">Q", bits))[0]
            self.set_frame(a, frame)
        elif name == "APPLY_THROW":
            assert self.read(self.fp(a) + 0x1A58) == b
            assert self.read(self.fp(b) + 0x1A58) == a
            self.damage[b] += self.throw_data[a]
            self.throws.append((a, b, self.throw_data[a]))
            self.write(self.fp(b) + 0x1848, self.throw_angles[a])
            self.write(self.fp(a) + 0x1A58, 0)
            self.write(self.fp(b) + 0x1A58, 0)
        elif name == "JOINT_WORLD":
            u.mem_write(self.reg(5), struct.pack(">3f", *self.joints[a]))
        elif name == "GROUND_PROBE":
            result = int(a in self.grounded)
        elif name == "GROUND_IMPACT":
            self.impacts.append(a)
        elif name == "SET_AIRBORNE":
            self.write(a + 0xE0, 1)
        elif name == "LAUNCH_VICTIM":
            fp = self.fp(a)
            angle = self.read(fp + 0x1848)
            self.launches.append((a, angle, self.reg(5)))
            self.write(fp + 0x21A8, 0x8008FE00)  # native damage state's callback
            self.write(fp + 0x10, 90 if angle == 270 else 87)
            u.mem_write(fp + 0x221E, b"\0")
        elif name in ("MH_THROWN", "CH_THROWN"):
            u.mem_write(self.fp(a) + 0x221E, b"\0")
        elif name == "ALLOC":
            self.allocations.append(a)
            result = self.BASE
        elif name in ("FLUSH_CODE", "INVALIDATE_CODE"):
            pass
        elif name == "CAPTURE_CUT":
            self.cuts.append(a)
            self.write(self.fp(a) + 0x1A58, 0)
        elif name in ("MASTER_IDLE", "CRAZY_IDLE"):
            self.write(self.fp(a) + 0x10, 341)
        elif name not in ("ANIM_INIT", "ANIM_EVALUATE"):
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
        if not self.u.mem_read(self.fp(hand) + 0x221E, 1)[0] & 2:
            return False
        if self.read(self.fp(target) + 0x1A58):
            return False
        self.write(self.fp(hand) + 0x1A58, target)
        self.write(self.fp(target) + 0x1A58, hand)
        self.u.mem_write(self.fp(target) + 0x221E, b"\x80")
        self.invoke("on_grab", hand)
        return True

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
        if index not in self.installed_hooks:
            self.u.mem_write(base, struct.pack(">" + "I" * len(words), *words))
            self.write(address, 0x48000000 | ((base - address) & 0x3FFFFFC))
            self.installed_hooks.add(index)
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
        self.u.emu_start(base, address + 4, count=100000)
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
        self.collisions()

    def collisions(self):
        # Deliberately no hurtbox overlap or collision awards. The v3 fixture
        # assumed overlap and missed the actual no-damage report.
        pass


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
        for forced, manual in ((False, False), (True, False), (False, True)):
            code, *_ = build(SETTINGS, forced, manual)
            self.assertLessEqual(len(code.splitlines()) * 8, 3256)

    def test_manual_build_keeps_the_working_v6_arrival_hook(self):
        text, _, symbols, _ = build(SETTINGS, manual=True)
        self.assertIn("C215A114", text)
        self.assertNotIn("C2150320", text)
        self.assertIn("sync_captured_fighter", symbols)
        self.assertIn("on_grab", symbols)

    def test_cpu_build_does_not_include_manual_capture_follow_helpers(self):
        _, _, symbols, _ = build(SETTINGS, manual=False)
        self.assertNotIn("attach_captured", symbols)
        self.assertNotIn("sync_captured_fighter", symbols)

    def test_manual_nametag_sync_reads_byte_sized_player_slot(self):
        _, runtime, symbols, _ = build(SETTINGS, manual=True)
        # Match Fighter_procPlayer: lbz r3,0x0c(r31), not lwz.
        slot_load = symbols["sync_captured_fighter"] + 0x28
        self.assertEqual(struct.unpack(">I", runtime[slot_load:slot_load + 4])[0],
                         0x887E000C)
        self.assertEqual(struct.unpack(">I", runtime[slot_load + 4:slot_load + 8])[0],
                         0x889E221F)

    def test_manual_empty_capture_skips_native_attachment(self):
        r = Runtime(manual=True)
        r.invoke("on_grab", r.MH)
        self.assertEqual(r.attachments, [])
        self.assertEqual(r.read(r.fp(r.MH) + 0x1A58), 0)

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
        self.assertEqual(r.moves[1], (r.MH, r.BASE + r.symbols["start_pair"],
                                    (44.0, 30.0, 0.0)))

    def test_manual_arrival_loader_preserves_gobj_and_resets_on_heap_recreation(self):
        r = Runtime(manual=True)
        r.u.mem_write(r.BASE, b"\0" * (len(r.code) + 16))
        r.run_hook(0, {3: r.CH})
        self.assertEqual(r.moves[-1], (r.MH, r.BASE + r.symbols["start_pair"],
                                     (44.0, 30.0, 0.0)))
        self.assertEqual(r.reg(3), r.CH)
        self.assertEqual(bytes(r.u.mem_read(r.BASE, len(r.code))), r.code)
        r.run_hook(1, {3: 0x80600000, 4: 0x81700000})
        r.run_hook(0, {3: r.CH})
        self.assertEqual(len(r.allocations), 2)
        self.assertEqual(r.reg(3), r.CH)

    def test_manual_animation_callback_registers_and_rearms_both_catches(self):
        r = Runtime(manual=True)
        r.invoke("start_pair", r.MH)
        for frame in (45, 46, 47, 74):
            for hand in (r.MH, r.CH):
                r.set_frame(hand, frame)
                r.invoke("tag_anim", hand)
            expected = int(46 <= frame < 74)
            for hand in (r.MH, r.CH):
                self.assertEqual(r.read(r.fp(hand) + 0x914), expected)
                self.assertEqual(bool(r.u.mem_read(r.fp(hand) + 0x221E, 1)[0] & 2),
                                 bool(expected))
        creates = [e for e in r.events if e[1] == "CREATE_HITBOX"]
        self.assertEqual([e[2] for e in creates], [r.MH, r.CH])
        resets = [e for e in r.events if e[1] == "RESET_HIT_VICTIMS"]
        self.assertEqual(len(resets), 4)

    def test_manual_capture_attaches_each_fighter_and_installs_position_callback(self):
        r = Runtime(manual=True)
        r.invoke("start_pair", r.MH)
        self.assertTrue(r.capture(r.MH, r.A))
        self.assertTrue(r.capture(r.MH, r.B))
        # US 1.00 ATTACH_VICTIM ABI: hand Fighter, then captured Fighter.
        self.assertEqual(r.attachments, [
            (r.fp(r.MH), r.fp(r.A)),
            (r.fp(r.MH), r.fp(r.B)),
        ])
        for victim in (r.A, r.B):
            self.assertEqual(r.read(r.fp(victim) + 0x21B0),
                             r.BASE + r.symbols["sync_captured_fighter"])

    def test_manual_capture_callback_updates_player_nametag_coordinates(self):
        r = Runtime(manual=True)
        cases = (
            (r.A, 0, 0, (12.5, 34.0, 0.0)),
            (r.B, 1, 1, (-22.0, 18.5, 0.0)),
        )
        for victim, slot, sub_fighter, position in cases:
            fp = r.fp(victim)
            r.u.mem_write(fp + 0x0C, bytes([slot]))
            r.u.mem_write(fp + 0x221F, bytes([0x08 if sub_fighter else 0]))
            r.u.mem_write(fp + 0xB0, struct.pack(">3f", *position))
            r.invoke("sync_captured_fighter", victim)
            self.assertEqual(r.follow_calls[-1], victim)
            self.assertIn((slot, sub_fighter), r.nametag_positions,
                          f"nametag calls were {r.nametag_positions}")
            self.assertEqual(r.nametag_positions[(slot, sub_fighter)], position)

    def test_manual_edition_keeps_v4_damage_audio_and_two_victim_release(self):
        for hand, damage in ((Runtime.MH, 42), (Runtime.CH, 51)):
            r = Runtime(manual=True)
            r.invoke("start_pair", r.MH)
            for obj in (r.MH, r.CH):
                r.set_frame(obj, 46)
                r.invoke("tag_anim", obj)
            r.capture(hand, r.A)
            r.capture(hand, r.B)
            r.finish_grab()
            for frame in range(SETTINGS["throw_frame"] + 1):
                r.squeeze_frame(frame)
            self.assertEqual(r.damage, {r.A: damage, r.B: damage})
            self.assertEqual(len(r.throws), 2)
            self.assertEqual(len([s for s in r.sounds if s[1] == 113]), 10)

    def test_combo_test_variant_always_selects_restored_move(self):
        r = Runtime(force_combo=True)
        for rng in range(4):
            r.rng = rng
            r.run_hook(0, {3: 377, 27: 5, 29: r.fp(r.CH)})
            self.assertEqual(r.reg(3), 380)

    def test_character_audio_requests_include_hand_bank(self):
        r = self.r
        r.run_hook(4, {3: 4, 5: 0, 6: 1 << 22})
        self.assertEqual(r.reg(5), 1)  # bank 32 in the high u64 mask
        self.assertEqual(r.reg(6), 1 << 22)
        r.run_hook(4, {3: 1, 5: 0, 6: 3})
        self.assertEqual(r.reg(5), 0)

    def test_release_occurs_during_downstroke_and_preserves_damage_until_then(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        r.capture(r.MH, r.A)
        r.capture(r.CH, r.B)
        r.finish_grab()
        for frame in range(212):
            r.squeeze_frame(frame)
        self.assertEqual(r.damage, {r.A: 30, r.B: 35})
        self.assertEqual(r.throws, [])
        self.assertEqual(r.read(r.fp(r.A) + 0x1A58), r.MH)
        self.assertEqual(r.read(r.fp(r.B) + 0x1A58), r.CH)
        self.assertEqual(r.read(r.fp(r.MH) + 0x1914), 7)
        self.assertEqual(r.read(r.fp(r.CH) + 0x1914), 7)
        self.assertEqual(r.read(r.fp(r.A) + 0x1918), 6)
        self.assertEqual(r.read(r.fp(r.B) + 0x1918), 7)
        r.squeeze_frame(212)
        self.assertEqual(r.damage, {r.A: 42, r.B: 51})
        self.assertEqual(len(r.throws), 2)

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
        for name, count in (("TAKE_DAMAGE", 10), ("APPLY_THROW", 2)):
            events = [e for e in r.events if e[1] == name]
            self.assertEqual(len(events), count)
            for mh, ch in zip(events[::2], events[1::2]):
                self.assertEqual(mh[0], ch[0], "both hands must act in the same callback")
                expected = (r.fp(r.A), r.fp(r.B)) if name == "TAKE_DAMAGE" else (r.MH, r.CH)
                self.assertEqual((mh[2], ch[2]), expected)
        self.assertEqual([s[1] for s in r.sounds], ["laugh"] + [113, 113, 0x4E212] * 5 + [9])
        self.assertTrue(all(s[2:] == (127, 64) for s in r.sounds))
        self.assertEqual(r.flowers, [(r.B, 7)] * 5)
        self.assertEqual(len(r.hit_effects), 10)

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

    def test_either_hand_can_keep_two_victims_and_damage_and_slam_both(self):
        for hand, direct in ((Runtime.MH, 42), (Runtime.CH, 51)):
            r = Runtime()
            r.invoke("start_pair", r.MH)
            self.assertTrue(r.capture(hand, r.A))
            self.assertTrue(r.u.mem_read(r.fp(hand) + 0x221E, 1)[0] & 2)
            # A following native grab scan can clear the hand's single pointer.
            r.write(r.fp(hand) + 0x1A58, 0)
            self.assertTrue(r.capture(hand, r.B))
            self.assertFalse(r.u.mem_read(r.fp(hand) + 0x221E, 1)[0] & 2)
            self.assertFalse(r.capture(r.CH if hand == r.MH else r.MH, r.A))
            r.finish_grab()
            for frame in range(SETTINGS["throw_frame"] + 1):
                r.squeeze_frame(frame)
            self.assertEqual(r.damage, {r.A: direct, r.B: direct})
            self.assertEqual(len(r.pummels), 10)
            self.assertEqual([(h, v) for h, v, _ in r.throws], [(hand, r.A), (hand, r.B)])
            events = [e for e in r.events if e[1] == "APPLY_THROW"]
            self.assertEqual(events[0][0], events[1][0])
            self.assertEqual(r.launches, [(r.A, 270, 0), (r.B, 270, 0)])
            for victim in (r.A, r.B):
                pos = struct.unpack(">3f", r.u.mem_read(r.fp(victim) + 0xB0, 12))
                self.assertEqual(pos, (25.0 if hand == r.MH else -25.0, 38.0, 0.0))
                self.assertEqual(r.read(r.fp(victim) + 0x21A8),
                                 r.BASE + r.symbols["slam_collision"])
            self.assertEqual(r.impacts, [])
            r.invoke("slam_collision", r.A)
            self.assertEqual(r.impacts, [])
            r.grounded.add(r.A)
            r.invoke("slam_collision", r.A)
            self.assertEqual(r.impacts, [r.A])
            self.assertEqual(r.launches[-1], (r.A, 90, 1))
            self.assertEqual(r.read(r.fp(r.A) + 0x21A8), 0x8008FE00)
            self.assertEqual(r.damage, {r.A: direct, r.B: direct})

    def test_hand_death_releases_both_victims_owned_by_that_hand(self):
        r = self.r
        r.invoke("start_pair", r.MH)
        r.capture(r.MH, r.A)
        r.capture(r.MH, r.B)
        r.write(r.fp(r.MH) + 0x10, 344)
        r.invoke("tag_anim", r.CH)
        self.assertEqual(r.cuts, [r.A, r.B])
        self.assertEqual(r.read(r.fp(r.MH) + 0x10), 344)
        self.assertEqual(r.read(r.fp(r.CH) + 0x10), 341)

    def test_packed_loader_roundtrip_reuse_and_heap_reset(self):
        r = self.r
        r.u.mem_write(r.BASE, b"\0" * (len(r.code) + 16))
        r.run_hook(2, {28: r.MH}, (0x2C, (44.0, 30.0, 0.0)))
        self.assertEqual(bytes(r.u.mem_read(r.BASE, len(r.code))), r.code)
        self.assertEqual(len(r.allocations), 1)
        self.assertEqual([e[1] for e in r.events if e[1] in ("FLUSH_CODE", "INVALIDATE_CODE")],
                         ["FLUSH_CODE", "INVALIDATE_CODE"])
        r.run_hook(2, {28: r.MH}, (0x2C, (44.0, 30.0, 0.0)))
        self.assertEqual(len(r.allocations), 1)
        r.run_hook(3, {3: 0x80600000, 4: 0x81700000})
        r.u.mem_write(r.BASE, b"\0" * (len(r.code) + 16))
        r.run_hook(2, {28: r.MH}, (0x2C, (44.0, 30.0, 0.0)))
        self.assertEqual(len(r.allocations), 2)
        self.assertEqual(bytes(r.u.mem_read(r.BASE, len(r.code))), r.code)


if __name__ == "__main__":
    unittest.main()
