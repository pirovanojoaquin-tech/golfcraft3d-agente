// GolfCraft3D — Marcador de línea para pelota (diseño propio)
// La pelota se apoya en la cuna y el arco con ranura guía el fibrón: una línea recta para apuntar el putt.
// Se dibuja media vuelta, se gira la pelota 180° y se completa la línea. Se imprime tal cual, sin soportes.

bola       = 42.67;  // diámetro reglamentario
holgura    = 0.8;    // aire entre la bola y el arco
hundir     = 9;      // cuánto se hunde la bola en la cuna
ranura     = 2.2;    // ancho de la ranura para la punta del fibrón
pared      = 3.2;    // espesor de cada lado del arco (eje Y)
arco_esp   = 4;      // espesor radial del arco
base       = [64, 46, 14];
texto      = "GOLFCRAFT3D";
$fn = 96;

r  = bola / 2;
zc = base[2] + r - hundir;          // centro de la bola
ri = r + holgura;                   // radio interno del arco
ro = ri + arco_esp;                 // radio externo del arco
largo_arco = ranura + 2 * pared;    // ancho total del arco en Y

difference() {
    union() {
        translate([-base[0] / 2, -base[1] / 2, 0]) cube(base);
        // arco: anillo alrededor del eje Y, partido al medio por la ranura
        intersection() {
            translate([0, 0, zc]) rotate([90, 0, 0])
                difference() {
                    cylinder(r = ro, h = largo_arco, center = true);
                    cylinder(r = ri, h = largo_arco + 1, center = true);
                }
            translate([-50, -50, 0]) cube([100, 100, 100]);
        }
    }
    // cuna para la bola
    translate([0, 0, zc]) sphere(r = r + 0.3);
    // ranura para el fibrón (solo en el arco, por encima de la cuna)
    translate([-ro - 1, -ranura / 2, base[2]]) cube([2 * ro + 2, ranura, 100]);
    // texto grabado en el frente de la base
    translate([0, -base[1] / 2 + 0.6, base[2] / 2 - 1])
        rotate([90, 0, 0]) linear_extrude(1)
            text(texto, size = 4.2, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
}
