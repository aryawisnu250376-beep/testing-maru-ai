const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const projectRoot = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(projectRoot, 'app/web/index.html'), 'utf8');
const inlineScript = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(inlineScript, 'inline script exists');

const context2d = {
  font: '8px sans-serif', textAlign: 'left', textBaseline: 'alphabetic',
  beginPath() {}, closePath() {}, moveTo() {}, lineTo() {}, quadraticCurveTo() {},
  bezierCurveTo() {}, arc() {}, ellipse() {}, fill() {}, stroke() {},
  fillRect() {}, clearRect() {}, drawImage() {}, save() {}, restore() {},
  roundRect() {}, fillText() {},
  createLinearGradient() { return {addColorStop() {}}; },
  createRadialGradient() { return {addColorStop() {}}; },
  measureText(text) { return {width: String(text).length * 4}; }
};
const elements = new Map();
function getElement(id) {
  if (!elements.has(id)) {
    elements.set(id, {
      id, value: '', textContent: '', innerHTML: '', className: '', options: [], files: [], style: {}, dataset: {},
      hidden: false, disabled: false,
      classList: {contains: () => false, add() {}, remove() {}},
      getContext: () => context2d, addEventListener() {}, appendChild() {}, append() {},
      focus() {}, scrollIntoView() {}, requestSubmit() {}, remove() {}
    });
  }
  return elements.get(id);
}
class MockImage { set src(value) { this._src = value; } }
// Fixed clock: the office sim reads the real time at load (shift + prayer state).
// Pinning it to a work hour keeps navigation/rendering tests deterministic.
const FIXED_EPOCH_MS = Date.parse('2026-01-15T09:00:00+07:00');
class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [FIXED_EPOCH_MS])); }
  static now() { return FIXED_EPOCH_MS; }
}
const sandbox = {
  Image: MockImage,
  document: {getElementById: getElement, createElement: () => getElement('created')},
  sessionStorage: {getItem: () => null, setItem() {}, removeItem() {}},
  performance: {now: () => 0},
  requestAnimationFrame: () => 0,
  Intl, Date: FixedDate, Math, Map, Set, Object, Array, String, Number, Boolean, JSON, Promise,
  URLSearchParams, console,
  fetch: () => Promise.reject(new Error('network disabled in UI tests')),
  confirm: () => false,
  FormData: class { append() {} }
};
vm.createContext(sandbox);
vm.runInContext(`${inlineScript}\nglobalThis.__ui = {
  jobStageMeta, settingsGroups, ANSWER_PRESET_VALUES, videoDownloadUrl
};`, sandbox, {timeout: 10000});
const ui = sandbox.__ui;
const j = value => JSON.stringify(value);

// Job stage helpers drive the progress bar for summary/quiz jobs.
assert.equal(j(ui.jobStageMeta('queued')), '["Menunggu giliran…",5]');
assert.equal(j(ui.jobStageMeta('retrieve')), '["Mencari materi…",30]');
assert.equal(j(ui.jobStageMeta('draft')), '["Menyusun jawaban…",68]');
assert.equal(j(ui.jobStageMeta('verify')), '["Memverifikasi…",87]');
assert.equal(j(ui.jobStageMeta('done')), '["Selesai",100]');
assert.equal(j(ui.jobStageMeta('failed')), '["Gagal",100]');
assert.equal(j(ui.jobStageMeta('misterius')), '["Bekerja…",50]');

// Settings grouping splits runtime keys from restart keys.
const snapshot = {
  values: {RAG_TOP_K: '6', WEB_PORT: '8000', LOCAL_API_TOKEN: '***'},
  meta: {
    RAG_TOP_K: {runtime: true, secret: false},
    WEB_PORT: {runtime: false, secret: false},
    LOCAL_API_TOKEN: {runtime: true, secret: true}
  }
};
assert.equal(j(ui.settingsGroups(snapshot)), '{"runtime":["RAG_TOP_K","LOCAL_API_TOKEN"],"restart":["WEB_PORT"]}');
assert.equal(j(ui.settingsGroups({values: {}, meta: {}})), '{"runtime":[],"restart":[]}');

// Answer presets match the backend ANSWER_PRESETS.
assert.equal(j(Object.keys(ui.ANSWER_PRESET_VALUES)), '["singkat","seimbang","mendalam"]');
assert.equal(j(ui.ANSWER_PRESET_VALUES.mendalam), '{"RAG_TOP_K":"10","MAX_OUTPUT_TOKENS":"2500"}');

// New UI hooks exist in the markup.
for (const id of ['jobProgress', 'jobProgressFill', 'jobProgressLabel', 'exportBtn', 'settingsForm', 'settingsSave', 'settingsReload', 'settingsStatus', 'preset', 'videoBtn']) {
  assert.ok(html.includes(`id="${id}"`), `${id} exists in markup`);
}

assert.equal(ui.videoDownloadUrl('abc 123'), '/api/videos/abc%20123/download');

console.log('UI_HELPERS_OK');
