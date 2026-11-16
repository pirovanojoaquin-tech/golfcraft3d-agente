// GolfCraft3D — Exhibidor "Hoyo en uno" (diseño propio, 2 colores). Base con asiento para la pelota del hoyo en uno
// y placa al frente con el nombre y la fecha. Se imprime parado tal cual, sin soportes.
nombre = "MARTÍN";
fecha = "12 · 11 · 2026";
w = 110; d = 78; h = 26; bola = 42.7;
$fn = 72;
module base() hull() { for (x = [-w / 2 + 10, w / 2 - 10], y = [-d / 2 + 10, d / 2 - 10]) { translate([x, y, 0]) cylinder(r = 10, h = 1); translate([x * 0.9, y * 0.82 + 5, h - 1]) cylinder(r = 8, h = 1); } }
// cara del frente inclinada: sistema de coordenadas para el texto
ang = atan((d / 2 - 10) * 0.18 / (h - 2)) + 8;
module en_frente() translate([0, -d / 2 + 5.9, h / 2 - 1]) rotate([90 - 25, 0, 0]) children();
module textos(prof) en_frente() translate([0, 0, -prof]) linear_extrude(prof + 3) {
    translate([0, 4.5]) text("HOYO EN UNO", size = 7.6, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
    translate([0, -5.5]) text(str(nombre, "  ·  ", fecha), size = 4.4, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
}
