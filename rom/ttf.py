#!/usr/bin/env python3
"""
TrueType 글리프 래스터라이저 — 순수 Python (PIL·freetype 없음)

`plotlib.py` 의 5×7 비트맵 폰트는 서체 개념이 없다. 논문 그림에 세리프체를
쓰려면 TTF 를 직접 읽어 그려야 한다.

지원 범위 (그림 라벨에 필요한 만큼만)
  - cmap format 4 (BMP), loca/glyf, hmtx 로 자간
  - 단순 글리프 + 합성 글리프(오프셋만; 스케일 성분은 무시)
  - 2차 베지에를 선분으로 펴고, 비영 감기수(nonzero winding) 스캔라인 채움
  - 3×3 초과표본으로 계단 완화

글리프 비트맵은 (문자, 크기)로 캐시한다 — 프레임마다 다시 그리면 느리다.

    f = Font("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")
    f.text(canvas_put_pixel, x, y, "TEXT", size=13, color=(0,0,0))
"""
import os
import struct

# 저장소에 동봉한 Times New Roman 을 먼저 쓴다 (fonts/times.ttf).
_HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [
    os.environ.get("TTF_PATH", ""),
    os.path.join(_HERE, "..", "fonts", "times.ttf"),
    os.path.expanduser("~/.local/share/fonts/TimesNewRoman.ttf"),
    "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]
# 굵은 자형은 동봉본에 없다 → 같은 자형을 가로로 번지게 해 굵기를 만든다(_EMB).
BOLD_CANDIDATES = [
    os.environ.get("TTF_PATH_BOLD", ""),
    os.path.join(_HERE, "..", "fonts", "timesbd.ttf"),
    "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman_Bold.ttf",
]


def _pick(cands):
    for p in cands:
        if p and os.path.exists(p):
            return p
    return None


class Font:
    def __init__(self, path=None, bold=False):
        self.embolden = False
        if path is None and bold:
            path = _pick(BOLD_CANDIDATES)
            if not path:                 # 굵은 자형 파일이 없으면 합성한다
                path, self.embolden = _pick(CANDIDATES), True
        path = path or _pick(CANDIDATES)
        if not path:
            raise IOError("쓸 수 있는 TTF 가 없다")
        self.path = path
        self.d = open(path, "rb").read()
        self._tables()
        self._head()
        self._cmap()
        self._hmtx()
        self._cache = {}

    # ---- 표 목록 ----
    def _tables(self):
        d = self.d
        num = struct.unpack(">H", d[4:6])[0]
        self.tab = {}
        for i in range(num):
            o = 12 + 16 * i
            tag = d[o:o + 4].decode("latin1")
            off, ln = struct.unpack(">II", d[o + 8:o + 16])
            self.tab[tag] = (off, ln)

    def _head(self):
        o = self.tab["head"][0]
        self.upem = struct.unpack(">H", self.d[o + 18:o + 20])[0]
        self.loc_fmt = struct.unpack(">h", self.d[o + 50:o + 52])[0]
        o2 = self.tab["maxp"][0]
        self.nglyf = struct.unpack(">H", self.d[o2 + 4:o2 + 6])[0]
        o3, _ = self.tab["loca"]
        if self.loc_fmt:
            self.loca = list(struct.unpack(">%dI" % (self.nglyf + 1),
                                           self.d[o3:o3 + 4 * (self.nglyf + 1)]))
        else:
            s = struct.unpack(">%dH" % (self.nglyf + 1),
                              self.d[o3:o3 + 2 * (self.nglyf + 1)])
            self.loca = [x * 2 for x in s]

    def _cmap(self):
        o = self.tab["cmap"][0]
        n = struct.unpack(">H", self.d[o + 2:o + 4])[0]
        sub = None
        for i in range(n):
            pid, eid, off = struct.unpack(">HHI", self.d[o + 4 + 8 * i:o + 12 + 8 * i])
            if (pid, eid) in ((3, 1), (3, 0), (0, 3), (0, 4)):
                sub = o + off
                break
        if sub is None:
            raise IOError("cmap format 4 서브테이블 없음")
        fmt = struct.unpack(">H", self.d[sub:sub + 2])[0]
        if fmt != 4:
            raise IOError("cmap format %d 는 지원하지 않는다" % fmt)
        segX2 = struct.unpack(">H", self.d[sub + 6:sub + 8])[0]
        seg = segX2 // 2
        b = sub + 14
        end = struct.unpack(">%dH" % seg, self.d[b:b + segX2])
        b += segX2 + 2
        sta = struct.unpack(">%dH" % seg, self.d[b:b + segX2])
        b += segX2
        delta = struct.unpack(">%dh" % seg, self.d[b:b + segX2])
        b += segX2
        self._ro_base = b
        rng = struct.unpack(">%dH" % seg, self.d[b:b + segX2])
        self.cm = (seg, end, sta, delta, rng)

    def gid(self, ch):
        c = ord(ch)
        seg, end, sta, delta, rng = self.cm
        for i in range(seg):
            if c <= end[i]:
                if c < sta[i]:
                    return 0
                if rng[i] == 0:
                    return (c + delta[i]) & 0xFFFF
                o = self._ro_base + 2 * i + rng[i] + 2 * (c - sta[i])
                g = struct.unpack(">H", self.d[o:o + 2])[0]
                return 0 if g == 0 else (g + delta[i]) & 0xFFFF
        return 0

    def _hmtx(self):
        o = self.tab["hhea"][0]
        self.nhm = struct.unpack(">H", self.d[o + 34:o + 36])[0]
        self.hm_off = self.tab["hmtx"][0]

    def adv(self, g):
        i = min(g, self.nhm - 1)
        return struct.unpack(">H", self.d[self.hm_off + 4 * i:self.hm_off + 4 * i + 2])[0]

    # ---- 윤곽 ----
    def contours(self, g, depth=0):
        """글리프 윤곽을 폰트 단위 폴리곤 목록으로. 2차 베지에는 펴서 담는다."""
        if g >= self.nglyf or self.loca[g] >= self.loca[g + 1] or depth > 4:
            return []
        o = self.tab["glyf"][0] + self.loca[g]
        nc = struct.unpack(">h", self.d[o:o + 2])[0]
        if nc < 0:                       # 합성 글리프
            polys, p = [], o + 10
            while True:
                flags, gi = struct.unpack(">HH", self.d[p:p + 4])
                p += 4
                if flags & 1:
                    dx, dy = struct.unpack(">hh", self.d[p:p + 4])
                    p += 4
                else:
                    dx, dy = struct.unpack(">bb", self.d[p:p + 2])
                    p += 2
                if flags & 8:
                    p += 2
                elif flags & 0x40:
                    p += 4
                elif flags & 0x80:
                    p += 8
                for c in self.contours(gi, depth + 1):
                    polys.append([(x + dx, y + dy) for (x, y) in c])
                if not (flags & 0x20):
                    break
            return polys

        p = o + 10
        ends = struct.unpack(">%dH" % nc, self.d[p:p + 2 * nc])
        p += 2 * nc
        ins = struct.unpack(">H", self.d[p:p + 2])[0]
        p += 2 + ins
        npt = ends[-1] + 1
        flags = []
        while len(flags) < npt:
            f = self.d[p]
            p += 1
            flags.append(f)
            if f & 8:
                r = self.d[p]
                p += 1
                flags.extend([f] * r)
        flags = flags[:npt]
        xs, v = [], 0
        for f in flags:
            if f & 2:
                dx = self.d[p]
                p += 1
                v += dx if (f & 16) else -dx
            elif not (f & 16):
                v += struct.unpack(">h", self.d[p:p + 2])[0]
                p += 2
            xs.append(v)
        ys, v = [], 0
        for f in flags:
            if f & 4:
                dy = self.d[p]
                p += 1
                v += dy if (f & 32) else -dy
            elif not (f & 32):
                v += struct.unpack(">h", self.d[p:p + 2])[0]
                p += 2
            ys.append(v)

        polys, s = [], 0
        for e in ends:
            pts = [(xs[i], ys[i], bool(flags[i] & 1)) for i in range(s, e + 1)]
            s = e + 1
            if not pts:
                continue
            # 시작점을 곡선 위 점으로
            if not pts[0][2]:
                on = next((i for i, q in enumerate(pts) if q[2]), None)
                if on is None:               # 전부 곡선 밖 → 중점 삽입
                    mx = (pts[0][0] + pts[-1][0]) / 2.0
                    my = (pts[0][1] + pts[-1][1]) / 2.0
                    pts = [(mx, my, True)] + pts
                else:
                    pts = pts[on:] + pts[:on]
            out = [(pts[0][0], pts[0][1])]
            i, n = 1, len(pts)
            while i <= n:
                cur = pts[i % n]
                if cur[2]:
                    out.append((cur[0], cur[1]))
                    i += 1
                else:
                    nxt = pts[(i + 1) % n]
                    if nxt[2]:
                        end_pt = (nxt[0], nxt[1])
                        i += 2
                    else:                      # 곡선 밖 두 점 → 중점이 곡선 위
                        end_pt = ((cur[0] + nxt[0]) / 2.0, (cur[1] + nxt[1]) / 2.0)
                        i += 1
                    x0, y0 = out[-1]
                    for k in range(1, 9):      # 2차 베지에 8분할
                        t = k / 8.0
                        u = 1 - t
                        out.append((u * u * x0 + 2 * u * t * cur[0] + t * t * end_pt[0],
                                    u * u * y0 + 2 * u * t * cur[1] + t * t * end_pt[1]))
            polys.append(out)
        return polys

    # ---- 래스터 ----
    def glyph(self, ch, size):
        """(폭, 높이, 원점오프셋x, 원점오프셋y(위로), 알파맵) 을 캐시해 돌려준다."""
        key = (ch, size)
        if key in self._cache:
            return self._cache[key]
        g = self.gid(ch)
        sc = float(size) / self.upem
        polys = [[(x * sc, y * sc) for (x, y) in c] for c in self.contours(g)]
        aw = self.adv(g) * sc
        if not polys:
            self._cache[key] = (0, 0, 0, 0, None, aw)
            return self._cache[key]
        xs = [p[0] for c in polys for p in c]
        ys = [p[1] for c in polys for p in c]
        x0, x1 = int(min(xs)) - 1, int(max(xs)) + 2
        y0, y1 = int(min(ys)) - 1, int(max(ys)) + 2
        w, h = x1 - x0, y1 - y0
        SS = 3                                  # 초과표본
        cov = [0] * (w * h)
        for sy in range(h * SS):
            yy = y1 - (sy + 0.5) / SS           # 위에서 아래로
            xsx = []
            for c in polys:
                for i in range(len(c)):
                    ax, ay = c[i]
                    bx, by = c[(i + 1) % len(c)]
                    if (ay > yy) == (by > yy):
                        continue
                    t = (yy - ay) / (by - ay)
                    xsx.append((ax + t * (bx - ax), 1 if by > ay else -1))
            if not xsx:
                continue
            xsx.sort()
            wind, spans = 0, []
            for i in range(len(xsx) - 1):
                wind += xsx[i][1]
                if wind != 0:
                    spans.append((xsx[i][0], xsx[i + 1][0]))
            row = sy // SS
            for (a, b) in spans:
                ia = max(0, int((a - x0) * SS))
                ib = min(w * SS, int((b - x0) * SS) + 1)
                for px in range(ia, ib):
                    cx = x0 + (px + 0.5) / SS
                    if a <= cx <= b:
                        cov[row * w + px // SS] += 1
        m = SS * SS
        alpha = [min(255, 255 * v // m) for v in cov]
        if self.embolden:               # 가로 1 px 번짐으로 굵기 합성
            wb = w + 1
            nb = [0] * (wb * h)
            for j in range(h):
                for i in range(w):
                    a = alpha[j * w + i]
                    if a:
                        o = j * wb + i
                        if a > nb[o]:
                            nb[o] = a
                        if a > nb[o + 1]:
                            nb[o + 1] = a
            w, alpha, aw = wb, nb, aw + size / 24.0
        self._cache[key] = (w, h, x0, y1, alpha, aw)
        return self._cache[key]

    def width(self, s, size):
        return sum(self.glyph(c, size)[5] for c in s)

    def text(self, put, x, y, s, size, color):
        """put(px, py, (r,g,b), alpha) 로 그린다. (x, y) 는 글자 왼쪽 **위**."""
        pen = float(x)
        asc = size * 0.75                       # 대문자 윗선 기준 (근사)
        for ch in s:
            w, h, gx, gy, alpha, aw = self.glyph(ch, size)
            if alpha:
                for j in range(h):
                    for i in range(w):
                        a = alpha[j * w + i]
                        if a:
                            put(int(pen) + gx + i, int(y + asc - gy) + j, color, a)
            pen += aw
        return pen - x
