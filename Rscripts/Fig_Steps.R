library(ggplot2)
library(here)
library(patchwork)

FONT <- "Times New Roman"

IMG <- Filter(file.exists, here(c("./Data/Firing_Colour_Chart.png",
                                  "./Data/Firing_Colour_Chart.jpg")))[1]

all_df <- read.csv(here("./Data/Kiln_Steps.csv"), fileEncoding = "UTF-8")
df <- subset(all_df, all_df$finite == TRUE)

kiln_theme <- theme_bw() +
    theme(text = element_text(family = FONT),
        plot.title = element_text(hjust = 0.5, size = 12, face = 'bold'),
        axis.title.x = element_text(size = 12, colour = "black", face = 'bold'),
        axis.title.y = element_text(size = 12, colour = "black", face = 'bold'),
        axis.text = element_text(size = 10, colour = "black"),
        panel.grid.minor = element_blank())

f5 <- lm(fuel_kg ~ x_pos, data = df)
rng <- max(df$fuel_kg) - min(df$fuel_kg)

YLIM <- c(3000, 4000)
ypad <- diff(YLIM) * 0.03

p5 <- ggplot(df, aes(x = x_pos, y = fuel_kg)) +

    geom_smooth(method = "lm", formula = y ~ x, se = TRUE, fullrange = TRUE,
                colour = "red", fill = "grey70", alpha = 0.5, linewidth = 0.7) +
    geom_point(colour = "black", size = 2.6) +
    annotate("text", x = 5.2, y = YLIM[1] + ypad, hjust = 0, vjust = 0, size = 3.6, family = FONT,
             label = sprintf("y = %s%.2f x + %s\nR² = %.3f",
                             ifelse(coef(f5)[2] < 0, "−", ""), abs(coef(f5)[2]),
                             format(round(coef(f5)[1], 1), big.mark = ","),
                             summary(f5)$r.squared)) +
    annotate("text", x = 20.8, y = YLIM[2] - ypad, hjust = 1, vjust = 1, size = 3.6, family = FONT,
             label = sprintf("Range: %s kg (%.1f %%)", rng, rng / min(df$fuel_kg) * 100)) +
    scale_x_continuous(breaks = df$steps, limits = c(5, 21)) +
    scale_y_continuous(labels = function(v) format(v, big.mark = ",")) +

    coord_cartesian(ylim = YLIM) +
    xlab("Number of steps on the ware chamber floor") +
    ylab("Fuel consumed (kg)") +
    kiln_theme
ggsave(here("./Graph/Scatter(Fuel_by_steps).tiff"), p5, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", compression = "lzw")
ggsave(here("./Graph/Scatter(Fuel_by_steps).jpeg"), p5, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", quality = 95)

if (is.na(IMG)) {
    stop("사진이 없다. Data/Firing_Colour_Chart.{png,jpg} 를 두고 다시 실행할 것.")
}
img <- if (grepl("\\.png$", IMG, ignore.case = TRUE)) {
    library(png);  png::readPNG(IMG)
} else {
    library(jpeg); jpeg::readJPEG(IMG)
}
if (length(dim(img)) == 3 && dim(img)[3] == 4) img <- img[, , 1:3]
ar <- dim(img)[1] / dim(img)[2]

p_img <- ggplot() +
    annotation_raster(img, xmin = 0, xmax = 1, ymin = 0, ymax = ar,
                      interpolate = TRUE) +
    scale_x_continuous(limits = c(0, 1), expand = c(0, 0)) +
    scale_y_continuous(limits = c(0, ar), expand = c(0, 0)) +
    coord_fixed() +
    theme_void() +

    theme(text = element_text(family = FONT),
          plot.background = element_rect(fill = "white", colour = NA),
          plot.margin = margin(5, 5, 5, 5))

fig <- p5 + p_img + plot_annotation(tag_levels = "a", tag_prefix = "(", tag_suffix = ")") &
    theme(plot.tag = element_text(family = FONT, size = 13, face = "bold"))
ggsave(here("./Graph/Fig_Steps.tiff"), fig, dpi = 300, width = 10, height = 5, units = 'in', bg = "white", compression = "lzw")
ggsave(here("./Graph/Fig_Steps.jpeg"), fig, dpi = 300, width = 10, height = 5, units = 'in', bg = "white", quality = 95)
