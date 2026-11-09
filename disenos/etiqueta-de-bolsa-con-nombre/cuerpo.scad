include <comun.scad>
difference() {
    union() {
        hull() { linear_extrude(0.01) offset(r = -1) placa(); translate([0, 0, 1]) linear_extrude(esp - 1) placa(); }
        // pelota en relieve
        translate([-w / 2 + 23, 0, esp]) scale([1, 1, 0.35]) sphere(d = 26);
    }
    translate([-w / 2 + 23, 0, esp + 1.2]) linear_extrude(4) hoyuelos();
    translate([10, 0, esp - 1]) linear_extrude(2) texto();
    // ranura para la correa
    translate([w / 2 - 9, 0, -1]) linear_extrude(esp + 2) hull() for (y = [-12, 12]) translate([0, y]) circle(d = 5);
    translate([0, -h / 2 + 5, -0.01]) mirror([1, 0, 0]) linear_extrude(0.5) text("GOLFCRAFT3D", size = 4, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
}
