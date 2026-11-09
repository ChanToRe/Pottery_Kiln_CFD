#!/usr/bin/env python3
"""
ParaView 가 뽑은 온도장 낱장에 축(Length/Height)을 Times 로 얹는다.

ParaView 의 AxesGrid 는 두께 0 인 단면에서 렌더되지 않으므로 축은 이쪽에서
그린다. `render_panels.py` 가 남긴 `mapping.txt` 의 평행투영 사상을 그대로
쓰므로 눈금이 온도장과 정확히 맞는다.

    TEXT_SIZE=38 python3 cfd/post/panel_axes.py <패널디렉터리>   (Fig 2)

`<패널디렉터리>/raw/*.png` (축 없는 원본) 하나마다 `<패널디렉터리>/<같은 이름>.png` (축 포함) 를 만든다. 그림 안에는
축과 눈금만 두고, 제목·형식명·시각은 넣지 않는다 (사용자가 배치한다).
"""
import glob
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "rom"))
import plotlib as P                                            # noqa: E402
import pngio                                                   # noqa: E402

# 여백은 글자 크기에 비례시킨다. 글자만 키우면 축 라벨이 잘린다.
_TS = float(os.environ.get("TEXT_SIZE", "22"))
ML, MR = int(4.4 * _TS), int(1.1 * _TS)   # 왼쪽에 Height 축, 오른쪽 여백
MT, MB = int(1.7 * _TS), int(3.6 * _TS)   # 위에 Height 제목, 아래에 Length 축
AXC = (25, 25, 30)
TXC = (20, 20, 25)
TICK = int(os.environ.get("TICK_LEN", "5"))
P.TEXT_SIZE = _TS
# 수정본(K29): OUTER_AXES=1 이면 바깥 칸에만 축. 낱장 이름 <열>_t<행>.png 에서 열 순서는 COLS
# (기본 A,B,C — 첫 열만 세로축), 행은 t 번호(가장 큰 번호 = 아래 행만 가로축).
OUTER = os.environ.get("OUTER_AXES", "") == "1"
COLS = os.environ.get("COLS", "A,B,C").split(",")
AX_LW = int(os.environ.get("AX_LW", "1"))
XT_N = int(os.environ.get("XTICK_N", "7"))
ZT_N = int(os.environ.get("ZTICK_N", "5"))


def nice_ticks(a, b, target=7):
    """1·2·5 계열 간격으로 눈금을 고른다."""
    span = b - a
    raw = span / max(target, 2)
    mag = 10.0 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            step = m * mag
            break
    t0 = math.ceil(a / step) * step
    out = []
    v = t0
    while v <= b + 1e-9:
        out.append(round(v, 10))
        v += step
    return out, step


def fmt(v, step):
    dec = max(0, -int(math.floor(math.log10(step))))
    return ("%%.%df" % dec) % (v + 0.0)


def load_mapping(d):
    mp = {}
    for ln in open(os.path.join(d, "mapping.txt")):
        if ln.startswith("#") or not ln.strip():
            continue
        p = ln.split()
        mp[p[0]] = [float(x) for x in p[1:]] if len(p) > 2 else float(p[1])
    return mp


def compose(src, dst, mp, x_axis=True, y_axis=True):
    ml = ML if y_axis else 0
    mb = MB if x_axis else 0
    w, h, buf = pngio.read_png(src)
    W, H = int(mp["W"]), int(mp["H"])
    if (w, h) != (W, H):
        raise ValueError("%s 크기 %dx%d 가 mapping %dx%d 와 다르다" % (src, w, h, W, H))
    cx, cz, ppm = mp["cx"], mp["cz"], mp["ppm"]
    x0, x1 = mp["xlim"]
    z0, z1 = mp["zlim"]
    ox, oz = mp.get("origin", [0.0, 0.0])   # 눈금 0 으로 삼을 세계좌표

    cv = P.Canvas(ml + W + MR, MT + H + mb, (255, 255, 255))
    # 온도장 붙이기
    for y in range(H):
        s = y * W * 3
        o = ((MT + y) * cv.w + ml) * 3
        cv.buf[o:o + W * 3] = buf[s:s + W * 3]

    def PX(X):
        return ml + W / 2.0 + (X - cx) * ppm

    def PY(Z):
        return MT + H / 2.0 - (Z - cz) * ppm

    ax_y = MT + H          # 가로축 위치 (그림 아래변)
    ax_x = ml              # 세로축 위치 (그림 왼변)
    if y_axis:
        cv.line(ax_x, MT, ax_x, ax_y, AXC, lw=AX_LW)
    if x_axis:
        cv.line(ax_x, ax_y, ml + W, ax_y, AXC, lw=AX_LW)
        xt, xs = nice_ticks(x0 - ox, x1 - ox, XT_N)
        for v in xt:
            x = PX(v + ox)
            cv.line(x, ax_y, x, ax_y + TICK, AXC, lw=AX_LW)
            s = fmt(v, xs)
            cv.text(x - cv.text_w(s) / 2.0, ax_y + TICK + 4, s, TXC)
        lx = "Length (m)"
        cv.text(ml + W / 2.0 - cv.text_w(lx) / 2.0, ax_y + TICK + int(1.3 * _TS), lx, TXC)
    if y_axis:
        zt, zs = nice_ticks(z0 - oz, z1 - oz, ZT_N)
        for v in zt:
            y = PY(v + oz)
            cv.line(ax_x - TICK, y, ax_x, y, AXC, lw=AX_LW)
            s = fmt(v, zs)
            cv.text(ax_x - TICK - 4 - cv.text_w(s), y - cv.cap_h() / 2.0, s, TXC)
        # 세로축 제목은 회전 글꼴이 없으므로 축 위쪽에 가로로 둔다.
        cv.text(2, 3, "Height (m)", TXC)
    cv.save(dst)


def main():
    d = sys.argv[1]
    raw = os.path.join(d, "raw")
    mp = load_mapping(raw)
    n = 0
    srcs = sorted(glob.glob(os.path.join(raw, "*.png")))
    tmax = max(int(os.path.basename(p).split("_t")[1].split(".")[0]) for p in srcs) if OUTER else 0
    for src in srcs:
        dst = os.path.join(d, os.path.basename(src))
        if OUTER:
            col, t = os.path.basename(src)[:-4].split("_t")
            compose(src, dst, mp, x_axis=int(t) == tmax, y_axis=col == COLS[0])
        else:
            compose(src, dst, mp)
        print("→ %s" % os.path.basename(dst))
        n += 1
    print("%d 장" % n)


if __name__ == "__main__":
    main()
