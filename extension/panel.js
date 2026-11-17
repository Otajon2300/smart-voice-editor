/* Smart Voice Editor panel. ES5 + Promise only (CEP 7 / Premiere 2017 and newer).
   Speech recognition and audio stay on this computer. */
var nodeRequire = typeof require === 'function' ? require : (window.cep_node && window.cep_node.require);
if (!nodeRequire) throw Error('Panelning mahalliy modullari yuklanmadi. Premiere va panelni qayta oching.');
var fs = nodeRequire('fs'), path = nodeRequire('path'), http = nodeRequire('http'), child = nodeRequire('child_process');
var NodeBuffer = (window.cep_node && window.cep_node.Buffer) || (typeof Buffer !== 'undefined' ? Buffer : nodeRequire('buffer').Buffer);
var VERSION = '1.1.7';
var panelDirectory = path.dirname(decodeURIComponent(window.location.pathname).replace(/^\/(?=[A-Za-z]:)/, ''));
var root = path.dirname(fs.realpathSync(panelDirectory));
var L = window.SVEi18n, t = L.t, tr = L.tr;
var KIND = {repeat: 'kindRepeat', outside: 'kindOutside', between: 'kindBetween', uncertain: 'kindUncertain'};
var UNHEARD = .35; // seconds of unrecognised sound that the backend never cuts without being asked

var clip = null, scripts = [], analysis = null, plan = null, decisions = {}, gapSettings = {}, busy = false;
var lastError = null, planTimer = null, planPending = null, planSeq = 0, planLatest = null, stopAt = null, loaded = null, sourceUrl = null, running = null;
var CONTROLS = ['select', 'pick-script', 'no-script', 'analyze', 'mode', 'language', 'use-gpu', 'strict', 'pauses', 'breaths', 'auto-apply', 'ui-language'];

function $(id) { return document.getElementById(id); }
function each(list, fn) { Array.prototype.forEach.call(list, fn); }
function element(tag, className, text) { var e = document.createElement(tag); if (className) e.className = className; if (text !== undefined) e.textContent = text; return e; }
function fmt(s) { var m = Math.floor(s / 60), r = s - m * 60; return m + ':' + (r < 10 ? '0' : '') + r.toFixed(1); }

/* ------------------------------------------------------------ Premiere host */
function host(method, payload, timeout) {
 return new Promise(function (resolve, reject) {
  if (!window.__adobe_cep__) return reject(Error(t('openInPremiere')));
  var timer = timeout ? setTimeout(function () { reject(Error(t('premiereNoAnswer'))); }, timeout) : null;
  window.__adobe_cep__.evalScript('SVE.' + method + '(' + JSON.stringify(JSON.stringify(payload || {})) + ')', function (value) {
   if (timer) clearTimeout(timer);
   try {
    if (!value || value === 'EvalScript error.') throw Error(t('hostNotLoaded'));
    var data = JSON.parse(value);
    if (data.error) { var error = Error(data.error); error.details = data.details; throw error; }
    resolve(data);
   } catch (e) { reject(e); }
  });
 });
}
function loadHost() {
 return new Promise(function (resolve, reject) {
  if (!window.__adobe_cep__) return reject(Error(t('openInPremiere')));
  var timer = setTimeout(function () { reject(Error(t('hostNoAnswer'))); }, 20000);
  var file = path.join(root, 'extension', 'host.jsx').replace(/\\/g, '/');
  var code = '(function(){try{$.evalFile(new File(' + JSON.stringify(file) + '));return typeof SVE!=="undefined"&&SVE.version===' + JSON.stringify(VERSION) + '?"SVE_READY":"SVE_MISSING";}catch(e){return "SVE_ERROR: "+e.toString();}})()';
  window.__adobe_cep__.evalScript(code, function (value) { clearTimeout(timer); if (value === 'SVE_READY') resolve(); else reject(Error(t('hostState', value))); });
 });
}

/* ------------------------------------------------------------ backend */
function request(config, route, body, onProgress, timeout, hold) {
 return new Promise(function (resolve, reject) {
  var data = body ? JSON.stringify(body) : null, done = false;
  var headers = {Authorization: 'Bearer ' + config.token};
  if (data) { headers['Content-Type'] = 'application/json'; headers['Content-Length'] = NodeBuffer.byteLength(data); }
  function finish(fn, value) { if (!done) { done = true; fn(value); } }
  var req = http.request({hostname: '127.0.0.1', port: config.port, path: route, method: data ? 'POST' : 'GET', headers: headers}, function (res) {
   res.setEncoding('utf8');
   var buffer = '', result = null, failure = null, streamed = (res.headers['content-type'] || '').indexOf('ndjson') !== -1;
   res.on('data', function (chunk) {
    buffer += chunk; if (!streamed) return; var at;
    while ((at = buffer.indexOf('\n')) !== -1) {
     var line = buffer.slice(0, at); buffer = buffer.slice(at + 1);
     try { var event = JSON.parse(line); if (event.progress && onProgress) onProgress(event.progress); if (event.result) result = event.result; if (event.error) failure = Error(event.error); }
     catch (e) { failure = Error(t('backendBroken')); }
    }
   });
   res.on('aborted', function () { finish(reject, Error(t('backendLost'))); });
   res.on('end', function () {
    try {
     if (failure) throw failure;
     if (!streamed) result = JSON.parse(buffer);
     if (!result) throw Error(t('backendPartial'));
     if (result.error) throw Error(result.error);
     finish(resolve, result);
    } catch (e) { finish(reject, e); }
   });
  });
  req.on('error', function (e) { finish(reject, e); });
  // Closing the connection makes the backend stop at its next progress message.
  if (hold) hold.cancel = function () { finish(reject, Error(t('cancelled'))); try { req.abort(); } catch (ignored) {} };
  if (timeout) req.setTimeout(timeout, function () { req.abort(); finish(reject, Error(t('backendSilent'))); });
  req.end(data);
 });
}
function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
function readConfig() { return JSON.parse(fs.readFileSync(path.join(root, '.runtime.json'), 'utf8')); }
// The offline installer brings its own Python in "runtime"; a source installation has ".venv".
function pythonPath(windowless) {
 var places = [path.join(root, 'runtime'), path.join(root, '.venv', 'Scripts')], i;
 for (i = 0; i < places.length; i++) {
  var names = windowless ? ['pythonw.exe', 'python.exe'] : ['python.exe'];
  for (var k = 0; k < names.length; k++) if (fs.existsSync(path.join(places[i], names[k]))) return path.join(places[i], names[k]);
 }
 return null;
}
function startBackend() {
 var python = pythonPath(true);
 if (!python) throw Error(t('runSetup'));
 $('progress').textContent = t('backendStarting');
 ['backend.log', 'backend-error.log'].forEach(function (name) {
  // Logs grow with every analysis: keep one previous file once a log passes 2 MB.
  var file = path.join(root, name);
  try { if (fs.statSync(file).size > 2 * 1024 * 1024) { try { fs.unlinkSync(file + '.1'); } catch (ignored) {} fs.renameSync(file, file + '.1'); } } catch (ignored) {}
 });
 var log = fs.openSync(path.join(root, 'backend.log'), 'a'), err = fs.openSync(path.join(root, 'backend-error.log'), 'a');
 // -s: packages from the user's own Python folder must not mix with the program's.
 var proc = child.spawn(python, ['-s', path.join(root, 'backend', 'server.py')], {cwd: root, windowsHide: true, detached: true, stdio: ['ignore', log, err]});
 proc.unref(); fs.closeSync(log); fs.closeSync(err);
 var attempt = 0;
 function poll() {
  return wait(500).then(function () {
   var c = readConfig();
   return request(c, '/health', null, null, 2000).then(function (h) { if (h.version !== VERSION) throw Error('old'); return c; });
  }).catch(function () {
   if (++attempt >= 90) throw Error(t('backendNotStarted'));
   return poll();
  });
 }
 return poll();
}
function connection() {
 var config = null;
 try { config = readConfig(); } catch (e) { config = null; }
 if (!config) return startBackend();
 return request(config, '/health', null, null, 3000).then(function (health) {
  if (health.version === VERSION) return config;
  // An older backend is still running: stop it, then start this version.
  $('progress').textContent = t('stoppingOld', health.version);
  try { process.kill(config.pid); } catch (e) {}
  return wait(1500).then(startBackend);
 }, function () { return startBackend(); });
}

/* ------------------------------------------------------------ plan */
function currentOptions() { return {pauses: $('pauses').checked, breaths: $('breaths').checked, crossfade: $('crossfade').checked}; }
function refreshPlan(render) {
 if (!analysis) return Promise.resolve(null);
 var body = {session: analysis.session, decisions: decisions, gaps: gapSettings, options: currentOptions(), render: !!render};
 // Answers may arrive out of order: only the newest request may replace the plan.
 var seq = ++planSeq;
 var pending = connection().then(function (config) { return request(config, '/plan', body, null, 120000); }).then(function (result) {
  if (seq !== planSeq) { if (planLatest && planLatest !== pending) return planLatest; throw Error(t('planChanged')); }
  plan = result; loaded = render ? null : loaded; renderAll(); return result;
 });
 planLatest = pending;
 return pending;
}
// The backend exits after 30 idle minutes; listening makes no requests, so keep the open analysis alive.
setInterval(function () {
 if (!analysis || busy) return;
 try { request(readConfig(), '/health', null, null, 3000).catch(function () {}); } catch (ignored) {}
}, 5 * 60 * 1000);
function schedulePlan() {
 if (planTimer) clearTimeout(planTimer);
 plan.stale = true; ready();
 planTimer = setTimeout(function () {
  planTimer = null;
  planPending = refreshPlan(false).catch(function (e) { lastError = e.message; ready(); });
 }, 250);
}
function freshPlan(render) {
 var waitFor = planPending || Promise.resolve();
 if (planTimer) { clearTimeout(planTimer); planTimer = null; }
 return waitFor.then(function () { return (plan && !plan.stale && (!render || plan.preview)) ? plan : refreshPlan(render); });
}

/* ------------------------------------------------------------ listening */
function loadAudio(file) {
 var player = $('player');
 if (loaded === file) return Promise.resolve(player);
 return new Promise(function (resolve, reject) {
  if (sourceUrl) { URL.revokeObjectURL(sourceUrl); sourceUrl = null; }
  var stamp = 0; try { stamp = fs.statSync(file).mtime.getTime(); } catch (ignored) {}
  var direct = 'file:///' + encodeURI(file.replace(/\\/g, '/')).replace(/#/g, '%23').replace(/\?/g, '%3F') + '?t=' + stamp;
  function fromMemory() {
   // Fallback for a CEP version that refuses file URLs.
   try { sourceUrl = URL.createObjectURL(new Blob([fs.readFileSync(file)], {type: 'audio/wav'})); }
   catch (e) { return reject(Error(t('audioFailedBecause', e.message))); }
   player.onerror = function () { player.onerror = null; reject(Error(t('audioFailed'))); };
   player.src = sourceUrl; player.load();
  }
  player.oncanplay = function () { player.oncanplay = null; player.onerror = null; loaded = file; resolve(player); };
  player.onerror = function () { player.onerror = null; fromMemory(); };
  player.src = direct; player.load();
 });
}
function play(file, from, to, label) {
 var player = $('player'); player.pause(); stopAt = null;
 return loadAudio(file).then(function () {
  player.currentTime = Math.max(0, from); stopAt = to === undefined ? null : to;
  $('now').textContent = label;
  var promise = player.play(); if (promise && promise.catch) promise.catch(function (e) { $('now').textContent = e.message; });
 });
}
setInterval(function () { var p = $('player'); if (stopAt !== null && !p.paused && p.currentTime >= stopAt) { p.pause(); stopAt = null; } }, 20);
function playOriginal(start, end) { play(analysis.original_preview, start - .8, end + .8, t('originalAt', fmt(start), fmt(end))); }
function playJoin(junction, fallback) {
 freshPlan(true).then(function (p) {
  var at = junction === 'lead' ? p.lead_gap : (p.map || {})[junction];
  if (at === undefined) { if (fallback !== undefined) playOriginal(fallback, fallback); return; }
  return play(p.preview, at - 2.5, at + 2.5, t('resultAround', fmt(at)));
 }).catch(function (e) { $('now').textContent = t('error', tr(e.message)); });
}

/* ------------------------------------------------------------ rendering */
function chosen(item) { return decisions.hasOwnProperty(item.id) ? decisions[item.id] : item.selected; }
function renderSummary() {
 var a = analysis, s = plan ? plan.stats : null, text;
 if (a.pause_only) text = t('pauseMode');
 else {
  text = t('coverage', t(a.language === 'ru' ? 'languageRu' : a.language === 'en' ? 'languageEn' : 'languageUz'), (a.coverage * 100).toFixed(1));
  if (a.outside_script_words > 30) text += t('outsideIgnored');
 }
 $('summary').textContent = text;
 var warning = '';
 if (a.low_coverage) warning = t('lowCoverage', (a.coverage * 100).toFixed(0));
 else if (s && s.unheard) warning = t('unheardWarning', s.unheard);
 $('warning').textContent = warning; $('warning').hidden = !warning;
 $('stats').textContent = (s ? fmt(a.duration) + ' → ' + fmt(s.result_seconds) + ' · ' + s.removed_seconds.toFixed(1) + t('removedSeconds') +
  (s.gap_seconds ? ' · ' + s.gap_seconds.toFixed(0) + t('gapSeconds') : '') + (s.space_seconds ? ' · ' + t('breathSpace', s.space_seconds.toFixed(1)) : '') + ' · ' : '') +
  (a.model || '') + (a.cache ? ' · ' + t('savedAnalysis') : a.device ? ' · ' + String(a.device).toUpperCase() : '') + ' · ' + a.elapsed_seconds + ' s';
}
function renderItems() {
 var box = $('items'); box.textContent = '';
 var showFree = $('show-uncertain').checked, shown = 0, cut = 0;
 analysis.items.forEach(function (item) {
  var on = chosen(item);
  if (on) cut++;
  if (item.kind === 'uncertain' && !showFree && !on) return;
  shown++;
  var row = element('div', 'candidate' + (on ? ' selected' : '') + (item.review ? ' review' : ''));
  var label = element('label', 'check'), check = element('input'); check.type = 'checkbox'; check.checked = on;
  check.onchange = function () { decisions[item.id] = check.checked; renderItems(); schedulePlan(); };
  label.appendChild(check); label.appendChild(document.createTextNode(t(on ? 'cut' : 'kept') + ' · ' + (KIND[item.kind] ? t(KIND[item.kind]) : item.kind) + ' · ' + fmt(item.start)));
  row.appendChild(label); row.appendChild(element('div', 'words', item.text)); row.appendChild(element('div', 'muted', tr(item.reason || '')));
  var times = element('div', 'times'), a = element('button', '', t('listenOriginal')), b = element('button', '', t('result'));
  a.onclick = function () { playOriginal(item.start, item.end); };
  b.onclick = function () { playJoin(plan && plan.item_junction ? plan.item_junction[item.id] : null, item.start); };
  times.appendChild(a); times.appendChild(b); row.appendChild(times); box.appendChild(row);
 });
 // Sound the ASR did not write down: never cut silently, always listed.
 (plan ? plan.junctions : []).forEach(function (j) {
  if (!soundJunction(j)) return;
  shown++; if (j.enabled) cut++;
  box.appendChild(junctionRow(j, t(j.enabled ? 'cut' : 'kept') + ' · ' + soundTitle(j) + ' · ' + fmt(j.start),
   j.kind === 'edge' ? t(j.id === 'lead' ? 'recordingStart' : 'recordingEnd') : t('between', j.left_word || '', j.right_word || ''),
   j.aside ? t('asideNote', j.sound.toFixed(2)) : j.default ? t('stumbleNote') : t('unheardNote', j.sound.toFixed(2)), !j.default));
 });
 if (!shown) box.appendChild(element('div', 'muted', t('noRetakes')));
 $('item-count').textContent = t('willCut', cut);
}
function soundJunction(j) { return !j.forced && (j.kind === 'unheard' || j.kind === 'stumble' || (j.kind === 'edge' && j.sound >= UNHEARD)); }
function soundTitle(j) { return t(j.kind === 'stumble' ? 'shortSound' : 'unknownSound'); }
function junctionRow(j, title, words, note, review) {
 var row = element('div', 'candidate' + (j.enabled ? ' selected' : '') + (review ? ' review' : ''));
 var label = element('label', 'check'), check = element('input'); check.type = 'checkbox'; check.checked = j.enabled;
 check.onchange = function () { decisions[j.id] = check.checked; schedulePlan(); };
 label.appendChild(check); label.appendChild(document.createTextNode(title + (j.tight ? t('tight') : '')));
 row.appendChild(label); row.appendChild(element('div', 'words', words)); if (note) row.appendChild(element('div', 'muted', note));
 var times = element('div', 'times'), a = element('button', '', t('listenOriginal')), b = element('button', '', t('result'));
 a.onclick = function () { playOriginal(j.start, j.end); }; b.onclick = function () { playJoin(j.id, j.start); };
 times.appendChild(a); times.appendChild(b); row.appendChild(times);
 return row;
}
function gapRow(gap, isLead) {
 var setting = gapSettings[gap.id] || {}, enabled = setting.enabled !== false, seconds = setting.seconds !== undefined ? setting.seconds : gap.seconds;
 var row = element('div', 'candidate gap' + (enabled ? ' selected' : ''));
 var label = element('label', 'check'), check = element('input'); check.type = 'checkbox'; check.checked = enabled;
 check.onchange = function () { gapSettings[gap.id] = {enabled: check.checked, seconds: Math.max(0, Math.min(300, Number(input.value) || 0))}; renderGaps(); schedulePlan(); };
 label.appendChild(check); label.appendChild(document.createTextNode(t(isLead ? 'leadGap' : 'gap')));
 row.appendChild(label); row.appendChild(element('div', 'words', tr(gap.label)));
 var times = element('div', 'times'), input = element('input'); input.type = 'number'; input.min = 0; input.max = 300; input.step = 1; input.value = seconds;
 input.onchange = function () { gapSettings[gap.id] = {enabled: check.checked, seconds: Math.max(0, Math.min(300, Number(input.value) || 0))}; schedulePlan(); };
 times.appendChild(element('span', 'muted', t('seconds'))); times.appendChild(input);
 if (!isLead && plan) {
  var junction = null; plan.junctions.forEach(function (j) { if (j.gap === gap.id) junction = j.id; });
  if (junction) { var b = element('button', '', t('result')); b.onclick = function () { playJoin(junction); }; times.appendChild(b); }
 }
 row.appendChild(times); return row;
}
function renderGaps() {
 var box = $('gaps'); box.textContent = '';
 var list = analysis.gaps || [], lead = analysis.lead_gap, located = {};
 if (plan) plan.junctions.forEach(function (j) { if (j.gap) located[j.gap] = true; });
 $('gaps-section').hidden = !list.length && !lead && !(analysis.tail && analysis.tail.length);
 if (lead) box.appendChild(gapRow(lead, true));
 list.forEach(function (gap) {
  if (!plan || located[gap.id] || (gapSettings[gap.id] && gapSettings[gap.id].enabled === false)) box.appendChild(gapRow(gap, false));
  else box.appendChild(element('div', 'muted', t('gapNotFound', tr(gap.label))));
 });
 if (analysis.tail && analysis.tail.length) box.appendChild(element('div', 'muted', t('atEnd', tr(analysis.tail.join(' + ')))));
 var total = 0; each(box.querySelectorAll('.gap.selected input[type=number]'), function (i) { total += Number(i.value) || 0; });
 $('gap-count').textContent = list.length || lead ? '(' + total.toFixed(0) + ' s)' : '';
}
function renderPauses() {
 var box = $('pause-list'); box.textContent = '';
 var pauses = plan ? plan.junctions.filter(function (j) { return j.kind === 'pause'; }) : [];
 var breaths = pauses.filter(function (j) { return j.breath >= .1; }).length;
 $('pause-count').textContent = t('pauseCount', pauses.filter(function (j) { return j.enabled; }).length, breaths);
 if (!$('show-pauses').checked) return;
 pauses.forEach(function (j) {
  box.appendChild(junctionRow(j, (j.context ? tr(j.context) : t('pause')) + ' · ' + j.silence.toFixed(2) + ' s → ' + (j.pause || 0).toFixed(2) + ' s' + (j.breath >= .1 ? t('breath', j.breath.toFixed(2)) : ''),
   '«' + (j.left_word || '') + ' … ' + (j.right_word || '') + '»', '', false));
 });
}
function renderAll() { if (!analysis) return; renderSummary(); renderItems(); renderGaps(); renderPauses(); ready(); }
function ready() {
 var allowed = !busy && analysis && plan && !plan.stale;
 each($('results').querySelectorAll('input,button'), function (e) { if (e.id !== 'apply') e.disabled = busy; });
 $('apply').disabled = !allowed;
 $('apply-status').textContent = lastError ? t('error', tr(lastError)) : busy ? t('working') : plan && plan.stale ? t('replanning') :
  plan ? t('cuts', plan.stats.cuts) + (tightCount() ? t('tightCuts', tightCount()) : '') + '.' : '';
}
function tightCount() { var n = 0; plan.junctions.forEach(function (j) { if (j.tight && j.enabled) n++; }); return n; }
function setBusy(value) { busy = value; CONTROLS.forEach(function (id) { $(id).disabled = value; }); scriptState(); ready(); }
function invalidate() { planSeq++; planLatest = null; analysis = null; plan = null; decisions = {}; gapSettings = {}; loaded = null; $('results').hidden = true; ready(); }
function run(fn) {
 lastError = null; setBusy(true);
 return Promise.resolve().then(fn).catch(function (e) {
  lastError = e.message; window.SVEPanelError(e); $('progress').textContent = t('error', tr(e.message));
 }).then(function () { setBusy(false); });
}
function show(result, message) {
 planSeq++; planLatest = null; analysis = result; plan = result.plan; decisions = {}; gapSettings = {}; loaded = null;
 $('transcript').textContent = result.transcript || '';
 $('missing').textContent = result.pause_only ? '' : t('unread', (result.missing || []).slice(0, 300).join(', ') || t('none'));
 $('results').hidden = false; $('progress').textContent = message; renderAll();
}

/* ------------------------------------------------------------ titles */
function hashText(text) { var h = 5381, i; for (i = 0; i < text.length; i++) h = ((h * 33) ^ text.charCodeAt(i)) >>> 0; return h.toString(16); }
function wrapLines(g, text, width) {
 var words = text.split(/\s+/), lines = [], line = '';
 words.forEach(function (word) { var test = line ? line + ' ' + word : word; if (line && g.measureText(test).width > width) { lines.push(line); line = word; } else line = test; });
 if (line) lines.push(line);
 return lines;
}
function ensureFolder(folder) { if (!fs.existsSync(folder)) { ensureFolder(path.dirname(folder)); fs.mkdirSync(folder); } }
function titleImage(label, width, height) {
 var canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
 var g = canvas.getContext('2d'), size = Math.round(height * .042), pad = Math.round(width * .05), lines = [];
 g.font = 'bold ' + size + 'px Arial, sans-serif';
 label.split(' + ').forEach(function (part) { lines = lines.concat(wrapLines(g, part, width - pad * 3)); });
 lines = lines.slice(0, 7);
 var line = Math.round(size * 1.3), box = line * lines.length + size * 2.2, top = height - box - height * .07;
 g.fillStyle = 'rgba(0,0,0,0.72)'; g.fillRect(pad, top, width - pad * 2, box);
 g.fillStyle = '#f2c94c'; g.fillRect(pad, top, Math.round(width * .006), box);
 g.font = 'bold ' + Math.round(size * .6) + 'px Arial, sans-serif'; g.fillText(t('titleBanner'), pad * 1.5, top + size * .95);
 g.fillStyle = '#ffffff'; g.font = 'bold ' + size + 'px Arial, sans-serif';
 lines.forEach(function (text, i) { g.fillText(text, pad * 1.5, top + size * 1.9 + line * i + size * .2); });
 var folder = path.join(root, '.cache', 'titles'); ensureFolder(folder);
 var file = path.join(folder, 'titr-' + hashText(label + '|' + width + 'x' + height) + '.png');
 if (!fs.existsSync(file)) {
  var data = canvas.toDataURL('image/png').split(',')[1];
  fs.writeFileSync(file, NodeBuffer.from ? NodeBuffer.from(data, 'base64') : new NodeBuffer(data, 'base64'));
 }
 return file.replace(/\\/g, '/');
}
function writeReport(report) {
 var folder = path.join(root, 'reports'); ensureFolder(folder);
 var files = fs.readdirSync(folder).filter(function (f) { return /^edit-\d+\.json$/.test(f); }).sort();
 while (files.length >= 30) { try { fs.unlinkSync(path.join(folder, files.shift())); } catch (e) { files.shift(); } }
 var file = path.join(folder, 'edit-' + Date.now() + '.json');
 fs.writeFileSync(file, JSON.stringify(report, null, 1));
 return file;
}

/* ------------------------------------------------------------ actions */
function chooseScripts() {
 var result = null;
 if (window.cep && window.cep.fs) {
  result = window.cep.fs.showOpenDialogEx ? window.cep.fs.showOpenDialogEx(true, false, t('chooseScripts'), '', ['docx', 'txt'])
                                         : window.cep.fs.showOpenDialog(true, false, t('chooseScripts'), '', ['docx', 'txt']);
 }
 if (result && result.err === 0) return Promise.resolve(result.data || []);
 return new Promise(function (resolve) {
  var input = $('script'); input.value = '';
  input.onchange = function () { resolve(Array.prototype.map.call(input.files, function (f) { return f.path || f.name; })); };
  input.click();
 });
}
$('pick-script').onclick = function () {
 chooseScripts().then(function (files) {
  files = files.filter(function (f) { return /\.(docx|txt)$/i.test(f); });
  if (files.length) { scripts = files; $('no-script').checked = false; invalidate(); }
  scriptState();
 });
};
// "No script": only pauses and breaths are cleaned, so the script and the recording language are not needed.
function scriptState() {
 var none = $('no-script').checked;
 $('script-list').textContent = none ? t('noScriptShort') : scripts.length ? scripts.map(function (p) { return path.basename(p); }).join(' · ') : t('notChosen');
 $('strict').disabled = busy || none; $('language').disabled = busy || none;
 $('strict-row').className = 'check' + (none ? ' off' : ''); $('language-field').className = 'field' + (none ? ' off' : '');
}
$('no-script').onchange = function () { invalidate(); scriptState(); };
$('select').onclick = function () {
 return run(function () {
  invalidate(); $('clip').style.color = ''; $('clip').textContent = t('gettingClip');
  return loadHost().then(function () { return host('inspect', {}, 20000); }).then(function (data) {
   clip = data;
   var count = clip.pieces ? clip.pieces.length : 1;
   $('clip').textContent = clipText();
  });
 });
};
['mode', 'use-gpu', 'strict'].forEach(function (id) { $(id).onchange = invalidate; });
// The language is chosen by the user and remembered; it is never guessed.
try { var savedLanguage = window.localStorage.getItem('sve-language'); if (savedLanguage === 'uz' || savedLanguage === 'ru' || savedLanguage === 'en') $('language').value = savedLanguage; } catch (ignoredStorage) {}
$('language').onchange = function () { try { window.localStorage.setItem('sve-language', $('language').value); } catch (ignored) {} invalidate(); };
['pauses', 'breaths', 'crossfade'].forEach(function (id) { $(id).onchange = function () { if (analysis) schedulePlan(); }; });
$('show-uncertain').onchange = function () { if (analysis) renderItems(); };
$('show-pauses').onchange = function () { if (analysis) renderPauses(); };
$('stop').onclick = function () { $('player').pause(); stopAt = null; };
$('play-original').onclick = function () { if (analysis) play(analysis.original_preview, 0, undefined, t('original')); };
$('play-result').onclick = function () {
 freshPlan(true).then(function (p) { return play(p.preview, 0, undefined, t('result')); }).catch(function (e) { $('now').textContent = t('error', tr(e.message)); });
};
function analyse(extra, message) {
 return run(function () {
  invalidate();
  if (!clip) throw Error(t('needClip'));
  if (!extra.pause_only && !scripts.length) throw Error(t('needScript'));
  if (!extra.pause_only && !$('language').value) throw Error(t('needLanguage'));
  var began = Date.now();
  return connection().then(function (config) {
   var body = {clip: clip, scripts: scripts, language: $('language').value, mode: $('mode').value, use_gpu: $('use-gpu').checked, strict: $('strict').checked,
    pauses: $('pauses').checked, breaths: $('breaths').checked, crossfade: $('crossfade').checked};
   for (var k in extra) body[k] = extra[k];
   running = {}; $('cancel').hidden = false;
   return request(config, '/analyze', body, function (text) { $('progress').textContent = tr(text) + ' · ' + Math.round((Date.now() - began) / 1000) + ' s'; }, 0, running);
  }).then(function (result) {
   running = null; $('cancel').hidden = true;
   show(result, message);
   if (!$('auto-apply').checked) return;
   // A recording that does not match the script is never applied without a look.
   if (result.low_coverage) { $('progress').textContent = t('notMatched'); return; }
   $('progress').textContent = t('applying');
   return applyNow();
  });
 }).then(function () { running = null; $('cancel').hidden = true; });
}
$('cancel').onclick = function () { if (running && running.cancel) running.cancel(); };
$('analyze').onclick = function () { return $('no-script').checked ? analyse({pause_only: true}, t('pausesReady')) : analyse({}, t('readyCheck')); };
function applyNow() {
 {
  return freshPlan(false).then(function (p) {
   if (!p.ranges.length) throw Error(t('wholeRecording'));
   var payload = {clip: clip, ranges: p.ranges.map(function (r) { return {start: r.start, end: r.end, gapAfter: r.gapAfter || 0, gapLabel: r.gapLabel || '', gapPlain: r.gapPlain === true}; }),
    leadGap: p.lead_gap || 0, leadLabel: p.lead_label || '', tailLabel: p.tail_label || '', titles: $('titles').checked, shiftFollowing: $('shift').checked,
    titlesDisabled: $('titles-off').checked, titleGraphics: $('titles-edit').checked, backup: $('backup').checked, crossfade: $('crossfade').checked};
   if (payload.titles) {
    var own = path.join(root, 'titr.mogrt');
    if (fs.existsSync(own)) payload.titleTemplate = own.replace(/\\/g, '/');
    payload.titleFiles = {};
    var labels = [payload.leadGap ? (payload.leadLabel || t('gap')) : '', payload.tailLabel];
    payload.ranges.forEach(function (r) { if (r.gapAfter > 0 && !r.gapPlain) labels.push(r.gapLabel || t('gap')); });
    labels.forEach(function (label) {
     if (!label || payload.titleFiles[label]) return;
     try { payload.titleFiles[label] = titleImage(label, clip.width || 1920, clip.height || 1080); } catch (ignored) {}
    });
   }
   var report = {created: new Date().toISOString(), version: VERSION, clip: clip, scripts: scripts, decisions: decisions, gaps: gapSettings, stats: p.stats, payload: payload};
   // Editable titles: the backend writes a template file with the text inside for every title.
   var wanted = payload.titles && payload.titleGraphics && !payload.titleTemplate ? Object.keys(payload.titleFiles || {}) : [];
   var prepare = !wanted.length ? Promise.resolve() : host('template', {}, 15000).then(function (t) {
    if (!t.path) return null;
    return connection().then(function (config) { return request(config, '/titles', {template: t.path, labels: wanted}, null, 60000); })
     .then(function (made) { payload.titleGraphicFiles = made.files; });
   }).then(null, function (e) { report.titleError = String(e && e.message || e); });
   return prepare.then(function () {
   var file = writeReport(report);
   $('progress').textContent = t('runningInPremiere');
   return host('apply', payload, 0).then(function (result) {
    report.result = result; fs.writeFileSync(file, JSON.stringify(report, null, 1));
    $('progress').textContent = tr(result.message); invalidate(); clip = null;
    $('clip').textContent = t('doneReselect');
   }, function (e) {
    report.error = e.message; report.errorDetails = e.details; fs.writeFileSync(file, JSON.stringify(report, null, 1));
    throw e;
   });
   });
  });
 }
}
$('apply').onclick = function () { return run(applyNow); };

/* ------------------------------------------------------------ updates from GitHub
   A new version is a release of REPO with SmartVoiceEditor-<version>.zip and its .sha256. Only the program
   files change; runtime, models, caches and reports stay. Without internet nothing happens. */
var REPO = 'Otajon2300/smart-voice-editor', update = null;
function newer(a, b) {
 var x = String(a).split('.'), y = String(b).split('.'), i;
 for (i = 0; i < Math.max(x.length, y.length); i++) { var d = (parseInt(x[i], 10) || 0) - (parseInt(y[i], 10) || 0); if (d) return d > 0; }
 return false;
}
function download(url, timeout, redirects) {
 var https = nodeRequire('https');
 return new Promise(function (resolve, reject) {
  var req = https.get(url, {headers: {'User-Agent': 'SmartVoiceEditor-updater', Accept: 'application/vnd.github+json, application/octet-stream'}}, function (res) {
   if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
    res.resume();
    if ((redirects || 0) >= 5) return reject(Error(t('tooManyRedirects')));
    return resolve(download(res.headers.location, timeout, (redirects || 0) + 1));
   }
   if (res.statusCode !== 200) { res.resume(); return reject(Error(t('githubStatus', res.statusCode))); }
   var parts = [];
   res.on('data', function (c) { parts.push(c); });
   res.on('end', function () { resolve(NodeBuffer.concat(parts)); });
   res.on('error', reject);
  });
  req.on('error', reject);
  req.setTimeout(timeout, function () { req.abort(); reject(Error(t('noInternet'))); });
 });
}
function checkUpdate(manual) {
 if (manual) $('update-status').textContent = t('checking');
 return download('https://api.github.com/repos/' + REPO + '/releases/latest', 15000).then(function (body) {
  var release = JSON.parse(body.toString('utf8')), version = String(release.tag_name || '').replace(/^v/i, ''), files = {};
  (release.assets || []).forEach(function (a) { files[a.name] = a.browser_download_url; });
  var zip = files['SmartVoiceEditor-' + version + '.zip'], sum = files['SmartVoiceEditor-' + version + '.sha256'];
  if (!newer(version, VERSION) || !zip || !sum) { if (manual) $('update-status').textContent = t('latest', VERSION); return; }
  update = {version: version, zip: zip, sum: sum};
  $('update-text').textContent = t('newVersion', version, VERSION);
  $('update').hidden = false; $('update-status').textContent = '';
 }).catch(function (e) { if (manual) $('update-status').textContent = t('checkFailed', e.message); });
}
function installUpdate() {
 if (!update || busy) return;
 var target = update, folder = path.join(root, '.update'), file = path.join(folder, 'SmartVoiceEditor-' + target.version + '.zip');
 busy = true; $('update-now').disabled = true; $('update-text').textContent = t('downloading', target.version);
 Promise.all([download(target.zip, 120000), download(target.sum, 30000)]).then(function (got) {
  var expected = got[1].toString('utf8').trim().split(/\s+/)[0].toLowerCase();
  var actual = nodeRequire('crypto').createHash('sha256').update(got[0]).digest('hex');
  if (!expected || expected !== actual) throw Error(t('corrupt'));
  try { fs.mkdirSync(folder); } catch (ignored) {}
  fs.writeFileSync(file, got[0]);
  $('update-text').textContent = t('installing');
  // Unpack beside the program, copy over it (runtime, models and caches are not in the package), then bring
  // the Python packages in line with the new requirements (needs internet only when they changed).
  var script = "$ErrorActionPreference='Stop'; $t=Join-Path $env:SVE_ROOT '.update\\new'; if (Test-Path -LiteralPath $t) { Remove-Item -LiteralPath $t -Recurse -Force };" +
   " Expand-Archive -LiteralPath $env:SVE_ZIP -DestinationPath $t -Force; $s=Join-Path $t 'SmartVoiceEditor';" +
   " if (-not (Test-Path -LiteralPath (Join-Path $s 'backend\\server.py'))) { throw 'Paket buzilgan.' };" +
   " robocopy $s $env:SVE_ROOT /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null; if ($LASTEXITCODE -ge 8) { throw 'Fayllar nusxalanmadi.' };" +
   " & (Join-Path $env:SVE_ROOT 'start-backend.ps1') -InstallOnly";
  var env = {}; for (var k in process.env) env[k] = process.env[k];
  env.SVE_ROOT = root; env.SVE_ZIP = file;
  return new Promise(function (resolve, reject) {
   child.execFile('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script], {env: env, windowsHide: true, maxBuffer: 16 << 20},
    function (error, stdout, stderr) { if (error) reject(Error(String(stderr || error.message).trim().split('\n')[0])); else resolve(); });
  });
 }).then(function () {
  try { process.kill(readConfig().pid); } catch (ignored) {}
  $('update-text').textContent = t('updated', target.version);
  setTimeout(function () { window.location.reload(); }, 1500);
 }).catch(function (e) {
  busy = false; $('update-now').disabled = false; $('update-text').textContent = t('updateFailed', e.message);
 });
}
$('update-now').onclick = installUpdate;
$('check-update').onclick = function () { checkUpdate(true); };
setTimeout(function () { checkUpdate(false); }, 3000);

/* ------------------------------------------------------------ interface language */
function clipText() {
 var count = clip.pieces ? clip.pieces.length : 1;
 return clip.name + ' · ' + fmt(clip.duration) + (count > 1 ? t('pieces', count) : '') + t('track', clip.track + 1, clip.sequenceName) +
  (clip.canMove ? '' : t('oldPremiere')) + (clip.linked ? t('linked') : '');
}
$('ui-language').value = L.language();
$('ui-language').onchange = function () {
 var hint = !clip && $('clip').textContent === t('clipHint'), idle = $('progress').textContent === t('notStarted');
 L.set($('ui-language').value);
 // Texts written by the panel itself are redrawn; messages already shown stay until the next one.
 if (clip && $('clip').style.color === '') $('clip').textContent = clipText();
 if (hint) $('clip').textContent = t('clipHint');
 if (idle) $('progress').textContent = t('notStarted');
 if (update && !busy) $('update-text').textContent = t('newVersion', update.version, VERSION);
 scriptState(); renderAll(); ready();
};
L.apply(); $('clip').textContent = t('clipHint'); $('progress').textContent = t('notStarted'); scriptState();
window.SVEPanelReady = true;
