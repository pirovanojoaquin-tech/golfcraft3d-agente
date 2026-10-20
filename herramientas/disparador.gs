/**
 * GolfCraft3D — despertador del publicador.
 *
 * GitHub no siempre respeta los horarios programados en cuentas gratis. Este script, con un
 * activador de Google cada 15 minutos, le pide a GitHub que corra "Publicar en Instagram".
 * Va en el mismo proyecto de Apps Script que guardar_en_drive.gs (archivo aparte).
 *
 * GITHUB_TOKEN: token fine-grained de GitHub con acceso SOLO al repo golfcraft3d-agente y
 * permiso "Actions: Read and write". No lo compartas.
 */

const GITHUB_TOKEN = 'PEGAR_ACA_EL_TOKEN';
const WORKFLOW = 'https://api.github.com/repos/pirovanojoaquin-tech/golfcraft3d-agente/actions/workflows/publicar.yml/dispatches';

function dispararPublicacion() {
  const r = UrlFetchApp.fetch(WORKFLOW, {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + GITHUB_TOKEN, Accept: 'application/vnd.github+json' },
    payload: JSON.stringify({ ref: 'main', inputs: { modo: 'publicar' } }),
    muteHttpExceptions: true,
  });
  if (r.getResponseCode() !== 204) {
    throw new Error('GitHub respondió ' + r.getResponseCode() + ': ' + r.getContentText());
  }
}
