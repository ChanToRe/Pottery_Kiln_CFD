#!/usr/bin/env python3
"""
2-2 CFD 검증 케이스를 만든다 (풀지는 않는다 — cfd/checks/run_checks.sh 가 case_queue.py 로 푼다).

  grid     2-2a 격자 독립성 (E-04). 배경 격자 0.1 m → 0.0707 m (세 방향 √2 배, 표면 세분 1 단계 그대로).
           정상 3 + 비정상 3. 사전은 cases/ 의 정상·비정상 케이스 그대로, 격자만 다르다.
  courant  2-2b 시간 간격 (E-05). 세 형식의 비정상을 maxCo 10 → 2 로.
  oppoint  2-2d 조업점 (E-08). 정상 케이스에서 화구를 좁히고(바닥 가운데 정사각 개구, 나머지는 벽)
           발열률을 바꾼다. 개구율 φ·발열률은 축소모델 역산(Results/rom/rom_phi.csv)의 세 구간:
           40–45 h (81.7 kW, φ 0.231), 50–52 h (245 kW, φ 0.229), 52–78 h (448.9 kW, φ 0.070).
           출발장은 같은 형식의 정상 보정 해(cases/<형식>_steady 마지막 시각)를 mapFields 로 옮긴다.
           세 형식 모두 온도 상한 270–2,600 K 를 둔다(비정상과 같게, K21) — 걸린 셀 수를 보고한다.

    python3 cfd/checks/setup_checks.py [grid] [courant] [oppoint]
결과 케이스: Results/checks/{grid,courant,oppoint}/...
"""
import csv
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CFD = os.path.join(ROOT, "cfd")
OUT = os.path.join(ROOT, "Results", "checks")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import meshtools  # noqa: E402
import cases  # noqa: E402

MODELS = ["A_L065", "B_L065", "C_L065"]
REFINE = 2 ** 0.5               # 배경 격자 세 방향 √2 배 (B·C 106×26×44 → 150×37×62, A 106×26×40 → 150×37×57)
OP_SEGMENTS = [(40.0, "q082"), (50.0, "q245"), (52.0, "q449")]   # rom_phi.csv 의 t0_h
FACE = 0.05                     # 화구 면 크기 (배경 0.1 m, 표면 세분 1 단계)

LIMIT_T = """
limitT
{
    // 2-2d 조업점 검증용 — 비정상 케이스와 같은 상한 (결정 K21). 걸린 셀 수를 log 에서 볼 것.
    type            limitTemperature;
    selectionMode   all;
    min             270;
    max             2600;
}
"""


def sh(cmd, cwd):
    """OpenFOAM 환경을 읽고 명령을 돌린다."""
    full = 'source "%s/paths.sh" && kiln_openfoam && %s' % (ROOT, cmd)
    r = subprocess.run(["bash", "-c", full], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(r.stdout[-3000:] + r.stderr[-3000:])
        raise RuntimeError("%s 실패 (%s)" % (cmd, cwd))
    return r.stdout


def copy_case(src, dst, mesh_from=None):
    """사전(0, constant, system)만 복사한다. 격자는 mesh_from (기본: src) 의 polyMesh."""
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    shutil.copytree(os.path.join(src, "0"), os.path.join(dst, "0"))
    shutil.copytree(os.path.join(src, "system"), os.path.join(dst, "system"))
    os.makedirs(os.path.join(dst, "constant"))
    for f in os.listdir(os.path.join(src, "constant")):
        p = os.path.join(src, "constant", f)
        if f in ("polyMesh", "triSurface"):
            continue
        shutil.copy(p, os.path.join(dst, "constant", f))
    shutil.copytree(os.path.join(mesh_from or src, "constant", "polyMesh"),
                    os.path.join(dst, "constant", "polyMesh"))


def sub(path, pat, rep, count=1):
    txt = open(path).read()
    new, n = re.subn(pat, rep, txt, count=count, flags=re.M)
    if n != count:
        raise ValueError("%s: '%s' 를 %d 번 찾지 못했다" % (path, pat, count))
    open(path, "w").write(new)


# ── 2-2a 격자 ─────────────────────────────────────────────
def setup_grid():
    for M in MODELS:
        mesh = os.path.join(OUT, "grid", "mesh", M)
        if os.path.exists(mesh):
            shutil.rmtree(mesh)
        shutil.copytree(os.path.join(ROOT, "mesh", M, "system"), os.path.join(mesh, "system"))
        os.makedirs(os.path.join(mesh, "constant", "triSurface"))
        stl = "kiln_B_L065_cfd.stl" if M == "B_L065" else "kiln_%s.stl" % M
        shutil.copy(os.path.join(ROOT, "mesh", "stl", stl),
                    os.path.join(mesh, "constant", "triSurface", "kiln.stl"))
        bmd = os.path.join(mesh, "system", "blockMeshDict")
        m = re.search(r"hex \(0 1 2 3 4 5 6 7\) \((\d+) (\d+) (\d+)\)", open(bmd).read())
        fine = tuple(round(int(v) * REFINE) for v in m.groups())
        sub(bmd, re.escape(m.group(0)), "hex (0 1 2 3 4 5 6 7) (%d %d %d)" % fine)
        sh("blockMesh > log.blockMesh 2>&1 && snappyHexMesh -overwrite > log.snappyHexMesh 2>&1"
           " && (checkMesh > log.checkMesh 2>&1 || true)", mesh)
        nc = re.search(r"nCells:\s*(\d+)", open(os.path.join(mesh, "constant/polyMesh/owner")).read()).group(1)
        print("격자 %s 조밀: 배경 %s, 셀 %s" % (M, fine, nc))
        for kind in ("steady", "transient"):
            copy_case(cases.case_dir(kind, M), os.path.join(OUT, "grid", kind, M), mesh_from=mesh)


# ── 2-2b C 시간 간격 ──────────────────────────────────────
def setup_courant():
    for t in "ABC":
        dst = os.path.join(OUT, "courant", t + "_co2")
        copy_case(cases.case_dir("transient", t + "_L065"), dst)
        sub(os.path.join(dst, "system", "controlDict"), r"^maxCo\s+10;", "maxCo           2;")
        print("Courant %s_co2: maxCo 2" % t)


# ── 2-2d 조업점 ───────────────────────────────────────────
def rom_phi():
    rows = {}
    for r in csv.DictReader(open(os.path.join(ROOT, "Results", "rom", "rom_phi.csv"))):
        rows[float(r["t0_h"])] = (float(r["phi"]), float(r["Q_kW"]))
    return rows


def _block(t, key):
    """경계 블록 'key { … }' 의 (시작, 끝) — 없으면 None."""
    m = re.search(r"^(\s*)%s\s*\n\s*\{" % key, t, re.M)
    if not m:
        return None
    i = t.index("{", m.end() - 1)
    depth = 0
    for j in range(i, len(t)):
        depth += {"{": 1, "}": -1}.get(t[j], 0)
        if depth == 0:
            return m.start(), j + 1
    raise ValueError(key)


def fix_fields(field_path, base_path, name="stokeBlock"):
    """createPatch(v2312)는 필드 파일을 고치지 않는다. 옮겨 온 장(mapFields)의 inlet 블록은 면 수가
    바뀌었으므로 원래 케이스 0/ 의 inlet 블록(균일값)으로 바꾸고, name 블록은 원래 walls 블록을
    이름만 바꿔 넣는다 — 막은 화구는 벽과 같은 경계조건(벽 0.35 m · 외부 열전달)이다."""
    txt = open(field_path).read()
    base = open(base_path).read()
    bi, bw = _block(base, "inlet"), _block(base, "walls")
    i = _block(txt, "inlet")
    txt = txt[:i[0]] + base[bi[0]:bi[1]] + txt[i[1]:]
    if _block(txt, name):
        raise ValueError("%s 에 이미 %s 가 있다" % (field_path, name))
    w = _block(txt, "walls")
    txt = txt[:w[1]] + "\n" + base[bw[0]:bw[1]].replace("walls", name, 1) + txt[w[1]:]
    open(field_path, "w").write(txt)


def setup_oppoint():
    phi = rom_phi()
    for M in MODELS:
        src = cases.case_dir("steady", M)
        last = max((d for d in os.listdir(src) if re.fullmatch(r"\d+", d) and d != "0"), key=int)
        A_in = sum(a for _, a in meshtools.patch_faces(src, "inlet"))
        pf = meshtools.patch_faces(src, "inlet")
        for t0, tag in OP_SEGMENTS:
            ph, q = phi[t0]
            dst = os.path.join(OUT, "oppoint", "%s_%s" % (M, tag))
            copy_case(src, dst)
            # 개구: 화구 바닥 가운데의 거의 정사각인 직사각형. 실제 면 중심으로 면적을 세어
            # 목표 φ·A_in 에 가장 가까운 것을 고른다 (가로·세로 면 수 차이 1 이하).
            target = ph * A_in
            z0 = min(c[2] for c, _ in pf) - FACE / 2
            best = None
            for ny in range(1, 19):
                for nz in (ny - 1, ny, ny + 1):
                    if nz < 1:
                        continue
                    hy, top = ny * FACE / 2, z0 + nz * FACE
                    ar = sum(a for c, a in pf if abs(c[1]) <= hy and c[2] <= top)
                    if best is None or abs(ar - target) < abs(best[0] - target):
                        best = (ar, ny, nz, hy, top)
            _, ny, nz, hy, top = best
            n = (ny, nz)
            box = "(-3.2 %.4f %.4f) (-2.6 %.4f %.4f)" % (-hy, z0 - FACE, hy, top)
            # 출발장: 정상 보정 해 (패치를 바꾸기 전에 옮겨야 -consistent 가 된다)
            keep = set(os.listdir(os.path.join(dst, "0")))
            sh('mapFields "%s" -consistent -sourceTime %s > log.mapFields 2>&1' % (src, last), dst)
            for f in set(os.listdir(os.path.join(dst, "0"))) - keep:   # 후처리 필드(wallHeatFlux 등)는 뺀다
                os.remove(os.path.join(dst, "0", f))
            open(os.path.join(dst, "system", "topoSetDict.inlet"), "w").write(
                HEAD % "topoSetDict" + """actions
(
    { name f_open;  type faceSet; action new;      source patchToFace; patch inlet; }
    { name f_open;  type faceSet; action subset;   source boxToFace;   box %s; }
    { name f_block; type faceSet; action new;      source patchToFace; patch inlet; }
    { name f_block; type faceSet; action subtract; source faceToFace;  set f_open; }
);
""" % box)
            open(os.path.join(dst, "system", "createPatchDict"), "w").write(
                HEAD % "createPatchDict" + """pointSync false;
patches
(
    { name stokeBlock; patchInfo { type wall; } constructFrom set; set f_block; }
);
""")
            sh("topoSet -dict system/topoSetDict.inlet > log.topoSet.inlet 2>&1"
               " && createPatch -overwrite > log.createPatch 2>&1", dst)
            for f in os.listdir(os.path.join(dst, "0")):
                fix_fields(os.path.join(dst, "0", f), os.path.join(src, "0", f))
            A_open = sum(a for _, a in meshtools.patch_faces(dst, "inlet"))
            # 발열률과 온도 상한
            fvo = os.path.join(dst, "system", "fvOptions")
            sub(fvo, r"h\s+\(150000\.0 0\);", "h  (%.1f 0);" % (q * 1e3))
            if "limitTemperature" not in open(fvo).read():
                open(fvo, "a").write(LIMIT_T)
            # 벽 열유속에 막은 화구도 넣는다 (log 에 패치별로 따로 찍힌다)
            sub(os.path.join(dst, "system", "controlDict"), r"patches\s+\( walls \);",
                "patches         ( walls stokeBlock );")
            open(os.path.join(dst, "oppoint.txt"), "w").write(
                "model %s\nsegment_t0_h %g\nQ_kW %.1f\nphi_rom %.6f\nA_in_m2 %.5f\nA_open_m2 %.5f\n"
                "phi_mesh %.6f\nn_faces_y_z %d %d\n" % (M, t0, q, ph, A_in, A_open, A_open / A_in, n[0], n[1]))
            print("조업점 %s %s: %.1f kW, φ rom %.3f → 격자 %.3f (개구 %.4f m2)"
                  % (M, tag, q, ph, A_open / A_in, A_open))


HEAD = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      %s;
}
"""

if __name__ == "__main__":
    what = sys.argv[1:] or ["grid", "courant", "oppoint"]
    for w in what:
        {"grid": setup_grid, "courant": setup_courant, "oppoint": setup_oppoint}[w]()
