/**
 * GolfCraft3D — guarda en Google Drive los archivos 3D que aprueba el agente.
 *
 * Se instala una sola vez en https://script.google.com (ver README, "Google Drive").
 * Corre con TU cuenta de Google, así que los archivos quedan en TU Drive.
 * Solo acepta descargas de los sitios de modelos 3D de la lista.
 *
 * También:
 *  - escribe la planilla "GolfCraft3D · Mercado Libre" (la crea sola en la carpeta la primera vez);
 *  - recibe las notificaciones de Mercado Libre (ventas, preguntas) y despierta a GitHub al instante;
 *  - es la página a la que vuelve Mercado Libre cuando autorizás la app (doGet).
 * Usa GITHUB_TOKEN y dispararML_ de disparador.gs (mismo proyecto).
 */

const CARPETA_ID = '1d7j56w2Qh00IbWcfqnolZ9tt-Goz-UY5';  // PRODUCTOS 3D GOLF
const SITIOS_PERMITIDOS = ['files.printables.com', 'media.printables.com', 'raw.githubusercontent.com',
                           'cdn.thingiverse.com', 'cdn.thingiverse.net'];
const MAX_MB = 50;

function doPost(e) {
  try {
    const pedido = JSON.parse(e.postData.contents);
    if (pedido.topic && pedido.resource) return notificacionML_(pedido);
    if (pedido.accion === 'planilla') return json_(planilla_(pedido));
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

// ---------- Mercado Libre ----------

function notificacionML_(n) {
  // ML puede mandar la misma notificación varias veces: se procesa una sola vez por hora
  const cache = CacheService.getScriptCache();
  const clave = 'ml:' + n.topic + ':' + n.resource;
  if (!cache.get(clave)) {
    cache.put(clave, '1', 3600);
    dispararML_({ accion: 'evento', topic: String(n.topic), recurso: String(n.resource) });
  }
  return json_({ ok: true });
}

function doGet(e) {
  const codigo = e && e.parameter && e.parameter.code;
  if (!codigo) return HtmlService.createHtmlOutput('GolfCraft3D');
  dispararML_({ accion: 'autorizar', codigo: String(codigo) });
  return HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;text-align:center;margin-top:80px">' +
    '<h2>¡Listo!</h2><p>Mercado Libre quedó conectado con GolfCraft3D.<br>' +
    'En un minuto te llega la confirmación por Telegram. Ya podés cerrar esta pestaña.</p></div>');
}

function planilla_(p) {
  const libro = libroML_();
  let hoja = libro.getSheetByName(p.pestania);
  if (!hoja) {
    hoja = libro.insertSheet(p.pestania);
    hoja.appendRow(p.columnas);
    hoja.getRange(1, 1, 1, p.columnas.length).setFontWeight('bold').setBackground('#016040').setFontColor('#ffffff');
    hoja.setFrozenRows(1);
    const vacia = libro.getSheetByName('Hoja 1') || libro.getSheetByName('Sheet1');
    if (vacia && libro.getSheets().length > 1) libro.deleteSheet(vacia);
  }
  const fila = p.columnas.map(function (c) { return p.fila[c] === undefined ? '' : p.fila[c]; });
  const claves = hoja.getLastRow() > 1 ? hoja.getRange(2, 1, hoja.getLastRow() - 1, 1).getValues() : [];
  for (let i = 0; i < claves.length; i++) {
    if (String(claves[i][0]) === String(p.clave)) {
      hoja.getRange(i + 2, 1, 1, fila.length).setValues([fila]);
      return { ok: true, nuevo: false, url: libro.getUrl() };
    }
  }
  hoja.appendRow(fila);
  return { ok: true, nuevo: true, url: libro.getUrl() };
}

function libroML_() {
  const props = PropertiesService.getScriptProperties();
  const id = props.getProperty('PLANILLA_ML');
  if (id) return SpreadsheetApp.openById(id);
  const libro = SpreadsheetApp.create('GolfCraft3D · Mercado Libre');
  DriveApp.getFileById(libro.getId()).moveTo(DriveApp.getFolderById(CARPETA_ID));
  props.setProperty('PLANILLA_ML', libro.getId());
  return libro;
}
