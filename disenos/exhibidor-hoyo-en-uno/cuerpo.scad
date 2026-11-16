include <comun.scad>
difference() {
    union() { base(); translate([0, 6, h - 0.5]) cylinder(r1 = 21, r2 = 17, h = 7); }
    translate([0, 6, h + 6.5 + bola / 2 - 9]) sphere(d = bola + 0.6);   // asiento de la pelota
    textos(1.4);
    translate([0, 0, -0.01]) mirror([1, 0, 0]) linear_extrude(0.6) text("GOLFCRAFT3D", size = 6, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
}
