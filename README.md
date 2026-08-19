# 토기가마 형태의 전산유체 해석

*Computational fluid dynamics analysis of pottery kiln morphology: a case study
from Hanseong-period Baekje, Korea* 의 계산을 재현하기 위한 최소 구성이다. 계산은 두 모델로 나뉜다. 초 단위의 3차원 유동 계산이 데워진 기체가 소성실에 이르는 경로와 온도를 계산하고, 조업 전체를 다루는 축소모델은 전자의 대류 열전달계수와 유효 고온면적을 받아 조업 전반 규모의 연료소모량과 온도를 계산한다.

## 구성

    - `mesh/kiln_gen_pure.py` : 가마 형상 생성
    - `cases/` : OpenFOAM 케이스
    - `CFD/make_cases.py` : 형상 STL 파일을 기반으로 케이스를 생성
    - `CFD/flame_penetration.py` : 1,000°C 면의 소성실 침투 깊이 측정
    - `ROM/` : 축소모델과 스크립트 일괄

## 준비물

    - `OpenFOAM(v2312)`
    - `Python3`
    - `ParaView`

## 재현

### 1. 형상 생성

``` bash
python3 mesh/kiln_gen_pure.py
```

### 2. 케이스 생성

- `cases/` 에 든 것은 실제로 쓴 사용한 딕셔너리이며, `make_cases.py` 를 통해 같은 것을 생성할 수 있음
``` bash
    python3 cfd/make_cases.py
    cd cases/A_horizontal_unstepped
    blockMesh && snappyHexMesh -overwrite && buoyantPimpleFoam
```

### 3. 침투 깊이 측정

``` bash
    pvbatch cfd/flame_penetration.py
```

### 4. 축소모델 실행
- 각 스크립트는 논문의 표 하나에 대응함
- 축소모델은 양산 호계동 2호 실험의 승온곡선을 재현하는데 필요한 연료 투입률을 되풀이해 계산함(`rom/calibrate.py`)

``` bash
    python3 /efficiency.py        #형식별 연료
    python3 rom/form_axial.py        #형식별 축방향 온도
    python3 rom/length_study.py      #길이별 연료·온도차
    python3 rom/study_data.py        ##가정값 민감도
    python3 rom/ware_sensitivity.py  #적재 열용량 민감도
```

### ParaView로 확인

- 케이스 안에 빈 `.foam` 파일을 두면 ParaView가 인식
``` bash
    touch cases/A_horizontal_unstepped/case.foam
```

- ParaView는 기본값으로 다면체 셀을 쪼개서 수를 파악함으로 **117,649** 셀로 나오지만, 실제 격자는 **52,755** 셀이다. 리더의 `Decompose polyhedra`를 끄면 일치하는 결과를 확인할 수 있다. 본문에 서술된 5.3–5.6 × 10⁴ 는 후자에 해당한다.