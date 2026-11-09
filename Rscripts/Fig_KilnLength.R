# 중부지역 백제 한성기 토기 가마의 전체 길이 분포 (원고 Fig 5; 답변 E-23).
# 자료: 윤예주·주찬혁·송만영 2024, 한국고고학보 2024(2): 221–254, 표 2 '가마크기(m) 길이·폭'
#       → Data/yun2024_table2_kilns.csv (69기 그대로 옮김; 길이는 가마의 전체 길이).
# 길이·폭이 모두 있는 46기 가운데 괄호 값(잔존 치수)인 원주 만종리 4호를 뺀 45기를 한 상자로 그린다.
#   Rscript Rscripts/Fig_KilnLength.R      (Rscripts/make_figures.sh graphs 가 부른다)
library(ggplot2)
library(here)

FONT <- "Times New Roman"
OUT <- here("Results/figures/kiln_length")
dir.create(OUT, showWarnings = FALSE, recursive = TRUE)

d <- read.csv(here("Data/yun2024_table2_kilns.csv"), fileEncoding = "UTF-8", stringsAsFactors = FALSE)
k <- d[!is.na(d$length_m) & !is.na(d$width_m) & d$note == "", ]

x <- k$length_m
g <- data.frame(group = sprintf("n = %d", length(x)), length_m = x)

# 요약값 (답변서·원고 문장의 수치)
s <- data.frame(n = length(x), min = min(x), q1 = unname(quantile(x, .25)), median = median(x),
                q3 = unname(quantile(x, .75)), max = max(x), mean = mean(x),
                n_2.5_6.5 = sum(x >= 2.5 & x <= 6.5), n_4.5_6.5 = sum(x >= 4.5 & x <= 6.5))
write.csv(s, file.path(OUT, "Kiln_Length_summary.csv"), row.names = FALSE)
print(s)

set.seed(1)
p <- ggplot(g, aes(x = group, y = length_m)) +
    geom_boxplot(width = 0.5, outlier.shape = NA, fill = "grey90", linewidth = 0.4) +
    geom_jitter(width = 0.10, height = 0, size = 1.1, shape = 16, alpha = 0.7) +
    scale_y_continuous(limits = c(0, 8), breaks = 0:8) +
    labs(x = NULL, y = "Overall length (m)") +
    theme_bw() +
    theme(text = element_text(family = FONT),
          axis.title.y = element_text(size = 10, colour = "black", face = "bold"),
          axis.text = element_text(size = 9, colour = "black"),
          panel.grid.minor = element_blank(),
          panel.grid.major.x = element_blank())

W <- 2.5; H <- 3.0
ggsave(file.path(OUT, "Kiln_Length.tiff"), p, width = W, height = H, units = "in", dpi = 600,
       compression = "lzw", device = "tiff", type = "cairo")
ggsave(file.path(OUT, "Kiln_Length.jpeg"), p, width = W, height = H, units = "in", dpi = 600,
       quality = 95, device = "jpeg", type = "cairo")
