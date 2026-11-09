include <comun.scad>
difference() {
    union() {
        cylinder(d = bola + 7, h = alto);
        // porta tees
        hull() for (y = [-9, 9]) translate([bola / 2 + 6, y, 0]) cylinder(d = 11, h = alto);
        // argolla
        translate([-(bola / 2 + 8), 0, 0]) difference() { cylinder(d = 18, h = 6); translate([0, 0, -1]) cylinder(d = 9, h = 8); }
    }
    // jaula: la bola entra a presión (boca de 39 mm) y queda por debajo del borde
    translate([0, 0, bola / 2 + 3]) sphere(d = bola + 0.6);
    translate([0, 0, 3]) cylinder(d = bola - 4, h = alto);
    // ranuras para que flexe
    for (a = [45, 90, 135, 225, 270, 315]) rotate(a) translate([0, -1.5, 14]) cube([bola / 2 + 4, 3, alto]);
    // 3 tees
    for (y = [-9, 0, 9]) translate([bola / 2 + 6, y, 3]) cylinder(d = 6.2, h = alto);
    // banda de color (la llena el acento)
    translate([0, 0, alto - 5]) difference() { cylinder(d = bola + 8, h = 6); cylinder(d = bola + 5.4, h = 6); }
}
