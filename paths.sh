# 공용 경로·도구 설정. 다른 스크립트가 source 한다.
#   source paths.sh
# 기계가 바뀌면 이 파일만 고친다.

KILN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export KILN_ROOT

# OpenFOAM ESI v2312
KILN_OPENFOAM_BASHRC="${KILN_OPENFOAM_BASHRC:-/usr/lib/openfoam/openfoam2312/etc/bashrc}"

# ParaView 5.10 (pvbatch, 헤드리스 렌더링에 DISPLAY 필요)
KILN_PVBATCH="${KILN_PVBATCH:-/opt/paraviewopenfoam510/bin/pvbatch}"
export DISPLAY="${DISPLAY:-:0}"

# 형상 생성기(numpy)와 R 그래프(ggplot2·patchwork·here·png·jpeg)용 환경.
# env/setup_env.sh 가 env/kiln 에 만든다. 축소모델·후처리는 시스템 python3
# (표준 라이브러리만) 으로 돈다.
KILN_PY="${KILN_PY:-$KILN_ROOT/env/kiln/bin/python}"
KILN_RSCRIPT="${KILN_RSCRIPT:-$KILN_ROOT/env/kiln/bin/Rscript}"
export KILN_PY KILN_RSCRIPT KILN_PVBATCH KILN_OPENFOAM_BASHRC

# 보충 표(S1–S8 Table, xlsx)를 쓰는 openpyxl 환경. setup_env.sh 가 env/doc 에 만든다.
KILN_DOC_PY="${KILN_DOC_PY:-$KILN_ROOT/env/doc/bin/python}"
export KILN_DOC_PY

kiln_openfoam() {
    # OpenFOAM bashrc 는 unset 변수를 참조하므로 set -u 상태로 부르면 안 된다.
    source "$KILN_OPENFOAM_BASHRC" >/dev/null 2>&1 || true
    command -v blockMesh >/dev/null || { echo "OpenFOAM 환경을 읽지 못했다: $KILN_OPENFOAM_BASHRC" >&2; return 1; }
}

kiln_case() {
    # kiln_case steady|transient A_L065  → 저장소의 케이스 폴더 (cfd/cases.py 와 같은 규칙)
    local n
    case ${2:0:1} in
        A) n=A_horizontal_unstepped ;;
        B) n=B_horizontal_stepped ;;
        C) n=C_vertical_stepped ;;
        *) echo "모르는 형식: $2" >&2; return 1 ;;
    esac
    [ "$1" = steady ] && n=${n}_steady
    echo "$KILN_ROOT/cases/$n"
}
