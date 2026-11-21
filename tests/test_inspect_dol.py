import hashlib
import struct
import unittest

from tools.inspect_dol import Dol, inspect


def sample_dol():
    data = bytearray(0x140)
    for base, value in ((0, 0x100), (0x48, 0x80003100),
                        (0x90, 0x20), (0xE0, 0x80003100)):
        struct.pack_into(">I", data, base, value)
    data[0x100:0x104] = bytes.fromhex("4e800020")
    return data


class DolTests(unittest.TestCase):
    def test_maps_only_file_backed_addresses(self):
        dol = Dol(sample_dol())
        self.assertEqual(dol.file_offset(0x80003100), 0x100)
        self.assertEqual(dol.read(0x80003100, 4), bytes.fromhex("4e800020"))
        for address, size in ((0x800030FF, 1), (0x80003120, 1), (0x8000311F, 2)):
            with self.subTest(address=address, size=size), self.assertRaises(ValueError):
                dol.read(address, size)

    def test_rejects_truncated_header_and_section(self):
        with self.assertRaises(ValueError):
            Dol(bytes(0xFF))
        data = sample_dol()
        struct.pack_into(">I", data, 0x90, 0x41)
        with self.assertRaises(ValueError):
            Dol(data)

    def test_rejects_overlapping_memory_sections(self):
        data = sample_dol()
        for base, value in ((4, 0x120), (0x4C, 0x80003110), (0x94, 0x20)):
            struct.pack_into(">I", data, base, value)
        with self.assertRaises(ValueError):
            Dol(data)

    def test_rejects_non_executable_entry_point(self):
        data = sample_dol()
        struct.pack_into(">I", data, 0xE0, 0x80004000)
        with self.assertRaises(ValueError):
            Dol(data)

    def test_verifies_hash_and_instruction_check(self):
        data = sample_dol()
        # Include two full motion tables so the report can inspect their entries.
        data.extend(bytes(50 * 32 + 49 * 32))
        for base, value in ((28, 0x140), (0x64, 0x80300000),
                            (0xAC, 99 * 32)):
            struct.pack_into(">I", data, base, value)
        struct.pack_into(">8I", data, 0x140, 295, 0, 0, 0x80003100, 0, 0, 0, 0)
        profile = {"name": "synthetic", "sha256": hashlib.sha256(data).hexdigest(),
                   "checks": [{"name": "return", "address": "0x80003100",
                               "expected": "4e800020"}],
                   "addresses": {"master_action_table": "0x80300000",
                                 "crazy_action_table": "0x80300640"}}
        report = inspect(data, profile)
        self.assertEqual(report["checks"][0]["file_offset"], "0x00000100")
        self.assertEqual(report["motion_state_rows"]["master"][0], {
            "action_id": 341, "motion_id": 295, "anim_callback": "0x80003100"})
        profile["checks"][0]["expected"] = "60000000"
        with self.assertRaises(ValueError):
            inspect(data, profile)
        profile["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            inspect(data, profile)


if __name__ == "__main__":
    unittest.main()
