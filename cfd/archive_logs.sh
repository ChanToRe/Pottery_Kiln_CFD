#!/bin/bash
# 계산 로그를 Results/logs/ 에 xz 로 압축해 보관한다 (저장소에 올리는 기록).
#   bash cfd/archive_logs.sh
# 대상: 격자(mesh/<M>/log.*), 기본 케이스(cases/*/log.*), 병렬 분할 재현판(Results/cfd/np/*/log.*),
#       수치 점검(Results/checks/**/log.*). 경로는 원래 자리를 따른다 (cfd/cases.py 의 archived()):
#   cases/A_horizontal_unstepped/log.solver      → Results/logs/cases/A_horizontal_unstepped/log.solver.xz
#   Results/checks/grid/steady/A_L065/log.solver → Results/logs/checks/grid/steady/A_L065/log.solver.xz
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../paths.sh"
cd "$KILN_ROOT"
N=0
while IFS= read -r -d '' f; do
  rel=${f#./}; rel=${rel#Results/}
  dst="Results/logs/$rel.xz"
  mkdir -p "$(dirname "$dst")"
  xz -T0 -9 -c "$f" > "$dst"
  N=$((N + 1))
done < <(find ./mesh ./cases ./Results/cfd ./Results/checks -path ./Results/logs -prune -o \
              -type f -name 'log.*' -print0 2>/dev/null)
echo "로그 $N 개 → Results/logs ($(du -sh Results/logs | cut -f1))"
