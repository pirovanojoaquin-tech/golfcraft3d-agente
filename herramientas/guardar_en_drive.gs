/**
 * GolfCraft3D — guarda en Google Drive los archivos 3D que aprueba el agente.
 *
 * Se instala una sola vez en https://script.google.com (ver README, "Google Drive").
 * Corre con TU cuenta de Google, así que los archivos quedan en TU Drive.
 * Solo acepta descargas de los sitios de modelos 3D de la lista.
 */

const CARPETA_ID = '1d7j56w2Qh00IbWcfqnolZ9tt-Goz-UY5';  // PRODUCTOS 3D GOLF
const SITIOS_PERMITIDOS = ['files.printables.com', 'media.printables.com', 'raw.githubusercontent.com',
                           'cdn.thingiverse.com', 'cdn.thingiverse.net'];
const MAX_MB = 50;

function doPost(e) {
  try {
    const pedido = JSON.parse(e.postData.contents);
    const raiz = DriveApp.getFolderById(CARPETA_ID);
    const carpeta = subcarpeta_(raiz, pedido.carpeta);
    const guardados = [];

    (pedido.archivos || []).forEach(function (a) {
      const host = a.url.split('/')[2];
      if (SITIOS_PERMITIDOS.indexOf(host) === -1) throw new Error('Sitio no permitido: ' + host);
      const blob = UrlFetchApp.fetch(a.url).getBlob();
      if (blob.getBytes().length > MAX_MB * 1024 * 1024) throw new Error('Archivo muy grande: ' + a.nombre);
      blob.setName(a.nombre);
      reemplazar_(carpeta, a.nombre);
      guardados.push(carpeta.createFile(blob).getName());
    });

    if (pedido.ficha) {
      reemplazar_(carpeta, 'ficha.txt');
      carpeta.createFile('ficha.txt', pedido.ficha, MimeType.PLAIN_TEXT);
      guardados.push('ficha.txt');
    }
    return json_({ ok: true, carpeta: carpeta.getUrl(), archivos: guardados });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function subcarpeta_(raiz, nombre) {
  const it = raiz.getFoldersByName(nombre);
  return it.hasNext() ? it.next() : raiz.createFolder(nombre);
}

function reemplazar_(carpeta, nombre) {
  const it = carpeta.getFilesByName(nombre);
  while (it.hasNext()) it.next().setTrashed(true);
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
