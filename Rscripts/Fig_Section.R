# 종단면 개념도 (2-3a, E-25·R-02) — 형식 B(수평연소 유단식), 소성실 6.5 m.
# 화구·연소실·연료층·단·소성실·연도와 Table 2 의 주요 치수를 적는다.
# 형상은 mesh/section_data.py 가 STL 생성기에서 꺼낸 중심면 바닥·천장선 그대로이고,
# 벽(0.35 m)은 그 선을 경로 법선 방향으로 민 띠다.
# 별도 낱장: 연소부 세 형식(A·B·C)의 확대 단면 — h_step·h_drop 표시.
#   Rscript Rscripts/Fig_Section.R      (make_figures.sh section 이 부른다)
library(here)

FONT <- "Times New Roman"
D <- here("Results/figures/section")
dims <- read.csv(file.path(D, "dims.csv"))
dv <- function(n) dims$value[dims$name == n]
prof <- function(f) read.csv(file.path(D, sprintf("profile_%s.csv", f)))

WALLC <- "grey62"
AIRC <- "grey94"
FUELC <- "#C8A06A"
CEX <- 0.78          # 이름표 ≈ 9.4 pt (그림을 줄이지 않고 7.5 in 폭으로 싣는다)
CEXS <- 0.70         # 치수 ≈ 8.4 pt

arrow2 <- function(x0, y0, x1, y1) arrows(x0, y0, x1, y1, length = 0.05, angle = 20, code = 3, lwd = 0.6)
ext <- function(x0, y0, x1, y1) segments(x0, y0, x1, y1, lwd = 0.4, col = "grey30")
leader <- function(x0, y0, x1, y1) segments(x0, y0, x1, y1, lwd = 0.5)

draw_kiln <- function(p, fuel = TRUE, floor0 = 0) {
    t <- dv("wall")
    wf <- list(x = p$x_floor - p$nx * t, z = p$z_floor - p$nz * t)
    wc <- list(x = p$x_ceil + p$nx * t, z = p$z_ceil + p$nz * t)
    polygon(c(p$x_floor, rev(wf$x)), c(p$z_floor, rev(wf$z)), col = WALLC, border = NA)
    polygon(c(p$x_ceil, rev(wc$x)), c(p$z_ceil, rev(wc$z)), col = WALLC, border = NA)
    polygon(c(p$x_floor, rev(p$x_ceil)), c(p$z_floor, rev(p$z_ceil)), col = AIRC, border = NA)
    if (fuel) rect(dv("fuel_x0"), floor0, dv("fuel_x1"), floor0 + dv("fuel_bed"), col = FUELC, border = "black", lwd = 0.5)
    lines(p$x_floor, p$z_floor, lwd = 1.1)
    lines(p$x_ceil, p$z_ceil, lwd = 1.1)
    lines(wf$x, wf$z, lwd = 0.5)
    lines(wc$x, wc$z, lwd = 0.5)
    invisible(list(wf = wf, wc = wc))
}

main_fig <- function() {
    p <- prof("B")
    par(mar = c(0, 0, 0, 0), family = FONT, xpd = NA)
    plot(NA, xlim = c(-0.9, 11.0), ylim = c(-1.55, 4.55), asp = 1, axes = FALSE, xlab = "", ylab = "")
    w <- draw_kiln(p)

    th <- dv("slope_deg") * pi / 180
    xs <- dv("step_x")                       # 연소부/소성부 경계 (단)
    zw <- dv("h_step_B")                     # 소성실 바닥 시작 높이 (가장 낮은 바닥 = 0)
    L <- dv("ware_length")
    x1 <- xs + L * cos(th); z1 <- zw + L * sin(th)
    xmax <- max(p$x_floor, p$x_ceil)

    # ---- 이름표 ----
    text(0.66, 0.35, "Firemouth", cex = CEX)
    text(2.05, 0.95, "Firebox", cex = CEX)
    text((dv("fuel_x0") + dv("fuel_x1")) / 2, 0.175, "Fuel bed", cex = CEXS)
    xm <- xs + 0.50 * L * cos(th); zm <- zw + 0.50 * L * sin(th)
    text(xm - sin(th) * 0.55, zm + cos(th) * 0.55, "Ware chamber", cex = CEX, srt = dv("slope_deg"))
    text(10.38, 3.15, "Flue", cex = CEX, adj = c(0, 0.5))
    # 단 (h_step) — 단 모서리에서 소성실 안으로 끌어낸다
    leader(xs + 0.02, zw - 0.05, 3.55, 1.02)
    text(3.58, 1.04, expression("Step, " * h[step] == 0.35 ~ m), cex = CEXS, adj = c(0, 0.5))
    # 흐름
    arrows(-0.85, 0.35, -0.10, 0.35, length = 0.07, angle = 22, lwd = 1.0)
    text(-0.85, 0.47, "Air", cex = CEXS, adj = c(0, 0))
    fx <- tail(p$x_ceil, 1); fz <- tail(p$z_ceil, 1); gx <- tail(p$x_floor, 1); gz <- tail(p$z_floor, 1)
    mx <- (fx + gx) / 2; mz <- (fz + gz) / 2
    arrows(mx, mz + 0.05, mx + 0.30, mz + 0.60, length = 0.07, angle = 22, lwd = 1.0)
    text(mx + 0.36, mz + 0.62, "Exhaust", cex = CEXS, adj = c(0, 0.5))

    # ---- 치수 ----
    # 화구·연소실 길이 (위) — 글자는 설계값(kiln_geometry APRON·L_COMB), 선은 형상 그대로
    yt <- 2.05
    ext(0, 0.75, 0, yt + 0.08); ext(dv("firebox_x"), 1.40, dv("firebox_x"), yt + 0.08); ext(xs, 1.40, xs, yt + 0.08)
    arrow2(0, yt, dv("firebox_x"), yt); arrow2(dv("firebox_x"), yt, xs, yt)
    text(dv("firebox_x") / 2, yt + 0.06, sprintf("%.2f m", dv("firemouth_tunnel")), cex = CEXS, adj = c(0.5, 0))
    text((dv("firebox_x") + xs) / 2, yt + 0.06, sprintf("%.2f m", dv("firebox_length")), cex = CEXS, adj = c(0.5, 0))
    # 벽 두께 t_w (소성실 천장)
    i <- which.min(abs(p$x_ceil - (xs + 2.1)))
    arrow2(p$x_ceil[i], p$z_ceil[i], w$wc$x[i], w$wc$z[i])
    text(w$wc$x[i] - 0.08, w$wc$z[i] + 0.16, expression(t[w] == 0.35 ~ m), cex = CEXS, adj = c(1, 0.5))
    # 소성실 천장 높이 (경사에 수직)
    xh <- xs + 0.78 * L * cos(th); zh <- zw + 0.78 * L * sin(th)
    arrow2(xh, zh, xh - sin(th) * dv("ware_height"), zh + cos(th) * dv("ware_height"))
    text(xh + 0.10, zh + 0.55, sprintf("%.2f m", dv("ware_height")), cex = CEXS, adj = c(0, 0.5), srt = dv("slope_deg"))
    # 소성실 길이 L (경사를 따라, 바닥 벽 바깥)
    off <- 0.70
    nx <- sin(th); nz <- -cos(th)
    ext(xs, zw - 0.40, xs + nx * (off + 0.08), zw + nz * (off + 0.08))
    ext(x1, z1 - 0.40, x1 + nx * (off + 0.08), z1 + nz * (off + 0.08))
    lx0 <- xs + nx * off; lz0 <- zw + nz * off
    arrow2(lx0, lz0, x1 + nx * off, z1 + nz * off)
    text((xs + x1) / 2 + nx * (off - 0.06), (zw + z1) / 2 + nz * (off - 0.06),
         sprintf("Ware chamber length L = %.1f m", L), cex = CEXS, srt = dv("slope_deg"), adj = c(0.5, 0))
    # 경사각 θ — L 치수선 시작점에서 수평 기준선과 이룬 각
    segments(lx0, lz0, lx0 + 2.3, lz0, lty = 2, lwd = 0.4)
    a <- seq(0, th, length.out = 30); r <- 2.0
    lines(lx0 + r * cos(a), lz0 + r * sin(a), lwd = 0.5)
    text(lx0 + r + 0.08, lz0 + 0.11, sprintf("\u03b8 = %.0f\u00b0", dv("slope_deg")), cex = CEXS, adj = c(0, 0.5))
    # 전체 길이 (맨 아래)
    yb <- -1.35
    ext(0, -0.40, 0, yb - 0.08); ext(xmax, gz - 0.6, xmax, yb - 0.08)
    arrow2(0, yb, xmax, yb)
    text(xmax / 2, yb + 0.06, sprintf("Overall length %.1f m", dv("overall_length")), cex = CEXS, adj = c(0.5, 0))
}

firebox_fig <- function(f) {
    p <- prof(f)
    o <- read.table(file.path(D, sprintf("origin_%s.txt", f)))
    z0 <- o$V2[o$V1 == "z0"]                                # 소성실 바닥(경계 x = 0) = 0 으로 되돌린다
    p$z_floor <- p$z_floor + z0; p$z_ceil <- p$z_ceil + z0
    p <- p[p$x_floor < 4.3, ]
    par(mar = c(0, 0, 0, 0), family = FONT, xpd = NA)
    plot(NA, xlim = c(-0.1, 4.3), ylim = c(-1.45, 1.75), asp = 1, axes = FALSE, xlab = "", ylab = "")
    h_step <- c(A = 0, B = 0.35, C = 0.35)[[f]]; h_drop <- c(A = 0, B = 0, C = 0.55)[[f]]
    fl <- -h_step                                           # 연소부 바닥 (소성실 바닥 = 0)
    draw_kiln(p, fuel = TRUE, floor0 = fl)
    xs <- dv("step_x"); xf <- dv("firebox_x")
    yl <- -1.20                                             # 글자는 가마 아래로 빼낸다
    if (h_step > 0) {
        arrow2(xs + 0.10, fl, xs + 0.10, 0)
        leader(xs + 0.10, fl - 0.02, xs + 0.45, yl + 0.20)
        text(xs + 0.50, yl, bquote(h[step] == .(sprintf("%.2f", h_step)) ~ m), cex = CEXS, adj = c(0.5, 0.5))
    }
    if (h_drop > 0) {
        arrow2(xf - 0.10, fl, xf - 0.10, fl + h_drop)
        leader(xf - 0.10, fl - 0.02, 0.85, yl + 0.20)
        text(0.80, yl, bquote(h[drop] == .(sprintf("%.2f", h_drop)) ~ m), cex = CEXS, adj = c(0.5, 0.5))
    }
    if (h_step == 0 && h_drop == 0) text(2.1, yl, expression(h[step] == h[drop] * " = 0"), cex = CEXS)
}

out <- function(name, w, h, fun, ...) {
    tiff(file.path(D, paste0(name, ".tiff")), width = w, height = h, units = "in", res = 600,
         compression = "lzw", type = "cairo", family = FONT)
    fun(...); dev.off()
    jpeg(file.path(D, paste0(name, ".jpeg")), width = w, height = h, units = "in", res = 600,
         quality = 95, type = "cairo", family = FONT)
    fun(...); dev.off()
}

out("Fig_Section", 7.5, 3.9, main_fig)
# 세 장을 가로로 늘어놓으면 7.5 in 폭이 되는 크기 (글자 ≈ 8.4 pt)
for (f in c("A", "B", "C")) out(paste0("Firebox_", f), 2.5, 1.82, firebox_fig, f)
