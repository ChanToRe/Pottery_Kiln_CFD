#!/usr/bin/env python3
"""PNG 읽기 — 순수 Python (PIL 없음).

`plotlib.Canvas` 는 PNG 를 쓰기만 한다. ParaView 가 뽑은 온도장 위에 축을
얹으려면 읽어야 하므로 최소한의 판독기를 둔다.

8비트 트루컬러(RGB/RGBA), 인터레이스 없음만 지원한다 — ParaView 의
SaveScreenshot 출력이 그 형식이다.

    w, h, buf = read_png(path)     # buf 는 RGB bytearray, 길이 w*h*3
"""
import struct
import zlib


def read_png(path):
    d = open(path, "rb").read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG 가 아니다: %s" % path)
    pos, idat, w = 8, bytearray(), None
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        body = d[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, ctype, comp, filt, inter = struct.unpack(">IIBBBBB", body)
            if depth != 8 or ctype not in (2, 6) or inter:
                raise ValueError("8비트 RGB/RGBA·비인터레이스만 지원 "
                                 "(depth=%d ctype=%d inter=%d)" % (depth, ctype, inter))
            nch = 3 if ctype == 2 else 4
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
        pos += 12 + ln
    if w is None:
        raise ValueError("IHDR 없음")

    raw = zlib.decompress(bytes(idat))
    stride = w * nch
    out = bytearray(w * h * 3)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 1:                       # Sub
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 0xFF
        elif ft == 2:                     # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:                     # Average
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:                     # Paeth
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                b = prev[i]
                c = prev[i - nch] if i >= nch else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ft != 0:
            raise ValueError("알 수 없는 필터 %d" % ft)
        prev = line
        o = y * w * 3
        if nch == 3:
            out[o:o + stride] = line
        else:
            for x in range(w):
                s = x * 4
                out[o + x * 3:o + x * 3 + 3] = line[s:s + 3]
    return w, h, out
