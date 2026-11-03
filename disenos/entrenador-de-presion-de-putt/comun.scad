// GolfCraft3D — Entrenador de presión para el putt (diseño propio, 2 colores)
// Rampa con un hoyito arriba: si le pegás con la velocidad justa, la bola sube y se queda en el hoyito;
// corto no llega, largo pasa de largo y cae atrás. Entrena la velocidad (lo que más falla en el putt).
ancho = 76; alto = 22; rampa = 105; meseta = 62; bajada = 26; bola = 42.67; hundir = 5.5;
largo = rampa + meseta + bajada;
cx = rampa + meseta / 2;   // centro del hoyito
$fn = 96;
function perfil() = concat(
    [for (i = [0 : 20]) let(x = rampa * i / 20) [x, alto * pow(i / 20, 1.6)]],
    [[rampa + meseta, alto], [largo, 1.2], [largo, 0]]);
module cuerpo() {
    difference() {
        rotate([90, 0, 0]) translate([0, 0, -ancho / 2]) linear_extrude(ancho) polygon(concat([[0, 0]], perfil()));
        translate([cx, 0, alto + bola / 2 - hundir]) sphere(d = bola + 0.6);
        translate([cx, 0, alto - 1]) aro(1.2);   // canal para el aro de color
        translate([rampa + meseta - 16, 0, alto - 0.6]) rotate(90) linear_extrude(1) text("GOLFCRAFT3D", size = 4, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
    }
}
module aro(h) { difference() { cylinder(d = 58, h = h); translate([0, 0, -1]) cylinder(d = 49, h = h + 2); } }
module acento() {
    translate([cx, 0, alto - 1]) aro(1.6);   // aro de color alrededor del hoyito (sobresale 0,6 mm)
    // flechas de color en la meseta, apuntando al hoyito
    for (y = [-26, 26]) translate([rampa + 4, y, alto - 0.01]) linear_extrude(0.8) polygon([[0, -5], [9, 0], [0, 5]]);
}
