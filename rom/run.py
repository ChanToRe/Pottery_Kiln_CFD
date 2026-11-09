#!/usr/bin/env python3
"""
축소모델 공통 설정과 역문제 — 화구 개구율 φ(t) 역산

화구 개구율 φ 를 연료 구간별로 역산해 실측 승온곡선에 맞춘다
(형식 B, 소성실 첫 구간 = FIT_NODE 'ware1' 기준). 확정된 φ(t) 는 모든 형식·변형에
똑같이 적용된다 (조업자 행동을 고정하고 가마 형식만 바꾸는 대조).

rom_phi.csv 는 다른 모든 분석(study_data, efficiency …)이 읽는 공통 입력이다.

    python3 run.py        → Results/rom/rom_phi.csv
"""
import os
import math

import calibrate
import rom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RESULTS = os.path.join(ROOT, "Results", "rom")
SCHED = os.path.join(ROOT, "Data", "fuel_schedule.csv")
CURVE = os.path.join(ROOT, "Data", "heating_curve_Hong2011.csv")

DT = 60.0
T_SEAL = 78 * 3600.0          # 화구·연도 동시 폐쇄 (소성 끝)
T_AMB = 292.45                # 19.3 ℃ — 가마 건조기간(2009-05-12–22) 평균기온, 소성기 외기의 대용값 (N-61)
FIT_FORM = "B"                # 역문제를 푸는 형식

# φ 역산 때의 적재 설정 — 기본은 본계산과 같은 값(rom.LOAD_FRAC·BLOCK_FRAC)이다.
# 투고본의 rom_phi.csv 는 빈 가마(적재 0, 차폐 0)로 역산되었고(2026-08-11 07:32, 그때
# rom.py 의 LOAD_FRAC 기본값이 0), 모든 비교 계산은 적재 0.5·차폐 0.10 으로 돌아
# 역산과 본계산의 물리 조건이 달랐다 (오류목록 N-52). 투고본 φ 를 재현하려면
#   FIT_LOAD_FRAC=0 FIT_BLOCK_FRAC=0 python3 run.py
FIT_LOAD_FRAC = float(os.environ.get("FIT_LOAD_FRAC", str(rom.LOAD_FRAC)))
FIT_BLOCK_FRAC = float(os.environ.get("FIT_BLOCK_FRAC", str(rom.BLOCK_FRAC)))


def load_curve():
    ts, Ts = [], []
    with open(CURVE) as f:
        for line in f:
            if line.startswith("#") or line.startswith("t_h"):
                continue
            p = line.split(",")
            if len(p) >= 2:
                ts.append(float(p[0]) * 3600.0)
                Ts.append(float(p[1]) + 273.15)
    return ts, Ts


def curve_at(ts, Ts, t):
    if t <= ts[0]:
        return Ts[0]
    for i in range(1, len(ts)):
        if t <= ts[i]:
            f = (t - ts[i - 1]) / (ts[i] - ts[i - 1])
            return Ts[i - 1] + f * (Ts[i] - Ts[i - 1])
    return Ts[-1]


# 역산이 실측 승온곡선에 맞출 지점.
#   comb  연소부 기체 (종전 기본값)
#   ware1 소성실 앞쪽 구간
#   ware  소성실 전 구간 평균
# 홍진근 2011 은 "소성실 4곳, 연도부 1곳" 에서 측정했다고 적으므로 실측 위치는
# 소성실이다. 종전 기본값(comb)은 위치가 어긋나 있었다.
FIT_NODE = os.environ.get("FIT_NODE", "ware1")
# 역산과 본계산이 **같은 분할**을 써야 한다. 분할하지 않으면 노드 1 이 소성실
# 전체를 뜻하고, 1 m 로 쪼개면 노드 1 이 앞쪽 구간을 뜻한다 — 두 경로가 서로
# 다른 분할을 쓰면 φ 는 소성실 전체에, 연료는 앞쪽 구간에 맞춰지는 엇갈림이 난다.
SEG_M = float(os.environ.get("SEG_M", "1.0"))


def fit_T(k):
    """FIT_NODE 가 가리키는 기체온도 [K].

    노드 구성이 두 가지다. 분할하지 않으면 ['comb','ware'] 2개, seg_m 을 주면
    ['comb','ware1',...,'flue'] 다. 어느 쪽이든 인덱스 1 이 소성실의 앞쪽이다.
    """
    n = len(k.T)
    if FIT_NODE == "comb" or n < 2:
        return k.T[0]
    if FIT_NODE == "ware1" or n == 2:
        return k.T[1]
    return sum(k.T[1:n - 1]) / (n - 2)      # ware 평균 (comb·flue 제외)


def advance(k, sched, t0, t1, phi, rows=None, every=600.0, qmul=1.0):
    """qmul: 발열률 배수. 온도 이력을 고정하고 연료를 구하는 역문제에 쓴다."""
    n = int(round((t1 - t0) / DT))
    nxt = t0
    for i in range(n):
        r = k.step(DT, qmul * rom.Q_at(sched, t0 + i * DT), phi)
        if rows is not None and r["t"] >= nxt:
            r["stored"] = k.stored()
            rows.append(r)
            nxt += every
    return fit_T(k)


def fit_phi(sched, ts, Ts):
    """구간별 이분법. 앞 구간의 종료 상태가 뒤 구간의 초기조건이 된다.

    적재 설정은 FIT_LOAD_FRAC·FIT_BLOCK_FRAC 로 따로 준다 (위 주석 참조).
    """
    saved = rom.LOAD_FRAC, rom.BLOCK_FRAC
    rom.LOAD_FRAC, rom.BLOCK_FRAC = FIT_LOAD_FRAC, FIT_BLOCK_FRAC
    try:
        k, _ = calibrate.build("%s_L065" % FIT_FORM, seg_m=SEG_M, T_amb=T_AMB)
    finally:
        rom.LOAD_FRAC, rom.BLOCK_FRAC = saved
    bounds = [p[0] for p in sched if p[1] > 0] + [T_SEAL]
    out = []
    for j in range(len(bounds) - 1):
        t0, t1 = bounds[j], bounds[j + 1]
        target = curve_at(ts, Ts, t1)
        state = k.save()
        lo, hi = 1e-4, 1.0        # φ 를 키우면 공기가 늘어 온도가 내려간다

        def endT(phi):
            k.restore(state)
            return advance(k, sched, t0, t1, phi)

        Thi, Tlo = endT(hi), endT(lo)
        if Thi >= target:
            phi, note = hi, "개방한계"
        elif Tlo <= target:
            phi, note = lo, "폐쇄한계"
        else:
            for _ in range(18):
                mid = math.sqrt(lo * hi)     # 저항이 1/φ² 이므로 로그중점
                if endT(mid) > target:
                    lo = mid
                else:
                    hi = mid
            phi, note = math.sqrt(lo * hi), ""
        k.restore(state)
        got = advance(k, sched, t0, t1, phi)
        out.append(dict(t0=t0, t1=t1, phi=phi, target=target, got=got,
                        note=note, Q=rom.Q_at(sched, t0)))
    return out


PHI_CSV = os.path.join(RESULTS, "rom_phi.csv")


def save_fit(fit):
    with open(PHI_CSV, "w") as f:
        f.write("t0_h,t1_h,phi,Q_kW,target_C,got_C,note\n")
        for x in fit:
            f.write("%.1f,%.1f,%.6f,%.1f,%.1f,%.1f,%s\n" %
                    (x["t0"] / 3600, x["t1"] / 3600, x["phi"], x["Q"] / 1e3,
                     x["target"] - 273.15, x["got"] - 273.15, x["note"]))


def load_fit():
    fit = []
    with open(PHI_CSV) as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split(",")
            fit.append(dict(t0=float(p[0]) * 3600, t1=float(p[1]) * 3600,
                            phi=float(p[2]), Q=float(p[3]) * 1e3,
                            target=float(p[4]) + 273.15,
                            got=float(p[5]) + 273.15, note=p[6]))
    return fit


def main(refit=True):
    os.makedirs(RESULTS, exist_ok=True)
    sched = rom.load_schedule(SCHED)
    ts, Ts = load_curve()

    print("── 1. 화구 개구율 역산 (형식 %s, 실측 승온곡선 대조) ──\n" % FIT_FORM)
    if refit or not os.path.exists(PHI_CSV):
        fit = fit_phi(sched, ts, Ts)
        save_fit(fit)
    else:
        fit = load_fit()
    print("%9s %8s %8s %9s %9s %7s" %
          ("구간[h]", "Q[kW]", "φ", "실측[℃]", "계산[℃]", "개구[m2]"))
    for f in fit:
        print("%3.0f - %3.0f %8.0f %8.4f %9.0f %9.0f %7.3f  %s" %
              (f["t0"] / 3600, f["t1"] / 3600, f["Q"] / 1e3, f["phi"],
               f["target"] - 273.15, f["got"] - 273.15,
               f["phi"] * 0.5538, f["note"]))

    return fit, sched, (ts, Ts)


if __name__ == "__main__":
    main()
