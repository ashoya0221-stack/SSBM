"""Normal-Versus P3/P4 input -> native movement and grab initialization.

Animation loading and state application are isolated. Manual hand lookup is
resolved through ordinary player slots, not a debug/boss fighter-list fixture.
"""

import struct
import unittest

import test_native_readers as native
from tools.build_gecko import FUNCTIONS


@unittest.skipUnless(native.AVAILABLE and native.DOL_PATH, "requires Unicorn and SSBM_MAIN_DOL")
class NativeStartupTests(unittest.TestCase):
    OBJ, FP, EVENT, SCRIPT = (native.NativeReaderTests.OBJ, native.NativeReaderTests.FP,
                              native.NativeReaderTests.EVENT, native.NativeReaderTests.SCRIPT)
    STACK, STOP = native.NativeReaderTests.STACK, native.NativeReaderTests.STOP
    read, write, call_native = (native.NativeReaderTests.read, native.NativeReaderTests.write,
                                native.NativeReaderTests.call_native)
    install_manual_hooks = native.NativeReaderTests.install_manual_hooks
    CH, CHF, CORE = 0x80900100, 0x80970000, 0x81300000

    def setUp(self):
        native.NativeReaderTests.setUp(self)
        self.states, self.registrations, self.allocations, self.aborts = [], [], [], []
        # Ordinary Versus slots are zero-based: P3 (Master Hand) = 2,
        # P4 (Crazy Hand) = 3. No debug/boss fighter-list is constructed.
        self.player_entities = {2: self.OBJ, 3: self.CH}
        self.player_slot_queries = []
        for obj, fp, kind, player, dat, attrs, motions in (
                (self.OBJ, self.FP, 27, 2, 0x80960000, 0x80961000, 0x80962000),
                (self.CH, self.CHF, 28, 3, 0x80980000, 0x80981000, 0x80982000)):
            self.write(fp + 4, kind)
            self.u.mem_write(fp + 0xC, bytes([player]))
            self.write(fp + 0x10, 341)
            self.write(fp + 0x2258, 341)
            self.write(fp + 0x10C, dat)
            self.write(dat + 4, attrs)
            self.write(dat + 12, motions)
            for offset, xy in ((0x11C, (-44, 30)), (0x13C, (44, 30))):
                self.u.mem_write(attrs + offset, struct.pack(">2f", *xy))
        for slot in range(4):
            self.write(0x804510C0 + slot * 0xE90 + 8, 0)  # all Human
        self.code, self.symbols = self.install_manual_hooks()

    def subcall(self, u, address, size, data):
        from unicorn.ppc_const import (UC_PPC_REG_0, UC_PPC_REG_PC, UC_PPC_REG_LR)
        if not hasattr(self, "states"):
            return native.NativeReaderTests.subcall(self, u, address, size, data)
        if address == FUNCTIONS["PLAYER_GET_ENTITY"]:
            slot = u.reg_read(UC_PPC_REG_0 + 3)
            self.player_slot_queries.append(slot)
            u.reg_write(UC_PPC_REG_0 + 3, self.player_entities.get(slot, 0))
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
            return
        elif address in (FUNCTIONS["MASTER_MOVE"], FUNCTIONS["CRAZY_MOVE"]):
            obj, callback, ptr = (u.reg_read(UC_PPC_REG_0 + i) for i in (3, 4, 5))
            self.moves.append((obj, callback, struct.unpack(">3f", u.mem_read(ptr, 12))))
            return  # actual native movement registration executes
        if address == 0x8015BB10:
            return  # actual requested-move query traverses the fighter list
        if address == FUNCTIONS["INIT_GRAB"]:
            self.registrations.append(tuple(u.reg_read(UC_PPC_REG_0 + i)
                                            for i in (3, 4, 5, 7)))
            return  # actual acceptance flag, mask and callbacks are installed
        if address == FUNCTIONS["CHANGE_STATE"]:
            obj, action = (u.reg_read(UC_PPC_REG_0 + i) for i in (3, 4))
            self.write(self.read(obj + 0x2C) + 0x10, action)
            self.states.append((obj, action))
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        elif address == FUNCTIONS["ANIM_INIT"]:
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        elif address == FUNCTIONS["ANIM_REMAINING"]:
            u.reg_write(UC_PPC_REG_0 + 3, 1)
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        elif address == FUNCTIONS["CRAZY_IDLE"]:
            self.aborts.append(u.reg_read(UC_PPC_REG_0 + 3))
            self.write(self.CHF + 0x10, 341)
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        else:
            if address == FUNCTIONS["ALLOC"]:
                self.allocations.append(u.reg_read(UC_PPC_REG_0 + 3))
            native.NativeReaderTests.subcall(self, u, address, size, data)

    def request(self, buttons=0x801):
        # Run CH's actual idle animation callback, including the Human/CPU slot
        # branch and its call to the original 4P input routine.
        self.write(0x804BFE2C + 0xCC, buttons)
        self.call_native(0x80155A84, {3: self.CH}, count=200000)

    def crazy_arrives(self):
        self.write(self.CHF + 0x2358, 0)  # movement physics has reached its target
        self.call_native(0x8015B284, {3: self.CH}, count=200000)

    def master_arrives(self):
        self.write(self.FP + 0x2358, 0)
        self.call_native(0x80150678, {3: self.OBJ}, count=200000)

    def test_4p_human_input_alone_reaches_both_native_grab_initializers(self):
        self.request()
        self.assertEqual(self.read(self.CHF + 0x2250), 380)
        self.assertEqual(self.read(self.CHF + 0x10), 388)
        self.crazy_arrives()
        self.assertEqual(self.read(self.CHF + 0x10), 384)
        self.assertEqual(self.read(self.FP + 0x10), 389)
        self.assertIn(2, self.player_slot_queries)  # P3 Master Hand
        self.assertEqual(self.read(0x804BFE2C + 0x88), 0)  # no 3P input at all
        self.assertEqual(self.moves, [(self.CH, 0x8015A114, (-44, 30, 0)),
                                      (self.OBJ, self.CORE + self.symbols["start_pair"],
                                       (44, 30, 0))])
        self.master_arrives()
        self.assertEqual((self.read(self.FP + 0x10), self.read(self.CHF + 0x10)), (385, 380))
        self.assertEqual([(fp, mask, grabbed) for fp, mask, _, grabbed in self.registrations],
                         [(self.CHF, 256, 0x8015AB94), (self.FP, 128, 0x801550D8)])
        for fp in (self.FP, self.CHF):
            self.assertTrue(self.u.mem_read(fp + 0x221E, 1)[0] & 2)
            self.assertEqual(self.read(fp + 0x2190), self.CORE + self.symbols["on_grab"])
        self.assertEqual(bytes(self.u.mem_read(self.CORE, len(self.code))), self.code)

    def test_busy_master_is_retried_before_entering_crazy_wait(self):
        self.write(self.FP + 0x10, 349)
        self.request()
        self.crazy_arrives()
        self.assertEqual(self.read(self.CHF + 0x10), 388)
        self.assertEqual(len(self.moves), 1)
        self.write(self.FP + 0x10, 341)  # the other attack finishes
        self.crazy_arrives()
        self.assertEqual(len(self.moves), 2)
        self.master_arrives()
        self.assertEqual(len(self.registrations), 2)
        self.assertEqual(len(self.allocations), 1)  # cold and cached loader preserve r3

    def test_other_requests_keep_native_wait_without_automatic_master_start(self):
        for buttons, request in ((0x808, 377), (0x802, 378), (0x804, 379)):
            with self.subTest(request=request):
                self.setUp()
                self.request(buttons)
                self.crazy_arrives()
                self.assertEqual(self.read(self.CHF + 0x2250), request)
                self.assertEqual(self.read(self.CHF + 0x10), 384)
                self.assertEqual(len(self.moves), 1)
                self.assertEqual(self.registrations, [])

    def test_cached_loader_accepts_a_later_taggrab_request(self):
        self.request(0x808)
        self.crazy_arrives()
        self.request()
        self.crazy_arrives()
        self.master_arrives()
        self.assertEqual(len(self.allocations), 1)
        self.assertEqual(len(self.registrations), 2)

    def test_missing_master_slot_returns_crazy_to_idle(self):
        self.player_entities.pop(2)
        self.request()
        self.crazy_arrives()
        self.assertEqual(self.aborts, [self.CH])
        self.assertEqual(self.registrations, [])

    def test_dead_or_sleeping_master_does_not_start_the_pair(self):
        for action, sleeping in ((344, 0), (345, 0), (341, 0x10)):
            with self.subTest(action=action, sleeping=sleeping):
                self.setUp()
                self.write(self.FP + 0x10, action)
                self.u.mem_write(self.FP + 0x221F, bytes([sleeping]))
                self.request()
                self.crazy_arrives()
                self.assertEqual(self.aborts, [self.CH])
                self.assertEqual(self.registrations, [])
