// GolfCraft3D — Unión en T para varillas de alineación (diseño propio)
// Une dos varillas a 90°: una marca la línea de los pies y la otra la posición de la bola.
// La varilla larga pasa de lado a lado; la otra entra de frente. Varillas estándar de 3/8" (≈9,5 mm).
// Se imprime acostada, sin soportes (agujeros horizontales chicos).

varilla   = 10.0;   // diámetro del agujero (varilla de 9,5 mm + aire)
largo     = 70;     // largo en X (por donde pasa la varilla principal)
ancho     = 34;     // en Y
alto      = 26;     // en Z
z_a       = 8;      // altura del eje de la varilla principal
z_b       = 18.5;   // altura del eje de la varilla en T (más arriba para no chocar)
prof_b    = 30;     // profundidad del agujero de la T
texto     = "GOLFCRAFT3D";
$fn = 64;

difference() {
    // cuerpo con cantos redondeados en planta
    hull() for (x = [-largo / 2 + 4, largo / 2 - 4], y = [-ancho / 2 + 4, ancho / 2 - 4])
        translate([x, y, 0]) cylinder(r = 4, h = alto);
    // varilla principal (eje X, de lado a lado)
    translate([0, 0, z_a]) rotate([0, 90, 0]) cylinder(d = varilla, h = largo + 2, center = true);
    // varilla en T (eje Y, entra por el frente)
    translate([0, -ancho / 2 - 1, z_b]) rotate([-90, 0, 0]) cylinder(d = varilla, h = prof_b + 1);
    // texto grabado arriba
    translate([0, 8, alto - 0.8]) linear_extrude(1)
        text(texto, size = 4.6, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
}
