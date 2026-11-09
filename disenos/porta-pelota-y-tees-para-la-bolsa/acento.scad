include <comun.scad>
translate([0, 0, alto - 5]) difference() { cylinder(d = bola + 7, h = 5); translate([0, 0, -1]) cylinder(d = bola + 5.6, h = 7); for (a = [45, 90, 135, 225, 270, 315]) rotate(a) translate([0, -1.5, -1]) cube([bola / 2 + 4, 3, 8]); }
