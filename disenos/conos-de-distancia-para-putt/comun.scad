// GolfCraft3D — Conos de distancia para putt (diseño propio, 2 colores). Set de 5 conos numerados del 1 al 5:
// se ponen a 1, 2, 3, 4 y 5 metros del hoyo para el ejercicio de la escalera. Se imprimen parados, sin soportes.
numero = "3";
base = 52; tope = 22; alto = 58;
inc = atan((base - tope) / 2 / alto);
$fn = 4;
module cono() rotate(45) cylinder(d1 = base * 1.414, d2 = tope * 1.414, h = alto);
module cifra(prof) translate([0, -(base / 2 - (base - tope) / 2 * 0.42), alto * 0.42]) rotate([90 - inc, 0, 0]) translate([0, 0, -prof]) linear_extrude(prof + 0.01) text(numero, size = 20, halign = "center", valign = "center", font = "Liberation Sans:style=Bold", $fn = 32);
