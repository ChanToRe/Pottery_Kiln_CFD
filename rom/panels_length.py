#!/usr/bin/env python3
"""
원고 Fig 4(소성실 길이 4수준)·Fig 6(계단 4수준) 낱장 — 모델 4개 × 시각 5등분 = 20 장.

`section_render.py` 의 렌더링(실제 STL 실루엣 + 적재 포함 축소모델)을 쓰되,
합성 그림 대신 한 장에 한 칸만 담는다. 최종 배치와 제목은 사용자가 하므로
그림 안에는 축·온도장·구간온도 숫자만 둔다.

  x축 Length (m)      가마 앞끝을 0 으로
  y축 Height (m)      가마 바닥을 0 으로
  색  Temperature (°C)  레인보우, 전 20 장 공통 고정 범위
  소성실 각 구간(1 m) 안에 그 시각의 기체온도를 적는다

전 패널이 같은 축척(px/m)을 쓰므로 길이 차이가 그대로 보인다.

투고본 그림의 실행 설정 (run_all.sh figures 가 이대로 부른다 — 낱장이 바이트 단위로 같다)
  Fig 4  TEXT_SIZE=38 SEG_TEXT=30 T_FROM=47 python3 panels_length.py Results/figures/fig4_length_panels
  Fig 6  TEXT_SIZE=38 SEG_TEXT=30 CACHE_TAG=_step T_FROM=47 \\
         MODELS=B_L065,B_L065_S6,B_L065_S12,B_L065_S20 TAGS=S00,S06,S12,S20 \\
         python3 panels_length.py Results/figures/fig6_steps_panels
T_FROM=47 → 47–78 h 를 5등분 (53.2·59.4·65.6·71.8·78.0 h).
"""
import csv
import hashlib
import math
import os
import sys

import calibrate
import efficiency
import geom
import plotlib as P
import rom
import run
import section_render as SR

OUT = (sys.argv[1] if len(sys.argv) > 1
       else os.path.join(run.ROOT, "Results", "figures", "fig4_length_panels"))
LENS = os.environ.get("MODELS", "B_L025,B_L045,B_L065,B_L085").split(",")
# 파일명 접두. 비우면 소성실 길이에서 만든다(L25 …) — 길이가 같은 변형끼리
# 비교할 때는 그 이름이 겹치므로 TAGS 로 직접 준다.
TAGS = [t for t in os.environ.get("TAGS", "").split(",") if t]
# 발열 스케줄을 한 모델 것으로 통일한다. 기본(빈 값)은 모델마다 실측곡선을
# 재현하도록 연료를 역산하므로 온도가 같게 나오고 차이는 연료에만 남는다.
# 같은 연료를 넣고 온도가 갈리는 것을 보이려면 이쪽을 쓴다.
SHARED = os.environ.get("SHARED_SCHED", "")
NT = int(os.environ.get("NT", "5"))                 # 시각 등분 수
# 등분 구간의 시작 [h]. 기본 0 이면 전 과정을 등분하는데, 실측 소성은 47 h 까지
# 건조·예열(165 ℃ 이하)이라 앞쪽 패널이 거의 단색이 된다. T_FROM=47 을 주면
# 승온이 실제로 일어나는 구간만 등분한다.
T_FROM = float(os.environ.get("T_FROM", "0")) * 3600.0
TLO = float(os.environ.get("TLO", "0"))             # 색범위 [℃] — Fig 2 와 통일
THI = float(os.environ.get("THI", "1200"))
PPM = float(os.environ.get("PPM", "72"))            # 축척 [px/m]
PAD = 0.18                                          # 형상 둘레 여백 [m]
_TS = float(os.environ.get("TEXT_SIZE", "22"))
ML, MR = int(4.4 * _TS), int(1.1 * _TS)             # 여백 [px], 글자 크기에 비례
MT, MB = int(1.7 * _TS), int(3.6 * _TS)
MB0 = int(0.5 * _TS)                                 # OUTER_AXES 에서 가로축 없는 행의 아래 여백 [px]
P.TEXT_SIZE = _TS
SEG_SIZE = float(os.environ.get("SEG_TEXT", "18"))     # 구간 온도 숫자 크기 (0 이면 숫자를 넣지 않는다 — 수정본 K30)
AXC, TXC = (25, 25, 30), (20, 20, 25)
TICK = 5
# 수정본(K29): OUTER_AXES=1 이면 바깥 칸에만 축 — 첫 모델(왼쪽 열)만 세로축, 마지막 시각(아래 행)만
# 가로축. 축이 없는 쪽은 여백도 없앤다(위·오른쪽 여백은 모든 칸이 같아 행·열이 맞는다).
OUTER = os.environ.get("OUTER_AXES", "") == "1"
AX_LW = int(os.environ.get("AX_LW", "1"))          # 축선 두께 [px]
XT_N = int(os.environ.get("XTICK_N", "7"))         # 눈금 수 목표
ZT_N = int(os.environ.get("ZTICK_N", "5"))
if os.environ.get("TICK_LEN"):
    TICK = int(os.environ["TICK_LEN"])

SR.TLO, SR.THI = TLO, THI
SR.SOIL_D = 0.0                     # 가마 내부만 — Fig 2 의 CFD 단면과 같은 모양
SR.BG = (255, 255, 255)


def fit_frame(models):
    """네 모델의 실루엣을 모두 담는 하나의 틀을 잡는다.

    전 패널이 같은 틀·같은 축척을 써야 길이 차이가 눈에 보인다. 틀을 가장 긴
    모델에 맞춰 잡으므로 짧은 모델의 오른쪽은 비게 되는데, 그것이 곧 결과다.
    """
    global X0, X1, Z0, Z1, PW, PH
    xa = za = 1e30
    xb = zb = -1e30
    for m in models:
        prof, _, _ = SR.silhouette(m)
        xa = min(xa, min(p[0] for p in prof))
        xb = max(xb, max(p[0] for p in prof))
        za = min(za, min(p[1] for p in prof))
        zb = max(zb, max(p[2] for p in prof))
    X0, X1 = xa - PAD, xb + PAD
    Z0, Z1 = za - PAD, zb + PAD
    SR.X0, SR.X1, SR.Z0, SR.Z1 = X0, X1, Z0, Z1
    SR.PW = PW = int(round((X1 - X0) * PPM))
    SR.PH = PH = int(round((Z1 - Z0) * PPM))
    return xa, za            # 눈금 0 으로 삼을 세계좌표 (가마 앞끝·바닥)


def nice_ticks(a, b, target=7):
    step = None
    raw = (b - a) / max(target, 2)
    mag = 10.0 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            step = m * mag
            break
    v, out = math.ceil(a / step) * step, []
    while v <= b + 1e-9:
        out.append(round(v, 10))
        v += step
    return out, step


def fmt(v, step):
    return ("%%.%df" % max(0, -int(math.floor(math.log10(step))))) % v


def text_halo(cv, x, y, s, sc):
    """검은 글자에 흰 테두리 — 색표 어디에 놓여도 읽힌다."""
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                   (-1, -1), (1, -1), (-1, 1), (1, 1)):
        cv.text(x + dx, y + dy, s, (255, 255, 255), sc=sc)
    cv.text(x, y, s, (0, 0, 0), sc=sc)


def margins(col, row, nrow):
    """칸 위치별 여백 (ML, MB). OUTER 가 아니면 모든 칸에 축."""
    if not OUTER:
        return ML, MB, True, True
    ya, xa = col == 0, row == nrow - 1
    # 가로축이 없는 행도 세로축 '0' 눈금 글자의 아래 절반이 잘리지 않게 글자 높이의 반만큼 남긴다
    return (ML if ya else 0), (MB if xa else MB0), xa, ya


def draw_axes(cv, ox, oz, ml=None, x_axis=True, y_axis=True):
    """온도장 둘레에 Length/Height 축을 Times 로 그린다."""
    ml = ML if ml is None else ml
    ax_y, ax_x = MT + PH, ml
    if y_axis:
        cv.line(ax_x, MT, ax_x, ax_y, AXC, lw=AX_LW)
    if x_axis:
        cv.line(ax_x, ax_y, ml + PW, ax_y, AXC, lw=AX_LW)
    if x_axis:
        xt, xs = nice_ticks(X0 - ox, X1 - ox, XT_N)
        for v in xt:
            x = ml + (v + ox - X0) * PPM
            if not (ml <= x <= ml + PW):
                continue
            cv.line(x, ax_y, x, ax_y + TICK, AXC, lw=AX_LW)
            s = fmt(v, xs)
            cv.text(x - cv.text_w(s) / 2.0, ax_y + TICK + 4, s, TXC)
        lx = "Length (m)"
        cv.text(ml + PW / 2.0 - cv.text_w(lx) / 2.0, ax_y + TICK + int(1.3 * _TS), lx, TXC)
    if y_axis:
        zt, zs = nice_ticks(Z0 - oz, Z1 - oz, ZT_N)
        for v in zt:
            y = MT + (Z1 - v - oz) * PPM
            if not (MT <= y <= ax_y):
                continue
            cv.line(ax_x - TICK, y, ax_x, y, AXC, lw=AX_LW)
            s = fmt(v, zs)
            cv.text(ax_x - TICK - 4 - cv.text_w(s), y - cv.cap_h() / 2.0, s, TXC)
        cv.text(2, 3, "Height (m)", TXC)          # 회전 글꼴이 없어 축 위쪽에 가로로


def calib_sig(models):
    """모델들이 쓰는 형식별 보정값 (A_hot, h_conv_ref, mdot_ref) 을 글자로."""
    out = []
    for t in sorted({geom.extract(m)["type"] for m in models}):
        out.append("%s:%.6g/%.6g/%.6g" % (
            t, calibrate.A_hot_of(t), calibrate.h_conv_ref(t),
            calibrate.read_cfd("%s_L065" % t)["mdot"]))
    return ";".join(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    sched = rom.load_schedule(run.SCHED)
    fit = run.load_fit()
    ts, Ts = run.load_curve()

    cache_dir = os.path.join(run.ROOT, "Results", "figures", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_p = os.path.join(cache_dir, "section_sched%s.csv" % os.environ.get("CACHE_TAG", ""))
    # 캐시를 모델명만으로 열지 않는다. 발열 스케줄은 적재율·차폐율·보정
    # 기준점·분할·외기, φ(rom_phi.csv), 정상상태 CFD 보정값에 따라 달라지므로
    # 서명이 다르면 버리고 다시 푼다.
    # (2026-08-17: 서명이 없던 탓에 옛 설정의 스케줄이 재사용되어 도면 온도가
    #  본문 표보다 60~70 도 낮게 나왔다.)
    sig = "LOAD=%.3f BLOCK=%s FIT=%s SEG=%.3f TAMB=%.2f PHI=%s CAL=%s" % (
        rom.LOAD_FRAC, rom.BLOCK_FRAC, run.FIT_NODE, SR.SEG_M, run.T_AMB,
        hashlib.md5(open(run.PHI_CSV, "rb").read()).hexdigest()[:12],
        calib_sig(LENS + ([SHARED] if SHARED else [])))
    cache = {}
    if os.path.exists(cache_p):
        lines = open(cache_p).read().splitlines()
        head = lines[0] if lines else ""
        if head.startswith("# ") and head[2:].strip() == sig:
            for ln in lines[2:]:
                if not ln.strip():
                    continue
                c = ln.split(",")
                cache.setdefault(c[0], []).append(
                    dict(t0=float(c[1]), t1=float(c[2]), Q=float(c[3])))
        else:
            print("  캐시 설정이 달라 버린다")
            print("    캐시: %s" % (head[2:].strip() or "(서명 없음)"))
            print("    지금: %s" % sig)

    new_cache = [False]

    # ---- 시각: 전 모델 공통으로 총 소성시간을 NT 등분 ----
    t_tot = max(r["t1"] for rows in cache.values() for r in rows) if cache else None

    ox, oz = fit_frame(LENS)
    print("  틀 x %.2f~%.2f  z %.2f~%.2f  %dx%d px" % (X0, X1, Z0, Z1, PW, PH))
    data = {}
    for m in LENS:
        print("  %s 형상..." % m, flush=True)
        codes, zones, g, prof, zone_at, depths = SR.build_codes(m)
        src = SHARED or m
        if src in cache:
            rows = cache[src]
        else:
            print("  %s 연료 역산... (몇 분)" % m, flush=True)
            _, rows, _ = efficiency.demand(src, fit, sched, ts, Ts, seg_m=SR.SEG_M)
            cache[src] = [dict(t0=r["t0"], t1=r["t1"], Q=r["Q"]) for r in rows]
            new_cache[0] = True
        tt = t_tot or max(r["t1"] for r in rows)
        want = [T_FROM + (tt - T_FROM) * k / NT for k in range(1, NT + 1)]

        k2, _ = calibrate.build(m, seg_m=SR.SEG_M, T_amb=run.T_AMB)
        snaps, wi = [], 0
        for r in rows:
            phi = next(f["phi"] for f in fit if f["t1"] == r["t1"])
            for _ in range(int(round((r["t1"] - r["t0"]) / run.DT))):
                k2.step(run.DT, r["Q"], phi)
                while wi < len(want) and k2.t >= want[wi]:
                    snaps.append((k2.t, list(k2.T),
                                  [list(k2.stacks[z].T) for z in zones]))
                    wi += 1
        while len(snaps) < NT:               # 끝 시각이 살짝 못 미치는 경우
            snaps.append((k2.t, list(k2.T),
                          [list(k2.stacks[z].T) for z in zones]))
        data[m] = (codes, zones, g, zone_at, depths, k2, snaps)
        print("     스냅 %d장 (마지막 %.1f h)" % (len(snaps), snaps[-1][0] / 3600), flush=True)

    if new_cache[0]:            # 다음 실행에서 역산을 건너뛰도록 남긴다
        with open(cache_p, "w") as f:
            f.write("# %s\n" % sig)
            f.write("model,t0,t1,Q_W\n")
            for mm, rr in cache.items():
                for r in rr:
                    f.write("%s,%.1f,%.1f,%.2f\n" % (mm, r["t0"], r["t1"], r["Q"]))
        print("  발열 스케줄 캐시 저장 → %s" % os.path.basename(cache_p))

    tlog = open(os.path.join(OUT, "times.txt"), "w")
    seg_rows = []        # 구간별 기체온도 — 선그래프(K30)용 segments.csv
    for m in LENS:
        codes, zones, g, zone_at, depths, k, snaps = data[m]
        wk = g["ware_keys"]
        x_P1 = (g["L_fire"] + 0.30) * math.cos(math.radians(SR.geom.SLOPE_DEG))
        tag = TAGS[LENS.index(m)] if TAGS else "L%02d" % round(g["L_fire"] * 10)
        for ti, (tsec, Tn, walls) in enumerate(snaps):
            k.T = Tn
            for z, wt in zip(zones, walls):
                k.stacks[z].T = wt
            pal, node_of = SR.palette(k, zones, depths)
            img = b"".join(map(pal.__getitem__, codes))

            ml, mb, xa, ya = margins(LENS.index(m), ti, len(snaps))
            cv = P.Canvas(ml + PW + MR, MT + PH + mb, (255, 255, 255))
            for j in range(PH):
                o = ((MT + j) * cv.w + ml) * 3
                cv.buf[o:o + PW * 3] = img[j * PW * 3:(j + 1) * PW * 3]
            draw_axes(cv, ox, oz, ml, xa, ya)

            # ---- 소성실 구간마다 그 시각의 기체온도 ----
            for j, z in enumerate(wk):
                Tg = Tn[node_of[z]] - 273.15
                seg_rows.append(dict(tag=tag, model=m, t_index=ti + 1, t_h="%.2f" % (tsec / 3600.0), segment=j + 1,
                                     s_mid_m="%.3f" % ((j + 0.5) * g["seg_len"]), T_gas_C="%.1f" % Tg))
                if SEG_SIZE <= 0:
                    continue
                xc = (j + 0.5) / len(wk) * x_P1
                i = int((xc - X0) * PPM)
                if not (0 <= i < PW):
                    continue
                col = [jj for jj in range(PH) if codes[jj * PW + i] == zones.index(z) * 64]
                if not col:
                    continue
                yc = MT + 0.5 * (col[0] + col[-1])
                s = "%.0f°C" % Tg
                sc = SEG_SIZE / P.TEXT_SIZE
                text_halo(cv, ml + i - cv.text_w(s, sc) / 2.0,
                          yc - cv.cap_h(sc) / 2.0, s, sc)

            p = os.path.join(OUT, "%s_t%d.png" % (tag, ti + 1))
            cv.save(p)
            Tw = [Tn[node_of[z]] - 273.15 for z in wk]
            tlog.write("%s t%d %s %.2f h  소성실 %.0f~%.0f degC (평균 %.0f)\n"
                       % (tag, ti + 1, m, tsec / 3600.0,
                          min(Tw), max(Tw), sum(Tw) / len(Tw)))
            print("→ %s  (%.1f h)" % (os.path.basename(p), tsec / 3600.0), flush=True)
    tlog.close()
    with open(os.path.join(OUT, "segments.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(seg_rows[0]))
        w.writeheader()
        w.writerows(seg_rows)
    print("→ segments.csv (구간 %d 행)" % len(seg_rows))
    if os.environ.get("NO_CBAR") == "1":
        return

    # ---- 공통 컬러바 ----
    # 크기와 글자는 도면 조판에 맞춰 키운다. 눈금은 100 단위 고정.
    P.TEXT_SIZE = float(os.environ.get("CBAR_TS", "46"))
    cw = int(os.environ.get("CBAR_W", "64"))
    ch = int(os.environ.get("CBAR_H", "2300"))
    step = float(os.environ.get("CBAR_STEP", "100"))
    pad = int(P.TEXT_SIZE * 1.6)
    cb = P.Canvas(cw + int(P.TEXT_SIZE * 7), ch + pad * 2, (255, 255, 255))
    for j in range(ch):
        cb.fill(14, pad + j, 14 + cw, pad + j, SR.CMAP(1.0 - j / (ch - 1.0)))
    cb.line(14, pad, 14, pad + ch, AXC, lw=AX_LW)
    cb.line(14 + cw, pad, 14 + cw, pad + ch, AXC, lw=AX_LW)
    cb.line(14, pad, 14 + cw, pad, AXC, lw=AX_LW)
    cb.line(14, pad + ch, 14 + cw, pad + ch, AXC, lw=AX_LW)
    v = step * round(TLO / step)
    while v <= THI + 1e-9:
        if v >= TLO - 1e-9:
            y = pad + ch * (1.0 - (v - TLO) / (THI - TLO))
            cb.line(14 + cw, y, 14 + cw + TICK * 2, y, AXC, lw=AX_LW)
            cb.text(14 + cw + TICK * 2 + 8, y - cb.cap_h() / 2.0, "%.0f" % v, TXC)
        v += step
    cb.text(8, 2, "Temperature (°C)", TXC)
    cb_p = os.environ.get("CBAR_OUT") or os.path.join(OUT, "colorbar.png")
    cb.save(cb_p)
    print("→ %s" % cb_p)


if __name__ == "__main__":
    main()
