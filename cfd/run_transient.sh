#!/bin/bash
# 비정상 냉시동 계산 (buoyantPimpleFoam, 163.3 kW, 유량 0.10 kg/s, 19.3 ℃, 45 s).
# 1,000 ℃ 면 침투(원고 Fig 2·7b)의 출처다.
# 세 형식을 동시에 돌린다 (각 6코어). 투고본: A 약 13분, B·C 약 6분.
#   bash cfd/run_transient.sh [A_L065 B_L065 C_L065]
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../paths.sh"
MODELS=${*:-"A_L065 B_L065 C_L065"}
PIDS=""
for M in $MODELS; do
  bash "$HERE/run_case.sh" "$(kiln_case transient $M)" & PIDS="$PIDS $!"
done
FAIL=0
for P in $PIDS; do wait $P || FAIL=1; done
exit $FAIL
