include <comun.scad>
difference() { linear_extrude(esp) offset(r = 1) offset(delta = -1) silueta(); translate([0, 0, esp - 0.8]) linear_extrude(1) texto(); }
