#!/usr/bin/env python3
"""
2-2a 격자 독립성 · 2-2b 시간 간격 · 2-2d 조업점 결과 정리 (cfd/checks/run_checks.sh 뒤에).

    python3 cfd/checks/summarize_checks.py [--no-pen] [--no-rom]

  2-2a (E-04)  기본 격자(cases/*_steady) 대 조밀 격자(Results/checks/grid/steady)의 보정 입력
               (화구 유입량·체적평균온도·벽 손실)과 보정값 h_ref·A_hot, 그 보정으로 φ 를 다시
               역산한 축소모델 연료(형식 셋), 조밀 격자 비정상 해의 1,000 ℃ 면 45 s 최대 침투.
               두 격자 GCI (Roache: 안전계수 3, 차수 p = 2 가정, r = (N조밀/N기본)^(1/3)).
  2-2b (E-05)  maxCo 2 대 10: Results/checks/courant/{A,B,C}_co2 (기본 계산과 같은 사전에서 maxCo 만 2).
  2-2d (E-08)  조업점 정상해(Results/checks/oppoint): CFD 유입량 대 축소모델 식(1)(보정 A_hot) 예측,
               CFD 표면측 대류계수 대 축소모델 h_ref (ṁ/ṁ_ref)^0.8, 에너지 수지, 온도 상한 발동.
출력: Results/checks/summary_2-2abd.txt, *.csv
"""
import csv
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RES = os.path.join(ROOT, "Results", "checks")
ROM = os.path.join(ROOT, "rom")
sys.path.insert(0, ROM)
sys.path.insert(0, os.path.join(ROOT, "cfd"))
import cases  # noqa: E402
NAVG = 2000
FORMS = "ABC"
OUT_LINES = []


def say(s=""):
    print(s)
    OUT_LINES.append(s)


def ncells(case):
    return int(re.search(r"nCells:\s*(\d+)", open(os.path.join(case, "constant/polyMesh/owner")).read()).group(1))


def calib(steady_dir):
    """그 정상 케이스 묶음으로 보정한 값 (calibrate.py 를 따로 띄워 STEADY_DIR 를 바꾼다)."""
    code = r"""
import json, calibrate
out = {}
for t in "ABC":
    c = calibrate.read_cfd("%s_L065" % t)
    out[t] = dict(c, h_ref=calibrate.h_conv_ref(t), A_hot=calibrate.A_hot_of(t))
print(json.dumps(out))
"""
    env = dict(os.environ)
    env.pop("KILN_STEADY_DIR", None)
    if steady_dir:                      # None = 저장소의 기본 정상 케이스 (cases/*_steady)
        env["KILN_STEADY_DIR"] = steady_dir
    r = subprocess.run([sys.executable, "-c", code], cwd=ROM, env=env, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-2000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def rom_fine():
    """조밀 격자 보정으로 φ 를 다시 역산하고 형식 셋·길이·계단 연료를 낸다 (rom/sensitivity.py 의 work)."""
    out = os.path.join(RES, "grid", "rom")
    path = os.path.join(out, "grid_fine.json")
    if not os.path.exists(path):
        code = r"""
import os, sys, sensitivity
sensitivity.OUT = %r
os.makedirs(sensitivity.OUT, exist_ok=True)
print(sensitivity.work(("grid_fine", "2-2a", "조밀 격자 보정", {})))
""" % out
        env = dict(os.environ, KILN_STEADY_DIR=os.path.join(RES, "grid", "steady"))
        r = subprocess.run([sys.executable, "-c", code], cwd=ROM, env=env, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(r.stderr[-2000:])
    return json.load(open(path))


def pen_run(cases, out_csv):
    """pvbatch 로 1,000 ℃ 면 침투 시계열을 낸다."""
    env = dict(os.environ, KILN_PEN_CASES=",".join("%s=%s" % kv for kv in cases), KILN_PEN_OUT=out_csv)
    cmd = 'source "%s/paths.sh" && "$KILN_PVBATCH" "%s/cfd/post/flame_penetration.py"' % (ROOT, ROOT)
    r = subprocess.run(["bash", "-c", cmd], env=env, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stdout[-2000:] + r.stderr[-2000:])


def pen_max(path, t_end=45.0):
    """{모델: 45 s 까지 최대 x}"""
    out = {}
    for r in csv.DictReader(open(path)):
        if r["x_penetration_m"] and float(r["t_s"]) <= t_end + 0.5:
            x = float(r["x_penetration_m"])
            out[r["model"]] = max(out.get(r["model"], x), x)
    return out


def gci(f_base, f_fine, r, p=2.0, fs=3.0):
    e = (f_fine - f_base) / f_fine if f_fine else float("nan")
    return 100 * e, 100 * fs * abs(e) / (r ** p - 1)


# ── 2-2a ─────────────────────────────────────────────────
def grid(do_pen, do_rom):
    say("=" * 100)
    say("2-2a 격자 독립성 (E-04) — 기본 격자 대 조밀 격자 (배경 0.1 → 0.0707 m, 표면 세분 1 단계 그대로)")
    say("=" * 100)
    base_dir = None                     # 기본 격자 = cases/*_steady
    fine_dir = os.path.join(RES, "grid", "steady")
    cb, cf = calib(base_dir), calib(fine_dir)
    rows = []
    say("%-3s %8s %8s %6s | %-18s %10s %10s %8s %8s" % ("형식", "N기본", "N조밀", "r", "양", "기본", "조밀", "차[%]", "GCI[%]"))
    for t in FORMS:
        nb, nf = ncells(cases.case_dir("steady", t)), ncells(os.path.join(fine_dir, t + "_L065"))
        r = (nf / nb) ** (1 / 3)
        for key, lab, fmt in (("mdot", "화구 유입량 kg/s", "%.4f"), ("T_bulk", "체적평균온도 ℃", "%.1f"),
                              ("T_out", "출구온도 ℃", "%.1f"), ("wall_loss", "벽 손실 kW", "%.2f"),
                              ("h_ref", "h_ref W/m2K", "%.4f"), ("A_hot", "A_hot m2", "%.4f")):
            vb, vf = cb[t][key], cf[t][key]
            if key in ("T_bulk", "T_out"):
                vb, vf = vb - 273.15, vf - 273.15
            if key == "wall_loss":
                vb, vf = vb / 1e3, vf / 1e3
            e, g = gci(vb, vf, r)
            say("%-3s %8d %8d %6.3f | %-18s %10s %10s %8.2f %8.2f" % (t, nb, nf, r, lab, fmt % vb, fmt % vf, e, g))
            rows.append(dict(form=t, quantity=key, base=vb, fine=vf, diff_pct=e, gci_pct=g, n_base=nb, n_fine=nf, r=r))
        say("    (조밀 격자 마지막 %d 회 진동 폭 sd: 유입량 %.4f kg/s, 벽 손실 %.2f kW)" % (NAVG, cf[t]["mdot_sd"], cf[t]["wall_loss_sd"] / 1e3))
    write_csv("grid_steady.csv", rows)

    if do_rom:
        say("\n축소모델 — 조밀 격자로 보정해 φ 를 다시 역산한 연료 [kg] (기준: Results/rom/sensitivity/base.json)")
        fb = json.load(open(os.path.join(ROOT, "Results", "rom", "sensitivity", "base.json")))
        ff = rom_fine()
        say("  φ 52–78 h: 기본 %.4f / 조밀 %.4f" % (fb["phi"][-1]["phi"], ff["phi"][-1]["phi"]))
        for m in ("A_L065", "B_L065", "C_L065", "B_L025", "B_L045", "B_L085"):
            a, b = fb["models"][m]["fuel"], ff["models"][m]["fuel"]
            say("  %-8s 기본 %7.0f  조밀 %7.0f  (%+.2f %%)" % (m, a, b, 100 * (b - a) / a))
        for lab, d in (("기본", fb), ("조밀", ff)):
            f = dict((m, d["models"][m]["fuel"]) for m in ("A_L065", "B_L065", "C_L065"))
            say("  %s: A−B %+.2f %%, C−B %+.2f %%, 차폭 %.2f %%, 순서 %s" % (
                lab, 100 * (f["A_L065"] / f["B_L065"] - 1), 100 * (f["C_L065"] / f["B_L065"] - 1),
                100 * (max(f.values()) / min(f.values()) - 1),
                " < ".join(m[0] for m in sorted(f, key=f.get))))
        g = lambda d, m: d["models"][m]["gas"][1:-1]
        for m in ("B_L025", "B_L045", "B_L065", "B_L085"):
            say("  %-8s 앞뒤차 기본 %.1f / 조밀 %.1f ℃" % (m, g(fb, m)[0] - min(g(fb, m)), g(ff, m)[0] - min(g(ff, m))))

    if do_pen:
        say("\n1,000 ℃ 면 — 45 s 까지 최대 침투 [m] (기본 격자: 분할 4·6·8·10 범위, Results/cfd/flame_penetration_max.csv)")
        out = os.path.join(RES, "grid", "flame_penetration_fine.csv")
        pen_run([(t, os.path.join(RES, "grid", "transient", t + "_L065")) for t in FORMS], out)
        pm = pen_max(out)
        base = dict((r["form"], r) for r in csv.DictReader(open(os.path.join(ROOT, "Results", "cfd", "flame_penetration_max.csv"))))
        for t in FORMS:
            b = base[t]
            say("  %s  기본 np6 %.2f (범위 %.2f–%.2f)   조밀 np6 %.2f" % (
                t, float(b["max_x_np6_m"]), float(b["max_x_min_m"]), float(b["max_x_max_m"]), pm.get(t, float("nan"))))


# ── 2-2b ─────────────────────────────────────────────────
def courant(do_pen):
    say("\n" + "=" * 100)
    say("2-2b 시간 간격 (E-05) — maxCo 2 대 10, 1,000 ℃ 면 45 s 까지 최대 침투 [m]")
    say("=" * 100)
    out = os.path.join(RES, "courant", "flame_penetration_co2.csv")
    if do_pen:
        pen_run([(t, os.path.join(RES, "courant", t + "_co2")) for t in FORMS], out)
    co2 = pen_max(out)
    base = dict((r["form"], r) for r in csv.DictReader(open(os.path.join(ROOT, "Results", "cfd", "flame_penetration_max.csv"))))
    for t in FORMS:
        b = base[t]
        say("  %s  maxCo 10: np6 %.2f (분할 범위 %.2f–%.2f)   maxCo 2: %s" % (
            t, float(b["max_x_np6_m"]), float(b["max_x_min_m"]), float(b["max_x_max_m"]),
            "%.2f" % co2[t] if t in co2 else "—"))
    say("  (세 형식 모두 기본 계산과 같은 사전 — 온도 상한 270–2,600 K 포함 — 에서 maxCo 만 10 → 2)")


# ── 2-2d ─────────────────────────────────────────────────
def read_log(case):
    txt = open(os.path.join(case, "log.solver"), errors="ignore").read()
    steps = [(int(s.group(1)), s.start()) for s in re.finditer(r"^Time = (\d+)$", txt, re.M)]
    first = steps[-1][0] - NAVG
    tail = txt[next(pos for t, pos in steps if t > first):]
    pats = {"mdot": r"sum\(inlet\) of phi = ([-\d.e+]+)",
            "T_bulk": r"volAverage\(region0\) of T = ([\d.e+-]+)",
            "T_out": r"areaAverage\(outlet\) of T = ([\d.e+-]+)",
            "wall": r"min/max/integ\(walls\) = [-\d.e+]+, [-\d.e+]+, ([-\d.e+]+)",
            "stoke": r"min/max/integ\(stokeBlock\) = [-\d.e+]+, [-\d.e+]+, ([-\d.e+]+)"}
    out = {"last": steps[-1][0]}
    for k, p in pats.items():
        w = [abs(float(x)) for x in re.findall(p, tail)]
        out[k] = sum(w) / len(w) if w else float("nan")
        out[k + "_sd"] = (sum((x - out[k]) ** 2 for x in w) / len(w)) ** 0.5 if w else float("nan")
    lim = [int(x) for x in re.findall(r"limitT Upper limited (\d+)", tail)]
    out["lim_max"] = max(lim) if lim else 0
    out["lim_iters"] = len(lim)
    return out


def oppoint():
    import geom
    import rom
    say("\n" + "=" * 100)
    say("2-2d 조업점 (E-08) — 화구를 좁히고 발열률을 바꾼 정상 CFD 대 축소모델 (보정점: 화구 완전개방 150 kW)")
    say("=" * 100)
    cb = calib(None)
    T_amb = rom.CFD_STEADY["T_amb"]
    cp = 1100.0
    rows = []
    say("%-12s %6s %6s | %8s %8s %6s | %7s %7s %6s | %6s %6s %6s | %6s %6s" % (
        "케이스", "Q kW", "φ", "ṁCFD", "ṁROM", "비", "hCFD", "hROM", "비", "T평균", "T출구", "수지%", "상한셀", "반복"))
    cases = sorted(d for d in os.listdir(os.path.join(RES, "oppoint")) if os.path.isdir(os.path.join(RES, "oppoint", d)))
    for d in cases:
        case = os.path.join(RES, "oppoint", d)
        if not os.path.exists(os.path.join(case, "log.solver")):
            say("%-12s 해 없음" % d)
            continue
        info = dict(l.split(None, 1) for l in open(os.path.join(case, "oppoint.txt")))
        t = d[0]
        g = geom.extract("%s_L065" % t)
        c = read_log(case)
        phi = float(info["phi_mesh"])
        Q = float(info["Q_kW"]) * 1e3
        m_rom = rom.draft(c["T_bulk"], phi, g["H_stack"], g["A_in"], cb[t]["A_hot"], T_amb)
        U = c["wall"] / (g["A_wall"] * (c["T_bulk"] - T_amb))
        h_cfd = 1.0 / (1.0 / U - rom.CFD_STEADY["R_ext"]) if 1.0 / U > rom.CFD_STEADY["R_ext"] else float("nan")
        h_rom = cb[t]["h_ref"] * (c["mdot"] / cb[t]["mdot"]) ** rom.H_EXP
        bal = (c["mdot"] * cp * (c["T_out"] - T_amb) + c["wall"] + (c["stoke"] if c["stoke"] == c["stoke"] else 0)) / Q
        say("%-12s %6.1f %6.3f | %8.4f %8.4f %6.3f | %7.3f %7.3f %6.3f | %6.0f %6.0f %6.1f | %6d %6d" % (
            d, Q / 1e3, phi, c["mdot"], m_rom, m_rom / c["mdot"], h_cfd, h_rom, h_rom / h_cfd,
            c["T_bulk"] - 273.15, c["T_out"] - 273.15, 100 * bal, c["lim_max"], c["last"]))
        rows.append(dict(case=d, form=t, Q_kW=Q / 1e3, phi_mesh=phi, mdot_cfd=c["mdot"], mdot_cfd_sd=c["mdot_sd"],
                         mdot_rom=m_rom, h_cfd=h_cfd, h_rom=h_rom, T_bulk_C=c["T_bulk"] - 273.15,
                         T_out_C=c["T_out"] - 273.15, wall_kW=c["wall"] / 1e3, stoke_kW=c["stoke"] / 1e3,
                         balance_pct=100 * bal, limiter_cells_max=c["lim_max"], limiter_iters=c["lim_iters"],
                         last_iter=c["last"]))
    say("  ṁROM: 식 (1) = rom.draft(CFD 체적평균온도, 격자 개구율 φ, 형식 H·A_in, 보정 A_hot). 비 = ROM/CFD.")
    say("  hCFD: 벽 손실/(벽면적·(T평균−외기)) 에서 외부저항 0.45 를 벗긴 표면측 값. hROM = h_ref (ṁCFD/ṁ_ref)^0.8.")
    say("  수지: (ṁ cp (T출구 − 외기) + 벽 + 막은 화구) / 발열률, cp 1,100. 상한셀: 마지막 %d 회 중 온도 상한에 걸린 셀 수 최대." % NAVG)
    write_csv("oppoint.csv", rows)


def write_csv(name, rows):
    if not rows:
        return
    with open(os.path.join(RES, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    do_pen = "--no-pen" not in sys.argv
    do_rom = "--no-rom" not in sys.argv
    grid(do_pen, do_rom)
    courant(do_pen)
    oppoint()
    open(os.path.join(RES, "summary_2-2abd.txt"), "w").write("\n".join(OUT_LINES) + "\n")
    print("→ Results/checks/summary_2-2abd.txt")
