#!/bin/bash
# 형식별 CFD 격자를 만든다: blockMesh → snappyHexMesh (직렬) → checkMesh.
# 만든 constant/polyMesh 를 정상(steady)·비정상(transient) 케이스에 복사한다.
# 두 계산은 같은 격자를 쓴다 (투고본도 그랬다 — points md5 동일).
#
#   bash mesh/make_mesh.sh [A_L065 B_L065 C_L065]   (STL 은 mesh/make_stl.sh 가 mesh/stl/ 에 푼다)
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../paths.sh"
kiln_openfoam || exit 1
MODELS=${*:-"A_L065 B_L065 C_L065"}

stl_of() {   # 형식별 격자 STL (mesh/stl_manifest.csv)
  case $1 in
    B_L065) echo "$KILN_ROOT/mesh/stl/kiln_B_L065_cfd.stl" ;;
    *)      echo "$KILN_ROOT/mesh/stl/kiln_$1.stl" ;;
  esac
}

FAIL=0
for M in $MODELS; do
  C=$HERE/$M
  ( cd "$C" || exit 1
    rm -rf constant/polyMesh constant/triSurface log.* [1-9]*
    mkdir -p constant/triSurface
    cp "$(stl_of $M)" constant/triSurface/kiln.stl
    blockMesh > log.blockMesh 2>&1 || { echo "$M blockMesh 실패"; exit 1; }
    snappyHexMesh -overwrite > log.snappyHexMesh 2>&1 || { echo "$M snappyHexMesh 실패"; exit 1; }
    checkMesh > log.checkMesh 2>&1 )
  [ $? = 0 ] || { FAIL=1; continue; }
  NC=$(grep -m1 -oP 'nCells:\s*\K[0-9]+' "$C/constant/polyMesh/owner")
  MD=$(md5sum "$C/constant/polyMesh/points" | cut -c1-8)
  REF=$(grep "^$M " "$HERE/mesh_reference.txt")
  if [ "$REF" = "$M $NC $MD" ]; then OK="투고본 격자와 동일"; else OK="★ 투고본과 다름 (기준: $REF)"; FAIL=1; fi
  echo "$M  셀 $NC  points md5 $MD  — $OK"
  for kind in steady transient; do
    D=$(kiln_case $kind $M)
    rm -rf "$D/constant/polyMesh" "$D/constant/triSurface"
    cp -r "$C/constant/polyMesh" "$D/constant/polyMesh"
  done
done
exit $FAIL
