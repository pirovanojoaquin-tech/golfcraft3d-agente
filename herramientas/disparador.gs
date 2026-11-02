/**
 * GolfCraft3D — despertador del publicador.
 *
 * GitHub no siempre respeta los horarios programados en cuentas gratis. Este script, con un
 * activador de Google cada 15 minutos, le pide a GitHub que corra "Publicar en Instagram".
 * Va en el mismo proyecto de Apps Script que guardar_en_drive.gs (archivo aparte).
 *
 * GITHUB_TOKEN: token fine-grained de GitHub con acceso a los repos golfcraft3d-agente e impronta3d-agente
 * y permiso "Actions: Read and write". No lo compartas.
 */

const GITHUB_TOKEN = 'PEGAR_ACA_EL_TOKEN';
// Una entrada por marca: el despertador publica las dos (GolfCraft3D e Impronta 3D)
const WORKFLOWS = [
  'https://api.github.com/repos/pirovanojoaquin-tech/golfcraft3d-agente/actions/workflows/publicar.yml/dispatches',
  'https://api.github.com/repos/pirovanojoaquin-tech/impronta3d-agente/actions/workflows/publicar.yml/dispatches',
];
// dispararML_ (en guardar_en_drive.gs) usa esta: Mercado Libre de GolfCraft3D
const WORKFLOW = WORKFLOWS[0];

function dispararPublicacion() {
  const errores = [];
  WORKFLOWS.forEach(function (url) {
    const r = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: { Authorization: 'Bearer ' + GITHUB_TOKEN, Accept: 'application/vnd.github+json' },
      payload: JSON.stringify({ ref: 'main', inputs: { modo: 'publicar' } }),
      muteHttpExceptions: true,
    });
    if (r.getResponseCode() !== 204) errores.push(url.split('/')[5] + ': GitHub respondió ' + r.getResponseCode());
  });
  // si una marca falla, la otra igual se publica
  if (errores.length) throw new Error(errores.join(' | '));
}
