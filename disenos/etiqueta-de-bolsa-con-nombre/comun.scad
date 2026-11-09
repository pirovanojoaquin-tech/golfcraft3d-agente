// GolfCraft3D — Etiqueta de bolsa con nombre (diseño propio, 2 colores). Pelota con hoyuelos en relieve, el nombre
// del jugador y ranura para la correa. Se imprime acostada, sin soportes.
nombre = "MARTÍN";
w = 98; h = 52; esp = 4;
$fn = 48;
module placa() hull() for (x = [-w / 2 + 8, w / 2 - 8], y = [-h / 2 + 8, h / 2 - 8]) translate([x, y]) circle(r = 8);
module hoyuelos() for (r = [0, 5, 10], k = [0:max(1, r * 0.9) - 1]) let(a = 360 * k / max(1, round(r * 0.9))) translate([r * cos(a), r * sin(a)]) circle(d = 2.6, $fn = 12);
module texto() text(nombre, size = 8, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
