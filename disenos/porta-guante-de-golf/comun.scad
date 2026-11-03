// GolfCraft3D — Porta guante que mantiene la forma (diseño propio, 2 colores)
// El guante se pone sobre esta "mano" para que seque estirado y no se arrugue ni se endurezca.
// Ojal arriba para colgarlo de la bolsa con un mosquetón. Se imprime acostado, sin soportes.
esp = 2.6;
nombre = "GOLFCRAFT3D";
$fn = 48;
module dedo(x, largo, ang = 0, ancho = 17) { translate([x, 0]) rotate(ang) hull() { circle(d = ancho); translate([0, largo]) circle(d = ancho - 2); } }
module silueta() {
    hull() { translate([-38, 8]) circle(r = 10); translate([38, 8]) circle(r = 10); translate([-34, 70]) circle(r = 8); translate([34, 70]) circle(r = 8); }
    translate([0, 72]) { dedo(-28, 50); dedo(-9, 60); dedo(10, 56); dedo(28, 44, 0, 15); }
    translate([-38, 40]) dedo(0, 46, 40, 19);    // pulgar
    translate([-14, -10]) square([28, 18]);      // muñeca
}
module mano() {
    difference() {
        linear_extrude(esp) offset(r = -0.4) silueta();
        translate([0, 18, -1]) linear_extrude(esp + 2) offset(r = 0) translate([-30, 0]) square([60, 26]);   // ventana para que respire
        translate([0, -2, -1]) cylinder(d = 7, h = esp + 2);       // ojal
    }
}
module acento() {
    // borde de color alrededor de la ventana y nombre en relieve
    translate([0, 0, esp]) linear_extrude(0.8) difference() { translate([-33, 15]) square([66, 32]); translate([-30, 18]) square([60, 26]); }
    translate([0, 58, esp]) linear_extrude(0.8) text(nombre, size = 5.5, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
}
