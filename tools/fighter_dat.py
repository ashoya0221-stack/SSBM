"""Read-only access to HSD fighter motion descriptors (no game data included)."""

import struct


class FighterDat:
    def __init__(self, data):
        if len(data) < 0x20:
            raise ValueError("truncated DAT header")
        size, data_size, relocations, publics, externals = struct.unpack_from(">5I", data)
        if size != len(data) or data_size > size - 0x20:
            raise ValueError("invalid DAT size")
        root_table = 0x20 + data_size + 4 * relocations
        strings = root_table + 8 * (publics + externals)
        if publics != 1 or strings >= size:
            raise ValueError("unsupported DAT root table")
        self.data = data[0x20:0x20 + data_size]
        self.root, name = struct.unpack_from(">II", data, root_table)
        if self.root + 0x60 > data_size or strings + name >= size:
            raise ValueError("invalid DAT root")
        end = data.find(b"\0", strings + name)
        if end < 0:
            raise ValueError("unterminated DAT root name")
        self.name = data[strings + name:end].decode("ascii")
        self.motions = self.u32(self.root + 0xC)

    def u32(self, offset):
        if not 0 <= offset <= len(self.data) - 4:
            raise ValueError("DAT pointer outside data section")
        return struct.unpack_from(">I", self.data, offset)[0]

    def motion(self, index):
        if index < 0:
            raise ValueError("negative motion index")
        offset = self.motions + index * 24
        if offset + 24 > len(self.data):
            raise ValueError("motion descriptor outside DAT")
        row = struct.unpack_from(">6I", self.data, offset)
        name = row[0]
        if not 0 < name < len(self.data):
            raise ValueError("motion has no name")
        end = self.data.find(b"\0", name)
        if end < 0:
            raise ValueError("unterminated motion name")
        return {"name": self.data[name:end].decode("ascii"), "script": row[3],
                "animation_offset": row[1], "animation_size": row[2]}
