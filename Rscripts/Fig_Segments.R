# Fig 4·6 칸 안에 있던 소성실 구간 기체온도를 선그래프로 (결정 K30, E-26·R-08).
# 자료: rom/panels_length.py 가 낱장과 같은 시각·같은 계산으로 남긴 segments.csv.
#   Rscript Rscripts/Fig_Segments.R
library(ggplot2)
library(here)

FONT <- "Times New Roman"

kiln_theme <- theme_bw() +
    theme(text = element_text(family = FONT),
        axis.title = element_text(size = 10, colour = "black", face = "bold"),
        axis.text = element_text(size = 9, colour = "black"),
        strip.text = element_text(size = 10, colour = "black"),
        strip.background = element_rect(fill = "grey92"),
        legend.title = element_text(size = 9, face = "bold"),
        legend.text = element_text(size = 9),
        legend.position = "bottom", legend.margin = margin(0, 0, 0, 0), legend.box.spacing = unit(2, "pt"),
        panel.grid.minor = element_blank())

seg_plot <- function(csv, facet_lab, out) {
    df <- read.csv(here(csv))
    df$panel <- factor(facet_lab[df$tag], levels = unname(facet_lab))
    df$time <- factor(sprintf("%.1f h", df$t_h), levels = sprintf("%.1f h", sort(unique(df$t_h))))
    p <- ggplot(df, aes(x = s_mid_m, y = T_gas_C, group = time, colour = time, shape = time)) +
        geom_line(linewidth = 0.5) +
        geom_point(size = 1.4) +
        facet_wrap(~panel, nrow = 1) +
        scale_colour_grey(start = 0.75, end = 0.0, name = "Time") +
        scale_shape_manual(values = c(1, 2, 0, 5, 16), name = "Time") +
        scale_y_continuous(limits = c(300, 1200), breaks = seq(300, 1200, 100),
                           labels = function(v) format(v, big.mark = ",")) +
        scale_x_continuous(limits = c(0, NA), breaks = seq(0, 10, 2)) +
        xlab("Distance from the front of the ware chamber (m)") +
        ylab(expression(bold(paste("Gas temperature (", degree, "C)")))) +
        kiln_theme
    for (ext in c("tiff", "jpeg")) {
        f <- here(sprintf("Results/figures/graphs/%s.%s", out, ext))
        if (ext == "tiff") ggsave(f, p, dpi = 600, width = 7.5, height = 2.8, units = "in", bg = "white", compression = "lzw")
        else ggsave(f, p, dpi = 600, width = 7.5, height = 2.8, units = "in", bg = "white", quality = 95)
    }
}

seg_plot("Results/figures/fig4_length_panels/segments.csv",
         c(L25 = "L = 2.5 m", L45 = "L = 4.5 m", L65 = "L = 6.5 m", L85 = "L = 8.5 m"), "Fig_Segments_Length")
seg_plot("Results/figures/fig6_steps_panels/segments.csv",
         c(S00 = "No steps", S06 = "6 steps", S12 = "12 steps", S20 = "20 steps"), "Fig_Segments_Steps")
