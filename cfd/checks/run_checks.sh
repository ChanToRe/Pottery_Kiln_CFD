#!/bin/bash
# 2-2 CFD 검증 계산 (2-2a 격자, 2-2b C 시간 간격, 2-2d 조업점) — 케이스를 만들고 대기열로 푼다.
#   bash cfd/checks/run_checks.sh [budget]      (기본 16 프로세스)
# 케이스: Results/checks/{grid,courant,oppoint}. 정리는 cfd/checks/summarize_checks.py.
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BUDGET=${1:-16}
R=$ROOT/Results/checks
python3 "$HERE/setup_checks.py" grid courant oppoint || exit 1
python3 "$HERE/case_queue.py" "$BUDGET" \
  $R/grid/transient/A_L065 $R/grid/transient/B_L065 $R/grid/transient/C_L065 \
  $R/courant/A_co2 $R/courant/B_co2 $R/courant/C_co2 \
  $R/grid/steady/A_L065 $R/grid/steady/B_L065 $R/grid/steady/C_L065 \
  $R/oppoint/{A,B,C}_L065_q449 $R/oppoint/{A,B,C}_L065_q245 $R/oppoint/{A,B,C}_L065_q082
