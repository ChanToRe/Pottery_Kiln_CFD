#!/bin/bash
# 케이스 하나를 처음부터 푼다 (0 만 남기고 지운 뒤 topoSet → 분할 → 병렬 풀이 → 재구성).
#   bash cfd/run_case.sh <케이스 디렉터리>
# 솔버는 system/controlDict 의 application, 분할 수는 decomposeParDict 에서 읽는다.
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../paths.sh"
kiln_openfoam || exit 1
C="$(cd "$1" && pwd)" || exit 1
[ -d "$C/constant/polyMesh" ] || { echo "$C: 격자 없음 — mesh/make_mesh.sh 먼저"; exit 1; }
APP=$(grep -oP '^application\s+\K\w+' "$C/system/controlDict")
NP=$(grep -oP 'numberOfSubdomains\s+\K[0-9]+' "$C/system/decomposeParDict")
cd "$C"
for d in $(ls | grep -E '^[0-9]+(\.[0-9]+)?(e[-+]?[0-9]+)?$'); do [ "$d" = "0" ] || rm -rf "$d"; done
rm -rf processor* postProcessing log.*
touch "$(basename "$C").foam"
# 입력 지문 — rom/calibrate.py 가 로그를 읽기 전에 지금 사전과 같은지 대조한다.
# (사전만 고치고 다시 풀지 않은 로그로 보정하는 일을 막는다.)
INPUTS="$(md5sum 0/* constant/g constant/thermophysicalProperties constant/turbulenceProperties \
          system/* constant/polyMesh/{points,faces,owner,neighbour,boundary})" || exit 1
topoSet > log.topoSet 2>&1 \
  && decomposePar -force > log.decompose 2>&1 \
  && mpirun -np $NP $APP -parallel > log.solver 2>&1 \
  && reconstructPar > log.reconstruct 2>&1
RC=$?
[ $RC = 0 ] && echo "$INPUTS" > log.inputs.md5
rm -rf processor*
LAST=$(ls | grep -E '^[0-9]+(\.[0-9]+)?$' | sort -g | tail -1)
[ $RC = 0 ] && echo "$(basename $(dirname "$C"))/$(basename "$C")  $APP ×$NP  완료 (마지막 시각 $LAST)" \
            || echo "$(basename $(dirname "$C"))/$(basename "$C")  ★ 실패 rc=$RC (로그 $C/log.*)"
exit $RC
