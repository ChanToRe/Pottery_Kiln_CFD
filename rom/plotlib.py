#!/usr/bin/env python3
"""
순수 Python 플로팅 (PNG 출력). 이 환경에는 matplotlib·PIL 이 없다.

  Canvas  픽셀 버퍼 + 선/사각형/텍스트 (Times New Roman, ttf.py 로 래스터)

글자는 fonts/times.ttf 를 직접 래스터해 그린다. 그 파일이 없을 때만
아래 5x7 비트맵 폰트로 물러서며, 그때는 표준오류에 ★ 경고를 낸다. 그림 안 라벨은 영문으로 쓰고,
설명은 README 에 한글로 둔다.
"""
import os
import struct
import sys
import zlib

FONT = {
    ' ': (0x00, 0x00, 0x00, 0x00, 0x00), '!': (0x00, 0x00, 0x5F, 0x00, 0x00),
    '"': (0x07, 0x00, 0x07, 0x00, 0x00), '#': (0x14, 0x7F, 0x14, 0x7F, 0x14),
    '%': (0x23, 0x13, 0x08, 0x64, 0x62), "'": (0x00, 0x07, 0x00, 0x00, 0x00),
    '(': (0x00, 0x1C, 0x22, 0x41, 0x00), ')': (0x00, 0x41, 0x22, 0x1C, 0x00),
    '*': (0x14, 0x08, 0x3E, 0x08, 0x14), '+': (0x08, 0x08, 0x3E, 0x08, 0x08),
    ',': (0x00, 0x50, 0x30, 0x00, 0x00), '-': (0x08, 0x08, 0x08, 0x08, 0x08),
    '.': (0x00, 0x60, 0x60, 0x00, 0x00), '/': (0x20, 0x10, 0x08, 0x04, 0x02),
    '0': (0x3E, 0x51, 0x49, 0x45, 0x3E), '1': (0x00, 0x42, 0x7F, 0x40, 0x00),
    '2': (0x42, 0x61, 0x51, 0x49, 0x46), '3': (0x21, 0x41, 0x45, 0x4B, 0x31),
    '4': (0x18, 0x14, 0x12, 0x7F, 0x10), '5': (0x27, 0x45, 0x45, 0x45, 0x39),
    '6': (0x3C, 0x4A, 0x49, 0x49, 0x30), '7': (0x01, 0x71, 0x09, 0x05, 0x03),
    '8': (0x36, 0x49, 0x49, 0x49, 0x36), '9': (0x06, 0x49, 0x49, 0x29, 0x1E),
    ':': (0x00, 0x36, 0x36, 0x00, 0x00), '<': (0x00, 0x08, 0x14, 0x22, 0x41),
    '=': (0x14, 0x14, 0x14, 0x14, 0x14), '>': (0x41, 0x22, 0x14, 0x08, 0x00),
    '?': (0x02, 0x01, 0x51, 0x09, 0x06),
    'A': (0x7E, 0x11, 0x11, 0x11, 0x7E), 'B': (0x7F, 0x49, 0x49, 0x49, 0x36),
    'C': (0x3E, 0x41, 0x41, 0x41, 0x22), 'D': (0x7F, 0x41, 0x41, 0x22, 0x1C),
    'E': (0x7F, 0x49, 0x49, 0x49, 0x41), 'F': (0x7F, 0x09, 0x09, 0x09, 0x01),
    'G': (0x3E, 0x41, 0x49, 0x49, 0x7A), 'H': (0x7F, 0x08, 0x08, 0x08, 0x7F),
    'I': (0x00, 0x41, 0x7F, 0x41, 0x00), 'J': (0x20, 0x40, 0x41, 0x3F, 0x01),
    'K': (0x7F, 0x08, 0x14, 0x22, 0x41), 'L': (0x7F, 0x40, 0x40, 0x40, 0x40),
    'M': (0x7F, 0x02, 0x0C, 0x02, 0x7F), 'N': (0x7F, 0x04, 0x08, 0x10, 0x7F),
    'O': (0x3E, 0x41, 0x41, 0x41, 0x3E), 'P': (0x7F, 0x09, 0x09, 0x09, 0x06),
    'Q': (0x3E, 0x41, 0x51, 0x21, 0x5E), 'R': (0x7F, 0x09, 0x19, 0x29, 0x46),
    'S': (0x46, 0x49, 0x49, 0x49, 0x31), 'T': (0x01, 0x01, 0x7F, 0x01, 0x01),
    'U': (0x3F, 0x40, 0x40, 0x40, 0x3F), 'V': (0x1F, 0x20, 0x40, 0x20, 0x1F),
    'W': (0x3F, 0x40, 0x38, 0x40, 0x3F), 'X': (0x63, 0x14, 0x08, 0x14, 0x63),
    'Y': (0x07, 0x08, 0x70, 0x08, 0x07), 'Z': (0x61, 0x51, 0x49, 0x45, 0x43),
    '[': (0x00, 0x7F, 0x41, 0x41, 0x00), ']': (0x00, 0x41, 0x41, 0x7F, 0x00),
    '_': (0x40, 0x40, 0x40, 0x40, 0x40), '|': (0x00, 0x00, 0x7F, 0x00, 0x00),
}


# ---------------------------------------------------------------- 서체
# 그림 글자는 Times New Roman (fonts/times.ttf) 로 그린다. TTF 가 없을 때만
# 위의 5x7 비트맵 폰트로 물러선다.
# 기본 10.5 — 이 크기에서 Times 대문자 문자열의 폭이 옛 5x7 고정폭(6 px/자)과
# 거의 같아 기존 그림의 좌표 계산이 그대로 성립한다. 새로 그리는 그림은
# P.TEXT_SIZE 를 직접 올려 쓴다.
TEXT_SIZE = float(os.environ.get("TEXT_SIZE", "10.5"))
_FONTS = {}


def _font(bold=False):
    if bold not in _FONTS:
        try:
            import ttf
            _FONTS[bold] = ttf.Font(bold=bold)
        except Exception as e:
            # 그림은 계속 그리되 크게 알린다 — 글자 폭이 달라 투고본 낱장과 어긋난다
            print("★ Times 글꼴(fonts/times.ttf)을 읽지 못해 5x7 비트맵 글꼴로 그린다: %s" % e,
                  file=sys.stderr)
            _FONTS[bold] = None
    return _FONTS[bold]


class Canvas:
    def __init__(self, w, h, bg=(255, 255, 255)):
        self.w, self.h = w, h
        self.buf = bytearray(bg * (w * h))

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i] = c[0]
            self.buf[i + 1] = c[1]
            self.buf[i + 2] = c[2]

    def fill(self, x0, y0, x1, y1, c):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.px(x, y, c)

    def line(self, x0, y0, x1, y1, c, lw=1):
        x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        r = lw // 2
        while True:
            for oy in range(-r, r + 1):
                for ox in range(-r, r + 1):
                    self.px(x0 + ox, y0 + oy, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def polyline(self, pts, c, lw=1):
        for i in range(1, len(pts)):
            self.line(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1], c, lw)

    def blend(self, x, y, c, a):
        if 0 <= x < self.w and 0 <= y < self.h and a:
            i = (y * self.w + x) * 3
            for k in range(3):
                self.buf[i + k] = (self.buf[i + k] * (255 - a) + c[k] * a) // 255

    def text(self, x, y, s, c, sc=1, bold=False):
        """(x, y) 는 글자 왼쪽 위. sc 는 배율 (1 = 본문 크기)."""
        f = _font(bold)
        if f is None:                     # TTF 가 없으면 비트맵 폰트로 물러선다
            return self._text_bitmap(x, y, s, c, int(sc))
        return f.text(self.blend, x, y, s, TEXT_SIZE * sc, c)

    def text_w(self, s, sc=1, bold=False):
        f = _font(bold)
        if f is None:
            return len(s) * 6 * int(sc)
        return f.width(s, TEXT_SIZE * sc)

    def cap_h(self, sc=1):
        """대문자 높이 — 세로 가운데 맞춤에 쓴다."""
        return (TEXT_SIZE * sc * 0.662) if _font(False) else 7 * int(sc)

    def _text_bitmap(self, x, y, s, c, sc=1):
        cx = int(x)
        for ch in s.upper():
            g = FONT.get(ch)
            if g is None:
                cx += 6 * sc
                continue
            for col in range(5):
                bits = g[col]
                for row in range(7):
                    if bits & (1 << row):
                        for a in range(sc):
                            for b in range(sc):
                                self.px(cx + col * sc + a, int(y) + row * sc + b, c)
            cx += 6 * sc
        return cx - int(x)

    def save(self, path):
        raw = bytearray()
        for y in range(self.h):
            raw.append(0)
            raw += self.buf[y * self.w * 3:(y + 1) * self.w * 3]
        out = [b"\x89PNG\r\n\x1a\n"]

        def chunk(typ, data):
            return (struct.pack(">I", len(data)) + typ + data
                    + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

        out.append(chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0)))
        out.append(chunk(b"IDAT", zlib.compress(bytes(raw), 6)))
        out.append(chunk(b"IEND", b""))
        with open(path, "wb") as f:
            f.write(b"".join(out))
