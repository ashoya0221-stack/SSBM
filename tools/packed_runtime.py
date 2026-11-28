"""Small LZ byte stream and PPC loader for our own generated patch code.

Game assets are never included. The loader allocates from the game's current
heap, flushes executable memory, and invalidates its pointer before heap reset.
"""


def _pack_runtime_greedy(data):
    out, literals = bytearray(), bytearray()

    def flush():
        if literals:
            out.append(len(literals) - 1)
            out.extend(literals)
            literals.clear()

    pos = 0
    while pos < len(data):
        best, distance = 0, 0
        if pos + 5 <= len(data):
            candidate = data.rfind(data[pos:pos + 5], max(0, pos - 65535), pos)
            while candidate >= 0:
                length = 5
                while length < 130 and pos + length < len(data) and data[candidate + length] == data[pos + length]:
                    length += 1
                if length > best:
                    best, distance = length, pos - candidate
                if length == 130:
                    break
                candidate = data.rfind(data[pos:pos + 5], max(0, pos - 65535), candidate)
        if best >= 5:
            flush()
            out.extend((0x80 | (best - 3), distance >> 8, distance & 255))
            pos += best
        else:
            literals.append(data[pos])
            pos += 1
            if len(literals) == 128:
                flush()
    flush()
    return bytes(out)


def pack_runtime(data):
    """Pack with minimum-cost LZ parsing; keep the older encoder as a fallback.

    Literal packets carry one header per 1..128 bytes. Backreferences cost three
    bytes and support lengths 3..130. Dynamic programming accounts for literal
    packet headers, so a locally shorter match cannot make the complete stream
    larger through extra packet fragmentation.
    """
    data = bytes(data)
    if not data:
        return b""

    size = len(data)
    inf = size * 4 + 16
    costs = [[inf] * 128 for _ in range(size + 1)]
    parents = [[None] * 128 for _ in range(size + 1)]
    costs[0][0] = 0
    positions = {}

    for pos in range(size):
        row = costs[pos]
        next_row = costs[pos + 1]

        # Add one literal. The packet header is paid when its first literal
        # enters the packet; a 128-byte packet then closes automatically.
        for run, current_cost in enumerate(row):
            if current_cost == inf:
                continue
            if run == 0:
                next_run, extra = 1, 2
            elif run == 127:
                next_run, extra = 0, 1
            else:
                next_run, extra = run + 1, 1
            candidate_cost = current_cost + extra
            if candidate_cost < next_row[next_run]:
                next_row[next_run] = candidate_cost
                parents[pos + 1][next_run] = (pos, run, None)

        # A backreference resets any open literal packet. Its three-byte cost
        # is independent of the current literal run length.
        if pos + 3 <= size:
            key = data[pos:pos + 3]
            best_length, best_distance = 0, 0
            max_length = min(130, size - pos)
            for previous in reversed(positions.get(key, ())):
                length = 3
                while length < max_length and data[previous + length] == data[pos + length]:
                    length += 1
                if length > best_length:
                    best_length = length
                    best_distance = pos - previous
                    if length == max_length:
                        break

            if best_length >= 3:
                best_run = min(range(128), key=row.__getitem__)
                best_cost = row[best_run] + 3
                if row[best_run] != inf:
                    for length in range(3, best_length + 1):
                        target = pos + length
                        if best_cost < costs[target][0]:
                            costs[target][0] = best_cost
                            parents[target][0] = (
                                pos, best_run, (length, best_distance)
                            )
            positions.setdefault(key, []).append(pos)

    final_run = min(range(128), key=costs[size].__getitem__)
    actions = []
    pos, run = size, final_run
    while pos:
        parent = parents[pos][run]
        if parent is None:
            raise ValueError("LZ parser could not reconstruct its shortest path")
        previous, previous_run, match = parent
        if match is None:
            actions.append((0, data[previous]))
        else:
            actions.append((1, match[0], match[1]))
        pos, run = previous, previous_run
    actions.reverse()

    out, literals = bytearray(), bytearray()

    def flush():
        if literals:
            out.append(len(literals) - 1)
            out.extend(literals)
            literals.clear()

    for action in actions:
        if action[0] == 0:
            literals.append(action[1])
            if len(literals) == 128:
                flush()
        else:
            flush()
            length, distance = action[1], action[2]
            out.extend((0x80 | (length - 3), distance >> 8, distance & 255))
    flush()

    packed = bytes(out)
    greedy = _pack_runtime_greedy(data)
    return packed if len(packed) <= len(greedy) else greedy


def unpack_runtime(data, size):
    out, pos = bytearray(), 0
    while len(out) < size:
        token = data[pos]
        pos += 1
        if token < 128:
            count = token + 1
            out.extend(data[pos:pos + count])
            pos += count
        else:
            count = (token & 127) + 3
            distance = int.from_bytes(data[pos:pos + 2], "big")
            pos += 2
            if not 0 < distance <= len(out):
                raise ValueError("invalid packed runtime backreference")
            for _ in range(count):
                out.append(out[-distance])
    if len(out) != size or pos != len(data):
        raise ValueError("packed runtime size mismatch")
    return bytes(out)


def loader_source(packed, size, preserve_r3=False):
    if not 0 < size < 32768 or len(unpack_runtime(packed, size)) != size:
        raise ValueError("invalid runtime size")
    padded = packed + b"\0" * (-len(packed) % 4)
    words = "\n".join(f".long 0x{int.from_bytes(padded[i:i+4], 'big'):08x}"
                      for i in range(0, len(padded), 4))
    return f"""
ENTER
stfd 0,0x30(1)
{"stw 3,0x38(1)" if preserve_r3 else ""}
PTR 30,loaded_core
lwz 29,0(30)
cmpwi 29,0
bne loader_ready
li 3,{size}
CALL ALLOC
mr 29,3
mr 26,29
PTR 27,packed_core
addi 28,29,{size}
decode_packet:
lbz 8,0(27)
addi 27,27,1
cmpwi 8,128
bge decode_match
addi 8,8,1
mtctr 8
decode_literal:
lbz 9,0(27)
stb 9,0(26)
addi 27,27,1
addi 26,26,1
bdnz decode_literal
b decode_next
decode_match:
andi. 8,8,127
addi 8,8,3
lbz 9,0(27)
lbz 10,1(27)
slwi 9,9,8
or 9,9,10
subf 9,9,26
addi 27,27,2
mtctr 8
decode_copy:
lbz 10,0(9)
stb 10,0(26)
addi 9,9,1
addi 26,26,1
bdnz decode_copy
decode_next:
cmplw 26,28
blt decode_packet
mr 3,29
li 4,{size}
CALL FLUSH_CODE
mr 3,29
li 4,{size}
CALL INVALIDATE_CODE
stw 29,0(30)
loader_ready:
mr 12,29
lfd 0,0x30(1)
{"lwz 3,0x38(1)" if preserve_r3 else ""}
LEAVE_HOOK
mtctr 12
bctr
loaded_core:
.long 0
packed_core:
{words}
loader_end:
nop
"""


def helper_sources(state_offset, loader_hook=0x8014FB2C):
    # Resolve the C2 loader through the handler's installed relative branch.
    # This remains valid if other Gecko codes move the code list in memory.
    reset = f"""
lis 8,{loader_hook >> 16}
ori 8,8,{loader_hook & 0xFFFF}
lwz 9,0(8)
slwi 9,9,6
srawi 9,9,6
add 8,8,9
li 0,0
stw 0,{state_offset}(8)
mflr 0
reset_end:
nop
"""
    # Audio setup marks requested character banks before loading them. Include
    # mhands.ssm (bank 32) in that category, including debug character swaps.
    # Native ABI: r3 = category flags; u64 mask = r5:r6. No mid-match bank unload.
    sound_mask = """
andi. 0,3,4
beq sound_mask_done
ori 5,5,1
sound_mask_done:
mflr 0
sound_mask_return:
nop
"""
    return reset, sound_mask
