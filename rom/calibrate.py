#!/usr/bin/env python3
"""
정상상태 CFD → 축소모델 보정. 넘어가는 값은 두 종류다.

  A_hot      형식별 유효 고온부 유동면적  ← CFD 화구 유입량
  h_conv_ref 대류 열전달계수             ← CFD 벽체 손실 (외부저항 벗겨냄)

보정 출처는 cases/{A_horizontal_unstepped,B_horizontal_stepped,C_vertical_stepped}_steady (buoyantSimpleFoam, 150 kW, 화구 완전개방,
외기 19.3 ℃, 벽 0.35 m · k 1.0). 세 형식 모두 자기 해가 있다.
값은 각 케이스의 log.solver 에서 마지막 NAVG 회 평균으로 읽는다.

    python3 calibrate.py          보정값 표를 출력한다
    KILN_STEADY_DIR=<경로>        다른 정상상태 케이스 묶음을 읽을 때 (비교용)
"""
import hashlib
import os
import re
import sys

import geom
import rom

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cfd"))
import cases  # noqa: E402

# 기본은 저장소의 정상 케이스 cases/<형식>_steady. KILN_STEADY_DIR 를 주면 그 아래 <모델> 폴더를 읽는다.
STEADY_DIR = os.environ.get("KILN_STEADY_DIR")


def case_of(model):
    return os.path.join(STEADY_DIR, model) if STEADY_DIR else cases.case_dir("steady", model)

NAVG = 2000        # 마지막 몇 회를 평균할지


def read_cfd(model, navg=NAVG):
    """정상상태 해에서 보정에 쓸 값을 읽는다. **마지막 navg 회의 평균**을 쓴다.

    C 는 자유 부력 플룸이 감쇠 없이 흔들려 SIMPLE 이 고정점에 닿지 않는다
    (잔차 ~1e-2). 발산이 아니라 정상해가 없는 것이므로, 마지막 반복 하나를
    뽑으면 에너지 수지가 어긋난다. A·B 는 수렴하므로 평균해도 값이 같다.

    로그가 없으면 멈춘다. 예전 판은 하드코딩한 기록값(벽 0.20 m 시절)으로
    조용히 물러섰는데, 그러면 다른 조건의 보정값이 섞인다.
    """
    path = os.path.join(case_of(model), "log.solver")
    if not cases.exists(path):
        raise FileNotFoundError(
            "%s 가 없다 — cfd/run_steady.sh 로 정상상태 CFD 를 먼저 돌릴 것" % path)
    check_wall_bc(model)
    check_inputs(model)
    keys = {"mdot": r"sum\(inlet\) of phi = ([-\d.e+]+)",
            "T_bulk": r"volAverage\(region0\) of T = ([\d.e+-]+)",
            "T_out": r"areaAverage\(outlet\) of T = ([\d.e+-]+)",
            # 로그 줄이 "min/max/integ(walls) = min, max, integ" 형식이라
            # 앞 두 값을 건너뛰고 세 번째(면적분)를 잡아야 한다.
            "wall_loss": r"min/max/integ\(walls\) = [-\d.e+]+, [-\d.e+]+, ([-\d.e+]+)"}
    txt = cases.read_log(path)
    # 함수객체는 매 반복이 아니라 50 회마다(벽 손실은 저장 시각마다) 기록하므로 표본 개수로
    # 자르면 반복 수와 어긋난다(예전 판은 표본 300 개 전부 = 출발 과도까지 평균했다).
    # "Time = N" 줄로 반복 번호를 읽어 마지막 navg 회에 해당하는 부분만 남긴다.
    steps = [(int(s.group(1)), s.start()) for s in re.finditer(r"^Time = (\d+)$", txt, re.M)]
    if not steps:
        raise ValueError("%s 에서 반복 번호(Time = N)를 찾지 못했다" % path)
    first = steps[-1][0] - navg
    txt = txt[next(pos for t, pos in steps if t > first):]
    out = {"source": path}
    for k, pat in keys.items():
        w = [float(x) for x in re.findall(pat, txt)]
        if not w:
            raise ValueError("%s 의 마지막 %d 회에서 %s 를 찾지 못했다" % (path, navg, k))
        out[k] = sum(w) / len(w)
        out[k + "_sd"] = (sum((x - out[k]) ** 2 for x in w) / len(w)) ** 0.5
        out["n"] = len(w)
    out["mdot"] = abs(out["mdot"])
    out["wall_loss"] = abs(out["wall_loss"])
    return out


def check_wall_bc(model):
    """CFD 케이스 사전(0/T walls)의 외기·벽 조건이 rom.CFD_STEADY·CFD_WALL 과 같은지 본다.

    사전이 없으면(로그만 모은 KILN_STEADY_DIR) 건너뛴다. 투고본은 벽 두께가 0.20 → 0.35 m 로
    바뀐 뒤에도 외부저항을 옛 값으로 두어 보정값이 어긋났다(E-11) — 같은 일을 막는다.
    """
    path = os.path.join(case_of(model), "0", "T")
    if not os.path.exists(path):
        return
    txt = open(path).read()
    walls = txt[txt.index("walls"):]
    walls = walls[:walls.index("}")]
    got = {}
    for key, pat in (("h_out", r"\bh\s+uniform\s+([\d.eE+-]+)"),
                     ("T_amb", r"\bTa\s+uniform\s+([\d.eE+-]+)"),
                     ("th", r"thicknessLayers\s+\(\s*([\d.eE+-]+)\s*\)"),
                     ("k", r"kappaLayers\s+\(\s*([\d.eE+-]+)\s*\)")):
        m = re.search(pat, walls)
        if m:
            got[key] = float(m.group(1))
    want = dict(rom.CFD_WALL, T_amb=rom.CFD_STEADY["T_amb"])
    bad = ["%s: 사전 %g / rom %g" % (k, got[k], want[k])
           for k in got if abs(got[k] - want[k]) > 1e-9]
    if bad:
        raise ValueError("%s 의 벽 조건이 rom.py 와 다르다 — %s" % (path, "; ".join(bad)))


def check_inputs(model):
    """log.solver 가 지금의 케이스 사전으로 푼 것인지 본다 (cfd/run_case.sh 가 남긴 log.inputs.md5).

    사전이 있는 케이스 폴더에서만 본다. 로그만 모은 폴더(KILN_STEADY_DIR)는
    대조할 사전이 없으므로 건너뛴다.
    """
    case = case_of(model)
    if not os.path.isdir(os.path.join(case, "0")):
        sys.stderr.write("주의: %s 에 케이스 사전이 없어 로그의 계산 조건을 대조하지 못한다 "
                         "\n" % case)
        return
    stamp = os.path.join(case, "log.inputs.md5")
    # 케이스를 다시 풀지 않았으면 Results/logs 의 보관본(로그와 그 입력 지문)을 쓴다. 이때 격자
    # (constant/polyMesh)는 만들어져 있지 않으므로 사전 파일만 대조한다.
    from_archive = not os.path.exists(os.path.join(case, "log.solver"))
    if not cases.exists(stamp):
        raise FileNotFoundError(
            "%s 가 없다 — 이 로그를 만든 입력을 확인할 수 없다. cfd/run_steady.sh 로 다시 풀 것" % stamp)
    if from_archive:
        sys.stderr.write("주의: %s 는 Results/logs 의 보관 로그로 보정한다 (격자 지문은 대조하지 않음)\n" % case)
    listed = {}
    for line in cases.read_log(stamp).splitlines():
        md5, path = line.split(None, 1)
        if from_archive and path.strip().startswith("constant/polyMesh/"):
            continue
        listed[path.strip()] = md5
    now = sorted(["0/" + f for f in os.listdir(os.path.join(case, "0"))]
                 + ["system/" + f for f in os.listdir(os.path.join(case, "system"))])
    bad = [p for p in now if p not in listed]
    for path, md5 in listed.items():
        full = os.path.join(case, path)
        if not os.path.exists(full) or hashlib.md5(open(full, "rb").read()).hexdigest() != md5:
            bad.append(path)
    if bad:
        raise ValueError("%s: 로그 이후 입력이 바뀌었다 (%s) — cfd/run_steady.sh 로 다시 풀 것"
                         % (case, ", ".join(sorted(set(bad)))))


def h_conv_ref(form="A"):
    """CFD 벽체손실에서 표면측 대류계수만 분리한다.

    총 관통 컨덕턴스 U = 벽체손실 / (습윤면적 × (체적평균온도 − 외기)) 에서
    벽 경계조건의 외부저항 rom.CFD_STEADY["R_ext"] 를 벗겨낸 나머지가
    표면측 대류저항이다. 정상상태 CFD 에는 복사모델이 없으므로 순수 대류값이다.
    (R_ext 값의 사정은 rom.py 의 CFD_STEADY 주석 참조.)
    """
    c = read_cfd("%s_L065" % form)
    A_wall = geom.extract("%s_L065" % form)["A_wall"]
    dT = c["T_bulk"] - rom.CFD_STEADY["T_amb"]
    U = c["wall_loss"] / (A_wall * dT)                      # 총 관통 컨덕턴스
    R_conv = 1.0 / U - rom.CFD_STEADY["R_ext"]
    if R_conv <= 0:
        raise ValueError("외부저항이 총저항보다 크다 — 보정 불가")
    return 1.0 / R_conv


def A_hot_of(form):
    """형식별 유효 고온부 유동면적. 그 형식의 CFD 해에서 역산한다.

    세 형식 모두 자기 정상상태 해가 있다 (예전 판은 해가 없는 형식이 다른
    형식의 값을 빌렸다).
    """
    c = read_cfd("%s_L065" % form)
    g = geom.extract("%s_L065" % form)
    return rom.calibrate_A_hot(
        g["H_stack"], g["A_in"], c["mdot"],
        rom.CFD_STEADY["T_amb"], c["T_bulk"])


def build(model, seg_m=None, **kw):
    """보정을 마친 Kiln 인스턴스. seg_m 을 주면 소성부를 축방향으로 쪼갠다.

    길이·계단 변형(B_L025, B_L065_S6 …)은 같은 형식(B)의 L065 보정값을 쓴다.
    """
    g = geom.extract(model, seg_m=seg_m)
    t = g["type"]
    A_hot = A_hot_of(t)
    k = dict(A_hot=A_hot, h_conv_ref=h_conv_ref(t),
             mdot_ref=read_cfd("%s_L065" % t)["mdot"])
    k.update(kw)
    return rom.Kiln(g, **k), dict(A_hot=A_hot)


if __name__ == "__main__":
    print("정상상태 CFD 보정 기준점 (cases/*_steady, 150 kW, 화구 완전개방, 외기 %.1f ℃)\n"
          % (rom.CFD_STEADY["T_amb"] - 273.15))
    print("마지막 %d 회 평균 (± 는 그 구간의 표준편차 = 진동 폭)\n" % NAVG)
    print("%-8s %14s %13s %13s %11s" %
          ("model", "mdot [kg/s]", "volAvg T[℃]", "outlet T[℃]", "벽체손실[kW]"))
    for t in "ABC":
        c = read_cfd("%s_L065" % t)
        print("%-8s %8.3f±%.3f %8.1f±%.1f %8.1f±%.1f %7.1f±%.1f" %
              (t + "_L065", c["mdot"], c["mdot_sd"],
               c["T_bulk"] - 273.15, c["T_bulk_sd"],
               c["T_out"] - 273.15, c["T_out_sd"],
               c["wall_loss"] / 1e3, c["wall_loss_sd"] / 1e3))

    print("\n형식별 대류계수 (외부저항 R=%.2f m2K/W 를 벗겨낸 표면측 값)"
          % rom.CFD_STEADY["R_ext"])
    for t in "ABC":
        print("  %s  h_conv,ref = %.4f W/m2K" % (t, h_conv_ref(t)))

    print("\n%-8s %8s %8s %9s %10s %10s" %
          ("model", "H[m]", "A_wall", "A_hot[m2]", "재현 mdot", "CFD mdot"))
    for t in "ABC":
        m = "%s_L065" % t
        k, info = build(m)
        c = read_cfd(m)
        md = rom.draft(c["T_bulk"], 1.0, k.H,
                       k.A_in, info["A_hot"], rom.CFD_STEADY["T_amb"])
        print("%-8s %8.3f %8.2f %9.4f %10.3f %10.3f" %
              (m, k.H, k.geo["A_wall"], info["A_hot"], md, c["mdot"]))
