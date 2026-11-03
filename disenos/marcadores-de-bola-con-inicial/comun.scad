// GolfCraft3D — Marcadores de bola con tu inicial, pack x4 (diseño propio, 2 colores)
// Moneda de 26 mm con canto estriado, inicial en relieve y anillo de otro color. Se imprimen acostados.
inicial = "J";
d = 26; h = 2.6;
$fn = 72;
module moneda() {
    difference() {
        cylinder(d = d, h = h);
        for (a = [0 : 15 : 359]) rotate(a) translate([d / 2, 0, -1]) cylinder(d = 1.6, h = h + 2, $fn = 12);   // canto estriado
        translate([0, 0, h - 0.6]) difference() { cylinder(d = d - 4, h = 1); cylinder(d = d - 6.4, h = 1); }  // canal del anillo
    }
}
module acento1() {
    translate([0, 0, h - 0.6]) difference() { cylinder(d = d - 4, h = 1.2); translate([0, 0, -1]) cylinder(d = d - 6.4, h = 3); }
    translate([0, 0, h]) linear_extrude(0.8) text(inicial, size = 12, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
}
module grilla() { for (i = [0 : 3]) translate([(i % 2) * 32, floor(i / 2) * 32, 0]) children(); }
