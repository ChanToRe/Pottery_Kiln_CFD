#!/bin/bash
# 정상상태 보정 계산 (buoyantSimpleFoam, 150 kW, 화구 완전개방, 외기 19.3 ℃).
# 축소모델의 A_hot·h_conv_ref 출처다 (rom/calibrate.py 가 log.solver 를 읽는다).
# 세 형식을 동시에 돌린다 (각 4코어). 투고본: 형식당 약 13분.
#   bash cfd/run_steady.sh [A_L065 B_L065 C_L065]
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../paths.sh"
MODELS=${*:-"A_L065 B_L065 C_L065"}
PIDS=""
for M in $MODELS; do
  bash "$HERE/run_case.sh" "$(kiln_case steady $M)" & PIDS="$PIDS $!"
done
FAIL=0
for P in $PIDS; do wait $P || FAIL=1; done
exit $FAIL
