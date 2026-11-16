// Premiere DOM/QE are mocked. Checks: only selected clips change, gaps open,
// other tracks stay, nothing is deleted when a guard fails.
const assert = require('assert/strict'), fs = require('fs'), vm = require('vm');
const code = fs.readFileSync('extension/host.jsx', 'utf8').replace(/^#include.*$/m, '');
const TICKS = 254016000000, FRAME = .04;

function time(s) { return {get seconds() { return s; }, set seconds(v) { s = v; }, get ticks() { return String(Math.round(s * TICKS)); }}; }
function world(options = {}) {
  const log = {fades: [], razors: 0, removals: 0, moves: 0, markers: [], titles: [], imported: []};
  function list() { const a = []; Object.defineProperty(a, 'numItems', {get: () => a.length}); return a; }
  const a1 = list(), a2 = list(), v1 = list(), v2 = list(), media = {};
  // One project item per file; with `overwrite` it has in/out marks (Premiere 13+).
  function source(path) {
    if (media[path]) return media[path];
    const p = media[path] = {getMediaPath: () => path};
    if (options.overwrite) {
      p.marks = {in: null, out: null};
      p.setInPoint = (t) => { p.marks.in = Number(t) / TICKS; }; p.setOutPoint = (t) => { p.marks.out = Number(t) / TICKS; };
      p.clearInPoint = () => { p.marks.in = null; }; p.clearOutPoint = () => { p.marks.out = null; };
    }
    return p;
  }
  function make(track, start, end, input, selected, path = 'D:/voice.wav') {
    const item = {name: 'voice', start: time(start), end: time(end), inPoint: time(input), outPoint: time(input + end - start),
      get duration() { return time(item.end.seconds - item.start.seconds); }, projectItem: source(path),
      isSelected: () => selected, getSpeed: () => 1, isSpeedReversed: () => false};
    if (options.linkedVideo && track === a1) item.getLinkedItems = () => { const l = [{mediaType: 'Video'}, {mediaType: 'Audio'}]; l.numItems = 2; return l; };
    item.remove = (ripple) => {
      if (options.failRemove) return;
      const index = track.indexOf(item), length = item.end.seconds - item.start.seconds;
      track.splice(index, 1); log.removals++;
      if (ripple) for (const c of track) if (c.start.seconds >= item.start.seconds - 1e-9) { c.start.seconds -= length; c.end.seconds -= length; }
      log.ripple = (log.ripple || 0) + (ripple ? 1 : 0);
    };
    if (!options.noMove) item.move = (offset) => {
      const d = offset.seconds; log.moves++;
      const s = item.start.seconds + d, e = item.end.seconds + d;
      for (const c of track) if (c !== item && c.start.seconds < e - 1e-6 && c.end.seconds > s + 1e-6) throw Error('overlap on move');
      item.start.seconds = s; item.end.seconds = e;
    };
    item.track = track; track.push(item); return item;
  }
  (options.clips || [[10, 20, 0]]).forEach(([s, e, i, sel = true]) => make(a1, s, e, i, sel));
  if (options.next !== undefined) make(a1, options.next, options.next + 5, 50, false, 'D:/other.wav');
  make(a2, 0, 60, 0, false, 'D:/music.wav');
  make(v1, 0, 60, 0, false, 'D:/picture.png');
  if (options.selectOther) a2[0].isSelected = () => true;
  if (options.overwrite) log.relaid = [];
  const overwriteA1 = (item, at) => {
    const t = typeof at === 'string' ? Number(at) / TICKS : at, m = item.marks, length = m.out - m.in;
    for (const c of a1) if (c.start.seconds < t + length - 1e-6 && c.end.seconds > t + 1e-6) throw Error('overwrite on top of a clip at ' + t);
    const c = make(a1, t, t + length, m.in, false, item.getMediaPath());
    a1.sort((x, y) => x.start.seconds - y.start.seconds); log.relaid.push(+t.toFixed(3));
  };
  let position = 3;
  const seq = {name: 'Ishchi sequence', sequenceID: 's1', timebase: String(FRAME * TICKS),
    audioTracks: {0: {clips: a1}, 1: {clips: a2}, numTracks: 2},
    videoTracks: options.titles ? {0: {clips: v1}, 1: {clips: v2, overwriteClip: (item, t) => {
      const c = make(v2, t, t + 5, 0, false, item.getMediaPath()); log.titles.push(c); }}, numTracks: 2} : {0: {clips: v1}, numTracks: 1},
    getPlayerPosition: () => ({ticks: String(position * TICKS)}), setPlayerPosition: t => { position = Number(t) / TICKS; },
    markers: {createMarker: t => { const m = {time: t}; log.markers.push(m); return m; }}};
  if (options.overwrite) seq.audioTracks[0].overwriteClip = overwriteA1;
  if (options.graphics) seq.importMGT = (file, ticks, v) => {
    if (options.graphics === 'fail') return null;
    const t = Number(ticks) / TICKS, c = make(v2, t, t + 5, 0, false, file); log.titles.push(c); c.template = file;
    const text = {value: JSON.stringify({textEditValue: 'Your Title Here', fontTextRunLength: [15], fontSizeEditValue: [100]})};
    const scale = {value: 100};
    const prop = (o, name) => ({displayName: name, getValue: () => o.value, setValue: x => { o.value = x; }});
    const comps = [{matchName: 'AE.ADBE Opacity', properties: Object.assign([prop({value: 100}, 'Opacity')], {numItems: 1})},
      {matchName: 'AE.ADBE Motion', properties: Object.assign([prop({value: [.5, .5]}, 'Position'), prop(scale, 'Scale')], {numItems: 2})},
      {matchName: 'AE.ADBE Text', properties: Object.assign([prop(text, 'Source Text')], {numItems: 1})}];
    c.components = Object.assign(comps, {numItems: comps.length}); c.getMGTComponent = () => null;
    c.text = () => JSON.parse(text.value); c.scale = () => scale.value;
    return c;
  };
  const qitems = () => a1.slice().sort((x, y) => x.start.seconds - y.start.seconds).map(c => ({type: 'Clip', start: {secs: c.start.seconds},
    addTransition: (transition, atStart, duration) => { log.fades.push([c.start.seconds, transition.name, atStart, duration]); return true; }}));
  const qseq = {get CTI() { return {timecode: String(position)}; }, getAudioTrackAt: () => ({get numItems() { return a1.length; }, getItemAt: i => qitems()[i], razor: tc => {
    log.razors++; if (options.failRazor) return;
    const t = Number(tc), index = a1.findIndex(c => c.start.seconds < t - 1e-6 && c.end.seconds > t + 1e-6);
    assert.ok(index >= 0, 'razor outside a clip at ' + t);
    const c = a1[index], tail = make([], t, c.end.seconds, c.inPoint.seconds + t - c.start.seconds, false);
    tail.track = a1; tail.remove = c.remove.bind(null); // rebinding below
    a1.splice(index + 1, 0, tail); tail.isSelected = c.isSelected;
    tail.remove = (ripple) => { const i = a1.indexOf(tail), length = tail.end.seconds - tail.start.seconds; if (options.failRemove) return; a1.splice(i, 1); log.removals++; if (ripple) for (const x of a1) if (x.start.seconds >= tail.start.seconds - 1e-9) { x.start.seconds -= length; x.end.seconds -= length; } };
    if (c.move) tail.move = (offset) => { const d = offset.seconds, s = tail.start.seconds + d, e = tail.end.seconds + d; log.moves++; for (const x of a1) if (x !== tail && x.start.seconds < e - 1e-6 && x.end.seconds > s + 1e-6) throw Error('overlap on move'); tail.start.seconds = s; tail.end.seconds = e; };
    c.end.seconds = t; c.outPoint.seconds = c.inPoint.seconds + t - c.start.seconds;
  }})};
  const Time = function () { let s = 0; Object.defineProperty(this, 'seconds', {get: () => s, set: v => { s = v; }}); };
  const children = list(), bin = {name: 'Smart Voice titrlar', type: 2, children: list()};
  const rootItem = {children, createBin: name => { children.push(bin); }};
  const sequences = [seq]; Object.defineProperty(sequences, 'numSequences', {get: () => sequences.length});
  if (!options.noClone) seq.clone = () => {
    if (options.failClone) return false;
    const copy = {name: seq.name + ' Copy', sequenceID: 's' + (sequences.length + 1)}; sequences.push(copy);
    if (options.cloneActivates) project.activeSequence = copy;   // some versions bring the copy to the front
    return true;
  };
  const project = {activeSequence: seq, sequences, rootItem, importFiles: (paths, quiet, target) => {
    for (const f of paths) { log.imported.push(f); target.children.push({name: f, getMediaPath: () => f}); } }};
  const File = function (f) { this.exists = /titr/.test(f); };
  const context = {app: {version: 'mock', path: 'C:\\Program Files\\titr-app\\', project, enableQE: () => {}}, qe: {project: {getActiveSequence: () => qseq, getAudioTransitionByName: name => options.noTransition || name !== 'Constant Power' ? null : {name}}}, JSON, Time, File};
  vm.createContext(context); vm.runInContext(code, context);
  return {SVE: context.SVE, a1, a2, v1, log, position: () => position, sequences, project, seq};
}
const spans = track => track.map(c => [+c.start.seconds.toFixed(3), +c.end.seconds.toFixed(3), +c.inPoint.seconds.toFixed(3)]);

// 1. Move path: cuts, an open gap with a marker, other tracks untouched.
let w = world({next: 30});
let clip = JSON.parse(w.SVE.inspect());
assert.equal(clip.canMove, true); assert.equal(clip.duration, 10); assert.equal(clip.nextStart, 30);
let result = JSON.parse(w.SVE.apply(JSON.stringify({clip, ranges: [{start: 0, end: 2}, {start: 3, end: 5, gapAfter: 4, gapLabel: 'СНХР: Test'}, {start: 6, end: 10}]})));
assert.ok(result.message, result.error);
assert.deepEqual(spans(w.a1), [[10, 12, 0], [12, 14, 3], [18, 22, 6], [30, 35, 50]]);
assert.deepEqual(spans(w.a2), [[0, 60, 0]]); assert.deepEqual(spans(w.v1), [[0, 60, 0]]);
assert.equal(w.log.markers.length, 1); assert.equal(w.log.markers[0].time, 14); assert.equal(w.log.markers[0].name, 'СНХР: Test');
assert.equal(w.position(), 3); assert.equal(result.method, 'move'); assert.equal(w.log.ripple || 0, 0);

// 2. Not enough room before the next clip: refuse before touching anything.
w = world({next: 21}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, ranges: [{start: 0, end: 5, gapAfter: 10}, {start: 5, end: 10}]})));
assert.match(result.error, /sig‘maydi/); assert.equal(w.log.razors, 0); assert.equal(w.log.removals, 0);

// 3. Old Premiere without move(): ripple fallback, gap held from removed material.
w = world({noMove: true}); clip = JSON.parse(w.SVE.inspect());
assert.equal(clip.canMove, false);
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, ranges: [{start: 0, end: 2, gapAfter: 1}, {start: 5, end: 10}]})));
assert.ok(result.message, result.error);
assert.deepEqual(spans(w.a1), [[10, 12, 0], [13, 18, 5]]);
assert.deepEqual(spans(w.v1), [[0, 60, 0]]);
// 3b. Ripple: a gap with too little removed material opens only partly; later markers follow the real
// timeline (Premiere 2020: every short gap used to push all following titles to the right).
w = world({noMove: true}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, ranges: [{start: 0, end: 2, gapAfter: 2, gapLabel: 'A'},
  {start: 2.4, end: 5, gapAfter: 2, gapLabel: 'B'}, {start: 8, end: 10}]})));
assert.ok(result.message, result.error);
assert.deepEqual(spans(w.a1), [[10, 12, 0], [12.4, 15, 2.4], [17, 19, 8]]);
assert.deepEqual(w.log.markers.map(m => +m.time.toFixed(2)), [12, 15]);
assert.match(result.note, /1 ta bo‘sh joy to‘liq ochilmadi/);
assert.ok(Math.abs(result.gapSeconds - 2.4) < .05, String(result.gapSeconds));

// 3d. Same plan, but Premiere can lay a piece again (overwriteClip + in/out points): the gaps open in full,
// pieces are laid right to left, the media item's own in/out marks are cleared again.
w = world({noMove: true, overwrite: true, next: 30}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, ranges: [{start: 0, end: 2, gapAfter: 2, gapLabel: 'A'},
  {start: 2.4, end: 5, gapAfter: 2, gapLabel: 'B'}, {start: 8, end: 10}]})));
assert.ok(result.message, result.error);
assert.deepEqual(spans(w.a1), [[10, 12, 0], [14, 16.6, 2.4], [18.6, 20.6, 8], [29, 34, 50]]);   // ripple delete pulls the next clip left
assert.deepEqual(w.log.markers.map(m => +m.time.toFixed(2)), [12, 16.6]);
assert.deepEqual(w.log.relaid, [18.6, 14]);
assert.equal(result.moved, 2); assert.ok(Math.abs(result.gapSeconds - 4) < .05, String(result.gapSeconds));
assert.match(result.note, /qayta qo‘yish orqali ochildi/);
assert.deepEqual(w.a1[0].projectItem.marks, {in: null, out: null});
// Not enough room before the next clip: the gaps are not forced open, the old behaviour stays.
w = world({noMove: true, overwrite: true, next: 21}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, ranges: [{start: 0, end: 2, gapAfter: 2, gapLabel: 'A'},
  {start: 2.4, end: 5, gapAfter: 2, gapLabel: 'B'}, {start: 8, end: 10}]})));
assert.ok(result.message, result.error);
assert.deepEqual(w.log.relaid, []); assert.match(result.note, /to‘liq ochilmadi/);

// 3c. The selection was lost during the analysis: the analysed clip is found again by its position.
w = world({next: 30}); clip = JSON.parse(w.SVE.inspect());
w.a1.forEach(c => { c.isSelected = () => false; });
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, ranges: [{start: 0, end: 2}, {start: 3, end: 10}]})));
assert.ok(result.message, result.error);
assert.deepEqual(spans(w.a1), [[10, 12, 0], [12, 19, 3], [30, 35, 50]]);

// 4. Several selected clips on one track (already edited pieces) are analysed together.
w = world({clips: [[10, 12, 0], [12, 15, 4], [15, 16, 9]], next: 40}); clip = JSON.parse(w.SVE.inspect());
assert.equal(clip.pieces.length, 3); assert.ok(Math.abs(clip.duration - 6) < 1e-9);
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, ranges: [{start: 0, end: 1}, {start: 2.4, end: 6}]})));
assert.ok(result.message, result.error);
assert.deepEqual(spans(w.a1), [[10, 11, 0], [11, 13.6, 4.4], [13.6, 14.6, 9], [40, 45, 50]]);

// 5. Guards.
w = world({selectOther: true}); assert.match(JSON.parse(w.SVE.inspect()).error, /bir nechta audio trekda/);
w = world({clips: [[10, 12, 0], [12, 14, 2, false], [14, 16, 4]]}); assert.match(JSON.parse(w.SVE.inspect()).error, /orasida tanlanmagan/);
w = world({clips: [[10, 12, 0, false]]}); assert.match(JSON.parse(w.SVE.inspect()).error, /tanlang/);
w = world({failRazor: true}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, ranges: [{start: 0, end: 2}, {start: 3, end: 10}]})));
assert.match(result.error, /bo‘lmadi/); assert.equal(w.log.removals, 0);
w = world(); clip = JSON.parse(w.SVE.inspect()); w.a1[0].end.seconds = 19;
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, ranges: [{start: 0, end: 2}]})));
assert.match(result.error, /o‘zgargan/);
// 6. Titles instead of markers (move mode); no digital fill is ever added.
w = world({next: 40, titles: true}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, titles: true, titleFiles: {'СНХР: Test': 'C:/cache/titr-1.png'},
  ranges: [{start: 0, end: 2, fillAfter: .2}, {start: 3, end: 5, gapAfter: 4, gapLabel: 'СНХР: Test'}, {start: 6, end: 10}]})));
assert.ok(result.message, result.error);
assert.deepEqual(spans(w.a1), [[10, 12, 0], [12, 14, 3], [18, 22, 6], [40, 45, 50]]);
assert.equal(w.log.markers.length, 0); assert.equal(result.titles, 1); assert.deepEqual(w.log.imported, ['C:/cache/titr-1.png']);
assert.deepEqual(spans(w.log.titles), [[14, 18, 0]]); assert.equal(w.log.titles[0].name, 'СНХР: Test');
assert.deepEqual(spans(w.v1), [[0, 60, 0]]);

// 7. Not enough room, but the user allows shifting the following clips on this track.
w = world({next: 21}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, shiftFollowing: true, ranges: [{start: 0, end: 5, gapAfter: 10, gapLabel: 'СНХР'}, {start: 5, end: 10}]})));
assert.ok(result.message, result.error);
assert.equal(result.shifted, 1);
assert.deepEqual(spans(w.a1), [[10, 15, 0], [25, 30, 5], [30.04, 35.04, 50]]);
assert.deepEqual(spans(w.a2), [[0, 60, 0]]); assert.deepEqual(spans(w.v1), [[0, 60, 0]]);

// 8. Audio linked to video is refused before anything changes (the video must stay put).
w = world({linkedVideo: true}); clip = JSON.parse(w.SVE.inspect());
assert.equal(clip.linked, true);
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, ranges: [{start: 0, end: 2}, {start: 3, end: 10}]})));
assert.match(result.error, /Unlink/); assert.equal(w.log.razors, 0); assert.equal(w.log.removals, 0);

// 9. Backup: a copy of the sequence is made before the first change, and the work stays in the original.
const cut = {ranges: [{start: 0, end: 2}, {start: 3, end: 10}]};
w = world({cloneActivates: true}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify(Object.assign({clip, backup: true}, cut))));
assert.ok(result.message, result.error);
assert.equal(w.sequences.length, 2); assert.match(w.sequences[1].name, /^Ishchi sequence — zaxira \d\d\.\d\d$/);
assert.equal(result.backup, w.sequences[1].name); assert.match(result.message, /zaxira/);
assert.equal(w.project.activeSequence, w.seq); assert.deepEqual(spans(w.a1), [[10, 12, 0], [12, 19, 3]]);
// No backup unless asked for; a failed backup stops before anything is cut; an old Premiere only gets a note.
w = world(); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify(Object.assign({clip}, cut))));
assert.ok(result.message, result.error); assert.equal(w.sequences.length, 1); assert.equal(result.backup, '');
w = world({failClone: true}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify(Object.assign({clip, backup: true}, cut))));
assert.match(result.error, /zaxira/); assert.equal(w.log.razors, 0); assert.equal(w.log.removals, 0);
w = world({noClone: true}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify(Object.assign({clip, backup: true}, cut))));
assert.ok(result.message, result.error); assert.match(result.message, /zaxira olinmadi/); assert.equal(w.log.removals, 1);
// A plan that does not fit is refused before the backup is made.
w = world({next: 21}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, backup: true, ranges: [{start: 0, end: 5, gapAfter: 10}, {start: 5, end: 10}]})));
assert.match(result.error, /sig‘maydi/); assert.equal(w.sequences.length, 1);

// 10. Titles can be placed disabled: visible on the timeline, absent from the export.
w = world({next: 40, titles: true}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, titles: true, titlesDisabled: true, titleFiles: {'СНХР: Test': 'C:/cache/titr-1.png'},
  ranges: [{start: 0, end: 2}, {start: 3, end: 5, gapAfter: 4, gapLabel: 'СНХР: Test'}, {start: 6, end: 10}]})));
assert.ok(result.message, result.error); assert.equal(w.log.titles[0].disabled, true);

// 11. Crossfades: one on every join inside the result, none on its outer edges or next to a gap; never fatal.
const three = {ranges: [{start: 0, end: 2}, {start: 3, end: 5, gapAfter: 4}, {start: 6, end: 8}, {start: 9, end: 10}]};
w = world({next: 40}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify(Object.assign({clip, crossfade: true}, three))));
assert.ok(result.message, result.error); assert.equal(result.crossfades, 2); assert.match(result.message, /Crossfade: 2\/2/);
assert.deepEqual(w.log.fades, [[12, 'Constant Power', true, '00:00:00:01'], [20, 'Constant Power', true, '00:00:00:01']]);
w = world({next: 40}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify(Object.assign({clip}, three))));
assert.equal(w.log.fades.length, 0); assert.doesNotMatch(result.message, /Crossfade/);
w = world({next: 40, noTransition: true}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify(Object.assign({clip, crossfade: true}, three))));
assert.ok(result.message, result.error); assert.match(result.message, /Crossfade qo‘yilmadi/); assert.equal(w.log.removals, 3);

// 12. Plain space where a breath was: the clips stay apart, but no title and no marker is made for it.
w = world({next: 40}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify({clip, ranges: [{start: 0, end: 2, gapAfter: .2, gapPlain: true}, {start: 3, end: 10}]})));
assert.ok(result.message, result.error); assert.deepEqual(spans(w.a1).slice(0, 2), [[10, 12, 0], [12.2, 19.2, 3]]);
assert.equal(w.log.markers.length, 0); assert.equal(w.log.titles.length, 0); assert.equal(result.gapSeconds, 0);
assert.doesNotMatch(result.message, /bo‘sh joy/); assert.equal(typeof result.times, 'object');

// 13. Editable titles: Premiere's own graphic with the text written into it; the picture is only the fallback.
const titled = {titles: true, titleFiles: {'Звук: песни + СНХР: Test': 'C:/cache/titr-1.png'},
  ranges: [{start: 0, end: 2}, {start: 3, end: 5, gapAfter: 4, gapLabel: 'Звук: песни + СНХР: Test'}, {start: 6, end: 10}]};
w = world({next: 40, titles: true, graphics: true}); clip = JSON.parse(w.SVE.inspect());
result = JSON.parse(w.SVE.apply(JSON.stringify(Object.assign({clip}, titled))));
assert.ok(result.message, result.error); assert.equal(result.titles, 1); assert.equal(result.titleGraphics, 1);
assert.deepEqual(w.log.imported, []); assert.deepEqual(spans(w.log.titles), [[14, 18, 0]]);
assert.match(w.log.titles[0].template, /Basic Title\.mogrt$/); assert.equal(w.log.titles[0].text().textEditValue, 'Звук: песни' + String.fromCharCode(13) + 'СНХР: Test');
assert.deepEqual(w.log.titles[0].text().fontTextRunLength, [22]); assert.equal(w.log.titles[0].scale(), 50);
assert.equal(w.log.titles[0].name, 'Звук: песни + СНХР: Test');
w = world({next: 40, titles: true, graphics: true}); clip = JSON.parse(w.SVE.inspect());            // the user's own template
result = JSON.parse(w.SVE.apply(JSON.stringify(Object.assign({clip, titleTemplate: 'D:/x/titr.mogrt'}, titled))));
assert.equal(w.log.titles[0].template, 'D:/x/titr.mogrt');
w = world({next: 40, titles: true, graphics: true}); clip = JSON.parse(w.SVE.inspect());            // text already in the file
result = JSON.parse(w.SVE.apply(JSON.stringify(Object.assign({clip, titleGraphicFiles: {'Звук: песни + СНХР: Test': 'C:/cache/titr-ab.mogrt'}}, titled))));
assert.equal(result.titleGraphics, 1); assert.equal(w.log.titles[0].template, 'C:/cache/titr-ab.mogrt');
assert.equal(w.log.titles[0].text().textEditValue, 'Your Title Here'); assert.equal(w.log.titles[0].scale(), 100);
assert.match(JSON.parse(w.SVE.template()).path, /Basic Title\.mogrt$/);
for (const extra of [{graphics: 'fail'}, {graphics: true, off: true}]) {                              // fallback and switch
  w = world({next: 40, titles: true, graphics: extra.graphics}); clip = JSON.parse(w.SVE.inspect());
  result = JSON.parse(w.SVE.apply(JSON.stringify(Object.assign({clip}, titled, extra.off ? {titleGraphics: false} : {}))));
  assert.ok(result.message, result.error); assert.equal(result.titles, 1); assert.equal(result.titleGraphics, 0);
  assert.deepEqual(w.log.imported, ['C:/cache/titr-1.png']); assert.deepEqual(spans(w.log.titles), [[14, 18, 0]]);
}

console.log('Host: editable titles, plain breath space, crossfades, sequence backup, disabled titles, titles, move layout, gaps+markers, shifting following clips, linked guard, other tracks untouched, ripple fallback, multi-piece selection and guards passed');
