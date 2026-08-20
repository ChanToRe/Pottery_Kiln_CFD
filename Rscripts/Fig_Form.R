library(ggplot2)
library(here)
library(patchwork)

FONT <- "Times New Roman"

df <- read.csv(here("./Data/Kiln_Form.csv"), fileEncoding = "UTF-8")
df$form <- factor(df$form, levels = c("A", "B", "C"))
df$axis <- paste(df$form, df$desc, sep = "\n")
df$axis <- factor(df$axis, levels = df$axis[order(df$form)])

kiln_theme <- theme_bw() +
    theme(text = element_text(family = FONT),
        plot.title = element_text(hjust = 0.5, size = 12, face = 'bold'),
        axis.title.x = element_text(size = 12, colour = "black", face = 'bold'),
        axis.title.y = element_text(size = 12, colour = "black", face = 'bold'),
        axis.text = element_text(size = 10, colour = "black"),
        panel.grid.minor = element_blank())

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
ggsave(here("./Graph/Bar(Fuel_by_form).tiff"), p1, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", compression = "lzw")
ggsave(here("./Graph/Bar(Fuel_by_form).jpeg"), p1, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", quality = 95)

drop <- (df$penetration_m[df$form == "A"] - df$penetration_m[df$form == "C"]) /
         df$penetration_m[df$form == "A"] * 100

p2 <- ggplot(df, aes(x = axis, y = penetration_m)) +
    geom_col(fill = "grey75", colour = "black", width = 0.65) +
    geom_text(aes(label = sprintf("%.2f", penetration_m)),
              vjust = -0.6, size = 3.6, family = FONT) +
    annotate("text", x = 3.45, y = 4.15, hjust = 1, size = 3.6, family = FONT,
             label = sprintf("A → C: −%.1f %%", drop)) +
    scale_y_continuous(limits = c(0, 4.3), expand = c(0, 0)) +
    xlab("Firebox form") +
    ylab(expression(bold(paste("Penetration of the 1,000 ", degree, "C isosurface (m)")))) +
    kiln_theme
ggsave(here("./Graph/Bar(Penetration_by_form).tiff"), p2, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", compression = "lzw")
ggsave(here("./Graph/Bar(Penetration_by_form).jpeg"), p2, dpi = 300, width = 5, height = 5, units = 'in', bg = "white", quality = 95)

fig <- p1 + p2 + plot_annotation(tag_levels = "a", tag_prefix = "(", tag_suffix = ")") &
    theme(plot.tag = element_text(family = FONT, size = 13, face = "bold"))
ggsave(here("./Graph/Fig_Form.tiff"), fig, dpi = 300, width = 10, height = 5, units = 'in', bg = "white", compression = "lzw")
ggsave(here("./Graph/Fig_Form.jpeg"), fig, dpi = 300, width = 10, height = 5, units = 'in', bg = "white", quality = 95)
