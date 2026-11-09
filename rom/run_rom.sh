#!/bin/bash
# 축소모델 전 분석. 보정은 정상상태 CFD 로그(cases/*_steady/log.solver)를 읽는다.
# 정상 CFD 를 다시 풀지 않았으면 Results/logs/cases/*_steady/log.solver.xz (보관본)를 읽는다.
#
#   bash rom/run_rom.sh            (약 1시간 반, 3단계는 병렬)
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
OUT=../Results/rom
mkdir -p $OUT
set -o pipefail

echo "=== 1. 정상상태 CFD → 보정값"
python3 calibrate.py | tee $OUT/calibration.txt || exit 1

echo "=== 2. φ 역산 (rom_phi.csv — 이후 모든 분석의 입력)"
python3 run.py > $OUT/run.log 2>&1 || { tail -20 $OUT/run.log; exit 1; }
cat $OUT/rom_phi.csv

echo "=== 3. 비교 분석 (병렬)"
declare -A JOBS=(
  [study_data]="python3 study_data.py"
  [efficiency]="python3 efficiency.py"
  [efficiency_sens]="python3 efficiency.py --sens"
  [form_axial]="python3 form_axial.py"
  [length_axial_ware]="env TAG=_ware python3 length_axial.py"
  [length_axial_empty]="env TAG=_empty LOAD_FRAC=0 BLOCK_FRAC=0 python3 length_axial.py"
  [h_sensitivity]="python3 h_sensitivity.py"
)
declare -A PID
for j in "${!JOBS[@]}"; do
  ${JOBS[$j]} > $OUT/log_$j.txt 2>&1 &
  PID[$j]=$!
done
FAIL=0
for j in "${!JOBS[@]}"; do
  if wait ${PID[$j]}; then echo "  $j 완료"; else echo "  ★ $j 실패 — $OUT/log_$j.txt"; FAIL=1; fi
done
[ $FAIL = 0 ] || exit 1
echo "=== 4. 민감도 27 경우 (S4 Table) → 에너지 수지 (S8) → 값의 구분 (S1)"
python3 sensitivity.py > $OUT/log_sensitivity.txt 2>&1 || { echo "  ★ sensitivity 실패 — $OUT/log_sensitivity.txt"; exit 1; }
echo "  sensitivity 완료"
python3 energy_audit.py > $OUT/log_energy_audit.txt 2>&1 || { echo "  ★ energy_audit 실패"; exit 1; }
echo "  energy_audit 완료"
python3 value_classes.py > $OUT/log_value_classes.txt 2>&1 || { echo "  ★ value_classes 실패"; exit 1; }
echo "  value_classes 완료"
