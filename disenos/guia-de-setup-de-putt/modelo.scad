// GolfCraft3D — Guía de setup para el putt (diseño propio)
// Placa que se apoya en el piso: la bola va en el hueco, la línea larga marca hacia dónde apuntás y la
// línea corta, detrás de la bola, es donde va la cara del putter (cuadrada a la línea). Ojos sobre la bola.
// Se imprime acostada, tal cual, sin soportes.

largo   = 170;
ancho   = 64;
alto    = 3;
bola    = 42.67;
hueco   = 2.2;     // profundidad del asiento de la bola
bola_x  = 60;      // centro de la bola desde la punta de atrás
linea   = 1.6;     // ancho de las líneas grabadas
texto   = "GOLFCRAFT3D";
$fn = 96;

difference() {
    hull() for (x = [ancho / 2, largo - ancho / 2]) translate([x, ancho / 2, 0]) cylinder(d = ancho, h = alto);
    // asiento de la bola: casquete esférico poco profundo
    translate([bola_x, ancho / 2, alto + bola / 2 - hueco]) sphere(d = bola);
    // línea de apunte (hacia adelante, desde la bola hasta la punta)
    translate([bola_x + bola / 2 * 0.62, ancho / 2 - linea / 2, alto - 0.8]) cube([largo - bola_x - 22, linea, 1]);
    // flecha en la punta
    translate([largo - 12, ancho / 2, alto - 0.8]) linear_extrude(1)
        polygon([[0, -6], [10, 0], [0, 6]]);
    // línea de la cara del putter (perpendicular, detrás de la bola)
    translate([bola_x - bola / 2 - 6, 8, alto - 0.8]) cube([linea, ancho - 16, 1]);
    // marca
    translate([largo - 50, 10, alto - 0.8]) linear_extrude(1)
        text(texto, size = 4.2, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
}
