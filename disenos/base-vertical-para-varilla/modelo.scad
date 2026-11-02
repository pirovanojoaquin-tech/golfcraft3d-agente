// GolfCraft3D — Base vertical para varilla de alineación (diseño propio)
// Deja una varilla parada en la alfombra o en el piso del driving. Con dos bases armás una "puerta" para
// entrenar el recorrido del palo (que la cabeza pase entre las varillas) o marcás un blanco.
// Base ancha y pesada; se imprime parada, sin soportes. Varillas de 3/8" (≈9,5 mm).

varilla = 10.0;
base_d  = 90;
base_h  = 7;
torre_d = 24;
torre_h = 45;
texto   = "GOLFCRAFT3D";
$fn = 96;

difference() {
    union() {
        cylinder(d = base_d, h = base_h);
        // torre cónica: firme abajo, liviana arriba
        cylinder(d1 = torre_d + 14, d2 = torre_d, h = base_h + torre_h);
    }
    translate([0, 0, 4]) cylinder(d = varilla, h = base_h + torre_h);
    // marca alrededor, en la cara de arriba de la base
    for (i = [0 : len(texto) - 1]) rotate([0, 0, 90 - i * 13])
        translate([0, base_d / 2 - 8, base_h - 0.8]) linear_extrude(1)
            text(texto[i], size = 5, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
}
