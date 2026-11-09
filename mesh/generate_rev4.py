"""
rev4 STL 생성기 (원 파일명 mesh/build_rev4.py). numpy 가 필요하다.

    env/kiln/bin/python mesh/generate_rev4.py [출력디렉터리]

3 형식(A·B·C) × 소성부 4 길이(2.5·4.5·6.5·8.5 m) = 12 기를 <출력>/stl/ 에 쓰고
설계표 <출력>/design_matrix.csv 를 남긴다. 기본 출력은 Results/geometry/rev4.
무엇을 mesh/stl/ 로 옮겨 쓰는지는 mesh/stl_manifest.csv 가 정한다.
"""
import os, sys, csv
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rev4_builder import build, finalize, TYPES
from rev4_common import check_watertight, write_stl, signed_volume
OUT = (sys.argv[1] if len(sys.argv) > 1 else
       os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Results", "geometry", "rev4"))
os.makedirs(f"{OUT}/stl", exist_ok=True)
LENS=[2.5,4.5,6.5,8.5]
rows,cache=[],{}
for t,(hs,hd,lab) in TYPES.items():
    for Lf in LENS:
        nm=f"{t}_L{int(Lf*10):03d}"
        r=build(hs,hd,Lf); w,i_,o=finalize(r)
        chk=check_watertight(w,i_,o); vol=abs(signed_volume(np.vstack([w,i_,o])))
        ar=lambda x:.5*np.linalg.norm(np.cross(x[:,1]-x[:,0],x[:,2]-x[:,0]),axis=1).sum()
        write_stl(f"{OUT}/stl/kiln_{nm}.stl",{"walls":w,"inlet":i_,"outlet":o})
        R=r['rings']
        rows.append(dict(model=nm,type=t,label=lab,h_step_m=hs,h_drop_m=hd,L_fire_m=Lf,
            L_total_m=round(float(R[:,:,0].max()-R[:,:,0].min()),2),
            stack_height_m=round(float(R[-1][:,2].mean()-R[0][:,2].mean()),2),
            volume_m3=round(float(vol),3), wetted_area_m2=round(float(ar(w)),2),
            A_inlet_m2=round(float(ar(i_)),4), A_outlet_m2=round(float(ar(o)),4),
            AV_ratio=round(float(ar(w)/vol),3), max_hR=round(r['hR'],3),
            open_edges=chk['open_edges'], tris=chk['n_tri']))
        cache[nm]=dict(rings=R,P=r['P'],W=r['W'],H=r['H'],s=r['s'],
                       sfb=r['sfb'],s0=r['s0'],s1=r['s1'])
with open(f"{OUT}/design_matrix.csv","w",newline="") as f:
    wr=csv.DictWriter(f,fieldnames=list(rows[0].keys())); wr.writeheader(); wr.writerows(rows)
print("불량:",sum(1 for r in rows if r['open_edges'] or r['max_hR']>0.75))
print(f"{'model':10s}{'단':>6s}{'낙차':>6s}{'Lf':>6s}{'총장':>7s}{'연돌고':>7s}{'용적':>8s}{'A/V':>7s}{'h/R':>7s}{'openE':>7s}")
for r in rows:
    print(f"{r['model']:10s}{r['h_step_m']:6.2f}{r['h_drop_m']:6.2f}{r['L_fire_m']:6.1f}"
          f"{r['L_total_m']:7.2f}{r['stack_height_m']:7.2f}{r['volume_m3']:8.2f}"
          f"{r['AV_ratio']:7.2f}{r['max_hR']:7.3f}{r['open_edges']:7d}")
# 기하 검증
print("\n[검증] 모델      화구바닥  연소부바닥  소성부기점   실측낙차  실측단차")
for t in TYPES:
    d=cache[f"{t}_L065"]; R=d['rings']; s=d['s']; flo=R[:,64+8,2]
    a=np.searchsorted(s,d['sfb']); b=np.searchsorted(s,d['s0'])
    print(f"        {t}      {flo[2]:8.3f} {flo[a+2]:10.3f} {flo[b+2]:11.3f}"
          f"{flo[a-2]-flo[a+2]:11.3f}{flo[b+2]-flo[b-2]:10.3f}")
