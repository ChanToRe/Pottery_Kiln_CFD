#!/bin/bash
# 원고 그림의 낱장을 만든다. 배치·제목·글자 삽입은 사용자가 한다.
#   Fig 1·3·5  형상 3D       ← mesh/stl              (ParaView)
#   Fig 2      CFD 온도장    ← cases/<형식>         (ParaView + 축)
#   Fig 4·6    축소모델 단면 ← rom (rom_phi.csv)     (순수 Python)
#   Fig 7·8    그래프        ← Results/rom, Results/cfd (R)  (Fig 9 는 결정 K8 로 뺐다)
#   종단면도   개념도        ← mesh/kiln_geometry.py (R, 수정본 새 그림 — graphs 단계에서)
#
#   bash Rscripts/make_figures.sh [geometry|cfd|rom|graphs]   (인자 없으면 전부)
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../paths.sh"
cd "$KILN_ROOT"
OUT=Results/figures
mkdir -p $OUT/graphs
WHAT=${1:-all}
FAIL=0

pv() {  # X 연결이 간헐적으로 끊겨 렌더가 죽는 일이 있어 세 번까지 다시 한다
  for try in 1 2 3; do "$KILN_PVBATCH" "$@" && return 0; echo "  (pvbatch 재시도 $try)"; sleep 3; done
  return 1
}

if [ $WHAT = all ] || [ $WHAT = geometry ]; then
  echo "=== Fig 1·3·5 형상 낱장"
  # 그림마다 카메라 기준(ANCHOR)·축척·크기가 다르다 (투고본 낱장과 바이트 단위로 같은 설정)
  : > $OUT/log_geometry.txt
  ONLY=forms  ANCHOR=kiln_A_L065 SCALE=0.37 VIEW=1600,1120 pv mesh/render_geometry_panels.py >> $OUT/log_geometry.txt 2>&1 || { echo "  ★ Fig 1 실패"; FAIL=1; }
  ONLY=length ANCHOR=kiln_B_L085 SCALE=0.40 VIEW=1250,1120 pv mesh/render_geometry_panels.py >> $OUT/log_geometry.txt 2>&1 || { echo "  ★ Fig 3 실패"; FAIL=1; }
  ONLY=steps  ANCHOR=kiln_B_L065 SCALE=0.37 VIEW=1600,1120 pv mesh/render_geometry_panels.py >> $OUT/log_geometry.txt 2>&1 || { echo "  ★ Fig 5 실패"; FAIL=1; }
fi

# 수정본 낱장 설정 (2-3b, E-26·R-08, 결정 K29·K30). 투고본 설정은 git 태그 '투고본'.
#   글자: 투고본처럼 배치해 가로 7.5 in 로 실을 때 약 8.5 pt — 낱장 그림 폭이 칸 하나(Fig 2 약 2.0 in,
#         Fig 4·6 약 1.5 in)가 된다고 보고 TEXT_SIZE = 8.5/72 × (낱장 그림 폭 px / 칸 폭 in).
#   축:   바깥 칸에만 (OUTER_AXES=1 — 왼쪽 열 세로축, 아래 행 가로축). 축선 3 px.
#   색표: Fig 2·4·6 공통 하나 — ParaView Jet 0–1,200 ℃ (Results/figures/colorbar_0-1200C.png).
#   구간 숫자: Fig 4·6 칸에서 빼고 segments.csv → 선그래프 (Rscripts/Fig_Segments.R).
if [ $WHAT = all ] || [ $WHAT = cfd ]; then
  echo "=== Fig 2 CFD 온도장 낱장 (9·17·26·34·43 s, 1,000 ℃ 등온선)"
  rm -rf $OUT/fig2_cfd_panels
  TIMES=9,17,26,34,43 ISO=1000 NO_CBAR=1 \
    pv cfd/post/render_panels.py $OUT/fig2_cfd_panels > $OUT/log_fig2.txt 2>&1 || { echo "  ★ 실패"; FAIL=1; }
  OUTER_AXES=1 COLS=A,B,C TEXT_SIZE=52 AX_LW=3 TICK_LEN=16 XTICK_N=6 ZTICK_N=3 \
    python3 cfd/post/panel_axes.py $OUT/fig2_cfd_panels >> $OUT/log_fig2.txt 2>&1 || { echo "  ★ 축 실패"; FAIL=1; }
fi

if [ $WHAT = all ] || [ $WHAT = rom ]; then
  echo "=== Fig 4 소성실 길이 낱장 (47–78 h 5등분) + 공통 색표"
  ( cd rom && PALETTE=jet OUTER_AXES=1 TEXT_SIZE=71 AX_LW=3 TICK_LEN=18 XTICK_N=4 ZTICK_N=3 SEG_TEXT=0 T_FROM=47 \
      CBAR_OUT=../$OUT/colorbar_0-1200C.png CBAR_TS=64 CBAR_W=80 CBAR_H=2000 \
      python3 panels_length.py ../$OUT/fig4_length_panels ) > $OUT/log_fig4.txt 2>&1 || { echo "  ★ 실패"; FAIL=1; }
  echo "=== Fig 6 소성실 계단 낱장"
  ( cd rom && PALETTE=jet OUTER_AXES=1 TEXT_SIZE=59 AX_LW=3 TICK_LEN=16 XTICK_N=4 ZTICK_N=3 SEG_TEXT=0 NO_CBAR=1 \
      CACHE_TAG=_step T_FROM=47 MODELS=B_L065,B_L065_S6,B_L065_S12,B_L065_S20 TAGS=S00,S06,S12,S20 \
      python3 panels_length.py ../$OUT/fig6_steps_panels ) > $OUT/log_fig6.txt 2>&1 || { echo "  ★ 실패"; FAIL=1; }
fi

if [ $WHAT = all ] || [ $WHAT = graphs ]; then
  echo "=== Fig 7·8 그래프 (자료: Data/Kiln_*.csv ← Rscripts/make_graph_data.py)"
  python3 Rscripts/make_graph_data.py || FAIL=1
  # R 은 글꼴을 이름("Times New Roman")으로 fontconfig 에서 찾는다. 이 폴더의
  # fonts/times.ttf 를 먼저 보도록 설정 파일을 만들어 준다 (없으면 다른 서체로
  # 조용히 바뀌므로 확인까지 한다).
  cat > $OUT/graphs/fonts.conf <<EOF_FC
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <dir>$KILN_ROOT/fonts</dir>
  <cachedir prefix="xdg">fontconfig</cachedir>
  <include ignore_missing="yes">$KILN_ROOT/env/kiln/etc/fonts/fonts.conf</include>
</fontconfig>
EOF_FC
  export FONTCONFIG_FILE=$KILN_ROOT/$OUT/graphs/fonts.conf
  # 이름만 보면 다른 판의 Times New Roman(예: 시스템에 깔린 더 새 판)이 잡혀도 통과하므로
  # 실제로 잡힌 글꼴 파일이 이 폴더의 fonts/times.ttf 인지 확인한다.
  # Times New Roman 은 상용 글꼴이라 저장소에 넣지 않았다. fonts/times.ttf 를 직접 두면 그것을 쓰고,
  # 없으면 fontconfig 가 고르는 다른 서체로 그린다 (수치는 같고 글꼴만 다르다).
  FCM="$(dirname "$KILN_RSCRIPT")/fc-match"
  if [ ! -f "$KILN_ROOT/fonts/times.ttf" ]; then
    echo "  (주의) fonts/times.ttf 가 없어 R 그래프의 글꼴이 Times New Roman 이 아니다 — README 'Fonts' 참고"
  elif [ -x "$FCM" ]; then
    got=$("$FCM" -f '%{file}' "Times New Roman")
    [ "$(readlink -f "$got")" = "$(readlink -f "$KILN_ROOT/fonts/times.ttf")" ] ||
      { echo "  ★ R 글꼴: fonts/times.ttf 대신 '$got' 이 잡힌다"; FAIL=1; }
  else
    echo "  ★ fc-match 가 없어 R 글꼴을 확인하지 못했다: $FCM"; FAIL=1
  fi
  # Fig 9(계단, Fig_Steps.R)는 원고에서 뺐다 (결정 K8) — 투고본 재현은 git 태그 '투고본'.
  for f in Fig_Form Fig_Length Fig_Segments; do
    "$KILN_RSCRIPT" Rscripts/$f.R > $OUT/graphs/log_$f.txt 2>&1 && echo "  $f 완료" || { echo "  ★ $f 실패"; FAIL=1; }
  done
  echo "=== 종단면 개념도 (2-3a, E-25·R-02) — 형식 B 중심면 + 연소부 A·B·C 확대"
  python3 mesh/section_data.py > $OUT/section_data.txt 2>&1 || { echo "  ★ 단면 자료 실패"; FAIL=1; }
  "$KILN_RSCRIPT" Rscripts/Fig_Section.R > $OUT/graphs/log_Fig_Section.txt 2>&1 && echo "  Fig_Section 완료" || { echo "  ★ Fig_Section 실패"; FAIL=1; }
  echo "=== 중부지역 백제 한성기 토기 가마 전체 길이 (답변서 Fig R1) ← Data/yun2024_table2_kilns.csv"
  "$KILN_RSCRIPT" Rscripts/Fig_KilnLength.R > $OUT/graphs/log_Fig_KilnLength.txt 2>&1 && echo "  Fig_KilnLength 완료" || { echo "  ★ Fig_KilnLength 실패"; FAIL=1; }
fi
exit $FAIL
