library(ggplot2)
library(here)
library(patchwork)

FONT <- "Times New Roman"

df <- read.csv(here("Data/Kiln_Form.csv"), fileEncoding = "UTF-8")
df$form <- factor(df$form, levels = c("A", "B", "C"))
# 7.5 in 폭에서 형식명이 겹치지 않게 설명을 두 줄로 ("Horizontal,\nunstepped")
df$axis <- paste(df$form, sub(", ", ",\n", df$desc, fixed = TRUE), sep = "\n")
df$axis <- factor(df$axis, levels = df$axis[order(df$form)])

kiln_theme <- theme_bw() +
    theme(text = element_text(family = FONT),
        plot.title = element_text(hjust = 0.5, size = 12, face = 'bold'),
        axis.title.x = element_text(size = 12, colour = "black", face = 'bold'),
        axis.title.y = element_text(size = 12, colour = "black", face = 'bold'),
        axis.text = element_text(size = 10, colour = "black"),
        panel.grid.minor = element_blank())

########## 1. Fuel consumed by firebox form ##########
# 세 형식의 차폭을 그대로 읽히게 하려고 y 를 0 에서 시작한다.
spread <- (max(df$fuel_kg) - min(df$fuel_kg)) / min(df$fuel_kg) * 100

p1 <- ggplot(df, aes(x = axis, y = fuel_kg)) +
    geom_col(fill = "grey75", colour = "black", width = 0.65) +
    geom_text(aes(label = format(fuel_kg, big.mark = ",")),
              vjust = -0.6, size = 3.6, family = FONT) +
    annotate("text", x = 0.55, y = 4180, hjust = 0, size = 3.6, family = FONT,
             label = sprintf("Range across forms: %.1f %%", spread)) +
    scale_y_continuous(limits = c(0, 4300), expand = c(0, 0),
                       labels = function(v) format(v, big.mark = ",")) +
    xlab("Firebox form") +
    ylab("Fuel consumed (kg)") +
    kiln_theme
ggsave(here("Results/figures/graphs/Bar(Fuel_by_form).tiff"), p1, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", compression = "lzw")
ggsave(here("Results/figures/graphs/Bar(Fuel_by_form).jpeg"), p1, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", quality = 95)

########## 2. Penetration of the 1,000 C isosurface ##########
# 결정 K22: 45 s 까지 도달한 최대 거리. 막대는 본계산(6 분할), 오차 막대는 병렬 분할 4·6·8·10
# 네 판의 범위(pen_min_m–pen_max_m). C 는 분할에 따라 갈리므로 A → C 감소도 범위로 적는다.
pA <- df$penetration_m[df$form == "A"]
drop_hi <- (pA - df$penetration_m[df$form == "C"]) / pA * 100
drop_lo <- (pA - df$pen_min_m[df$form == "C"]) / pA * 100

p2 <- ggplot(df, aes(x = axis, y = penetration_m)) +
    geom_col(fill = "grey75", colour = "black", width = 0.65) +
    geom_errorbar(aes(ymin = pen_min_m, ymax = pen_max_m), width = 0.2, linewidth = 0.5) +
    geom_text(aes(y = pen_max_m, label = sprintf("%.2f", penetration_m)),
              vjust = -0.8, size = 3.6, family = FONT) +
    annotate("text", x = 3.45, y = 4.15, hjust = 1, size = 3.6, family = FONT,
             label = sprintf("A → C: −%.0f to −%.0f %%", drop_hi, drop_lo)) +
    scale_y_continuous(limits = c(0, 4.3), expand = c(0, 0)) +
    xlab("Firebox form") +
    ylab(expression(bold(paste("Penetration of the 1,000 ", degree, "C isosurface (m)")))) +
    kiln_theme
ggsave(here("Results/figures/graphs/Bar(Penetration_by_form).tiff"), p2, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", compression = "lzw")
ggsave(here("Results/figures/graphs/Bar(Penetration_by_form).jpeg"), p2, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", quality = 95)

########## 1 x 2 ##########
# 원고 그림은 PLOS 최대 폭 7.5 in 에 600 dpi 로 낸다 — 줄여 싣지 않으므로 글자 크기(10–13 pt)가 그대로다 (E-26, R-08).
fig <- p1 + p2 + plot_annotation(tag_levels = "a", tag_prefix = "(", tag_suffix = ")") &
    theme(plot.tag = element_text(family = FONT, size = 13, face = "bold"))
ggsave(here("Results/figures/graphs/Fig_Form.tiff"), fig, dpi = 600, width = 7.5, height = 4, units = 'in', bg = "white", compression = "lzw")
ggsave(here("Results/figures/graphs/Fig_Form.jpeg"), fig, dpi = 600, width = 7.5, height = 4, units = 'in', bg = "white", quality = 95)
