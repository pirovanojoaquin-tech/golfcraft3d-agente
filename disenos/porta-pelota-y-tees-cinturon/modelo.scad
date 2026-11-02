// GolfCraft3D — Porta pelota y tees para el cinturón (diseño propio)
// El cinturón pasa por las dos ranuras de la placa; lleva una pelota (aro que la abraza) y 3 tees a mano.
// Todo plano y abierto hacia arriba: se imprime acostado, sin soportes.

bola      = 42.67;
aro_alto  = 14;     // alto del aro que sostiene la bola
pared     = 2.4;
placa     = [62, 46, 3.2];  // placa que va contra el cinturón
ranura    = [4.5, 38];      // ranuras por donde pasa el cinturón (hasta 35 mm de ancho)
tee       = 5.6;            // diámetro de los agujeros para tees
texto     = "GOLFCRAFT3D";
$fn = 96;

difference() {
    union() {
        translate([0, 0, 0]) cube(placa);
        // aro para la bola, al costado de la placa
        translate([placa[0] + bola / 2 - 4, placa[1] / 2, 0]) difference() {
            cylinder(d = bola + 2 * pared, h = aro_alto);
            translate([0, 0, -1]) cylinder(d = bola - 4, h = aro_alto + 2);      // la bola apoya en el borde
            translate([0, 0, 3]) cylinder(d = bola + 0.6, h = aro_alto);         // y queda abrazada
        }
        // barra para los tees, abajo de la placa
        translate([8, -11, 0]) cube([placa[0] - 16, 13, 9]);
    }
    for (x = [6, placa[0] - 6 - ranura[0]]) translate([x, (placa[1] - ranura[1]) / 2, -1]) cube([ranura[0], ranura[1], 10]);
    for (x = [18, 31, 44]) translate([x, -4.5, 2]) cylinder(d = tee, h = 10);
    translate([placa[0] / 2, placa[1] / 2, placa[2] - 0.8]) linear_extrude(1)
        text(texto, size = 3.8, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
}
