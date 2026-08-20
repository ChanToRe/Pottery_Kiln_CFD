library(ggplot2)
library(here)
library(patchwork)

FONT <- "Times New Roman"

df <- read.csv(here("./Data/Kiln_Length.csv"), fileEncoding = "UTF-8")

kiln_theme <- theme_bw() +
    theme(text = element_text(family = FONT),
        plot.title = element_text(hjust = 0.5, size = 12, face = 'bold'),
        axis.title.x = element_text(size = 12, colour = "black", face = 'bold'),
        axis.title.y = element_text(size = 12, colour = "black", face = 'bold'),
        axis.text = element_text(size = 10, colour = "black"),
        panel.grid.minor = element_blank())

eqn <- function(fit, ydigits = 1) {
    b <- coef(fit)
    sprintf("y = %s x %s %s\nR² = %.4f",
            format(round(b[2], ydigits), big.mark = ","),
            ifelse(b[1] < 0, "−", "+"),
            format(round(abs(b[1]), ydigits), big.mark = ","),
            summary(fit)$r.squared)
}

f3 <- lm(fuel_kg ~ length_m, data = df)

p3 <- ggplot(df, aes(x = length_m, y = fuel_kg)) +

    geom_smooth(method = "lm", formula = y ~ x, se = TRUE, fullrange = TRUE,
                colour = "red", fill = "grey70", alpha = 0.5, linewidth = 0.7) +
    geom_point(colour = "black", size = 2.6) +
    annotate("text", x = 8.7, y = 2780, hjust = 1, vjust = 0, size = 3.6,
             family = FONT, label = eqn(f3)) +
    scale_x_continuous(breaks = df$length_m, limits = c(2.0, 9.0)) +
    scale_y_continuous(labels = function(v) format(v, big.mark = ",")) +
    xlab("Ware chamber length (m)") +
    ylab("Fuel consumed (kg)") +
    kiln_theme
ggsave(here("./Graph/Scatter(Fuel_by_length).tiff"), p3, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", compression = "lzw")
ggsave(here("./Graph/Scatter(Fuel_by_length).jpeg"), p3, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", quality = 95)

f4 <- lm(spread_C ~ length_m, data = df)

p4 <- ggplot(df, aes(x = length_m, y = spread_C)) +

    geom_smooth(method = "lm", formula = y ~ x, se = TRUE, fullrange = TRUE,
                colour = "red", fill = "grey70", alpha = 0.5, linewidth = 0.7) +
    geom_point(colour = "black", size = 2.6) +
    annotate("text", x = 8.7, y = 8, hjust = 1, vjust = 0, size = 3.6,
             family = FONT, label = eqn(f4)) +
    scale_x_continuous(breaks = df$length_m, limits = c(2.0, 9.0)) +
    xlab("Ware chamber length (m)") +
    ylab(expression(bold(paste("Front-to-back temperature difference (", degree, "C)")))) +
    kiln_theme
ggsave(here("./Graph/Scatter(Spread_by_length).tiff"), p4, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", compression = "lzw")
ggsave(here("./Graph/Scatter(Spread_by_length).jpeg"), p4, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", quality = 95)

fig <- p3 + p4 + plot_annotation(tag_levels = "a", tag_prefix = "(", tag_suffix = ")") &
    theme(plot.tag = element_text(family = FONT, size = 13, face = "bold"))
ggsave(here("./Graph/Fig_Length.tiff"), fig, dpi = 300, width = 10, height = 5, units = 'in', bg = "white", compression = "lzw")
ggsave(here("./Graph/Fig_Length.jpeg"), fig, dpi = 300, width = 10, height = 5, units = 'in', bg = "white", quality = 95)
