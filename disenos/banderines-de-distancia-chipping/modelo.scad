// GolfCraft3D — Banderines de distancia para chipping (diseño propio), juego de 3: 5, 10 y 15 metros.
// Se clavan en el pasto para marcar dónde tiene que picar la bola. Se imprimen acostados, sin soportes.

distancias = ["5", "10", "15"];
estaca     = [110, 7, 3];   // largo, ancho, espesor de la estaca (punta afilada)
bandera    = [38, 30, 2.4]; // banderín
texto      = "GOLFCRAFT3D";
$fn = 48;

module banderin(numero) {
    // estaca con punta
    linear_extrude(estaca[2]) polygon([[0, 0], [estaca[0] - 12, 0], [estaca[0], estaca[1] / 2], [estaca[0] - 12, estaca[1]], [0, estaca[1]]]);
    // bandera con el número en relieve
    translate([-bandera[0] + 4, estaca[1] - 2, 0]) difference() {
        cube([bandera[0], bandera[1], bandera[2]]);
    }
    translate([-bandera[0] / 2 + 4, estaca[1] - 2 + bandera[1] / 2, bandera[2]]) linear_extrude(1.2)
        text(numero, size = 15, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
    translate([45, estaca[1] / 2, estaca[2]]) linear_extrude(0.8)
        text(texto, size = 3.6, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
}

for (i = [0 : 2]) translate([0, i * 40, 0]) banderin(distancias[i]);
