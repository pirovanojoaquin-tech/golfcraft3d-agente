// GolfCraft3D — Soporte de plano de swing (diseño propio)
// Sostiene una varilla de alineación inclinada para marcar el plano del swing en el driving o en casa.
// Se apoya detrás de la bola apuntando al objetivo; dos ángulos: 45° (hierros) y 55° (wedges y hierros cortos).
// Base ancha y plana; se imprime tal cual, sin soportes (agujeros internos inclinados).

varilla  = 10.0;          // varilla de 3/8" (≈9,5 mm) + aire
base     = [110, 70, 7];
angulos  = [45, 55];      // inclinación de cada agujero respecto del piso
prof     = 42;            // largo del agujero
texto    = "GOLFCRAFT3D";
$fn = 64;

module torre(x, ang) {
    // bloque inclinado que guía la varilla
    translate([x, 0, 0]) hull() {
        translate([-11, -14, 0]) cube([22, 28, base[2]]);
        translate([0, 0, base[2]]) rotate([ang - 90, 0, 0]) translate([0, 0, 0]) cylinder(d = varilla + 9, h = prof * 0.8);
    }
}

difference() {
    union() {
        hull() for (x = [-base[0] / 2 + 8, base[0] / 2 - 8], y = [-base[1] / 2 + 8, base[1] / 2 - 8])
            translate([x, y, 0]) cylinder(r = 8, h = base[2]);
        torre(-24, angulos[0]);
        torre(24, angulos[1]);
    }
    for (i = [0, 1]) translate([i == 0 ? -24 : 24, 0, base[2]]) rotate([angulos[i] - 90, 0, 0])
        translate([0, 0, -6]) cylinder(d = varilla, h = prof + 10);
    // ángulos grabados en la base
    for (i = [0, 1]) translate([i == 0 ? -24 : 24, -base[1] / 2 + 7, base[2] - 0.8]) linear_extrude(1)
        text(str(angulos[i], "°"), size = 6, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
    // marca en el canto de adelante de la base (arriba la tapaban las torres)
    translate([0, -base[1] / 2 + 0.6, base[2] / 2]) rotate([90, 0, 0]) linear_extrude(1)
        text(texto, size = 4.2, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
}
