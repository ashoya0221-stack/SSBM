"""US 1.00 native two-stage Human input -> MH movement -> pair initialization.

The actual DOL input handlers and movement callbacks execute as PPC. Rendering,
animation asset loading and stage simulation remain outside this fixture.
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
        self.states, self.registrations, self.allocations = [], [], []
        self.write(self.OBJ + 8, self.CH)
        self.write(self.CH + 0x2C, self.CHF)
        self.write(self.CHF, self.CH)
        self.write(0x804D56A4, 0x809A0000)
        self.write(0x809A0020, self.OBJ)

        # Normal Versus player table: P3 is Master Hand, P4 is Crazy Hand.
        for slot in range(4):
            player = 0x804510C0 + slot * 0xE90
            self.write(player + 8, 0)  # Human
            self.u.mem_write(player + 0x0C, b"\0")  # active transformed slot
            self.write(player + 0xB0, 0)
        self.write(0x804510C0 + 2 * 0xE90 + 0xB0, self.OBJ)
        self.write(0x804510C0 + 3 * 0xE90 + 0xB0, self.CH)

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
        self.code, self.symbols = self.install_manual_hooks()

    def subcall(self, u, address, size, data):
        from unicorn.ppc_const import (UC_PPC_REG_0, UC_PPC_REG_PC, UC_PPC_REG_LR)
        if not hasattr(self, "states"):
            return native.NativeReaderTests.subcall(self, u, address, size, data)
        if address in (FUNCTIONS["MASTER_MOVE"], FUNCTIONS["CRAZY_MOVE"]):
            obj, callback, ptr = (u.reg_read(UC_PPC_REG_0 + i) for i in (3, 4, 5))
            self.moves.append((obj, callback, struct.unpack(">3f", u.mem_read(ptr, 12))))
            return  # execute the original movement-registration function
        if address == 0x8015BB10:
            return  # execute the original CH request lookup
        if address == FUNCTIONS["INIT_GRAB"]:
            self.registrations.append(tuple(u.reg_read(UC_PPC_REG_0 + i)
                                            for i in (3, 4, 5, 7)))
            return  # execute native acceptance flag, mask and callback registration
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
        else:
            if address == FUNCTIONS["ALLOC"]:
                self.allocations.append(u.reg_read(UC_PPC_REG_0 + 3))
            native.NativeReaderTests.subcall(self, u, address, size, data)

    def request_crazy(self, buttons=0x0801):
        # 4P Y + D-pad Left enters CH's actual Human input path.
        self.write(0x804BFE2C + 0xCC, buttons)
        self.call_native(0x80155A84, {3: self.CH}, count=200000)

    def request_master(self, buttons=0x0808):
        # P3 Y + D-pad Up (0x0808) is the partner-request branch:
        # while held, MH reads CH's request through 0x8015BB10 and,
        # for request 380, reaches the hook at 0x80150320.
        self.write(0x804BFE2C + 0x88, buttons)
        self.call_native(0x8014FF44, {3: self.OBJ}, count=200000)

    def crazy_arrives(self):
        self.write(self.CHF + 0x2358, 0)
        self.call_native(0x8015B284, {3: self.CH}, count=200000)

    def master_arrives(self):
        self.write(self.FP + 0x2358, 0)
        self.call_native(0x80150678, {3: self.OBJ}, count=200000)

    def test_two_stage_4p_then_3p_human_input_reaches_both_native_grab_initializers(self):
        self.request_crazy()
        self.assertEqual(self.read(self.CHF + 0x2250), 380)
        self.assertEqual(self.read(self.CHF + 0x10), 388)
        self.crazy_arrives()
        self.assertEqual(self.read(self.CHF + 0x10), 384)
        self.assertEqual(self.read(self.FP + 0x10), 341)
        self.assertEqual(len(self.moves), 1)  # CH only: 4P input does not auto-start MH
        self.assertEqual(self.read(0x804BFE2C + 0x88), 0)

        self.request_master(0x0808)  # Hold 3P Y + D-pad Up while CH request 380 is pending.
        # This branch reads CH's request directly. It does not set MH's own
        # request field or enter the separate native action-373 path.
        self.assertEqual(len(self.moves), 2)
        self.assertEqual(self.moves[1],
                         (self.OBJ, self.CORE + self.symbols["start_pair"], (44, 30, 0)))

        self.master_arrives()
        self.assertEqual((self.read(self.FP + 0x10), self.read(self.CHF + 0x10)), (385, 380))
        self.assertEqual([(fp, mask, grabbed) for fp, mask, _, grabbed in self.registrations],
                         [(self.CHF, 256, 0x8015AB94), (self.FP, 128, 0x801550D8)])
        for fp in (self.FP, self.CHF):
            self.assertTrue(self.u.mem_read(fp + 0x221E, 1)[0] & 2)
            self.assertEqual(self.read(fp + 0x2190), self.CORE + self.symbols["on_grab"])
        self.assertEqual(bytes(self.u.mem_read(self.CORE, len(self.code))), self.code)

    def test_3p_y_up_does_not_start_without_ch_request_380(self):
        self.request_master(0x0808)
        self.assertFalse(any(obj == self.OBJ for obj, _, _ in self.moves))

    def test_other_three_4p_requests_do_not_trigger_the_tagtsukamu_master_branch(self):
        for buttons, requested in ((0x0808, 377), (0x0802, 378), (0x0804, 379)):
            with self.subTest(request=requested):
                self.setUp()
                self.request_crazy(buttons)
                self.assertEqual(self.read(self.CHF + 0x2250), requested)
                self.crazy_arrives()
                previous_moves = len(self.moves)
                self.request_master(0x0808)
                expected_callbacks = {377: 0x80154844, 378: 0x80154998, 379: 0x80154B14}
                self.assertEqual(len(self.moves), previous_moves + 1)
                self.assertEqual(self.moves[-1][0], self.OBJ)
                self.assertEqual(self.moves[-1][1], expected_callbacks[requested])
                self.assertEqual(self.registrations, [])
