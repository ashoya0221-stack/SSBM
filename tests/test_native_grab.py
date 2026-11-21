"""Actual US 1.00 catch decoding, overlap, filtering and grab dispatch.

Uses local DOL instructions. Rendering, stage geometry, animation loading and
capture attachment are isolated services; this is not a Dolphin gameplay test.
"""

import json
import struct
import unittest

import test_native_readers as native
from tools.build_gecko import ROOT, FUNCTIONS, build


@unittest.skipUnless(native.AVAILABLE and native.DOL_PATH, "requires Unicorn and SSBM_MAIN_DOL")
class NativeGrabTests(unittest.TestCase):
    OBJ, FP, EVENT, SCRIPT = (native.NativeReaderTests.OBJ, native.NativeReaderTests.FP,
                              native.NativeReaderTests.EVENT, native.NativeReaderTests.SCRIPT)
    STACK, STOP = native.NativeReaderTests.STACK, native.NativeReaderTests.STOP
    BASE = 0x81300000
    read, write, call_native = (native.NativeReaderTests.read, native.NativeReaderTests.write,
                                native.NativeReaderTests.call_native)

    def setUp(self):
        native.NativeReaderTests.setUp(self)
        self.visited = set()
        self.captures = []
        settings = json.loads((ROOT / "config/restoration.json").read_text())
        _, code, self.symbols, _ = build(settings, manual=True)
        self.u.mem_write(self.BASE, code)
        self.victims = (0x80900200, 0x80900300)
        self.fps = (0x80970000, 0x80980000)
        self.write(self.FP + 4, 27)
        self.write(self.FP + 0x10, 385)
        self.byte(self.FP + 0xC, 2)
        self.byte(self.FP + 0x61B, 1)
        self.write(self.FP + 0x3C, 0x3F800000)
        self.write(0x804D56A4, 0x809A0000)
        self.write(0x809A0020, self.victims[0])
        self.write(self.victims[0] + 8, self.victims[1])
        self.byte(0x804696D8 + 0x24D0, 1)  # teams on
        self.byte(0x804696D8 + 0x24C9, 0)  # friendly fire off
        for slot in range(4):
            self.write(0x804510C0 + slot * 0xE90 + 8, 0)  # all Human
        for index, (obj, fp) in enumerate(zip(self.victims, self.fps)):
            self.write(obj + 0x2C, fp)
            self.write(fp, obj)
            self.byte(fp + 0xC, index)
            self.byte(fp + 0x61B, 0)  # victims share a team, unlike the hand
            self.write(fp + 0x38, 0x3F800000)
            self.write(fp + 0x3C, 0x3F800000)
            self.byte(fp + 0x119E, 1)
            self.write(fp + 0x11E8, 1)  # grabbable hurt capsule
            self.write(fp + 0x11BC, 0x40A00000)  # radius 5
            self.write(fp + 0x11C0, 0x809B0000 + index * 0x100)
            self.byte(fp + 0x11C4, 0x80)  # world endpoints already current
            self.u.mem_write(fp + 0x11C8, struct.pack(">6f", 0, 5, 0, 0, 10, 0))
            self.u.mem_write(0x809B0044 + index * 0x100,
                             struct.pack(">12f", 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0))
        self.call_native(FUNCTIONS["INIT_GRAB"],
                         {3: self.FP, 4: 128,
                          5: self.BASE + self.symbols["on_grab"], 6: 0, 7: 0x801550D8})
        # Avoid dependencies on fighter-specific grab voice tables.
        self.byte(self.FP + 0x2225, 0x40)

    def byte(self, address, value):
        self.u.mem_write(address, bytes([value]))

    def subcall(self, u, address, size, data):
        from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_PC, UC_PPC_REG_LR
        if not hasattr(self, "visited"):
            return native.NativeReaderTests.subcall(self, u, address, size, data)
        self.visited.add(address)
        # Stage visibility and match bookkeeping are external to this fixture.
        # Catch sphere/capsule overlap, masks, team rules and grab callbacks run
        # from the DOL; no hook writes a candidate into the hand's victim field.
        isolated = {0x80084A3C, 0x80078348, 0x8007D8BC, 0x80097260,
                    0x800DCD1C, 0x800DA3D8, 0x800DAF1C,
                    FUNCTIONS["ANIM_INIT"], 0x80007D68}
        if address in isolated:
            if address == 0x80084A3C:
                u.reg_write(UC_PPC_REG_0 + 3, 0)
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        elif address == 0x80341178:  # PSMTXMultVec: Unicorn lacks paired singles
            matrix, vector, out = (u.reg_read(UC_PPC_REG_0 + i) for i in (3, 4, 5))
            m = struct.unpack(">12f", u.mem_read(matrix, 48))
            v = struct.unpack(">3f", u.mem_read(vector, 12)) + (1,)
            u.mem_write(out, struct.pack(">3f", *(sum(m[row * 4 + j] * v[j]
                                                   for j in range(4)) for row in range(3))))
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        elif address == FUNCTIONS["CHANGE_STATE"]:
            obj, action = (u.reg_read(UC_PPC_REG_0 + i) for i in (3, 4))
            self.write(self.read(obj + 0x2C) + 0x10, action)
            self.captures.append((obj, action))
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        else:
            native.NativeReaderTests.subcall(self, u, address, size, data)

    def tick(self, frame):
        self.u.mem_write(self.FP + 0x894, struct.pack(">f", frame))
        self.call_native(self.BASE + self.symbols["manual_grab_tick"], {3: self.OBJ})
        # CollPos normally derives these endpoints from the animated joint.
        # Supply its output here; the real capsule overlap itself is executed.
        hb = self.FP + 0x914
        self.u.mem_write(hb + 0x4C, struct.pack(">6f", 0, 0, 0, 0, 0, 0))
        self.call_native(0x8006C904, {3: self.OBJ}, count=200000)

    def test_two_opponents_caught_by_native_scan_without_script_execution(self):
        self.tick(45)
        self.assertEqual(self.captures, [])
        self.tick(46)
        # The native scan remembers both overlaps but accepts only one. A
        # second native scan without rearming reproduces the old exclusion.
        history = [self.read(self.FP + 0x914 + 0x74 + 8 * i) for i in range(12)]
        self.assertTrue(all(fp in history for fp in self.fps))
        self.call_native(0x8006C904, {3: self.OBJ}, count=200000)
        self.assertEqual(len(self.captures), 1)
        self.tick(47)
        self.assertEqual(self.captures, [(obj, 327) for obj in self.victims])
        for fp in self.fps:
            self.assertEqual(self.read(fp + 0x1A58), self.OBJ)
            self.assertEqual(struct.unpack(">H", self.u.mem_read(fp + 0x1A6A, 2))[0], 511)
        slots = self.BASE + self.symbols["victim_slots"]
        self.assertEqual((self.read(slots), self.read(slots + 4)), self.victims)
        self.tick(48)
        self.assertEqual(len(self.captures), 2)
        self.assertEqual(self.read(self.FP + 0x914), 0)
        self.assertIn(0x80007ECC, self.visited)
        self.assertIn(0x80006E58, self.visited)
        from unicorn.ppc_const import UC_PPC_REG_0
        for slot in range(4):
            self.call_native(0x8003239C, {3: slot})
            self.assertEqual(self.u.reg_read(UC_PPC_REG_0 + 3), 0)

    def test_crazy_hand_also_catches_two_human_opponents(self):
        self.write(self.FP + 4, 28)
        self.write(self.FP + 0x10, 380)
        self.byte(self.FP + 0xC, 3)
        self.call_native(FUNCTIONS["INIT_GRAB"],
                         {3: self.FP, 4: 256,
                          5: self.BASE + self.symbols["on_grab"], 6: 0, 7: 0x8015AB94})
        self.tick(46)
        self.tick(47)
        self.assertEqual(self.captures, [(obj, 336) for obj in self.victims])
        for fp in self.fps:
            self.assertEqual(self.read(fp + 0x1A58), self.OBJ)
        slots = self.BASE + self.symbols["victim_slots"] + 8
        self.assertEqual((self.read(slots), self.read(slots + 4)), self.victims)

    def test_catch_recovers_if_acceptance_and_script_hitbox_are_missing(self):
        self.byte(self.FP + 0x221E, 0)
        self.tick(52)
        self.tick(53)
        self.assertEqual(self.captures, [(obj, 327) for obj in self.victims])

    def test_airborne_opponents_are_capturable_too(self):
        for fp in self.fps:
            self.write(fp + 0xE0, 1)
        self.tick(46)
        self.tick(47)
        self.assertEqual(len(self.captures), 2)

    def test_native_filters_reject_teammates_and_invulnerable_opponents(self):
        self.byte(self.fps[0] + 0x61B, 1)
        self.write(self.fps[1] + 0x1988, 1)
        self.tick(46)
        self.tick(47)
        self.assertEqual(self.captures, [])

    def test_native_overlap_does_not_catch_a_distant_opponent(self):
        for fp in self.fps:
            self.u.mem_write(fp + 0x11C8, struct.pack(">6f", 100, 5, 0, 100, 10, 0))
        self.tick(46)
        self.assertEqual(self.captures, [])

    def test_end_of_window_clears_native_catch_and_acceptance(self):
        for fp in self.fps:
            self.write(fp + 0x1988, 1)
        self.tick(73)
        self.assertNotEqual(self.read(self.FP + 0x914), 0)
        self.tick(74)
        self.assertEqual(self.read(self.FP + 0x914), 0)
        self.assertFalse(self.u.mem_read(self.FP + 0x221E, 1)[0] & 2)


if __name__ == "__main__":
    unittest.main()
