#!/bin/bash
# 비정상 냉시동 계산의 병렬 분할 재현판 (결정 K22, E-05·E-14).
# cases/{A_horizontal_unstepped,B_horizontal_stepped,C_vertical_stepped} 와 설정이 같고 분할 수(decomposeParDict)만 다르다.
# C 는 1,000 ℃ 면이 나아갔다 물러났다 하여 시각별 값이 분할에 따라 갈린다 — 그래서 여러 판의 범위를 쓴다.
# 세 형식 모두 같은 분할 수(4·8·10)로 푼다. 본계산(6 분할)과 합쳐 cfd/post/penetration_max.py 가
# 형식별 '45 s 까지 최대 거리'의 범위를 낸다.
#   bash cfd/run_transient_np.sh        (약 1시간 40분: 동시 프로세스가 20 을 넘지 않게 네 묶음)
# 출력: Results/cfd/np/<형식>_np<N>/ (케이스), Results/cfd/np/flame_penetration_np.csv
# 물리 코어가 10 개라 10 분할이 최대다 (12 분할은 MPI 가 띄우지 않는다).
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$ROOT/paths.sh"
OUT="$ROOT/Results/cfd/np"
mkdir -p "$OUT"

prep() {  # prep <형식> <분할 수>
  local SRC="$(kiln_case transient $1)" DST="$OUT/$1_np$2"
  [ -e "$DST" ] && { echo "$DST 가 이미 있다 — 지우고 다시 실행할 것"; exit 1; }
  mkdir -p "$DST"
  cp -r "$SRC/0" "$SRC/constant" "$SRC/system" "$DST/"
  rm -rf "$DST/constant/polyMesh/sets"
  sed -i "s/^numberOfSubdomains .*/numberOfSubdomains $2;/" "$DST/system/decomposeParDict"
}
batch() {  # batch "<형식>:<분할>" ...
  local PIDS="" FAIL=0 J
  for J in "$@"; do prep "${J%%:*}" "${J##*:}"; done
  for J in "$@"; do bash "$HERE/run_case.sh" "$OUT/${J%%:*}_np${J##*:}" & PIDS="$PIDS $!"; done
  for P in $PIDS; do wait $P || FAIL=1; done
  return $FAIL
}
batch A:4 B:4 C:4 || exit 1
batch A:8 B:8 || exit 1
batch C:8 A:10 || exit 1
batch B:10 C:10 || exit 1

CASES=""
for N in 4 8 10; do for M in A B C; do CASES="$CASES${CASES:+,}${M}_np$N=$OUT/${M}_np$N"; done; done
KILN_PEN_CASES="$CASES" KILN_PEN_OUT="$OUT/flame_penetration_np.csv" \
  "$KILN_PVBATCH" "$HERE/post/flame_penetration.py"
