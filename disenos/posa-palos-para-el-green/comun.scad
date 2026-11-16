// GolfCraft3D — Posa palos para el green (diseño propio, 2 colores). Se clava en el pasto al borde del green y
// sostiene hasta 3 palos por el grip para que no se mojen ni queden olvidados. Se imprime acostado, sin soportes.
esp = 7; ancho = 150; alto = 60; pica = 110;
$fn = 48;
module silueta() {
    difference() {
        hull() { translate([-ancho / 2 + 8, alto - 8]) circle(r = 8); translate([ancho / 2 - 8, alto - 8]) circle(r = 8); translate([-14, 6]) circle(r = 6); translate([14, 6]) circle(r = 6); }
        for (x = [-48, 0, 48]) hull() { translate([x, alto - 10]) circle(d = 27); translate([x, alto + 20]) circle(d = 31); }   // apoyos de los grips
    }
    hull() { translate([-10, 0]) square([20, 10]); translate([0, -pica]) circle(r = 1.6); }   // pica
}
module texto() translate([0, 13]) text("GOLFCRAFT3D", size = 7, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
