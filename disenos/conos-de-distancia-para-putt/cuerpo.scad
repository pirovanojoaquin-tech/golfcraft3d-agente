include <comun.scad>
difference() { cono(); cifra(1); translate([0, 0, -0.01]) cylinder(d = base * 0.7, h = 3, $fn = 48); }
