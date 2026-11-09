#!/usr/bin/env python3
"""
2단계 민감도 (수정 계획 2-2e·h·i·j·k·l·m·n) — 가정을 바꿔도 형식·길이·계단의 '차이'가 유지되는가.

경우마다 매개변수를 바꾸고 φ(t) 를 형식 B 로 다시 역산한 뒤(run.fit_phi), 아홉 가마
(형식 A·B·C, 길이 2.5·4.5·8.5 m, 계단 6·12·20) 의 연료와 78 h 온도(가스·기물)를 efficiency.demand 로
낸다. '화구 개구' 와 '경사(φ 고정)' 경우는 역산하지 않고 기준 φ(Results/rom/rom_phi.csv)를 쓴다.

φ 를 다시 역산하는 경우 B_L065 의 연료는 구성상 언제나 일정표 총량(3,600 kg)이다 — 역산이
B 를 실측 승온곡선에 맞추기 때문이다. 그런 경우에는 다른 가마와의 차이와 φ 를 본다.

    python3 sensitivity.py            경우들을 병렬로 돌린다 (끝난 경우는 건너뛴다)
    python3 sensitivity.py --summary  결과만 다시 모은다
출력: Results/rom/sensitivity/<경우>.json, Results/rom/sensitivity.txt, sensitivity_cases.csv
"""
import csv
import json
import math
import multiprocessing as mp
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "Results", "rom", "sensitivity")
TABLE4 = os.path.join(HERE, "..", "Data", "table4_Hong2011.csv")
NPROC = int(os.environ.get("NPROC", "18"))

FORMS = ["A_L065", "B_L065", "C_L065"]
LENGTHS = ["B_L025", "B_L045", "B_L065", "B_L085"]
STEPS = ["B_L065_S6", "B_L065_S12", "B_L065_S20"]
MODELS = FORMS + ["B_L025", "B_L045", "B_L085"] + STEPS
SLOPE0 = 15.0

# (id, 계획 항목, 설명, 설정). 설정 키:
#   rom      rom 모듈 상수 {이름: 값} (WALL_th 는 rom.WALL["th"])
#   refit    φ 다시 역산 (기본 True)
#   phi_mul  기준 φ 에 곱함 (refit=False 와 함께)
#   curve_dT 목표 곡선 온도 오프셋 [K], curve_dt 시간 오프셋 [h]
#   slope    소성실 경사 [°] → 연돌고 H 만 바꾼다 (A_hot·h 보정은 15° CFD 그대로)
CASES = [
    ("base", "기준", "기준 (φ 다시 역산 — 2-1d 와 같아야 한다)", {}),
    ("hexp05", "2-2e", "대류 지수 0.8 → 0.5", {"rom": {"H_EXP": 0.5}}),
    ("hexp10", "2-2e", "대류 지수 0.8 → 1.0", {"rom": {"H_EXP": 1.0}}),
    ("load03", "2-2h", "적재 점유율 0.5 → 0.3", {"rom": {"LOAD_FRAC": 0.3}}),
    ("load07", "2-2h", "적재 점유율 0.5 → 0.7", {"rom": {"LOAD_FRAC": 0.7}}),
    ("blk005", "2-2h", "복사 차폐율 0.10 → 0.05", {"rom": {"BLOCK_FRAC": 0.05}}),
    ("blk020", "2-2h", "복사 차폐율 0.10 → 0.20", {"rom": {"BLOCK_FRAC": 0.20}}),
    ("lhv085", "2-2j", "발열량 14.7 → 12.5 MJ/kg (−15 %)", {"rom": {"LHV_EFF": 14.7e6 * 0.85}}),
    ("lhv115", "2-2j", "발열량 14.7 → 16.9 MJ/kg (+15 %)", {"rom": {"LHV_EFF": 14.7e6 * 1.15}}),
    ("cp085", "2-2j", "기물 비열 850 → 723 J/kgK (−15 %)", {"rom": {"WARE_CP": 850.0 * 0.85}}),
    ("cp115", "2-2j", "기물 비열 850 → 978 J/kgK (+15 %)", {"rom": {"WARE_CP": 850.0 * 1.15}}),
    ("wall025", "2-2j", "벽 두께 0.35 → 0.25 m", {"rom": {"WALL_th": 0.25}}),
    ("wall045", "2-2j", "벽 두께 0.35 → 0.45 m", {"rom": {"WALL_th": 0.45}}),
    ("phi050", "2-2j", "화구 개구 φ × 0.5 (φ 고정)", {"refit": False, "phi_mul": 0.5}),
    ("phi080", "2-2j", "화구 개구 φ × 0.8 (φ 고정)", {"refit": False, "phi_mul": 0.8}),
    ("phi120", "2-2j", "화구 개구 φ × 1.2 (φ 고정)", {"refit": False, "phi_mul": 1.2}),
    ("phi150", "2-2j", "화구 개구 φ × 1.5 (φ 고정)", {"refit": False, "phi_mul": 1.5}),
    ("cin06", "2-2k", "C_in 0.80 → 0.6", {"rom": {"C_IN": 0.6}}),
    ("cin10", "2-2k", "C_in 0.80 → 1.0", {"rom": {"C_IN": 1.0}}),
    ("crvm30", "2-2l", "목표 곡선 −30 ℃", {"curve_dT": -30.0}),
    ("crvp30", "2-2l", "목표 곡선 +30 ℃", {"curve_dT": 30.0}),
    ("crvm2h", "2-2l", "목표 곡선 −2 h", {"curve_dt": -2.0}),
    ("crvp2h", "2-2l", "목표 곡선 +2 h", {"curve_dt": 2.0}),
    ("slp10", "2-2n", "경사 15° → 10° (φ 다시 역산)", {"slope": 10.0}),
    ("slp20", "2-2n", "경사 15° → 20° (φ 다시 역산)", {"slope": 20.0}),
    ("slp10f", "2-2n", "경사 15° → 10° (φ 고정)", {"slope": 10.0, "refit": False}),
    ("slp20f", "2-2n", "경사 15° → 20° (φ 고정)", {"slope": 20.0, "refit": False}),
]
T4_HOURS = [48, 54, 60, 66, 72, 77]      # 〈표 4〉 측정 시각 가운데 소성 중후반


def dH_slope(model, deg):
    """경사를 바꿀 때 연돌고 변화. 소성부는 경사를 따라 (L + 0.30) m (geom.extract 의 x_P1)."""
    L = int(model.split("_L")[1][:3]) / 10.0
    return (L + 0.30) * (math.sin(math.radians(deg)) - math.sin(math.radians(SLOPE0)))


def apply(cfg):
    import calibrate
    import rom
    import run
    for k, v in cfg.get("rom", {}).items():
        if k == "WALL_th":
            rom.WALL["th"] = v
        else:
            setattr(rom, k, v)
        if k == "LOAD_FRAC":
            run.FIT_LOAD_FRAC = v           # 역산도 같은 적재로 (run.py 주석 N-52)
        if k == "BLOCK_FRAC":
            run.FIT_BLOCK_FRAC = v
    if "slope" in cfg:
        orig = calibrate.build

        def build(model, seg_m=None, **kw):
            k, info = orig(model, seg_m=seg_m, **kw)
            k.H = k.H + dH_slope(model, cfg["slope"])
            return k, info
        calibrate.build = build


def table4_run(fit, sched):
    """형식 B 를 φ(t) 로 전진시키며 〈표 4〉 측정 시각의 소성실 앞·뒤 구간 온도를 잰다."""
    import calibrate
    import rom
    import run
    k, _ = calibrate.build("B_L065", seg_m=run.SEG_M, T_amb=run.T_AMB)
    want = [h * 3600.0 for h in T4_HOURS]
    out = []
    for f in fit:
        n = int(round((f["t1"] - f["t0"]) / run.DT))
        for i in range(n):
            t = f["t0"] + i * run.DT
            k.step(run.DT, rom.Q_at(sched, t), f["phi"])
            while want and k.t >= want[0] - 1e-6:
                out.append(dict(t_h=want.pop(0) / 3600.0,
                                gas_front=k.T[1] - 273.15, gas_back=k.T[-2] - 273.15,
                                ware_front=k.ware[1].T - 273.15, ware_back=k.ware[-2].T - 273.15))
    return out


def work(case):
    cid, item, label, cfg = case
    path = os.path.join(OUT, cid + ".json")
    if os.path.exists(path):
        return cid, "있음"
    os.chdir(HERE)
    sys.path.insert(0, HERE)
    apply(cfg)
    import efficiency
    import rom
    import run
    sched = rom.load_schedule(run.SCHED)          # 발열량을 바꾼 뒤에 읽어야 한다 (kg × LHV)
    ts, Ts = run.load_curve()
    ts = [t + cfg.get("curve_dt", 0.0) * 3600.0 for t in ts]
    Ts = [T + cfg.get("curve_dT", 0.0) for T in Ts]
    if cfg.get("refit", True):
        fit = run.fit_phi(sched, ts, Ts)
    else:
        fit = run.load_fit()
        for f in fit:
            f["phi"] = min(1.0, f["phi"] * cfg.get("phi_mul", 1.0))
    res = dict(id=cid, item=item, label=label, cfg=cfg,
               phi=[dict(t0_h=f["t0"] / 3600, t1_h=f["t1"] / 3600, phi=f["phi"],
                         note=f.get("note", "")) for f in fit], models={})
    for m in MODELS:
        k, rows, _ = efficiency.demand(m, fit, sched, ts, Ts)
        res["models"][m] = dict(
            fuel=sum(r["fuel"] for r in rows),
            lam_min=min(r["lam_min"] for r in rows),
            notes=[r["note"] for r in rows if r["note"]],
            gas=[T - 273.15 for T in k.T],
            ware=[w.T - 273.15 for w in k.ware],
            ware_kg=sum(w.m_cp for w in k.ware) / rom.WARE_CP,
            H=k.H)
    if cid == "base":
        res["table4"] = table4_run(fit, sched)
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    return cid, "완료"


# ── 요약 ─────────────────────────────────────────────────
RANGES = [(1000, 1100), (950, 1100), (1000, 1150), (1000, 1200)]


def metrics(r):
    M = r["models"]
    f = dict((m, M[m]["fuel"]) for m in M)
    ware = lambda m: M[m]["gas"][1:-1]            # 소성실 구간 (연소실·연도 제외)
    d = dict(
        phi_last=r["phi"][-1]["phi"],
        fuel_A=f["A_L065"], fuel_B=f["B_L065"], fuel_C=f["C_L065"],
        dA=100 * (f["A_L065"] / f["B_L065"] - 1), dC=100 * (f["C_L065"] / f["B_L065"] - 1),
        span=100 * (max(f[m] for m in FORMS) - min(f[m] for m in FORMS)) / min(f[m] for m in FORMS),
        lam_min=min(M[m]["lam_min"] for m in FORMS),
        spread=dict((m, max(ware(m)) - min(ware(m))) for m in LENGTHS),
        per_kg=dict((m, f[m] / M[m]["ware_kg"]) for m in LENGTHS),
        steps=dict((m, 100 * (f[m] / f["B_L065"] - 1)) for m in STEPS),
        notes=sorted(set(n for m in M for n in M[m]["notes"])
                     | set(p["note"] for p in r["phi"] if p["note"])))
    return d


def in_range(T, lo, hi):
    return sum(1 for x in T if lo <= x <= hi), len(T)


def summary():
    runs = []
    for cid, item, label, cfg in CASES:
        p = os.path.join(OUT, cid + ".json")
        if os.path.exists(p):
            runs.append(json.load(open(p)))
    if not runs:
        print("결과 없음"); return
    L = ["2단계 민감도 — 가정을 바꿔도 형식·길이·계단의 차이가 유지되는가 (78 h, 소성실 1 m 분할)",
         "φ 를 다시 역산한 경우 B_L065 연료는 구성상 일정표 총량이다. 차이는 B 기준 [%].\n",
         "%-6s %-34s %7s %7s %7s %6s %6s %6s %5s | %s" % (
             "항목", "경우", "φ52-78", "A[kg]", "B[kg]", "A−B%", "C−B%", "차폭%", "λmin",
             "앞뒤차 2.5/4.5/6.5/8.5 m [℃] | kg/kg 2.5→8.5 | 계단 6/12/20 [%]")]
    rows = []
    for r in runs:
        d = metrics(r)
        rows.append((r, d))
        sp = "/".join("%.0f" % d["spread"][m] for m in LENGTHS)
        pk = "%.2f→%.2f" % (d["per_kg"]["B_L025"], d["per_kg"]["B_L085"])
        st = "/".join("%+.1f" % d["steps"][m] for m in STEPS)
        L.append("%-6s %-34s %7.4f %7.0f %7.0f %+6.1f %+6.1f %6.1f %5.2f | %s | %s | %s%s" % (
            r["item"], r["label"], d["phi_last"], d["fuel_A"], d["fuel_B"], d["dA"], d["dC"],
            d["span"], d["lam_min"], sp, pk, st,
            ("  ※ " + ",".join(d["notes"])) if d["notes"] else ""))
    # 2-2m 차이의 범위
    L.append("\n2-2m 구성 간 차이의 범위 (위 %d 경우의 최소–최대)" % len(rows))
    def rng(key, sub=None):
        v = [(d[key][sub] if sub else d[key]) for _, d in rows]
        return min(v), max(v)
    for name, key, sub, fmt in [("A − B 연료 [%]", "dA", None, "%+.1f"), ("C − B 연료 [%]", "dC", None, "%+.1f"),
                                ("형식 차폭 [%]", "span", None, "%.1f")] + \
            [("앞뒤차 L %.1f m [℃]" % (int(m[3:6]) / 10), "spread", m, "%.1f") for m in LENGTHS] + \
            [("기물 kg 당 연료 L %.1f m" % (int(m[3:6]) / 10), "per_kg", m, "%.2f") for m in LENGTHS] + \
            [("계단 %s단 − 무단 연료 [%%]" % m.split("_S")[1], "steps", m, "%+.1f") for m in STEPS]:
        lo, hi = rng(key, sub)
        L.append("  %-28s %s – %s" % (name, fmt % lo, fmt % hi))
    order = [d["fuel_A"] < d["fuel_C"] < d["fuel_B"] for _, d in rows]
    L.append("  형식 연료 순서 A < C < B 가 유지된 경우: %d / %d" % (sum(order), len(order)))
    mono = [all(d["spread"][LENGTHS[i]] < d["spread"][LENGTHS[i + 1]] for i in range(3)) for _, d in rows]
    L.append("  앞뒤차가 길이에 따라 커지는 경우: %d / %d" % (sum(mono), len(mono)))
    # 2-2i 소성 범위 판정 (기준 경우)
    base = next((r for r, _ in rows if r["id"] == "base"), None)
    if base:
        L.append("\n2-2i 소성 범위 판정 — 기준 경우, 78 h, 소성실 1 m 구간 중 범위 안에 드는 구간 수 (가스 / 기물)")
        L.append("%-12s " % "가마" + "  ".join("%13s" % ("%d–%d ℃" % rg) for rg in RANGES))
        for m in LENGTHS + ["A_L065", "C_L065"]:
            g, w = base["models"][m]["gas"][1:-1], base["models"][m]["ware"][1:-1]
            cells = []
            for lo, hi in RANGES:
                a, n = in_range(g, lo, hi)
                b, _ = in_range(w, lo, hi)
                cells.append("%2d/%d · %2d/%d" % (a, n, b, n))
            L.append("%-12s " % m + "  ".join("%13s" % c for c in cells))
        L.append("  (가스: 소성실 구간 기체 온도, 기물: 같은 구간 적재물 온도. 구간 길이는 같다.)")
        for m in LENGTHS:
            g, w = base["models"][m]["gas"][1:-1], base["models"][m]["ware"][1:-1]
            L.append("  %s 78 h 가스 %s | 기물 %s ℃" % (m, " ".join("%.0f" % x for x in g),
                                                      " ".join("%.0f" % x for x in w)))
    # 2-2l 〈표 4〉 대조
    if base and "table4" in base and os.path.exists(TABLE4):
        meas = dict((float(r["t_h"]), r) for r in csv.DictReader(l for l in open(TABLE4) if not l.startswith("#")))
        L.append("\n2-2l 〈표 4〉 대조 — 형식 B, 기준 φ. 측점 A = 소성실 맨 앞, D = 맨 뒤 구간으로 **가정**했다 (보고서에 위치가 없다)")
        L.append("%5s %8s %10s %10s | %8s %10s %10s" % ("t[h]", "A 실측", "앞 가스", "앞 기물", "D 실측", "뒤 가스", "뒤 기물"))
        eA, eD = [], []
        for x in base["table4"]:
            m = meas[x["t_h"]]
            eA.append(x["gas_front"] - float(m["T_A_degC"])); eD.append(x["gas_back"] - float(m["T_D_degC"]))
            L.append("%5.0f %8s %10.0f %10.0f | %8s %10.0f %10.0f" % (
                x["t_h"], m["T_A_degC"], x["gas_front"], x["ware_front"], m["T_D_degC"], x["gas_back"], x["ware_back"]))
        rms = lambda v: (sum(e * e for e in v) / len(v)) ** 0.5
        L.append("  가스 − 실측: A 평균 %+.0f ℃ · rms %.0f ℃ / D 평균 %+.0f ℃ · rms %.0f ℃ (48–77 h)" % (
            sum(eA) / len(eA), rms(eA), sum(eD) / len(eD), rms(eD)))
    txt = "\n".join(L)
    print(txt)
    res = os.path.join(OUT, "..")
    with open(os.path.join(res, "sensitivity.txt"), "w") as f:
        f.write(txt + "\n")
    with open(os.path.join(res, "sensitivity_cases.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "item", "label", "phi_52_78", "fuel_A", "fuel_B", "fuel_C", "dA_pct", "dC_pct",
                    "span_pct", "lam_min"] + ["spread_%s" % m for m in LENGTHS] + ["perkg_%s" % m for m in LENGTHS]
                   + ["steps_%s_pct" % m for m in STEPS] + ["notes"])
        for r, d in rows:
            w.writerow([r["id"], r["item"], r["label"], "%.6f" % d["phi_last"]] +
                       ["%.1f" % d[k] for k in ("fuel_A", "fuel_B", "fuel_C")] +
                       ["%.3f" % d[k] for k in ("dA", "dC", "span", "lam_min")] +
                       ["%.2f" % d["spread"][m] for m in LENGTHS] + ["%.3f" % d["per_kg"][m] for m in LENGTHS] +
                       ["%.3f" % d["steps"][m] for m in STEPS] + [";".join(d["notes"])])
    print("\n→ Results/rom/sensitivity.txt, sensitivity_cases.csv")


def main():
    if "--summary" not in sys.argv:
        os.makedirs(OUT, exist_ok=True)
        with mp.Pool(NPROC, maxtasksperchild=1) as pool:
            for cid, st in pool.imap_unordered(work, CASES):
                print("  %-8s %s" % (cid, st), flush=True)
    summary()


if __name__ == "__main__":
    main()
