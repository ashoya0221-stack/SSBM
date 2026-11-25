"""Small LZ byte stream and PPC loader for our own generated patch code.

Game assets are never included. The loader allocates from the game's current
heap, flushes executable memory, and invalidates its pointer before heap reset.
"""


def pack_runtime(data):
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


def loader_source(packed, size):
    if not 0 < size < 32768 or len(unpack_runtime(packed, size)) != size:
        raise ValueError("invalid runtime size")
    padded = packed + b"\0" * (-len(packed) % 4)
    words = "\n".join(f".long 0x{int.from_bytes(padded[i:i+4], 'big'):08x}"
                      for i in range(0, len(padded), 4))
    return f"""
ENTER
stfd 0,0x30(1)
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
