"""케이스 폴더 이름과 보관 로그 — 저장소 구조(cases/, Results/logs/)를 한곳에서 정한다.

형식 A·B·C 의 케이스 이름은 저장소의 첫 판(태그 Article)과 같다:
    cases/A_horizontal_unstepped        비정상 냉시동 (buoyantPimpleFoam)
    cases/A_horizontal_unstepped_steady 정상상태 보정 (buoyantSimpleFoam)
계산 중의 모델 이름은 A_L065·B_L065·C_L065 (소성실 6.5 m)이다.

계산 로그는 Results/logs/ 에 xz 로 압축해 보관한다 (cfd/archive_logs.sh). 경로는 저장소 안의
원래 자리를 따른다: cases/X/log.solver → Results/logs/cases/X/log.solver.xz,
Results/checks/grid/steady/A_L065/log.solver → Results/logs/checks/grid/steady/A_L065/log.solver.xz.
케이스를 다시 풀지 않은 저장소에서는 read_log 가 보관본을 읽는다.
"""
import lzma
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
NAMES = {"A": "A_horizontal_unstepped", "B": "B_horizontal_stepped", "C": "C_vertical_stepped"}
LOGS = os.path.join(ROOT, "Results", "logs")


def case_dir(kind, model):
    """kind = 'steady' | 'transient', model = 'A_L065' 또는 'A'."""
    n = NAMES[model[0]]
    return os.path.join(ROOT, "cases", n + ("_steady" if kind == "steady" else ""))


def archived(path):
    rel = os.path.relpath(os.path.abspath(path), ROOT)
    if rel.startswith("Results" + os.sep):
        rel = rel[len("Results") + 1:]
    return os.path.join(LOGS, rel + ".xz")


def exists(path):
    return os.path.exists(path) or os.path.exists(archived(path))


def read_log(path):
    """케이스 안의 로그, 없으면 Results/logs 의 보관본을 읽는다."""
    if os.path.exists(path):
        return open(path, errors="ignore").read()
    a = archived(path)
    if os.path.exists(a):
        with lzma.open(a, "rt", errors="ignore") as f:
            return f.read()
    raise FileNotFoundError("%s 도, 보관본 %s 도 없다" % (path, a))
