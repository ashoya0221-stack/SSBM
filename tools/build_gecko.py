#!/usr/bin/env python3
"""Build an experimental, version-checked US 1.00 Gecko restoration.

Only generated patch text is written. Input game files are never modified.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

try:
    from .fighter_dat import FighterDat
    from .inspect_dol import inspect
    from .inspect_animations import inspect_pair
    from .packed_runtime import pack_runtime, loader_source, helper_sources
except ImportError:
    from fighter_dat import FighterDat
    from inspect_dol import inspect
    from inspect_animations import inspect_pair
    from packed_runtime import pack_runtime, loader_source, helper_sources


ROOT = Path(__file__).resolve().parents[1]
DAT_HASHES = {
    "master": "e563fb4b2d3d83758f976c11f85aa0898eb7dae1a7228b758b9d115312a371c9",
    "crazy": "26e4475f0e4f5f7b322bc96d652566e7737b5b9e90eceaac5c697997f2e45f60",
}
FUNCTIONS = {
    "MASTER_MOVE": 0x80150474, "CRAZY_MOVE": 0x8015B080,
    "MASTER_IDLE": 0x801506C8, "CRAZY_IDLE": 0x8015B2D4,
    "GET_HAND": 0x8015BA34, "CHANGE_STATE": 0x80069288,
    "ANIM_INIT": 0x8006EA48, "ANIM_REMAINING": 0x8006F0DC,
    "INIT_GRAB": 0x8007E034, "SET_GRAB_MASK": 0x8007E058,
    "CLEAR_HITBOXES": 0x8007AD14, "CREATE_HITBOX": 0x800710A8,
    "SET_THROW_DATA": 0x80071C90, "CAPTURE_CUT": 0x800DC304,
    "MH_THROWN": 0x801553EC, "CH_THROWN": 0x8015AE9C,
    "APPLY_THROW": 0x800DDE5C, "LAUNCH_VICTIM": 0x800DE374,
    "RANDI": 0x8037E6CC,
    "PLAY_SFX": 0x80087EA0, "BOSS_LAUGH": 0x8015BC44,
    "ANIM_SEEK": 0x8006EA8C, "ANIM_EVALUATE": 0x8006E858,
    "JOINT_WORLD": 0x8000B1CC, "GROUND_PROBE": 0x80081B2C,
    "GROUND_IMPACT": 0x80097628, "SET_AIRBORNE": 0x8007D338,
    "ALLOC": 0x8037D330, "FLUSH_CODE": 0x80342EDC,
    "INVALIDATE_CODE": 0x80342FA4,
}


def data_words(settings):
    """Native hitbox encoding; only scalar parameters, no archived assets."""
    start, end = settings["grab_start_frame"], settings["grab_end_frame"]
    radius = round(settings["grab_radius"] * 256)
    output = {}
    for hand, suffix, mirrored in (("master", "MH", False), ("crazy", "CH", True)):
        output[f"GRAB_DATA_{suffix}"] = ([
            0x0800000F, 0x44000000, 156, 0x00007F40,
        ] if not mirrored else []) + [
            0x08000000 | start, 0x2C009000, (radius << 16) | 0x03E8,
            0x07D007D0 if mirrored else 0x07D0F830,
            0x14190013, 0x00200007, 0x08000000 | end, 0x40000000, 0,
        ]
        element = settings[hand]["pummel_element"]
        output[f"PUMMEL_DATA_{suffix}"] = [
            0x2C089000 | settings[hand]["pummel_damage"], 0x096003E8,
            0xFC1807D0 if mirrored else 0xFC18F830, 0x28000012,
            (element << 18) | (0x10F if mirrored else 0x12),
            0x00080000,  # native reader's following-word victim-only flag
        ]
        # MH's resident tag throw and CH's resident reverse throw knockback.
        output[f"THROW_DATA_{suffix}"] = [
            0x88000000 | settings[hand]["throw_damage"],
            (settings["slam_angle"] << 23) | (0x118000 if mirrored else 0x190000),
            0x1E002000 if mirrored else 0x19002000,
        ]
    return output


def expand(source, settings):
    constants = dict(FUNCTIONS)
    for i, frame in enumerate(settings["pummel_frames"], 1):
        constants[f"PUMMEL_{i}"] = frame
    constants["ACTIVE_FRAMES"] = settings["pummel_active_frames"]
    constants["THROW_FRAME"] = settings["throw_frame"]
    constants["SLAM_DROP_BITS"] = struct.unpack(">I", struct.pack(">f", settings["release_drop"]))[0]
    blobs = data_words(settings)
    calls = Counter(re.findall(r"^\s*(?:CALL|TAIL) (\w+)\s*$", source, re.M))
    thunks = {name for name, count in calls.items() if count > 1}
    lines = []
    counter = 0
    for raw in source.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line == "ENTER":
            lines += ["stwu 1,-0x60(1)", "mflr 0", "stw 0,0x64(1)", "stmw 26,0x48(1)"]
        elif line in ("LEAVE", "LEAVE_HOOK"):
            lines += ["lmw 26,0x48(1)", "lwz 0,0x64(1)", "mtlr 0", "addi 1,1,0x60"]
            if line == "LEAVE":
                lines.append("blr")
        elif line.startswith(("CALL ", "TAIL ")):
            name = line.split()[1]
            if name in thunks:
                branch = "bl" if line.startswith("CALL ") else "b"
                lines.append(f"{branch} native_{name}")
            else:
                value = constants[name]
                lines += [f"lis 12,{value >> 16}", f"ori 12,12,{value & 0xFFFF}",
                          "mtctr 12", "bctrl" if line.startswith("CALL ") else "bctr"]
        elif line.startswith("PTR "):
            reg, target = line[4:].split(",")
            label = f"get_pc_{counter}"
            counter += 1
            lines += [f"bl {label}", label + ":", f"mflr {reg}",
                      f"addi {reg},{reg},{target}-{label}"]
        elif line in blobs:
            lines += [f".long 0x{word:08x}" for word in blobs[line]]
        else:
            for key, value in constants.items():
                line = re.sub(r"\b" + key + r"\b", str(value), line)
            lines.append(line)
    # Share repeated native call veneers. The final label is the hook's branch
    # around its helpers/data, so keep veneers before that label's terminal nop.
    veneers = []
    for name in sorted(thunks):
        value = constants[name]
        veneers += [f"native_{name}:", f"lis 12,{value >> 16}",
                    f"ori 12,12,{value & 0xFFFF}", "mtctr 12", "bctr"]
    lines[-2:-2] = veneers
    labels, pc = {}, 0
    for line in lines:
        if line.endswith(":"):
            labels[line[:-1]] = pc
        else:
            pc += 4
    return "\n".join(lines), labels


def assemble(source, settings):
    from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC32, KS_MODE_BIG_ENDIAN
    expanded, labels = expand(source, settings)
    ks = Ks(KS_ARCH_PPC, KS_MODE_PPC32 | KS_MODE_BIG_ENDIAN)
    code, _ = ks.asm(expanded, as_bytes=True)
    if len(code) != max(labels.values(), default=0) + 4:
        # Every payload ends in an explicitly labeled single nop.
        raise ValueError("assembler layout differs from symbol layout")
    return bytes(code), labels, expanded


def c2(address, code):
    if len(code) % 4 or address & 3:
        raise ValueError("unaligned C2 hook")
    words = list(struct.unpack(">" + "I" * (len(code) // 4), code))
    if len(words) % 2 == 0:
        words.append(0x60000000)
    words.append(0)  # code handler fills this with the branch back to hook+4
    result = [f"{0xC2000000 | (address & 0x1FFFFFF):08X} {len(words) // 2:08X}"]
    result += [f"{words[i]:08X} {words[i+1]:08X}" for i in range(0, len(words), 2)]
    return result


def build(settings, force_combo=False):
    frames = settings["pummel_frames"]
    if (len(frames) != 5 or frames != sorted(set(frames)) or frames[0] < 1
            or frames[-1] + settings["pummel_active_frames"] >= settings["throw_frame"]
            or settings["throw_frame"] >= 331 or settings["pummel_active_frames"] < 1
            or any(b - a <= settings["pummel_active_frames"] for a, b in zip(frames, frames[1:]))):
        raise ValueError("invalid pummel/throw schedule")
    if not 0 < settings["grab_start_frame"] < settings["grab_end_frame"] < 180:
        raise ValueError("invalid grab window")
    if not 0 < settings["grab_radius"] < 128:
        raise ValueError("invalid grab radius")
    if settings["slam_angle"] != 270 or not 0 < settings["release_drop"] < 64:
        raise ValueError("invalid downward slam parameters")
    for hand in ("master", "crazy"):
        if not (1 <= settings[hand]["pummel_damage"] <= 1023
                and 0 <= settings[hand]["pummel_element"] <= 16
                and settings[hand]["pummel_element"] != 8
                and 1 <= settings[hand]["throw_damage"] <= 1023):
            raise ValueError("invalid damage or element")
    runtime, symbols, expanded = assemble((ROOT / "patches/tagtsukamu.s").read_text(), settings)
    selection = """
        stw 27,0x224c(29)
        cmpwi 27,5
        bne selection_end
        ENTER
        li 3,27
        CALL GET_HAND
        cmpwi 3,0
        beq no_master
        lwz 8,0x2c(3)
        lwz 0,0x10(8)
        cmpwi 0,344
        beq no_master
        cmpwi 0,345
        beq no_master
        lbz 0,0x221f(8)
        andi. 0,0,0x10
        bne no_master
        SELECT
        b selection_restore
        no_master:
        li 3,343
        selection_restore:
        LEAVE_HOOK
        selection_end:
        nop
    """.replace("SELECT", "li 3,380" if force_combo else "li 3,4\nCALL RANDI\naddi 3,3,377")
    selector, _, _ = assemble(selection, settings)
    request = """
        stfs 0,0x2c(1)
        ENTER
        mr 3,31
        lis 4,0x8015
        ori 4,4,0xa114
        addi 5,1,0x84
        CALL CRAZY_MOVE
        LEAVE_HOOK
        request_end:
        nop
    """
    requester, _, _ = assemble(request, settings)
    # Guards target untouched prologues; hooks themselves change after installation.
    lines = ["2014F8E0 7C0802A6", "20155A84 7C0802A6"]
    lines += c2(0x80155CCC, selector)
    lines += c2(0x80155FDC, requester)
    # The core lives in game-allocated memory and expires with the native heap.
    # Compress our own code to leave the default Gecko area usable by test codes.
    # Return to the original caller after the entry trampoline has run.
    back = bytes.fromhex("3d808014618cfb307d8903a64e800420")
    packed = pack_runtime(runtime + back)
    loader, loader_labels, _ = assemble(loader_source(packed, len(runtime) + len(back)), settings)
    reset, attack = helper_sources(loader_labels["loaded_core"])
    reset_code, _, _ = assemble(reset, settings)
    attack_code, _, _ = assemble(attack, settings)
    lines += c2(0x8014FB2C, loader)
    lines += c2(0x80373574, reset_code)
    lines += c2(0x8006CA3C, attack_code)
    lines.append("E0000000 80008000")
    # Dolphin 5.0-21460's default 6 KiB handler area, less its 2880-byte handler
    # and the 8-byte code-list header. Do not silently emit an oversized code.
    if len(lines) * 8 > 3256:
        raise ValueError("patch exceeds Dolphin's default Gecko code-list capacity")
    return "\n".join(lines) + "\n", runtime, symbols, expanded


def validate_inputs(dol_data, master_data, crazy_data):
    profile = json.loads((ROOT / "config/us-1.00.json").read_text())
    inspect(dol_data, profile)
    for hand, data, motion, root_name in (
        ("master", master_data, 339, "ftDataMasterhand"),
        ("crazy", crazy_data, 334, "ftDataCrazyhand"),
    ):
        if hashlib.sha256(data).hexdigest() != DAT_HASHES[hand]:
            raise ValueError(f"unsupported {hand} DAT hash")
        archive = FighterDat(data)
        if archive.name != root_name or not archive.motion(motion)["name"].endswith(
                "_Tagtsukamu_figatree"):
            raise ValueError(f"unexpected {hand} motion mapping")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dol", type=Path)
    parser.add_argument("master_dat", type=Path)
    parser.add_argument("crazy_dat", type=Path)
    parser.add_argument("--master-aj", type=Path)
    parser.add_argument("--crazy-aj", type=Path)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    try:
        validate_inputs(args.dol.read_bytes(), args.master_dat.read_bytes(), args.crazy_dat.read_bytes())
        settings = json.loads((ROOT / "config/restoration.json").read_text())
        if bool(args.master_aj) != bool(args.crazy_aj):
            raise ValueError("supply both --master-aj and --crazy-aj")
        if args.master_aj:
            report = inspect_pair(args.master_dat.read_bytes(), args.master_aj.read_bytes(),
                                  args.crazy_dat.read_bytes(), args.crazy_aj.read_bytes())
            if any(r["finger_flexion_peaks"] != settings["pummel_frames"]
                   for r in report.values()):
                raise ValueError("configured pulses differ from supplied AJ flexion peaks")
            print("Both AJ archives verified: 78 / 331 / 100 frames; five matching flexion peaks")
        outputs = {}
        for force, name in ((False, "Tagtsukamu-US-1.00"), (True, "Tagtsukamu-US-1.00-combo-test")):
            text, _, _, _ = build(settings, force)
            outputs[name + ".txt"] = text
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for name, text in outputs.items():
            (args.out_dir / name).write_text(text, encoding="ascii")
            print(args.out_dir / name)
    except (OSError, ValueError, KeyError, ImportError, struct.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
