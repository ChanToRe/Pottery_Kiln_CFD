#!/usr/bin/env python3
import os
import re

import geom
import rom

CFD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cfd_v2")
CFD_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Data",
                       "cfd_calibration.csv")


def _load_csv():
    table = {}
    if not os.path.exists(CFD_CSV):
        return table
    with open(CFD_CSV) as f:
        for line in f:
            if line.startswith("#") or line.startswith("model"):
                continue
            p = line.rstrip("\n").split(",")
            if len(p) < 6:
                continue
            table[p[0]] = dict(mdot=float(p[1]), T_bulk=float(p[2]),
                               T_out=float(p[3]), wall_loss=float(p[4]),
                               n=int(p[5]), source="cfd_calibration.csv")
    return table


_CSV = _load_csv()


NAVG = 2000


def read_cfd(model, navg=NAVG):
    if model in _CSV:
        return dict(_CSV[model])
    path = os.path.join(CFD_DIR, model, "log.solver")
    keys = {"mdot": r"sum\(inlet\) of phi = ([-\d.e+]+)",
            "T_bulk": r"volAverage\(region0\) of T = ([\d.e+-]+)",
            "T_out": r"areaAverage\(outlet\) of T = ([\d.e+-]+)",
            "wall_loss": r"min/max/integ\(walls\) = [-\d.e+]+, [-\d.e+]+, ([-\d.e+]+)"}
    if not os.path.exists(path):
        t = model[0]
        if t not in rom.CFD["mdot"]:
            return None
        return dict(mdot=rom.CFD["mdot"][t], T_bulk=rom.CFD["T_bulk"],
                    T_out=None, wall_loss=rom.CFD["wall_loss"][t], source="기록값")
    txt = open(path, errors="ignore").read()
    out = {"source": "log.solver"}
    for k, pat in keys.items():
        m = [float(x) for x in re.findall(pat, txt)]
        if not m:
            return None
        w = m[-navg:] if len(m) > navg else m
        out[k] = sum(w) / len(w)
        out[k + "_sd"] = (sum((x - out[k]) ** 2 for x in w) / len(w)) ** 0.5
        out["n"] = len(w)
    out["mdot"] = abs(out["mdot"])
    out["wall_loss"] = abs(out["wall_loss"])
    return out


def h_conv_ref(form="A"):
    c = read_cfd("%s_L065" % form)
    A_wall = geom.extract("%s_L065" % form)["A_wall"]
    dT = c["T_bulk"] - rom.CFD["T_amb"]
    U = c["wall_loss"] / (A_wall * dT)
    R_conv = 1.0 / U - rom.CFD["R_ext"]
    if R_conv <= 0:
        raise ValueError("외부저항이 총저항보다 크다 — 보정 불가")
    return 1.0 / R_conv


def A_hot_of(form):
    c = read_cfd("%s_L065" % form)
    src = form
    if c is None:
        src, c = "B", read_cfd("B_L065")
    g = geom.extract("%s_L065" % src)
    return rom.calibrate_A_hot(
        g["H_stack"], g["A_in"], c["mdot"],
        rom.CFD["T_amb"], c["T_bulk"]), src != form


def build(model, seg_m=None, **kw):
    g = geom.extract(model, seg_m=seg_m)
    A_hot, borrowed = A_hot_of(g["type"])
    src = g["type"] if read_cfd("%s_L065" % g["type"]) else "A"
    k = dict(A_hot=A_hot, h_conv_ref=h_conv_ref(src),
             mdot_ref=read_cfd("%s_L065" % src)["mdot"])
    k.update(kw)
    return rom.Kiln(g, **k), dict(A_hot=A_hot, borrowed=borrowed)


if __name__ == "__main__":
    print("CFD 기준점 (cfd_v2, 150 kW, 화구 완전개방, 외기 5 ℃)\n")
    print("마지막 %d 회 평균 (± 는 그 구간의 표준편차 = 진동 폭)\n" % NAVG)
    print("%-8s %14s %13s %13s %11s" %
          ("model", "mdot [kg/s]", "volAvg T[℃]", "outlet T[℃]", "벽체손실[kW]"))
    for t in "ABC":
        c = read_cfd("%s_L065" % t)
        if c is None:
            print("%-8s %14s" % (t + "_L065", "— (해 없음)"))
            continue
        print("%-8s %8.3f±%.3f %8.1f±%.1f %8.1f±%.1f %7.1f±%.1f" %
              (t + "_L065", c["mdot"], c["mdot_sd"],
               c["T_bulk"] - 273.15, c["T_bulk_sd"],
               c["T_out"] - 273.15, c["T_out_sd"],
               c["wall_loss"] / 1e3, c["wall_loss_sd"] / 1e3))

    print("\n형식별 대류계수 (외부저항 R=0.3 m2K/W 를 벗겨낸 표면측 값)")
    for t in "ABC":
        if read_cfd("%s_L065" % t):
            print("  %s  h_conv,ref = %.2f W/m2K" % (t, h_conv_ref(t)))

    print("\n%-8s %8s %8s %9s %10s %10s" %
          ("model", "H[m]", "A_wall", "A_hot[m2]", "재현 mdot", "CFD mdot"))
    for t in "ABC":
        m = "%s_L065" % t
        k, info = build(m)
        c = read_cfd(m)
        md = rom.draft(c["T_bulk"] if c else rom.CFD["T_bulk"], 1.0, k.H,
                       k.A_in, info["A_hot"], rom.CFD["T_amb"])
        print("%-8s %8.3f %8.2f %9.4f %10.3f %10s%s" %
              (m, k.H, k.geo["A_wall"], info["A_hot"], md,
               "%.3f" % c["mdot"] if c else "—",
               "   (B 저항 전용)" if info["borrowed"] else ""))
