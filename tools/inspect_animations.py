#!/usr/bin/env python3
"""Read FigaTree timing from local AJ archives; never extract or modify assets."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

try:
    from .fighter_dat import FighterDat
except ImportError:
    from fighter_dat import FighterDat


AJ_HASHES = {
    "master": "c4328c24095f52b1ff820debfb8d7a01f6dd27ac7b0f1a11d28b9a113a3e86b4",
    "crazy": "5a2853c166b191bb9b01c182d65ab7a62f88b1f3b9c07f178821389c0d0d08b8",
}


def decode_keys(stream, start, value_fraction, slope_fraction):
    """FigaTrack little-endian values and variable-length time deltas.

    This is a timing reader, not an interpolation or rendering implementation.
    See doldecomp/melee src/sysdolphin/baselib/fobj.c for the native format.
    """
    cursor, frame, result = 0, start, []

    def byte():
        nonlocal cursor
        if cursor >= len(stream):
            raise ValueError("truncated animation track")
        value = stream[cursor]
        cursor += 1
        return value

    def integer():
        value, shift = 0, 0
        while shift < 35:
            part = byte()
            value |= (part & 127) << shift
            if not part & 128:
                return value
            shift += 7
        raise ValueError("oversized animation time delta")

    def scalar(fraction):
        nonlocal cursor
        formats = {0: "<f", 0x20: "<h", 0x40: "<H", 0x60: "<b", 0x80: "<B"}
        fmt = formats.get(fraction & 0xE0)
        if fmt is None or ((fraction & 0xE0) == 0 and fraction != 0):
            raise ValueError("unsupported animation scalar encoding")
        size = struct.calcsize(fmt)
        if cursor + size > len(stream):
            raise ValueError("truncated animation value")
        value = struct.unpack_from(fmt, stream, cursor)[0]
        cursor += size
        value /= 2 ** (fraction & 31)
        if not math.isfinite(value):
            raise ValueError("nonfinite animation value")
        return value

    while cursor < len(stream):
        header = byte()
        opcode, count, shift = header & 15, ((header >> 4) & 7) + 1, 3
        while header & 128:
            header = byte()
            count += (header & 127) << shift
            shift += 7
            if shift > 35:
                raise ValueError("oversized animation packet")
        if opcode not in (1, 2, 3, 4, 5, 6):
            raise ValueError("unsupported animation opcode")
        for _ in range(count):
            if opcode == 5:
                scalar(slope_fraction)
                continue
            value = scalar(value_fraction)
            if opcode == 4:
                scalar(slope_fraction)
            result.append((frame, value))
            if cursor < len(stream):
                frame += integer()
    return result


def read_animation(aj, motion):
    offset, length = motion["animation_offset"], motion["animation_size"]
    archive = aj[offset:offset + length]
    if len(archive) != length or length < 0x20:
        raise ValueError("animation outside AJ archive")
    size, data_size, relocations, publics, externals = struct.unpack_from(">5I", archive)
    roots = 0x20 + data_size + 4 * relocations
    if size != length or publics != 1 or roots + 8 * (publics + externals) > size:
        raise ValueError("invalid animation archive header")
    data = archive[0x20:0x20 + data_size]
    root = struct.unpack_from(">I", archive, roots)[0]
    _, _, duration, nodes, cursor = struct.unpack_from(">IIfII", data, root)
    tracks = {}
    bone = 0
    while nodes + bone < len(data) and data[nodes + bone] != 255:
        for _ in range(data[nodes + bone]):
            size, start, kind, vf, sf, _, pointer = struct.unpack_from(">HHBBBBI", data, cursor)
            cursor += 12
            if pointer + size > len(data):
                raise ValueError("animation track outside data section")
            tracks[bone, kind] = decode_keys(data[pointer:pointer + size], start, vf, sf)
        bone += 1
    if nodes + bone >= len(data) or not math.isfinite(duration):
        raise ValueError("invalid animation node list or duration")
    return duration, tracks


def inspect_pair(master_dat, master_aj, crazy_dat, crazy_aj):
    report = {}
    for hand, dat, aj, base, sign in (("master", master_dat, master_aj, 339, 1),
                                      ("crazy", crazy_dat, crazy_aj, 334, -1)):
        if hashlib.sha256(aj).hexdigest() != AJ_HASHES[hand]:
            raise ValueError(f"unsupported {hand} AJ hash")
        fighter = FighterDat(dat)
        animations = [read_animation(aj, fighter.motion(base + i)) for i in range(3)]
        durations = [a[0] for a in animations]
        if durations != [78, 331, 100]:
            raise ValueError(f"unexpected {hand} tag motion durations")
        keys = [(f, sign * v) for f, v in animations[1][1][18, 1] if 38 <= f <= 175]
        maximum = max(v for _, v in keys)
        # A peak can have two equal keys (49/50 and 165/166); take its onset.
        peaks = []
        was_peak = False
        for frame, value in keys:
            is_peak = abs(value - maximum) < 0.0001
            if is_peak and not was_peak:
                peaks.append(frame)
            was_peak = is_peak
        report[hand] = {"sha256": AJ_HASHES[hand], "durations": durations,
                        "finger_flexion_peaks": peaks}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("master_dat", "master_aj", "crazy_dat", "crazy_aj"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    report = inspect_pair(*(getattr(args, name).read_bytes() for name in
                            ("master_dat", "master_aj", "crazy_dat", "crazy_aj")))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
