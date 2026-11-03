// GolfCraft3D — Exhibidor de pared para 12 pelotas (diseño propio, 2 colores)
// Para la colección de pelotas con logos de canchas y torneos. 3 estantes de 4 pelotas con asiento,
// marco de color y cartel con el nombre. Se imprime acostado (los estantes quedan parados), sin soportes.
cols = 4; filas = 3; paso = 52; bola = 42.67;
ancho = cols * paso + 16; alto_c = 34; alto = filas * paso + 16 + alto_c; esp = 4;
estante = 22;   // cuánto sobresale cada estante
nombre = "MI COLECCIÓN";
$fn = 64;
module placa() {
    difference() {
        cube([ancho, alto, esp]);
        for (x = [20, ancho - 20]) translate([x, alto - 8, -1]) cylinder(d = 5, h = esp + 2);   // para colgar
    }
    for (f = [0 : filas - 1]) translate([0, 8 + f * paso, 0]) difference() {
        cube([ancho, 6, esp + estante]);   // estante
        for (c = [0 : cols - 1]) translate([8 + paso / 2 + c * paso, -bola / 2 + 9, esp + estante / 2 + 3]) sphere(d = bola + 1);
    }
}
module acento() {
    // marco y cartel
    translate([0, 0, esp]) linear_extrude(1) difference() { square([ancho, alto]); translate([4, 4]) square([ancho - 8, alto - 8]); }
    translate([ancho / 2, alto - alto_c / 2 - 4, esp]) linear_extrude(1.2)
        text(nombre, size = 12, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
}
