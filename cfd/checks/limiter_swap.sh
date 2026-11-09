#!/bin/bash
# 2-1b 점검: 정상상태 보정 해에서 온도 리미터(limitTemperature 2,600 K)가 보정값과 연료에 주는 영향.
#
# A_L065 는 리미터가 있고(상한에 잘리는 셀이 남는다) B_L065 는 리미터가 없다(국소 온도가 2,600 K 를 넘는다).
# 두 형식을 서로의 조건으로 바꿔 지금 해에서 이어 푼다.
#   A_nolim : A_L065 에서 limitT 를 뺀다            (B 와 같은 처리)
#   B_lim   : B_L065 에 C_L065 의 limitT 를 더한다   (A 와 같은 처리)
# 그다음 축소모델 보정 → φ 역산 → 형식별 연료를 세 경우(base·A_nolim·B_lim)로 계산한다.
# 보정 평균은 세 경우 모두 rom/calibrate.py 그대로 마지막 2,000 회(로그의 반복 번호로 자른다)다.
# cases/*_steady 와 rom/ 은 건드리지 않는다. 산출물: Results/checks/limiter_swap/
#
#   bash cfd/checks/limiter_swap.sh          (CFD 2 건 병렬 약 15분 + 축소모델 3 건 병렬 약 25분)
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
source "$ROOT/paths.sh"
kiln_openfoam || exit 1
OUT="$ROOT/Results/checks/limiter_swap"
EXTRA=6000                      # 이어 풀 반복 수
mkdir -p "$OUT"

prep() {  # prep <원본 케이스> <새 이름>
  local SRC="$(kiln_case steady $1)" DST="$OUT/$2"
  local LAST
  LAST=$(ls "$SRC" | grep -E '^[0-9]+$' | sort -g | tail -1)
  [ -n "$LAST" ] || { echo "$SRC: 시간 디렉터리 없음 — cfd/run_steady.sh 먼저"; exit 1; }
  [ -e "$DST" ] && { echo "$DST 가 이미 있다 — 지우고 다시 실행할 것"; exit 1; }
  mkdir -p "$DST"
  cp -r "$SRC/0" "$SRC/constant" "$SRC/system" "$SRC/$LAST" "$DST/"
  touch "$DST/$2.foam"
  sed -i "s/^endTime .*/endTime         $((LAST + EXTRA));/" "$DST/system/controlDict"
}
prep A_L065 A_nolim
prep B_L065 B_lim
python3 - "$OUT" "$(kiln_case steady C_L065)/system/fvOptions" <<'EOF'
import sys
out, cfv = sys.argv[1], sys.argv[2]
a = out + "/A_nolim/system/fvOptions"; t = open(a).read()
i = t.index("limitT\n{"); open(a, "w").write(t[:i] + t[t.index("}\n", i) + 2:])
c = open(cfv).read(); j = c.index("limitT\n{")
open(out + "/B_lim/system/fvOptions", "a").write("\n" + c[j:c.index("}\n", j) + 2])
EOF

solve() {
  cd "$OUT/$1"
  decomposePar -force > log.decompose 2>&1 \
    && mpirun -np 4 buoyantSimpleFoam -parallel > log.solver 2>&1 \
    && reconstructPar -latestTime > log.reconstruct 2>&1
  local RC=$?
  rm -rf processor*
  # rom/calibrate.py 의 입력 지문 검사용 (cfd/run_case.sh 와 같은 목록)
  md5sum 0/* constant/g constant/thermophysicalProperties constant/turbulenceProperties \
         system/* constant/polyMesh/{points,faces,owner,neighbour,boundary} > log.inputs.md5
  echo "$1 rc=$RC"; return $RC
}
solve A_nolim & P1=$!
solve B_lim & P2=$!
wait $P1 && wait $P2

romtree() {  # romtree <이름> <A 케이스> <B 케이스>
  local T="$OUT/rom_$1"
  mkdir -p "$T/Results/rom" "$T/steady"
  cp -r "$ROOT/rom" "$T/"; rm -rf "$T/rom/__pycache__"
  for l in mesh Data cfd paths.sh; do ln -sfn "$ROOT/$l" "$T/$l"; done
  ln -sfn "$2" "$T/steady/A_L065"; ln -sfn "$3" "$T/steady/B_L065"
  ln -sfn "$(kiln_case steady C_L065)" "$T/steady/C_L065"
}
romtree base    "$(kiln_case steady A_L065)" "$(kiln_case steady B_L065)"
romtree A_nolim "$OUT/A_nolim"            "$(kiln_case steady B_L065)"
romtree B_lim   "$(kiln_case steady A_L065)" "$OUT/B_lim"

chain() {
  local T="$OUT/rom_$1"; cd "$T/rom"
  export KILN_STEADY_DIR="$T/steady"
  python3 calibrate.py > "$T/Results/rom/calibration.txt" 2>&1 \
    && python3 run.py > "$T/Results/rom/run.log" 2>&1 \
    && python3 efficiency.py > "$T/Results/rom/log_efficiency.txt" 2>&1
  local RC=$?; echo "rom_$1 rc=$RC"; return $RC
}
chain base & Q1=$!
chain A_nolim & Q2=$!
chain B_lim & Q3=$!
wait $Q1 && wait $Q2 && wait $Q3

python3 "$HERE/limiter_summary.py" "$OUT" | tee "$OUT/요약.txt"
