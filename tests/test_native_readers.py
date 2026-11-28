"""Optional integration checks using the user's actual US 1.00 DOL instructions.

Set SSBM_MAIN_DOL to a local main.dol. No binary is included in the repository.
Collision detection, rendering, audio output, and full combat are not emulated.
"""

import json
import os
from pathlib import Path
import struct
import unittest

from tools.build_gecko import ROOT, FUNCTIONS, data_words
from tools.inspect_dol import inspect

try:
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_PPC32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import (UC_PPC_REG_0, UC_PPC_REG_PC, UC_PPC_REG_LR,
                                   UC_PPC_REG_MSR, UC_PPC_REG_FPR0)
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


DOL_PATH = os.environ.get("SSBM_MAIN_DOL")


@unittest.skipUnless(AVAILABLE and DOL_PATH, "requires Unicorn and SSBM_MAIN_DOL")
class NativeReaderTests(unittest.TestCase):
    OBJ, FP, EVENT, SCRIPT = 0x80900000, 0x80910000, 0x80940000, 0x80941000
    STACK, STOP = 0x81700000, 0x817FF000

    def setUp(self):
        data = Path(DOL_PATH).read_bytes()
        profile = json.loads((ROOT / "config/us-1.00.json").read_text())
        inspect(data, profile)
        from tools.inspect_dol import Dol
        dol = Dol(data)
        self.u = Uc(UC_ARCH_PPC, UC_MODE_PPC32 | UC_MODE_BIG_ENDIAN)
        self.u.mem_map(0x80000000, 0x1800000)
        for s in dol.sections:
            self.u.mem_write(s.address, data[s.offset:s.offset + s.size])
        self.u.reg_write(UC_PPC_REG_MSR, 0x2000)
        # SDA bases loaded by this DOL's startup at 80005348/80005350.
        self.u.reg_write(UC_PPC_REG_0 + 2, 0x804DD860)
        self.u.reg_write(UC_PPC_REG_0 + 13, 0x804D9520)
        self.write(self.OBJ + 0x2C, self.FP)
        self.write(self.FP, self.OBJ)
        self.write(self.FP + 0x38, 0x3F800000)
        self.write(self.FP + 0x5E8, 0x80920000)
        self.write(0x80920000 + 18 * 16, 0x80930000)
        self.write(0x804D9520 - 0x514C, 0x80950000)
        self.write(0x80950000 + 0x7E8, 400)
        self.write(0x80950000 + 0x7EC, 420)
        self.write(0x804D9520 - 0x3E70, 0)
        self.blobs = data_words(json.loads((ROOT / "config/restoration.json").read_text()))
        self.sounds = []
        self.hud = []
        self.moves = []
        self.u.hook_add(UC_HOOK_CODE, self.subcall)

    def read(self, addr):
        return struct.unpack(">I", self.u.mem_read(addr, 4))[0]

    def write(self, addr, value):
        self.u.mem_write(addr, struct.pack(">I", value))

    def subcall(self, u, address, _size, _data):
        # These services depend on match-wide state. The parser and all bitfield
        # reads run natively; damage scaling is identity in this isolated fixture.
        if address in (0x80076718, 0x800DEA6C, 0x80088F80, 0x800801B4):
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        elif address == FUNCTIONS["PLAY_SFX"]:
            self.sounds.append(tuple(u.reg_read(UC_PPC_REG_0 + i) for i in range(3, 7)))
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        elif address == 0x80024104:  # lbAudioAx native hit-SFX dispatch
            self.sounds.append(tuple(u.reg_read(UC_PPC_REG_0 + i) for i in range(3, 7)))
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        elif address in (0x80034398, 0x8003EC10, 0x800C88CC):
            if address == 0x80034398:
                self.hud.append(u.reg_read(UC_PPC_REG_0 + 5))
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        elif address in (FUNCTIONS["MASTER_MOVE"], FUNCTIONS["CRAZY_MOVE"]):
            obj, callback, ptr = (u.reg_read(UC_PPC_REG_0 + i) for i in (3, 4, 5))
            self.moves.append((obj, callback, struct.unpack(">3f", u.mem_read(ptr, 12))))
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        elif address == 0x8015BB10:  # native query of CH's requested team move
            u.reg_write(UC_PPC_REG_0 + 3, self.read(self.FP + 0x2250))
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        elif address == FUNCTIONS["ALLOC"]:
            u.reg_write(UC_PPC_REG_0 + 3, 0x81300000)
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))
        elif address in (FUNCTIONS["FLUSH_CODE"], FUNCTIONS["INVALIDATE_CODE"]):
            u.reg_write(UC_PPC_REG_PC, u.reg_read(UC_PPC_REG_LR))

    def call_native(self, address, registers, floats=None, count=20000):
        self.u.reg_write(UC_PPC_REG_0 + 1, self.STACK)
        self.u.reg_write(UC_PPC_REG_LR, self.STOP)
        for index, value in registers.items():
            self.u.reg_write(UC_PPC_REG_0 + index, value)
        for index, value in (floats or {}).items():
            bits = struct.unpack(">Q", struct.pack(">d", value))[0]
            self.u.reg_write(UC_PPC_REG_FPR0 + index, bits)
        self.u.emu_start(address, self.STOP, count=count)
        self.assertEqual(self.u.reg_read(UC_PPC_REG_PC), self.STOP)
        self.assertEqual(self.u.reg_read(UC_PPC_REG_0 + 1), self.STACK)

    def run_reader(self, name, words):
        self.u.mem_write(self.SCRIPT, struct.pack(">" + "I" * len(words), *words))
        self.write(self.EVENT + 8, self.SCRIPT)
        self.u.reg_write(UC_PPC_REG_0 + 1, self.STACK)
        self.u.reg_write(UC_PPC_REG_0 + 3, self.OBJ)
        self.u.reg_write(UC_PPC_REG_0 + 4, self.EVENT)
        self.u.reg_write(UC_PPC_REG_LR, self.STOP)
        address = name if isinstance(name, int) else FUNCTIONS[name]
        self.u.emu_start(address, self.STOP, count=10000)
        self.assertEqual(self.u.reg_read(UC_PPC_REG_PC), self.STOP)
        self.assertEqual(self.u.reg_read(UC_PPC_REG_0 + 1), self.STACK)

    def test_actual_pummel_decoder_sets_damage_element_and_victim_filter(self):
        for hand, damage, element in (("MH", 6, 0), ("CH", 7, 15)):
            self.run_reader("CREATE_HITBOX", self.blobs[f"PUMMEL_DATA_{hand}"])
            hb = self.FP + 0x914
            self.assertEqual(self.read(hb + 8), damage)
            self.assertEqual(self.read(hb + 0x30), element)
            self.assertEqual(self.read(hb + 0x48), 0x80930000)
            self.assertTrue(self.u.mem_read(hb + 0x134, 1)[0] & 0x80)

    def test_actual_grab_decoder_uses_widened_catch_sphere(self):
        for hand, index in (("MH", 5), ("CH", 1)):
            words = self.blobs[f"GRAB_DATA_{hand}"][index:index + 5] + [0]
            self.run_reader("CREATE_HITBOX", words)
            hb = self.FP + 0x914
            self.assertEqual(self.read(hb + 0x30), 8)
            radius = struct.unpack(">f", self.u.mem_read(hb + 0x1C, 4))[0]
            # The native multiplier is approximately 0.003906, not exact 1/256.
            self.assertAlmostEqual(radius, 24, places=2)

    def test_actual_throw_decoder_keeps_native_throw_knockback(self):
        for hand, damage, angle in (("MH", 12, 270), ("CH", 16, 270)):
            self.run_reader("SET_THROW_DATA", self.blobs[f"THROW_DATA_{hand}"])
            hb = self.FP + 0xDF4
            self.assertEqual(self.read(hb + 8), damage)
            self.assertEqual(self.read(hb + 0x20), angle)
            self.assertEqual(self.read(self.EVENT + 8), self.SCRIPT + 12)

    def test_actual_grab_sound_command_dispatches_to_play_sfx(self):
        self.run_reader(0x800719DC, self.blobs["GRAB_DATA_MH"][1:4])
        self.assertEqual(self.sounds, [(self.FP, 156, 127, 64)])
        self.assertEqual(self.read(self.EVENT + 8), self.SCRIPT + 12)

    def test_actual_native_damage_increases_percent_and_updates_hud_five_times(self):
        for amount in (6, 7):
            self.write(self.FP + 0x1830, 0)
            self.write(self.FP + 0x1A58, 0x80900100)
            self.hud.clear()
            for i in range(1, 6):
                self.call_native(FUNCTIONS["TAKE_DAMAGE"], {3: self.FP}, {1: amount})
                percent = struct.unpack(">f", self.u.mem_read(self.FP + 0x1830, 4))[0]
                self.assertEqual(percent, amount * i)
                self.assertEqual(self.read(self.FP + 0x1A58), 0x80900100)
            self.assertEqual(self.hud, [amount * i for i in range(1, 6)])

    def test_actual_hand_hit_sound_decodes_to_common_sound_113(self):
        for hand in ("MH", "CH"):
            self.run_reader("CREATE_HITBOX", self.blobs[f"PUMMEL_DATA_{hand}"])
            self.call_native(0x80005BB0, {3: self.FP + 0x914, 4: 0})
            self.assertEqual(self.sounds[-1][:3], (113, 127, 64))

    def test_actual_audio_request_marks_mhands_bank_without_marking_other_characters(self):
        from tools.build_gecko import assemble
        from tools.packed_runtime import helper_sources
        settings = json.loads((ROOT / "config/restoration.json").read_text())
        prefix, _, _ = assemble(helper_sources(0)[1], settings)
        # Run the emitted hook prefix and then the original DOL function + 4.
        entry = 0x81200000
        back = bytes.fromhex("3d808002618c6fb07d8903a64e800420")
        self.u.mem_write(entry, prefix[:-4] + back)
        for flags, expected in ((4, 1), (1, 0)):
            self.u.mem_write(0x80431804, b"\0" * (55 * 4))
            self.call_native(entry, {3: flags, 5: 0, 6: 0})
            self.assertEqual(self.read(0x80431804 + 32 * 4), expected)
            self.assertEqual(self.read(0x80431804 + 6 * 4), 0)

    def setup_manual_input(self):
        self.write(self.FP + 0x10C, 0x80960000)
        self.write(0x80960000 + 4, 0x80961000)
        for offset, value in ((0x11C, -44.0), (0x120, 30.0), (0x13C, 44.0), (0x140, 30.0)):
            self.u.mem_write(0x80961000 + offset, struct.pack(">f", value))

    def test_actual_4p_y_dpad_right_requests_tagtsukamu(self):
        self.setup_manual_input()
        self.write(0x804BFE2C + 0xCC, 0x0801)  # pad 4: Y + D-pad right
        self.call_native(0x80156158, {3: self.OBJ})
        self.assertEqual(self.read(self.FP + 0x2250), 380)
        self.assertEqual(self.moves, [(self.OBJ, 0x8015A114, (-44.0, 30.0, 0.0))])

    def install_manual_hooks(self):
        from tools.build_gecko import build
        settings = json.loads((ROOT / "config/restoration.json").read_text())
        text, core, symbols, _ = build(settings, manual=True)
        lines, cursor, index = text.splitlines(), 2, 0
        while lines[cursor].startswith("C2"):
            head, count = (int(v, 16) for v in lines[cursor].split())
            address, base = 0x80000000 | (head & 0x1FFFFFF), 0x81200000 + index * 0x10000
            words = [int(w, 16) for line in lines[cursor+1:cursor+1+count] for w in line.split()]
            last = base + 4 * (len(words) - 1)
            words[-1] = 0x48000000 | ((address + 4 - last) & 0x3FFFFFC)
            self.u.mem_write(base, struct.pack(">" + "I" * len(words), *words))
            self.write(address, 0x48000000 | ((base - address) & 0x3FFFFFC))
            cursor += count + 1
            index += 1
        return core, symbols

    def test_actual_3p_y_dpad_up_preserves_native_other_team_commands(self):
        self.setup_manual_input()
        self.install_manual_hooks()
        for request, callback, offset in ((377, 0x80154844, 0x124),
                                           (378, 0x80154998, 0x12C),
                                           (379, 0x80154B14, 0x134)):
            self.moves.clear()
            self.write(self.FP + 0x2250, request)
            self.u.mem_write(0x80961000 + offset, struct.pack(">2f", 44, 30))
            self.write(0x804BFE2C + 0x88, 0x0808)
            self.call_native(0x8014FF44, {3: self.OBJ})
            self.assertEqual(self.moves, [(self.OBJ, callback, (44.0, 30.0, 0.0))])


if __name__ == "__main__":
    unittest.main()
