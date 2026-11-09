#!/bin/bash
# 투고본 계산에 쓴 STL 을 생성기로 다시 만들고 mesh/stl/ 과 대조한다.
# mesh/stl/ 은 덮어쓰지 않는다 (재현 확인용). 결과는 Results/geometry/.
#
#   bash mesh/make_stl.sh
set -eo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../paths.sh"
echo "=== 계산에 쓴 STL 풀기: mesh/*.stl.gz → mesh/stl/"
mkdir -p "$HERE/stl"
for z in "$HERE"/*.stl.gz; do gunzip -c "$z" > "$HERE/stl/$(basename "$z" .gz)"; done
ls "$HERE/stl" | wc -l
BUILD="$KILN_ROOT/Results/geometry"
rm -rf "$BUILD"
mkdir -p "$BUILD/rev4"

echo "=== rev4 생성기 (numpy) — 12기"
"$KILN_PY" "$HERE/generate_rev4.py" "$BUILD/rev4" > "$BUILD/rev4/log.txt"
sed -n '1p;/검증/,$p' "$BUILD/rev4/log.txt"      # 불량 개수와 기하 검증표

echo "=== 순수 Python 생성기 — B_L065 와 계단 3종"
for n in 0 6 12 20; do
  python3 "$HERE/kiln_geometry.py" B 6.5 $n "$BUILD/pure"
done

echo "=== mesh/stl/ 과 대조"
python3 "$HERE/verify_stl.py"
