// GolfCraft3D — Riel de golpe para el putt (diseño propio)
// Dos rieles paralelos unidos atrás: si el putter toca un riel, el golpe no fue derecho.
// La bola se pone en la boca abierta, adelante. La unión de atrás es una chapa de 1,6 mm (el putter pasa por encima).
// Se imprime tal cual, sin soportes.

largo    = 220;   // largo de los rieles (eje X)
luz      = 125;   // espacio libre entre rieles (putters de hoja y la mayoría de los mallets)
riel_a   = 7;     // ancho de cada riel
riel_h   = 12;    // alto de cada riel
chapa    = [24, 1.6];   // largo y espesor de la unión de atrás
texto    = "GOLFCRAFT3D";
$fn = 32;

ancho = luz + 2 * riel_a;

module riel(y) {
    translate([0, y, 0]) hull() {
        translate([riel_h / 2, 0, 0]) cube([largo - riel_h, riel_a, riel_h]);
        // puntas redondeadas para que no se enganche el putter
        translate([riel_h / 2, 0, 0]) cube([1, riel_a, 1]);
        translate([largo - riel_h / 2 - 1, 0, 0]) cube([1, riel_a, 1]);
    }
}

difference() {
    union() {
        riel(0);
        riel(luz + riel_a);
        cube([chapa[0], ancho, chapa[1]]);   // unión de atrás
    }
    // marcas cada 5 cm en la cara de arriba de un riel (largo del backswing)
    for (x = [50 : 50 : largo - 20]) translate([x, -0.1, riel_h - 2]) cube([1.2, riel_a + 0.2, 3]);
    translate([largo / 2, luz + riel_a + riel_a / 2, riel_h - 0.8]) linear_extrude(1)
        text(texto, size = 4.4, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
}
