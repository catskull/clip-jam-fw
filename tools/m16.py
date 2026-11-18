"""Minimal MIPS16e linear disassembler / constant tracer (enough to read drivers).

usage: m16.py FILE START END BASEADDR
Prints one line per instruction; tracks register constants within a function
(reset at save/jrc) and annotates loads/stores whose address is known.
"""
import struct
import sys

R = ['s0', 's1', 'v0', 'v1', 'a0', 'a1', 'a2', 'a3']
R32 = ['zero', 'at', 'v0', 'v1', 'a0', 'a1', 'a2', 'a3', 't0', 't1', 't2', 't3', 't4', 't5', 't6', 't7',
       's0', 's1', 's2', 's3', 's4', 's5', 's6', 's7', 't8', 't9', 'k0', 'k1', 'gp', 'sp', 'fp', 'ra']


def sx(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


def main(path, start, end, base):
    b = open(path, 'rb').read()
    pc = start
    regs = {}
    ext = None
    ext_pc = None

    def rd(off, n=4):
        return struct.unpack_from('<I' if n == 4 else '<H', b, off)[0]

    def addr(o):
        return base + (o - start)

    while pc < end:
        h = rd(pc, 2)
        op = h >> 11
        a = addr(pc)
        if op == 0b11110 and ext is None:
            ext = ((h & 0x1f) << 11) | (((h >> 5) & 0x3f) << 5)  # imm[15:11],[10:5]
            ext_pc = pc
            pc += 2
            continue
        ipc = ext_pc if ext is not None else pc
        rx = R[(h >> 8) & 7]
        ry = R[(h >> 5) & 7]
        txt = f'.half 0x{h:04x}'
        note = ''
        if op == 0b00011:  # jal/jalx
            lo = rd(pc + 2, 2)
            tgt = (((h & 0x1f) << 21) | (((h >> 5) & 0x1f) << 16) | lo) << 2
            tgt |= (addr(pc) + 4) & 0xf0000000
            x = (h >> 10) & 1
            args = ' '.join(f'{r}={regs[r]:#x}' for r in ('a0', 'a1', 'a2', 'a3') if r in regs)
            txt = f'{"jalx" if x else "jal"} 0x{tgt:08x}'
            note = args
            print(f'{a:08x}: {txt:34s} ; {note}')
            pc += 4
            # after call, arg regs are clobbered (delay slot executes first; ignore)
            for r in ('v0', 'v1', 'a0', 'a1', 'a2', 'a3'):
                regs.pop(r, None)
            ext = None
            continue
        if op == 0b01101:  # li
            imm = (ext | (h & 0x1f)) if ext is not None else h & 0xff
            regs[rx] = imm
            txt = f'li {rx}, 0x{imm:x}'
        elif op == 0b10110:  # lw rx, imm(pc)
            imm = (sx(ext | (h & 0x1f), 16)) if ext is not None else (h & 0xff) << 2
            la = (ipc & ~3) + imm
            v = rd(la) if 0 <= la < len(b) - 3 else None
            if v is not None:
                regs[rx] = v
            txt = f'lw {rx}, 0x{imm:x}(pc)'
            note = f'= 0x{v:08x}' if v is not None else ''
        elif op == 0b01001:  # addiu rx, imm
            imm = sx(ext | (h & 0x1f), 16) if ext is not None else sx(h & 0xff, 8)
            if rx in regs:
                regs[rx] = (regs[rx] + imm) & 0xffffffff
            txt = f'addiu {rx}, {imm}'
        elif op == 0b01000:  # addiu ry, rx, imm4
            imm = sx(ext | (h & 0xf), 15) if ext is not None else sx(h & 0xf, 4)
            if rx in regs:
                regs[ry] = (regs[rx] + imm) & 0xffffffff
            else:
                regs.pop(ry, None)
            txt = f'addiu {ry}, {rx}, {imm}'
        elif op in (0b11011, 0b11001, 0b11000, 0b10011, 0b10001, 0b10101, 0b10000, 0b10100):
            sc = {0b11011: 4, 0b10011: 4, 0b11001: 2, 0b10001: 2, 0b10101: 2}.get(op, 1)
            imm = sx(ext | (h & 0x1f), 16) if ext is not None else (h & 0x1f) * sc
            name = {0b11011: 'sw', 0b11001: 'sh', 0b11000: 'sb', 0b10011: 'lw', 0b10001: 'lh',
                    0b10101: 'lhu', 0b10000: 'lb', 0b10100: 'lbu'}[op]
            txt = f'{name} {ry}, {imm}({rx})'
            if rx in regs:
                ea = (regs[rx] + imm) & 0xffffffff
                note = f'[0x{ea:08x}]'
                if name.startswith('s'):
                    note += f' <- {regs[ry]:#x}' if ry in regs else ' <- ?'
            if name.startswith('l'):
                regs.pop(ry, None)
        elif op == 0b01100:
            f = (h >> 8) & 7
            if f == 4:
                s = (h >> 7) & 1
                txt = 'save' if s else 'restore'
                if s:
                    regs = {}
                    print(f'{"":10s}---- function @ {a:08x}')
            elif f == 5:  # mov32r r32, rz
                r32 = ((h >> 3) & 3) << 3 | ((h >> 5) & 7)
                rz = R[h & 7]
                txt = f'move {R32[r32]}, {rz}'
            elif f == 7:  # movr32 ry, r32
                txt = f'move {ry}, {R32[h & 0x1f]}'
                regs.pop(ry, None)
            elif f in (0, 1):  # bteqz / btnez
                off = sx(ext | (h & 0x1f), 16) if ext is not None else sx(h & 0xff, 8)
                nxt = (ipc + 4) if ext is not None else pc + 2
                txt = f'{"bteqz" if f == 0 else "btnez"} 0x{addr(nxt) + (off << 1):08x}'
            elif f == 2:
                txt = f'sw ra, {(h & 0xff) * 4}(sp)'
            elif f == 3:
                imm = sx(ext | (h & 0x1f), 16) if ext is not None else sx(h & 0xff, 8) * 8
                txt = f'addiu sp, {imm}'
            else:
                txt = f'i8 f{f}'
        elif op == 0b11101:
            fn = h & 0x1f
            if fn == 0:
                txt = {0: 'jr', 1: 'jr ra', 2: 'jalr', 4: 'jrc', 5: 'jrc ra', 6: 'jalrc'}.get(h >> 5 & 7, 'jr?') + (f' {rx}' if (h >> 5 & 7) in (0, 2, 4, 6) else '')
                if (h >> 5 & 7) in (2, 6):
                    note = ' '.join(f'{r}={regs[r]:#x}' for r in ('a0', 'a1', 'a2', 'a3') if r in regs)
                    if rx in regs:
                        note = f'-> {regs[rx]:#x} ' + note
            else:
                nm = {0xc: 'and', 0xd: 'or', 0xe: 'xor', 0xf: 'not', 0xa: 'cmp', 0x2: 'slt', 0x3: 'sltu',
                      0x4: 'sllv', 0x6: 'srlv', 0x7: 'srav', 0xb: 'neg', 0x10: 'mfhi', 0x12: 'mflo', 0x18: 'mult',
                      0x1a: 'div', 0x11: 'cnvt'}.get(fn, f'rr{fn:x}')
                txt = f'{nm} {rx}, {ry}'
                if nm == 'cnvt':
                    txt = f'{ {0: "zeb", 1: "zeh", 4: "seb", 5: "seh"}.get((h >> 5) & 7, "cnvt?")} {rx}'
                if nm in ('and', 'or', 'xor') and rx in regs and ry in regs:
                    regs[rx] = {'and': regs[rx] & regs[ry], 'or': regs[rx] | regs[ry],
                                'xor': regs[rx] ^ regs[ry]}[nm]
                elif nm not in ('cmp', 'mult', 'div'):
                    regs.pop(rx, None)
        elif op == 0b00110:
            sa = (h >> 2) & 7
            if ext is not None:
                sa = (ext >> 6) & 0x1f
            sa = sa or 8
            f = h & 3
            nm = {0: 'sll', 2: 'srl', 3: 'sra'}.get(f, 'sh?')
            txt = f'{nm} {rx}, {ry}, {sa}'
            if ry in regs:
                v = regs[ry]
                regs[rx] = (v << sa) & 0xffffffff if f == 0 else v >> sa
            else:
                regs.pop(rx, None)
        elif op == 0b11100:
            txt = f'{"addu" if (h & 3) == 1 else "subu"} {R[h >> 2 & 7]}, {rx}, {ry}'
            regs.pop(R[h >> 2 & 7], None)
        elif op == 0b00010:  # b
            off = sx(ext | (h & 0x1f), 16) if ext is not None else sx(h & 0x7ff, 11)
            nxt = (ipc + 4) if ext is not None else pc + 2
            txt = f'b 0x{addr(nxt) + (off << 1):08x}'
        elif op in (0b00100, 0b00101):  # beqz / bnez
            off = sx(ext | (h & 0x1f), 16) if ext is not None else sx(h & 0xff, 8)
            nxt = (ipc + 4) if ext is not None else pc + 2
            txt = f'{"beqz" if op == 4 else "bnez"} {rx}, 0x{addr(nxt) + (off << 1):08x}'
        elif op in (0b01010, 0b01011, 0b01110):  # slti / sltiu / cmpi
            imm = (ext | (h & 0x1f)) if ext is not None else h & 0xff
            txt = f'{ {0b01010: "slti", 0b01011: "sltiu", 0b01110: "cmpi"}[op]} {rx}, 0x{imm:x}'
        elif op == 0b00001:  # addiu rx, pc, imm
            imm = (ext | (h & 0x1f)) if ext is not None else (h & 0xff) << 2
            v = (addr(ipc) & ~3) + imm
            regs[rx] = v
            txt = f'addiu {rx}, pc, 0x{imm:x}'
            note = f'= 0x{v:08x}'
        elif op == 0b10010:
            txt = f'lw {rx}, {(h & 0xff) * 4}(sp)'
            regs.pop(rx, None)
        elif op == 0b11010:
            txt = f'sw {rx}, {(h & 0xff) * 4}(sp)'
        elif op == 0b00000:
            imm = (ext | (h & 0x1f)) if ext is not None else (h & 0xff) << 2
            txt = f'addiu {rx}, sp, {imm}'
            regs.pop(rx, None)
        else:
            txt = f'op{op:05b}'
            if op in (0b01010, 0b01011, 0b01110):
                pass
            else:
                regs.pop(rx, None)
        print(f'{a:08x}: {txt:34s} ; {note}')
        if txt in ('jrc ra', 'jr ra'):
            regs = {}
        ext = None
        pc += 2


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0), int(sys.argv[4], 0))
