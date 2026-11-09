# S1 Fig — CFD 잔차 이력 (2-2c, E-06). 원고에 쓴 기본 격자 6 건(정상 3, 비정상 3).
#   자료: Results/checks/convergence/residuals_{steady,transient}_<M>.csv (cfd/checks/convergence_summary.py)
#   출력: Results/supporting/S1_Fig.{tif,jpg}  (7.5 in, 600 dpi)
library(ggplot2)
library(here)

FONT <- "Times New Roman"
D <- here("Results/checks/convergence")
long <- function(kind, xcol, fields) {
    out <- NULL
    for (m in c("A", "B", "C")) {
        df <- read.csv(file.path(D, sprintf("residuals_%s_%s_L065.csv", kind, m)))
        for (f in fields) {
            out <- rbind(out, data.frame(x = df[[xcol]], value = df[[f]], field = f,
                                         form = m, kind = kind))
        }
    }
    out[is.finite(out$value) & out$value > 0, ]
}
st <- long("steady", "iter", c("Ux", "Uy", "Uz", "h", "p_rgh", "k", "omega"))
tr <- long("transient", "t_s", c("Ux", "Uy", "Uz", "h", "p_rgh", "k", "epsilon"))
st$panel <- sprintf("%s, steady", st$form)
tr$panel <- sprintf("%s, transient", tr$form)
theme_s <- theme_bw() + theme(text = element_text(family = FONT, size = 9),
    strip.background = element_rect(fill = "grey92"), legend.position = "bottom",
    legend.title = element_blank(), panel.grid.minor = element_blank())
p1 <- ggplot(st, aes(x, value, colour = field)) + geom_line(linewidth = 0.25) +
    facet_wrap(~panel, nrow = 1) + scale_y_log10() + xlab("Iteration") + ylab("Initial residual") + theme_s
p2 <- ggplot(tr, aes(x, value, colour = field)) + geom_line(linewidth = 0.25) +
    facet_wrap(~panel, nrow = 1) + scale_y_log10() + xlab("Time (s)") + ylab("Initial residual") + theme_s
library(patchwork)
fig <- p1 / p2
out <- here("Results/supporting")
ggsave(file.path(out, "S1_Fig.tif"), fig, dpi = 600, width = 7.5, height = 6, units = "in", bg = "white", compression = "lzw")
ggsave(file.path(out, "S1_Fig.jpg"), fig, dpi = 600, width = 7.5, height = 6, units = "in", bg = "white", quality = 95)
