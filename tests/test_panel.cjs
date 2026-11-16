// Panel smoke test without CEP: panel.js runs against a tiny fake DOM. Checks that it is still
// plain ES5, that a result renders (proposals, unrecognised sound, gaps, pauses, warnings) and that
// ticking a row sends the decision to /plan.
const assert = require('assert/strict'), fs = require('fs'), path = require('path'), vm = require('vm');
const file = path.join(__dirname, '..', 'extension', 'panel.js'), code = fs.readFileSync(file, 'utf8');
assert.ok(!/=>|`|\b(?:let|const|class|async|await)\s/.test(code), 'panel.js must stay ES5 (CEP 7)');
const html = fs.readFileSync(path.join(__dirname, '..', 'extension', 'index.html'), 'utf8');
const ids = new Set(Array.from(html.matchAll(/id="([^"]+)"/g), m => m[1]));
for (const m of code.matchAll(/\$\('([^']+)'\)/g)) assert.ok(ids.has(m[1]), 'index.html has no #' + m[1]);

function node(tag) {
  const e = {tag, children: [], style: {}, className: '', hidden: false, checked: false, disabled: false, value: '',
    appendChild(c) { e.children.push(c); return c; }, setAttribute() {}, pause() {}, load() {}, click() {},
    querySelectorAll() { return []; }};
  let text = '';
  Object.defineProperty(e, 'textContent', {get: () => text + e.children.map(c => c.textContent || '').join(''),
    set: v => { text = String(v); e.children = []; }});
  return e;
}
const elements = {}, requests = [], timers = [];
const document = {getElementById: id => elements[id] || (elements[id] = node(id)), createElement: node,
  createTextNode: t => ({textContent: String(t)})};
['pauses', 'breaths', 'titles', 'shift', 'backup', 'titles-off', 'auto-apply'].forEach(id => { document.getElementById(id).checked = true; });
const fakeHttp = {request(options, onResponse) {
  const req = {on() {}, setTimeout() {}, abort() {}, end(body) {
    requests.push({path: options.path, body: body ? JSON.parse(body) : null});
    const handlers = {}, res = {headers: {'content-type': 'application/json'}, setEncoding() {}, on(name, fn) { handlers[name] = fn; }};
    onResponse(res);
    const reply = options.path === '/health' ? {ok: true, version: context.VERSION} : plan(false);
    handlers.data(JSON.stringify(reply)); handlers.end();
  }};
  return req;
}};
const fakeFs = Object.assign({}, fs, {readFileSync: (name, enc) => /\.runtime\.json$/.test(name) ? JSON.stringify({port: 1, token: 't', pid: 1}) : fs.readFileSync(name, enc)});
const window = {location: {pathname: '/' + file.replace(/\\/g, '/')}, SVEPanelError: e => { throw e; }};
const context = {window, document, console, Promise, JSON, Math, Number, String, Array, Object, Error, Date, URL, Blob: function () {},
  require: name => name === 'http' ? fakeHttp : name === 'fs' ? fakeFs : require(name), Buffer, process,
  setTimeout: (fn, ms) => { timers.push(fn); return timers.length; }, clearTimeout() {}, setInterval() {}, decodeURIComponent, encodeURI};
vm.createContext(context); vm.runInContext(code, context);
assert.equal(window.SVEPanelReady, true);

function junction(id, kind, extra) {
  return Object.assign({id, kind, start: 5, end: 6, pause: .5, silence: 1.2, breath: 0, sound: 0, tight: false, enabled: true,
    forced: false, default: true, context: 'Gap oxiri', left_word: 'loyiha', right_word: 'yoshlar'}, extra);
}
function plan(unheardOn) {
  return {ranges: [{start: 0, end: 5}, {start: 6, end: 20}], lead_gap: 0, lead_label: '', tail_label: '', item_junction: {i0: 'j3'},
    junctions: [junction('j1', 'pause', {breath: .3}), junction('j2', 'unheard', {sound: 1.7, enabled: unheardOn, default: false}),
      junction('j3', 'retake', {forced: true, tight: true}), junction('j4', 'stumble', {sound: .2}),
      junction('j5', 'gap', {forced: true, gap: 'g0'}), junction('tail', 'edge', {sound: 1.1, enabled: false, default: false})],
    stats: {kept_seconds: 19, removed_seconds: 1, gap_seconds: 4, result_seconds: 23, pauses: 1, breaths: 1, unheard: 2, cuts: 4},
    preview: 'x.wav', map: {}};
}
const result = {session: 's1', pause_only: false, duration: 20, language: 'uz', coverage: .93, low_coverage: false, outside_script_words: 0,
  model: 'Kotib', device: 'cpu', cache: false, elapsed_seconds: 3, transcript: 'bugun yangi', missing: [], original_preview: 'o.wav',
  items: [{id: 'i0', kind: 'repeat', text: 'yangi loyiha', start: 1, end: 2, selected: true, review: false, reason: 'Qayta o‘qilgan joy'}],
  gaps: [{id: 'g0', label: 'СНХР: Ali', seconds: 4}, {id: 'g1', label: 'Стендап', seconds: 9}], lead_gap: null, tail: [], plan: plan(false)};
context.show(result, 'Tayyor');
const rows = elements.items.children.map(c => c.textContent);
assert.equal(rows.length, 4, rows.join('\n'));                       // 1 proposal + unheard + stumble + tail edge
assert.match(rows[1], /Saqlanadi · Tanilmagan tovush/); assert.match(rows[2], /Kesiladi · Tanilmagan qisqa tovush/);
assert.match(rows[3], /oxirida/); assert.match(elements['item-count'].textContent, /2 ta kesiladi/);
assert.match(elements.warning.textContent, /2 ta joyda tanilmagan tovush/); assert.equal(elements.warning.hidden, false);
assert.match(elements['apply-status'].textContent, /1 tasi uzluksiz nutq ichida/);
const gaps = elements.gaps.children.map(c => c.textContent);
assert.equal(gaps.length, 2); assert.match(gaps[1], /Joyi topilmadi.*Стендап/);
assert.match(elements['pause-count'].textContent, /1 ta qisqartiriladi, 1 tasida nafas/);

// Ticking the unrecognised sound asks the backend for a new plan with that decision.
const check = elements.items.children[1].children[0].children[0];
check.checked = true; check.onchange();
timers.pop()();
setImmediate(() => setImmediate(() => {
  const sent = requests.filter(r => r.path === '/plan').pop();
  assert.ok(sent, 'no /plan request'); assert.equal(sent.body.decisions.j2, true); assert.equal(sent.body.session, 's1');
  assert.deepEqual(Object.assign({}, sent.body.options), {pauses: true, breaths: true, crossfade: false});

  // A recording that does not match the script is called out.
  context.show(Object.assign({}, result, {coverage: .21, low_coverage: true}), 'Tayyor');
  assert.match(elements.warning.textContent, /DIQQAT.*21%/);
  console.log('Panel: ES5, element ids, rendering of proposals/unrecognised sound/gaps/pauses, warnings and re-planning passed');
}));
