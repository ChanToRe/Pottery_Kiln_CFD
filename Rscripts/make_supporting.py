#!/usr/bin/env python3
"""
수정 원고의 보충자료 S1–S8 Table (xlsx) 을 계산 결과 파일에서 만든다. 값은 손으로 옮기지 않는다.

    env/doc/bin/python Rscripts/make_supporting.py
출력: Results/supporting/S<n>_Table.xlsx  (S1 Fig 는 Rscripts/S1_Fig.R)

  S1 classification      ← Results/rom/value_classes.csv (2-2o)
  S2 interval calibration← Results/rom/rom_phi.csv
  S3 report table        ← Results/rom/sensitivity.txt 의 〈표 4〉 대조 (2-2l)
  S4 sensitivity         ← Results/rom/sensitivity_cases.csv, sensitivity.txt (2-2e·h·i·j·k·l·m·n)
  S5 CFD checks          ← Results/checks/convergence/{mesh_quality,convergence}.csv, limiter_swap/요약.txt (2-2c, K19)
  S6 grid / time step    ← Results/checks/grid_steady.csv, summary_2-2abd.txt, flame_penetration_max.csv (2-2a·b)
  S7 operating points    ← Results/checks/oppoint.csv (2-2d)
  S8 energy balance      ← Results/rom/energy_audit.txt, energy_audit_series.csv (2-2f·g)
"""
import csv
import os
import re

from openpyxl import Workbook
from openpyxl.styles import Font

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = lambda *p: os.path.join(ROOT, *p)
OUT = R("Results", "supporting")
FONT = Font(name="Arial", size=10)
BOLD = Font(name="Arial", size=10, bold=True)


def rows(p):
    return list(csv.DictReader(open(p, newline="")))


def num(x, nd=None):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return x
    return round(v, nd) if nd is not None else v


def book(name, title, sheets):
    """sheets: [(sheet title, header, rows, notes)]"""
    wb = Workbook()
    wb.remove(wb.active)
    for st, head, data, notes in sheets:
        ws = wb.create_sheet(st[:31])
        ws.append([title])
        ws["A1"].font = BOLD
        ws.append([])
        ws.append(head)
        for c in ws[3]:
            c.font = BOLD
        for r in data:
            ws.append(r)
        if notes:
            ws.append([])
            for n in notes:
                ws.append([n])
        for row in ws.iter_rows(min_row=4):
            for c in row:
                if c.font != BOLD:
                    c.font = FONT
        for col in ws.columns:
            w = max(len(str(c.value)) if c.value is not None else 0 for c in col[2:]) if len(col) > 2 else 10
            ws.column_dimensions[col[0].column_letter].width = min(max(10, w + 2), 60)
    p = os.path.join(OUT, name)
    wb.save(p)
    print("→", os.path.relpath(p, ROOT))


# ---------------------------------------------------------------- S1
CLASS = {"지정": "Prescribed", "가정": "Assumed", "보정": "Calibrated", "보정(결과)": "Calibrated (result)", "계산": "Calculated"}
QTY = {
    "총 땔감": ("Total fuel", "Hong 2011 text; used as the total of the heat-release schedule"),
    "발열 일정 (6 구간)": ("Heat-release schedule (six intervals)", "fuel input rates recorded by Hong 2011 x heating value; last interval scaled to the total of 3,600 kg"),
    "소성 시간": ("Firing time", "Hong 2011"),
    "유효 저위발열량": ("Effective lower heating value", "derived from Ragland et al. 1991 for 20 % moisture (wet basis)"),
    "이론 공기량": ("Stoichiometric air (wet wood)", "derived from Ragland et al. 1991, softwood composition"),
    "외기": ("Ambient temperature", "Hong 2011: mean of the drying period, used for the firing"),
    "벽 k·ρ·c": ("Wall k, rho, c", "Hein et al. 2008; Petcu et al. 2023"),
    "지반 k·ρ·c": ("Ground k, rho, c", "Farouki 1981 (moisture 15 %)"),
    "형상 H (A/B/C)": ("Height difference firemouth-flue H (A/B/C)", "geometry"),
    "화구 면적 A_in (A/B/C)": ("Firemouth area A_in (A/B/C)", "geometry"),
    "적재 부피 점유율": ("Volume fraction of the load", "assumed; mass of the load not reported"),
    "내부 방사율 ε": ("Gas-surface emissivity", "assumed"),
    "화구 유량계수 C_in": ("Firemouth discharge coefficient C_in", "assumed; the data constrain only C_in x phi"),
    "대류 지수": ("Exponent of Eq (2)", "Dittus-Boelter form; sensitivity 0.5, 1.0"),
    "축방향 복사 교환계수": ("Axial radiation exchange coefficient", "assumed"),
    "축방향 복사 핵": ("Axial radiation kernel", "geometrical approximation of this study"),
    "유효 고온부 면적 A_hot (A/B/C)": ("Effective hot area A_hot (A/B/C)", "steady CFD firemouth mass flow (150 kW, fully open)"),
    "대류계수 h_ref (A/B/C)": ("Reference convective coefficient h_ref (A/B/C)", "steady CFD wall loss, external resistance 0.45 m2K/W removed"),
    "기준 유량 ṁ_ref (A/B/C)": ("Reference mass flow (A/B/C)", "steady CFD"),
    "화구 개구율 φ (6 구간, 형식 B)": ("Firemouth opening ratio phi (six intervals, form B)", "gas temperature of the first ware-chamber segment fitted to the heating curve (shifted by -2 h)"),
    "복사 차폐율": ("Axial radiation shielding ratio", "fitted to the difference of about 120 C between firebox and flue before closure (Hong 2011)"),
    "앞 구간 78 h 온도": ("Temperature of the front segment at 78 h", "calibration target; the same in every case"),
    "형식 B 땔감": ("Fuel of form B", "equals the recorded 3,600 kg by construction (phi fitted on B); not an independent validation"),
    "형식 A·C 땔감": ("Fuel of forms A and C", "same phi and heating curve applied to A and C"),
    "길이별 땔감 2.5/4.5/8.5 m": ("Fuel for lengths 2.5/4.5/8.5 m", ""),
    "소성실 앞뒤 온도차 2.5/4.5/6.5/8.5 m": ("Front-to-back temperature difference 2.5/4.5/6.5/8.5 m", "78 h"),
    "최소 공기비 (A/B/C)": ("Minimum excess air ratio (A/B/C)", ""),
    "1,000 ℃ 면 45 s 최대 침투": ("Maximum penetration of the 1,000 C isotherm within 45 s", "transient CFD; see S6 Table"),
}


def s1():
    data = []
    for r in rows(R("Results", "rom", "value_classes.csv")):
        q, basis = QTY[r["quantity"]]
        v = r["value"].replace("℃", "C").replace("m2", "m2")
        if r["quantity"] == "1,000 ℃ 면 45 s 최대 침투":
            pm = {x["form"]: x for x in rows(R("Results", "cfd", "flame_penetration_max.csv"))}
            v = " / ".join("%s %.2f (%.2f-%.2f) m" % (f, float(pm[f]["max_x_np6_m"]), float(pm[f]["max_x_min_m"]),
                                                     float(pm[f]["max_x_max_m"])) for f in "ABC")
        data.append([CLASS[r["class_"]], q, v, basis])
    book("S1_Table.xlsx", "S1 Table. Classification of the model quantities.",
         [("S1 Table", ["Class", "Quantity", "Value", "Basis"], data,
           ["Source: Results/rom/value_classes.csv (rom/value_classes.py)."])])


# ---------------------------------------------------------------- S2
def s2():
    data = [[num(r["t0_h"]), num(r["t1_h"]), num(r["Q_kW"], 1), num(r["target_C"], 1), num(r["got_C"], 1),
             num(r["phi"], 4), "fully open limit" if r["note"] else ""] for r in rows(R("Results", "rom", "rom_phi.csv"))]
    book("S2_Table.xlsx", "S2 Table. Calibration of the firemouth opening ratio (form B).",
         [("S2 Table", ["Start (h)", "End (h)", "Heat release (kW)", "Target gas temperature (C)",
                        "Computed gas temperature (C)", "Opening ratio phi", "Note"], data,
           ["Target: digitised heating curve of Hong 2011, shifted by -2 h, at the end of each interval;",
            "computed: gas temperature of the first ware-chamber segment. Source: Results/rom/rom_phi.csv."])])


# ---------------------------------------------------------------- S3 / S4
def sens_txt():
    return open(R("Results", "rom", "sensitivity.txt")).read().splitlines()


def s3():
    L = sens_txt()
    i = next(k for k, l in enumerate(L) if l.startswith("2-2l 〈표 4〉"))
    data = []
    for l in L[i + 2:]:
        m = re.match(r"\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+) \|\s+(\d+)\s+(\d+)\s+(\d+)", l)
        if not m:
            break
        data.append([int(x) for x in m.groups()])
    book("S3_Table.xlsx", "S3 Table. Comparison with the temperatures tabulated in the report (form B).",
         [("S3 Table", ["Time (h)", "Point A, measured (C)", "Front segment, gas (C)", "Front segment, load (C)",
                        "Point D, measured (C)", "Rear segment, gas (C)", "Rear segment, load (C)"], data,
           ["Measured: Hong 2011, table of fuel input and temperature (p. 164); positions of points A and D not reported.",
            "A is taken as the front and D as the rear segment of the ware chamber (assumption).",
            "Gas minus measured, 48-77 h: A mean +28 C, rms 111 C; D mean +85 C, rms 110 C.",
            "Source: Results/rom/sensitivity.txt (rom/sensitivity.py) and Data/table4_Hong2011.csv."])])


LABEL = {
    "base": "Reference (phi back-calculated)",
    "hexp05": "Exponent of Eq (2) 0.8 -> 0.5", "hexp10": "Exponent of Eq (2) 0.8 -> 1.0",
    "load03": "Volume fraction of load 0.5 -> 0.3", "load07": "Volume fraction of load 0.5 -> 0.7",
    "blk005": "Shielding ratio 0.10 -> 0.05", "blk020": "Shielding ratio 0.10 -> 0.20",
    "lhv085": "Heating value 14.7 -> 12.5 MJ/kg (-15 %)", "lhv115": "Heating value 14.7 -> 16.9 MJ/kg (+15 %)",
    "cp085": "Specific heat of load 850 -> 723 J/kgK (-15 %)", "cp115": "Specific heat of load 850 -> 978 J/kgK (+15 %)",
    "wall025": "Wall thickness 0.35 -> 0.25 m", "wall045": "Wall thickness 0.35 -> 0.45 m",
    "phi050": "Opening ratio x 0.5 (phi fixed)", "phi080": "Opening ratio x 0.8 (phi fixed)",
    "phi120": "Opening ratio x 1.2 (phi fixed)", "phi150": "Opening ratio x 1.5 (phi fixed)",
    "cin06": "Discharge coefficient C_in 0.80 -> 0.6", "cin10": "Discharge coefficient C_in 0.80 -> 1.0",
    "crvm30": "Heating curve -30 C", "crvp30": "Heating curve +30 C",
    "crvm2h": "Heating curve -2 h", "crvp2h": "Heating curve +2 h",
    "slp10": "Slope 15 -> 10 deg (phi back-calculated)", "slp20": "Slope 15 -> 20 deg (phi back-calculated)",
    "slp10f": "Slope 15 -> 10 deg (phi fixed)", "slp20f": "Slope 15 -> 20 deg (phi fixed)",
}


def s4():
    keys = ["phi_52_78", "fuel_A", "fuel_B", "fuel_C", "dA_pct", "dC_pct", "span_pct", "lam_min",
            "spread_B_L025", "spread_B_L045", "spread_B_L065", "spread_B_L085",
            "perkg_B_L025", "perkg_B_L045", "perkg_B_L065", "perkg_B_L085",
            "steps_B_L065_S6_pct", "steps_B_L065_S12_pct", "steps_B_L065_S20_pct"]
    head = ["Case", "phi 52-78 h", "Fuel A (kg)", "Fuel B (kg)", "Fuel C (kg)", "A-B (%)", "C-B (%)",
            "Range of forms (%)", "Min. excess air ratio",
            "dT 2.5 m (C)", "dT 4.5 m (C)", "dT 6.5 m (C)", "dT 8.5 m (C)",
            "Fuel/kg ware 2.5 m", "Fuel/kg ware 4.5 m", "Fuel/kg ware 6.5 m", "Fuel/kg ware 8.5 m",
            "6 steps (%)", "12 steps (%)", "20 steps (%)", "Note"]
    data = []
    for r in rows(R("Results", "rom", "sensitivity_cases.csv")):
        note = "one interval at the fully open limit" if r["notes"].strip() else ""
        data.append([LABEL[r["id"]]] + [num(r[k], 4 if k == "phi_52_78" else 2) for k in keys] + [note])
    # 소성 범위 판정 (2-2i)
    L = sens_txt()
    i = next(k for k, l in enumerate(L) if l.startswith("2-2i"))
    band = []
    for l in L[i + 2:]:
        m = re.match(r"(\w+_L\d+)\s+(\d+)/(\d+) ·\s+(\d+)/\d+\s+(\d+)/\d+ ·\s+(\d+)/\d+\s+(\d+)/\d+ ·\s+(\d+)/\d+\s+(\d+)/\d+ ·\s+(\d+)/\d+", l)
        if not m:
            break
        g = m.groups()
        band.append([g[0], int(g[2]), int(g[1]), int(g[3]), int(g[4]), int(g[5]), int(g[6]), int(g[7]), int(g[8]), int(g[9])])
    book("S4_Table.xlsx", "S4 Table. Sensitivity of the comparisons to assumed and calibrated values.",
         [("Cases", head, data,
           ["Differences relative to form B. dT: front-to-back gas temperature difference at 78 h (form B).",
            "When phi is back-calculated, the fuel of form B equals 3,600 kg by construction.",
            "Source: Results/rom/sensitivity_cases.csv (rom/sensitivity.py)."]),
          ("Firing bands", ["Kiln", "Segments", "1000-1100 gas", "1000-1100 load", "950-1100 gas", "950-1100 load",
                            "1000-1150 gas", "1000-1150 load", "1000-1200 gas", "1000-1200 load"], band,
           ["Number of 1 m segments of the ware chamber within each band at 78 h (reference case)."])])


# ---------------------------------------------------------------- S5
def s5():
    mq = rows(R("Results", "checks", "convergence", "mesh_quality.csv"))
    mdata = [[r["model"].replace("*", " (fine)"), int(r["cells"]), num(r["aspect_max"], 2), num(r["nonorth_max"], 2),
              num(r["nonorth_avg"], 2), num(r["skew_max"], 2), r["verdict"]] for r in mq]
    cv = rows(R("Results", "checks", "convergence", "convergence.csv"))
    sdata, tdata = [], []
    for r in cv:
        name = r["model"].replace("*", " (fine)")
        if r["kind"].startswith("steady"):
            kind = {"steady": "base", "steady_fine": "fine grid", "steady_oppoint": "operating point"}[r["kind"]]
            sdata.append([name, kind, int(r["iters"])] + [num(r[f + "_mean"], 6) for f in ("Ux", "Uy", "Uz", "h", "p_rgh", "k", "omega")]
                         + [num(r["mass_imbalance_pct"], 4), num(r["energy_balance_pct"], 1), num(r["cum_continuity"], 6),
                            int(float(r["limiter_cells_max"]))])
        else:
            kind = {"transient": "base", "transient_fine": "fine grid", "transient_co2": "max Courant 2"}[r["kind"]]
            tdata.append([name, kind, int(r["iters"]), num(r["t_end"], 2)] + [num(r[f + "_median"], 6) for f in ("Ux", "Uy", "Uz", "h", "p_rgh", "k", "epsilon")]
                         + [num(r["continuity_global_max"], 9), num(r["cum_continuity"], 6), num(r["courant_max"], 1),
                            int(float(r["limiter_cells_max"]))])
    # K19: 리미터 바꿔 풀기
    lim = []
    for l in open(R("Results", "checks", "limiter_swap", "요약.txt")):
        m = re.match(r"\s+(A_L065|A_nolim|B_L065|B_lim|C_L065) \(.*?\)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+) \(\s*([\d.]+)%\)\s+(\S+)\s+(\d+)\s+(\d+)", l)
        if m:
            g = m.groups()
            lim.append([g[0], float(g[1]), float(g[2]), float(g[3]), float(g[5]), "none" if g[6] == "없음" else int(g[6]), int(g[7]), int(g[8])])
    fuel = []
    for l in open(R("Results", "checks", "limiter_swap", "요약.txt")):
        m = re.match(r"\s+(base|A_nolim|B_lim)\s+" + r"\s+".join([r"([\d.]+)"] * 10), l)
        if m:
            g = m.groups()
            fuel.append([g[0], int(g[7]), int(g[8]), int(g[9])])
    book("S5_Table.xlsx", "S5 Table. Grid quality, convergence and conservation of the CFD computations.",
         [("Grid quality", ["Grid", "Cells", "Max aspect ratio", "Max non-orthogonality (deg)", "Mean non-orthogonality (deg)",
                            "Max skewness", "checkMesh"], mdata,
           ["checkMesh (OpenFOAM v2312). Skewness criterion 4. Source: Results/checks/convergence/mesh_quality.csv."]),
          ("Steady", ["Case", "Kind", "Iterations", "Ux", "Uy", "Uz", "h", "p_rgh", "k", "omega",
                      "Mass imbalance (%)", "Energy balance (%)", "Cumulative continuity", "Limited cells (max)"], sdata,
           ["Initial residuals averaged over the last 2,000 iterations. Energy balance = (exhaust enthalpy + wall loss) / heat release;",
            "for the operating points the heat lost through the blocked part of the firemouth is not included.",
            "Source: Results/checks/convergence/convergence.csv (cfd/checks/convergence_summary.py)."]),
          ("Transient", ["Case", "Kind", "Time steps", "End time (s)", "Ux", "Uy", "Uz", "h", "p_rgh", "k", "epsilon",
                         "Max continuity error per step", "Cumulative continuity", "Max Courant number", "Limited cells (max)"], tdata,
           ["Initial residual of the first solution of each time step, median after 0.5 s.", "Temperature limit 270-2,600 K."]),
          ("Temperature limit", ["Case", "Mass flow (kg/s)", "Volume-mean T (C)", "Wall loss (kW)", "Energy balance (%)",
                                 "Limited cells", "Max T (K)", "Cells >= 2600 K"], lim,
           ["Steady computations of A without and B with the temperature limit, continued 6,000 iterations from the base solutions;",
            "averages of the last 2,000 iterations. Source: Results/checks/limiter_swap (cfd/checks/limiter_swap.sh)."]),
          ("Effect on fuel", ["Calibration", "Fuel A (kg)", "Fuel B (kg)", "Fuel C (kg)"], fuel,
           ["Reduced-order model calibrated on each set of steady computations."])])


# ---------------------------------------------------------------- S6
def s6():
    qn = {"mdot": "Firemouth mass flow (kg/s)", "T_bulk": "Volume-mean gas temperature (C)", "T_out": "Outlet temperature (C)",
          "wall_loss": "Wall heat loss (kW)", "h_ref": "h_ref (W/m2K)", "A_hot": "A_hot (m2)"}
    g = [[r["form"], qn.get(r["quantity"], r["quantity"]), num(r["base"], 4), num(r["fine"], 4), num(r["diff_pct"], 2),
          num(r["gci_pct"], 2), int(r["n_base"]), int(r["n_fine"]), num(r["r"], 3)] for r in rows(R("Results", "checks", "grid_steady.csv"))]
    txt = open(R("Results", "checks", "summary_2-2abd.txt")).read()
    fuel = []
    for m in re.finditer(r"(\w_L\d+)\s+기본\s+(\d+)\s+조밀\s+(\d+)\s+\(([-+\d.]+) %\)", txt):
        fuel.append([m.group(1), int(m.group(2)), int(m.group(3)), float(m.group(4))])
    pen = []
    pm = {x["form"]: x for x in rows(R("Results", "cfd", "flame_penetration_max.csv"))}
    for m in re.finditer(r"  ([ABC])  기본 np6 ([\d.]+) \(범위 ([\d.]+)–([\d.]+)\)   조밀 np6 ([\d.]+)", txt):
        pen.append([m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4)), float(m.group(5))])
    co = {m.group(1): float(m.group(2)) for m in re.finditer(r"  ([ABC])  maxCo 10: np6 [\d.]+ \(분할 범위 [\d.–]+\)   maxCo 2: ([\d.]+)", txt)}
    for p in pen:
        p.append(co.get(p[0]))
    book("S6_Table.xlsx", "S6 Table. Grid and time-step tests.",
         [("Steady, grid", ["Form", "Quantity", "Base grid", "Fine grid", "Difference (%)", "GCI (%)", "Cells base",
                            "Cells fine", "Refinement ratio"], g,
           ["Background grid refined by sqrt(2) in each direction; GCI with safety factor 3 and assumed order 2.",
            "Source: Results/checks/grid_steady.csv (cfd/checks/summarize_checks.py)."]),
          ("Fuel, recalibrated", ["Kiln", "Fuel, base calibration (kg)", "Fuel, fine-grid calibration (kg)", "Difference (%)"], fuel,
           ["phi back-calculated again with the fine-grid calibration."]),
          ("Penetration", ["Form", "Base grid, 6 subdomains (m)", "Base grid, min over 4/6/8/10 subdomains (m)",
                           "Base grid, max over 4/6/8/10 subdomains (m)", "Fine grid, 6 subdomains (m)", "Max Courant 2 (m)"], pen,
           ["Maximum distance of the 1,000 C isotherm into the ware chamber within 45 s. Max Courant number 10 in the base runs.",
            "All three forms with max Courant 2 use the same dictionaries as the base runs, including the temperature limit.",
            "Source: Results/checks/summary_2-2abd.txt, Results/cfd/flame_penetration_max.csv."])])


# ---------------------------------------------------------------- S7
def s7():
    data = []
    for r in rows(R("Results", "checks", "oppoint.csv")):
        data.append([r["case"].replace("_L065_q", " "), r["form"], num(r["Q_kW"], 1), num(r["phi_mesh"], 3), num(r["mdot_cfd"], 4),
                     num(r["mdot_rom"], 4), round(float(r["mdot_rom"]) / float(r["mdot_cfd"]), 3), num(r["h_cfd"], 3),
                     num(r["h_rom"], 3), round(float(r["h_rom"]) / float(r["h_cfd"]), 3), num(r["T_bulk_C"], 1),
                     num(r["T_out_C"], 1), num(r["balance_pct"], 1), int(r["limiter_cells_max"])])
    book("S7_Table.xlsx", "S7 Table. Steady computations at operating points of the reduced-order model.",
         [("S7 Table", ["Case", "Form", "Heat release (kW)", "Opening ratio (grid)", "Inflow, CFD (kg/s)", "Inflow, Eq (1) (kg/s)",
                        "Ratio Eq (1)/CFD", "h, CFD (W/m2K)", "h, Eq (2) (W/m2K)", "Ratio Eq (2)/CFD",
                        "Volume-mean T (C)", "Outlet T (C)", "Energy balance (%)", "Limited cells (max)"], data,
           ["Firemouth narrowed to a central opening (other faces as wall); ambient 19.3 C; temperature limit 270-2,600 K.",
            "Eq (1) with the CFD volume-mean temperature, the grid opening ratio and the calibrated A_hot.",
            "h, CFD = surface coefficient from the wall loss with the external resistance 0.45 m2K/W removed.",
            "Energy balance includes the heat lost through the blocked part of the firemouth; averages of the last 2,000 iterations.",
            "Source: Results/checks/oppoint.csv (cfd/checks/summarize_checks.py)."])])


# ---------------------------------------------------------------- S8
def s8():
    txt = open(R("Results", "rom", "energy_audit.txt")).read()
    g = lambda pat: float(re.search(pat, txt).group(1))
    bal = [["Heat released", g(r"투입 발열\s+([\d.]+)"), 100.0],
           ["Exhaust enthalpy at the flue outlet", g(r"배기 엔탈피 \(연도 출구\)\s+([\d.]+)"), g(r"배기 엔탈피 \(연도 출구\)\s+[\d.]+\s+\(\s*([\d.]+) %\)")],
           ["Gas to walls and floor", g(r"기체 → 벽·바닥 표면\s+([\d.]+)"), g(r"기체 → 벽·바닥 표면\s+[\d.]+\s+\(\s*([\d.]+) %\)")],
           ["  of which stored in walls and ground", g(r"그중 벽·지반 축열 증가\s+([\d.]+)"), None],
           ["  of which conducted beyond the ground layer (15 C)", g(r"그중 지중 경계\(15 ℃\) 유출\s+([\d.]+)"), None],
           ["Gas to load (stored in load)", g(r"기체 → 적재물 \(= 적재물 축열\)\s+([\d.]+)"), g(r"기체 → 적재물 \(= 적재물 축열\)\s+[\d.]+\s+\(\s*([\d.]+) %\)")],
           ["Closure (exhaust + walls + load) / released (%)", g(r"닫힘 \(배기 \+ 벽 \+ 적재물\)/투입\s+([\d.]+) %"), None]]
    rad = [["Radiative share of heat from gas to walls (%)", g(r"기체 → 벽 표면 열 중 복사 ([\d.]+) %")],
           ["Radiative share of heat from gas to load (%)", g(r"기체 → 적재물 열 중 복사 ([\d.]+) %")],
           ["Axial radiation exchanged between segments (GJ)", g(r"구간 사이 축방향 복사 교환 ([\d.]+) GJ")],
           ["  as share of heat released (%)", g(r"구간 사이 축방향 복사 교환 [\d.]+ GJ \(투입의 ([\d.]+) %\)")]]
    ser = rows(R("Results", "rom", "energy_audit_series.csv"))
    keys = ["t_h", "Q_kW", "T_front_C", "mdot", "hc", "hr", "rad_share_wall", "q_exh_kW", "q_wall_kW", "q_ware_kW",
            "q_axial_kW", "R_surf", "R_conv_only", "R_wall", "depth_m"]
    sdata = [[num(r[k], 4) for k in keys] for r in ser]
    book("S8_Table.xlsx", "S8 Table. Energy balance of the 78 h operation (form B, ware chamber 6.5 m).",
         [("Balance", ["Item", "GJ (0-78 h)", "Share of heat released (%)"], bal,
           ["Source: Results/rom/energy_audit.txt (rom/energy_audit.py)."]),
          ("Radiation", ["Item", "Value"], rad, []),
          ("Hourly", ["Time (h)", "Heat release (kW)", "Front gas T (C)", "Mass flow (kg/s)", "h_c wall (W/m2K)",
                      "h_r wall (W/m2K)", "Radiative share to wall", "Exhaust (kW)", "To walls (kW)", "To load (kW)",
                      "Axial radiation (kW)", "R surface 1/(h_c+h_r) (m2K/W)", "R convection only 1/h_c (m2K/W)",
                      "R wall t_w/k_w (m2K/W)", "Penetration depth sqrt(alpha t) (m)"], sdata,
           ["Area-weighted wall-surface coefficients. Source: Results/rom/energy_audit_series.csv."])])


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in (s1, s2, s3, s4, s5, s6, s7, s8):
        f()


if __name__ == "__main__":
    main()
