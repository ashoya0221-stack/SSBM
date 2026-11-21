#!/usr/bin/env python3
"""Read a DOL, verify the research baseline, and report mapped addresses.

This tool never modifies its input and does not generate a cheat code.
"""

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys


@dataclass(frozen=True)
class Section:
    kind: str
    offset: int
    address: int
    size: int


class Dol:
    def __init__(self, data):
        self.data = data
        if len(data) < 0x100:
            raise ValueError("DOL header is truncated")
        self.sections = []
        for index in range(18):
            offset, address, size = (
                struct.unpack_from(">I", data, base + index * 4)[0]
                for base in (0, 0x48, 0x90)
            )
            if not size:
                continue
            if offset < 0x100 or offset + size > len(data):
                raise ValueError(f"section {index} is outside the file")
            if address + size > 0x100000000:
                raise ValueError(f"section {index} wraps its memory address")
            section = Section("text" if index < 7 else "data", offset, address, size)
            for other in self.sections:
                for start, old_start in (
                    (offset, other.offset), (address, other.address)
                ):
                    if start < old_start + other.size and old_start < start + size:
                        raise ValueError(f"section {index} overlaps another section")
            self.sections.append(section)
        self.entry = struct.unpack_from(">I", data, 0xE0)[0]
        if not any(s.kind == "text" and s.address <= self.entry < s.address + s.size
                   for s in self.sections):
            raise ValueError("entry point is outside the text sections")

    def file_offset(self, address, size=1):
        if size <= 0:
            raise ValueError("read size must be positive")
        for section in self.sections:
            if section.address <= address and address + size <= section.address + section.size:
                return section.offset + address - section.address
        raise ValueError(f"address 0x{address:08x} is not backed by a DOL section")

    def read(self, address, size):
        offset = self.file_offset(address, size)
        return self.data[offset:offset + size]


def inspect(data, profile):
    dol = Dol(data)
    sha256 = hashlib.sha256(data).hexdigest()
    if sha256 != profile["sha256"]:
        raise ValueError(
            f"unsupported DOL SHA-256: {sha256}; this profile only describes "
            "the supplied research baseline"
        )
    checks = []
    for check in profile["checks"]:
        address = int(check["address"], 16)
        expected = bytes.fromhex(check["expected"])
        if dol.read(address, len(expected)) != expected:
            raise ValueError(f"byte check failed: {check['name']}")
        checks.append({"name": check["name"], "address": check["address"],
                       "file_offset": f"0x{dol.file_offset(address):08x}"})
    motion_rows = {}
    for hand, count in (("master", 50), ("crazy", 49)):
        base = int(profile["addresses"][f"{hand}_action_table"], 16)
        motion_rows[hand] = []
        for index in range(count):
            row = struct.unpack(">8I", dol.read(base + index * 32, 32))
            motion_rows[hand].append({
                "action_id": 341 + index, "motion_id": row[0],
                "anim_callback": f"0x{row[3]:08x}"
            })
    return {"baseline": profile["name"], "sha256": sha256,
            "size_bytes": len(data), "entry": f"0x{dol.entry:08x}",
            "checks": checks, "addresses": profile["addresses"],
            "motion_state_rows": motion_rows,
            "patch_status": "not_implemented"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dol", type=Path)
    parser.add_argument("--profile", type=Path, default=(
        Path(__file__).resolve().parents[1] / "config" / "us-1.00.json"))
    args = parser.parse_args()
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        report = inspect(args.dol.read_bytes(), profile)
    except (OSError, ValueError, KeyError, struct.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
