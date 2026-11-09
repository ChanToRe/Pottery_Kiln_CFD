#!/usr/bin/env python3
"""
PNG 을 JPEG·TIFF 로 바꾼다. 투고용으로 둘 다 필요하다.

    /opt/paraviewopenfoam510/bin/pvbatch Rscripts/png2jpg_tif.py <출력디렉터리> <png...>

이 환경에는 ImageMagick 도 PIL 도 없다. ParaView 가 싣고 오는 VTK 의
이미지 리더·라이터를 쓴다.

  JPEG  품질 95. 원고 검토·미리보기용.
  TIFF  Deflate 무손실 압축.
        (이 VTK 빌드는 LZW 가 특허 문제로 꺼져 있다 — Deflate 로 대신한다.)

해상도 정보 (E-26, R-08)
  VTK 의 TIFF 라이터는 해상도를 늘 10 픽셀/cm(약 25 dpi)로 적는다. 투고본 Fig 1–6 이 그래서
  가로 4,940 px 인데도 약 5 m 폭의 그림으로 읽혔다. 이제 쓴 뒤에 TIFF 의 XResolution·
  YResolution·ResolutionUnit 과 JPEG(JFIF) 의 밀도를 dpi 로 고쳐 적는다. 화소는 바꾸지 않는다.

    WIDTH_IN=7.5   (기본) 이 폭[in]이 되도록 dpi = 가로 화소 / WIDTH_IN 으로 적는다.
                   PLOS ONE 그림 규격: 폭 2.63–7.5 in, 300–600 dpi.
                   600 dpi 를 넘으면(화소가 7.5 in × 600 보다 많으면) 가로 WIDTH_IN × 600 화소로 줄인다.
                   300 dpi 에 못 미치면 경고만 한다(화소를 늘리지 않는다).
    DPI=600        이 값을 그대로 적는다(WIDTH_IN 무시, 크기 조정 없음).
"""
import os
import struct
import sys

import vtk

QUALITY = int(os.environ.get("JPEG_QUALITY", "95"))
DPI_MAX, DPI_MIN = 600.0, 300.0


def tiff_set_dpi(path, dpi):
    """TIFF 첫 IFD 의 해상도 태그(282·283 RATIONAL, 296 SHORT)를 제자리에서 고친다."""
    with open(path, "r+b") as f:
        b = f.read()
        e = "<" if b[:2] == b"II" else ">"
        off = struct.unpack(e + "I", b[4:8])[0]
        n = struct.unpack(e + "H", b[off:off + 2])[0]
        found = set()
        for i in range(n):
            p = off + 2 + 12 * i
            tag, typ, cnt = struct.unpack(e + "HHI", b[p:p + 8])
            if tag in (282, 283) and typ == 5:
                vo = struct.unpack(e + "I", b[p + 8:p + 12])[0]
                f.seek(vo)
                f.write(struct.pack(e + "II", int(round(dpi * 100)), 100))
                found.add(tag)
            elif tag == 296 and typ == 3:
                f.seek(p + 8)
                f.write(struct.pack(e + "H", 2) + b"\0\0")       # 2 = inch
                found.add(tag)
    if found != {282, 283, 296}:
        raise RuntimeError("%s: 해상도 태그를 찾지 못했다 %s" % (path, sorted(found)))


def jpeg_set_dpi(path, dpi):
    """JFIF APP0 의 밀도 단위·값을 dpi 로 고친다."""
    with open(path, "r+b") as f:
        b = f.read(20)
        if b[:4] != b"\xff\xd8\xff\xe0" or b[6:11] != b"JFIF\0":
            raise RuntimeError("%s: JFIF 머리가 아니다" % path)
        d = int(round(dpi))
        f.seek(13)
        f.write(struct.pack(">BHH", 1, d, d))                   # 1 = dots per inch


def convert(src, outdir):
    base = os.path.splitext(os.path.basename(src))[0]
    r = vtk.vtkPNGReader()
    r.SetFileName(src)
    r.Update()
    w = r.GetOutput().GetDimensions()[0]
    port = r.GetOutputPort()
    note = ""
    if os.environ.get("DPI"):
        dpi = float(os.environ["DPI"])
    else:
        width_in = float(os.environ.get("WIDTH_IN", "7.5"))
        dpi = w / width_in
        if dpi > DPI_MAX:
            f = DPI_MAX * width_in / w
            z = vtk.vtkImageResize()
            z.SetInputConnection(port)
            z.SetResizeMethodToMagnificationFactors()
            z.SetMagnificationFactors(f, f, 1.0)
            z.InterpolateOn()
            z.Update()
            port = z.GetOutputPort()
            w2 = z.GetOutput().GetDimensions()[0]
            note = "  (가로 %d → %d px 로 줄임)" % (w, w2)
            w, dpi = w2, w2 / width_in
        elif dpi < DPI_MIN:
            note = "  ★ %.0f dpi — 폭 %.2f in 로는 300 dpi 에 못 미친다" % (dpi, width_in)

    j = vtk.vtkJPEGWriter()
    j.SetInputConnection(port)
    j.SetQuality(QUALITY)
    j.ProgressiveOff()
    jp = os.path.join(outdir, base + ".jpg")
    j.SetFileName(jp)
    j.Write()
    jpeg_set_dpi(jp, dpi)

    t = vtk.vtkTIFFWriter()
    t.SetInputConnection(port)
    t.SetCompressionToDeflate()
    tp = os.path.join(outdir, base + ".tif")
    t.SetFileName(tp)
    t.Write()
    tiff_set_dpi(tp, dpi)

    return jp, tp, dpi, w, note


def main():
    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)
    for src in sys.argv[2:]:
        if not os.path.exists(src):
            print("  없음:", src)
            continue
        jp, tp, dpi, w, note = convert(src, outdir)
        print("  %-34s → %.1f MB (jpg) / %.1f MB (tif), %.0f dpi, 폭 %.2f in%s"
              % (os.path.basename(src), os.path.getsize(jp) / 1e6, os.path.getsize(tp) / 1e6,
                 dpi, w / dpi, note))


if __name__ == "__main__":
    main()
