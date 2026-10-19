// GolfCraft3D — Arco de putting (diseño propio)
// La bola (Ø 42,67 mm) tiene que pasar por debajo del arco: entrena la línea de salida del putt.
// Se imprime parado, tal cual, sin soportes (el travesaño es un puente de 54 mm).

luz_ancho = 54;    // espacio libre entre postes (bola + ~5,6 mm por lado)
luz_alto  = 48;    // altura libre bajo el travesaño
poste     = 8;     // ancho de cada poste (eje X)
fondo     = 10;    // profundidad de postes y travesaño (eje Y)
viga      = 8;     // alto del travesaño
pie_largo = 36;    // largo de cada pie (eje Y), para que no se caiga
pie_ancho = 16;    // ancho de cada pie (eje X)
pie_alto  = 3;
texto     = "GOLFCRAFT3D";

ancho_total = luz_ancho + 2 * poste;
alto_total  = pie_alto + luz_alto + viga;

module pie(x) {
    // el pie se extiende hacia afuera del arco para no estorbar a la bola
    translate([x, -pie_largo / 2 + fondo / 2, 0])
        cube([pie_ancho, pie_largo, pie_alto]);
}

difference() {
    union() {
        // postes
        cube([poste, fondo, alto_total]);
        translate([ancho_total - poste, 0, 0]) cube([poste, fondo, alto_total]);
        // travesaño
        translate([0, 0, alto_total - viga]) cube([ancho_total, fondo, viga]);
        // pies (hacia afuera)
        pie(poste - pie_ancho);
        pie(ancho_total - poste);
    }
    // texto grabado en el frente del travesaño
    translate([ancho_total / 2, 0.6, alto_total - viga / 2])
        rotate([90, 0, 0])
            linear_extrude(1)
                text(texto, size = 4.6, font = "Liberation Sans:style=Bold",
                     halign = "center", valign = "center");
}
