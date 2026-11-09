# 원고 그림 Fig 1–10 을 한 장씩 합친 판 (PLOS: 가로 7.5 in 이하, 세로 8.75 in 이하, 600 dpi, Times).
#   env/kiln/bin/Rscript Rscripts/assemble_figures.R      (Rscripts/make_figures.sh graphs 가 부른다)
#   → Results/figures/assembled/FigN.tif (LZW) · FigN.jpeg (품질 95)
# 낱장은 Results/figures/ (make_figures.sh 가 만든 것)를 그대로 쓴다. R 이 TIFF 를 읽지 못하므로 R 로 그린 낱장
# (종단면·연소부 확대·구간 온도 선그래프)은 원래 스크립트를 저장 함수만 바꿔 다시 돌려 PNG 로 받는다(cache/).
# 낱장은 바깥 칸에만 축이 있어 왼쪽 열은 세로축만큼 넓고 아래 행은 가로축만큼 높다 — 크기 그대로 이어 붙인다.
# 컬러바는 낱장과 같은 ParaView Jet (rom/colormaps.py _JET), 0–1,200 ℃, 그림 아래에 가로로 그린다.
# 사용자 지시(2026-11-09) '조각낸 도면들 합쳐진 버전 tif 파일도 제공'. 배치는 투고본 그림을 따른다
# (열 제목·가로줄·행 제목).
suppressMessages({library(grid); library(png); library(here)})

FONT <- "Times New Roman"
R <- here("Results/figures")
OUT <- file.path(R, "assembled"); CACHE <- file.path(OUT, "cache")
dir.create(CACHE, showWarnings = FALSE, recursive = TRUE)
PT <- 9                                    # 제목 글자 [pt]
W <- 7.5                                   # 그림 폭 [in]

# ── R 낱장의 PNG 판 ──────────────────────────────────────────
local({
    e <- new.env()
    e$tiff <- function(filename, ..., compression = NULL) png(file.path(CACHE, sub("\\.tiff$", ".png", basename(filename))), ...)
    e$jpeg <- function(filename, ..., quality = NULL) png(tempfile(fileext = ".png"), ...)   # JPEG 는 버린다
    sys.source(here("Rscripts/Fig_Section.R"), envir = e)
    e2 <- new.env()
    e2$ggsave <- function(filename, plot, ..., compression = NULL, quality = NULL) {
        if (grepl("\\.tiff$", filename))
            ggplot2::ggsave(file.path(CACHE, sub("\\.tiff$", ".png", basename(filename))), plot, ...)
    }
    sys.source(here("Rscripts/Fig_Segments.R"), envir = e2)
})
rd <- function(...) readPNG(file.path(...))

# ── 그리기 도구 ─────────────────────────────────────────────
txt <- function(label, x, y, just = "centre", size = PT, ...)
    grid.text(label, x = unit(x, "in"), y = unit(y, "in"), just = just,
              gp = gpar(fontfamily = FONT, fontsize = size, lineheight = 1.0, ...))
img <- function(a, x, y, w, h)              # (x, y) = 왼쪽 위 [in]
    grid.draw(rasterGrob(a, x = unit(x, "in"), y = unit(y, "in"), width = unit(w, "in"), height = unit(h, "in"),
                         just = c("left", "top"), interpolate = TRUE))
hline <- function(x0, x1, y) grid.lines(unit(c(x0, x1), "in"), unit(c(y, y), "in"), gp = gpar(lwd = 0.6, col = "grey40"))

JET <- list(c(0, 0, 0, 0.5625), c(0.111111, 0, 0, 1), c(0.36508, 0, 1, 1), c(0.492063, 0.5, 1, 0.5),
            c(0.619047, 1, 1, 0), c(0.873016, 1, 0, 0), c(1, 0.5, 0, 0))
jet <- function(f) {
    s <- do.call(rbind, JET)
    rgb(approx(s[, 1], s[, 2], f)$y, approx(s[, 1], s[, 3], f)$y, approx(s[, 1], s[, 4], f)$y)
}
colorbar <- function(xc, y, w = 3.6, h = 0.13) {   # y = 막대 위 [in]
    x0 <- xc - w / 2
    grid.draw(rasterGrob(matrix(jet(seq(0, 1, length.out = 600)), nrow = 1), x = unit(x0, "in"), y = unit(y, "in"),
                         width = unit(w, "in"), height = unit(h, "in"), just = c("left", "top"), interpolate = TRUE))
    grid.rect(unit(x0, "in"), unit(y, "in"), unit(w, "in"), unit(h, "in"), just = c("left", "top"),
              gp = gpar(fill = NA, lwd = 0.5))
    for (v in seq(0, 1200, 200)) {
        xv <- x0 + w * v / 1200
        grid.lines(unit(c(xv, xv), "in"), unit(c(y - h, y - h - 0.04), "in"), gp = gpar(lwd = 0.5))
        txt(format(v, big.mark = ","), xv, y - h - 0.10, size = 8)
    }
    txt("Temperature (°C)", x0 - 0.12, y - h / 2, just = "right", size = 8)
}

out <- function(name, h, fun) {
    tiff(file.path(OUT, paste0(name, ".tif")), width = W, height = h, units = "in", res = 600,
         compression = "lzw", type = "cairo", family = FONT); fun(h); invisible(dev.off())
    jpeg(file.path(OUT, paste0(name, ".jpeg")), width = W, height = h, units = "in", res = 600,
         quality = 95, type = "cairo", family = FONT); fun(h); invisible(dev.off())
    cat(sprintf("%-6s %.2f × %.2f in\n", name, W, h))
}

# 낱장 격자: cols × rows 이름 행렬, 각 열 폭·각 행 높이는 첫 행·첫 열의 실제 픽셀 크기
grid_panels <- function(dir, files, s, x0, ytop) {   # s = px/in
    a <- lapply(files, function(f) rd(dir, f)); dim(a) <- dim(files)
    cw <- sapply(seq_len(ncol(files)), function(j) dim(a[[1, j]])[2])
    rh <- sapply(seq_len(nrow(files)), function(i) dim(a[[i, 1]])[1])
    xs <- x0 + c(0, cumsum(cw))[seq_along(cw)] / s
    ys <- ytop - c(0, cumsum(rh))[seq_along(rh)] / s
    for (i in seq_along(rh)) for (j in seq_along(cw)) {
        p <- a[[i, j]]; img(p, xs[j], ys[i], dim(p)[2] / s, dim(p)[1] / s)
    }
    list(xs = xs, ys = ys, cw = cw / s, rh = rh / s, w = sum(cw) / s, h = sum(rh) / s,
         ax = (cw[1] - cw[min(2, length(cw))]) / s, top = rh[1] / s)  # ax = 왼쪽 열 세로축 폭
}

# 온도장 그림(Fig 3·6·8): 열 제목, 가로줄, 행 제목, 낱장, 컬러바 [, 아래 선그래프]
field_fig <- function(name, dir, cols, rows, heads, rlab, s, below = NULL, below_h = 0) {
    files <- outer(rows, cols, function(r, c) paste0(c, "_", r, ".png"))
    probe <- rd(dir, files[1, 1]); probe2 <- rd(dir, files[nrow(files), 1])
    cw <- sapply(cols, function(c) dim(rd(dir, paste0(c, "_", rows[1], ".png")))[2])
    gw <- sum(cw) / s; gh <- (dim(probe)[1] * (length(rows) - 1) + dim(probe2)[1]) / s
    lab <- 0.55; head <- 0.42; cb <- 0.55
    H <- head + gh + cb + below_h
    out(name, H, function(H) {
        x0 <- lab + (W - lab - gw) / 2
        g <- grid_panels(dir, files, s, x0, H - head)
        for (j in seq_along(cols)) {
            xc <- g$xs[j] + (if (j == 1) g$ax else 0) + (g$cw[j] - (if (j == 1) g$ax else 0)) / 2
            txt(heads[j], xc, H - 0.04, just = c("centre", "top"))
        }
        hline(x0 + g$ax * 0.6, x0 + g$w, H - head + 0.03)
        for (i in seq_along(rows)) txt(rlab[i], x0 - 0.05, g$ys[i] - g$top / 2, just = "right")
        colorbar(x0 + g$ax + (g$w - g$ax) / 2 + 0.45, H - head - gh - 0.12)
        if (!is.null(below)) {
            b <- rd(CACHE, below); bw <- W; bh <- bw * dim(b)[1] / dim(b)[2]
            img(b, 0, below_h, bw, bh)
        }
    })
}

# 3D 형상 그림(Fig 2·4·7): 한 줄, 열 제목
row_fig <- function(name, dir, files, heads, head = 0.42) {
    a <- lapply(files, function(f) rd(dir, f))
    tw <- sum(sapply(a, function(p) dim(p)[2])); s <- tw / W
    h <- max(sapply(a, function(p) dim(p)[1])) / s
    out(name, head + h, function(H) {
        x <- 0
        for (k in seq_along(a)) {
            p <- a[[k]]; w <- dim(p)[2] / s
            img(p, x, H - head, w, dim(p)[1] / s)
            txt(heads[k], x + w / 2, H - 0.04, just = c("centre", "top"))
            x <- x + w
        }
        hline(0.15, W - 0.15, H - head + 0.03)
    })
}

FORMS <- c("A\nHorizontal firebox, unstepped", "B\nHorizontal firebox, stepped", "C\nVertical firebox, stepped")
TH <- sprintf("%.1f h", c(53.2, 59.4, 65.6, 71.8, 78.0))

# Fig 1 종단면 + 연소부 A·B·C
local({
    m <- rd(CACHE, "Fig_Section.png"); fb <- lapply(c("A", "B", "C"), function(f) rd(CACHE, paste0("Firebox_", f, ".png")))
    mh <- W * dim(m)[1] / dim(m)[2]; fw <- W / 3; fh <- fw * dim(fb[[1]])[1] / dim(fb[[1]])[2]; head <- 0.40
    out("Fig1", mh + head + fh, function(H) {
        img(m, 0, H, W, mh)
        for (k in 1:3) {
            img(fb[[k]], (k - 1) * fw, fh, fw, fh)
            txt(FORMS[k], (k - 0.5) * fw, fh + head - 0.02, just = c("centre", "top"))
        }
    })
})
row_fig("Fig2", file.path(R, "fig1_forms_3d"), c("form_A_3d.png", "form_B_3d.png", "form_C_3d.png"), FORMS)
field_fig("Fig3", file.path(R, "fig2_cfd_panels"), c("A", "B", "C"), paste0("t", 1:5), FORMS,
          sprintf("t = %d s", c(9, 17, 26, 34, 43)), s = 431)
row_fig("Fig4", file.path(R, "fig3_length_3d"), sprintf("length_L%03d.png", c(25, 45, 65, 85)),
        c("2.5 m", "4.5 m", "6.5 m", "8.5 m"))
file.copy(file.path(R, "kiln_length/Kiln_Length.tiff"), file.path(OUT, "Fig5.tif"), overwrite = TRUE)
file.copy(file.path(R, "kiln_length/Kiln_Length.jpeg"), file.path(OUT, "Fig5.jpeg"), overwrite = TRUE)
field_fig("Fig6", file.path(R, "fig4_length_panels"), c("L25", "L45", "L65", "L85"), paste0("t", 1:5),
          c("2.5 m", "4.5 m", "6.5 m", "8.5 m"), TH, s = 594, below = "Fig_Segments_Length.png", below_h = 2.8)
row_fig("Fig7", file.path(R, "fig5_steps_3d"), sprintf("steps_S%02d.png", c(0, 6, 12, 20)),
        c("No steps", "6 steps", "12 steps", "20 steps"))
field_fig("Fig8", file.path(R, "fig6_steps_panels"), c("S00", "S06", "S12", "S20"), paste0("t", 1:5),
          c("No steps", "6 steps", "12 steps", "20 steps"), TH, s = 498, below = "Fig_Segments_Steps.png", below_h = 2.8)
for (k in c(9, 10)) {
    src <- c("9" = "Fig_Form", "10" = "Fig_Length")[as.character(k)]
    file.copy(file.path(R, "graphs", paste0(src, ".tiff")), file.path(OUT, sprintf("Fig%d.tif", k)), overwrite = TRUE)
    file.copy(file.path(R, "graphs", paste0(src, ".jpeg")), file.path(OUT, sprintf("Fig%d.jpeg", k)), overwrite = TRUE)
}
cat("→", OUT, "\n")
