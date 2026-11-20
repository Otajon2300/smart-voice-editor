#include "json2.js"
/*
 ExtendScript ES3 (Premiere Pro 2017+). Only the clips the user selected on one
 audio track change; video and other tracks stay where they are.

 With TrackItem.move (most versions): QE razor at every kept-range edge ->
 delete the unwanted pieces without ripple -> move kept pieces into place,
 leaving open gaps for interviews/standups. Without move(): ripple delete.
 Every step is checked; on a failed check nothing more is changed.
*/
var SVE = (function () {
    var TICKS = 254016000000;
    function fail(message) { throw new Error(message); }
    function has(object, name) { try { return !!object && typeof object[name] === 'function'; } catch (e) { return false; } }
    function seconds(time) { return Number(time.seconds); }
    function mediaPath(item) { try { return item.projectItem ? String(item.projectItem.getMediaPath()) : ''; } catch (e) { return ''; } }
    function round(value, frame) { return Math.round(value / frame) * frame; }
    function near(a, b, tolerance) { return Math.abs(a - b) <= tolerance; }
    function timeAt(value) { var t = new Time(); t.seconds = value; return t; }

    function sequenceFrame(seq) {
        var frame = Number(seq.timebase) / TICKS;
        if (!isFinite(frame) || frame <= 0) fail('Sequence kadr tezligi olinmadi.');
        return frame;
    }

    function trackClips(track) {
        var keyed = [], list = [], i, count = track.clips.numItems;
        for (i = 0; i < count; i++) { var clip = track.clips[i]; keyed.push({clip: clip, at: seconds(clip.start)}); }
        keyed.sort(function (a, b) { return a.at - b.at; });
        for (i = 0; i < keyed.length; i++) list.push(keyed[i].clip);
        return list;
    }

    function linkedToVideo(clip) {
        if (!has(clip, 'getLinkedItems')) return false;
        try {
            var items = clip.getLinkedItems(), i;
            if (!items) return false;
            for (i = 0; i < items.numItems; i++) {
                var type = String(items[i].mediaType || '');
                if (type.toLowerCase() === 'video') return true;
            }
        } catch (e) {}
        return false;
    }

    function selectedClips(seq) {
        var tracks = seq.audioTracks, trackIndex = -1, picked = [], i, j, clip;
        for (i = 0; i < tracks.numTracks; i++) {
            for (j = 0; j < tracks[i].clips.numItems; j++) {
                clip = tracks[i].clips[j];
                if (!has(clip, 'isSelected')) fail('Bu Premiere versiyasi tanlangan klipni bildirmaydi.');
                if (!clip.isSelected()) continue;
                if (trackIndex !== -1 && trackIndex !== i) fail('Kliplar bir nechta audio trekda tanlangan. Ovozni bitta audio trekda tanlang.');
                trackIndex = i; picked.push(clip);
            }
        }
        if (!picked.length) fail('Timeline’da tozalanadigan audio klipni (yoki ketma-ket kliplarni) tanlang.');
        picked.sort(function (a, b) { return seconds(a.start) - seconds(b.start); });
        return {track: trackIndex, clips: picked};
    }

    // The clips that were analysed, found again by sequence, track and position: the selection is easily lost
    // while the analysis runs (a click on the timeline, another sequence tab), and it is not needed to apply.
    function analysedClips(expected) {
        var id = String(expected.sequenceId || ''), seq = app.project.activeSequence, i, k;
        if (!seq || String(seq.sequenceID) !== id) {
            try { app.project.openSequence(id); } catch (e) {}
            seq = app.project.activeSequence;
        }
        if (!seq || String(seq.sequenceID) !== id) fail('Tahlil qilingan sequence («' + (expected.sequenceName || '') + '») ochilmadi. Uni timeline’da oching va qayta urinib ko‘ring.');
        var track = seq.audioTracks[expected.track], pieces = expected.pieces || [], picked = [];
        if (!track || !pieces.length) fail('Tahlil qilingan audio trek topilmadi. Klipni qayta oling va tahlil qiling.');
        var frame = sequenceFrame(seq), all = trackClips(track);
        for (k = 0; k < pieces.length; k++) {
            var found = null;
            for (i = 0; i < all.length && !found; i++) {
                if (near(seconds(all[i].start), pieces[k].start, frame * .1) && near(seconds(all[i].end), pieces[k].end, frame * .1) &&
                    normalPath(mediaPath(all[i])) === normalPath(pieces[k].path)) found = all[i];
            }
            if (!found) fail('Tahlil qilingan klip timeline’da o‘zgargan yoki o‘chirilgan (' + pieces[k].start.toFixed(2) + ' s). Klipni qayta oling va tahlil qiling.');
            picked.push(found);
        }
        return {seq: seq, chosen: {track: expected.track, clips: picked}};
    }

    function snapshot(expected) {
        var seq = app.project.activeSequence, chosen = null;
        if (expected) { var again = analysedClips(expected); seq = again.seq; chosen = again.chosen; }
        if (!seq) fail('Ochiq sequence topilmadi.');
        var frame = sequenceFrame(seq), pieces = [], signature = [], i, c, total = 0, linked = false;
        if (!chosen) chosen = selectedClips(seq);
        for (i = 0; i < chosen.clips.length; i++) {
            c = chosen.clips[i];
            if (has(c, 'getSpeed') && Math.abs(c.getSpeed() - 1) > 1e-6) fail('Tezligi o‘zgartirilgan klip qo‘llanmaydi: ' + c.name);
            if (has(c, 'isSpeedReversed') && c.isSpeedReversed()) fail('Teskari ijro etiladigan klip qo‘llanmaydi: ' + c.name);
            var path = mediaPath(c);
            if (!path) fail('Klip manba fayli topilmadi: ' + c.name);
            if (linkedToVideo(c)) linked = true;
            pieces.push({start: seconds(c.start), end: seconds(c.end), inPoint: seconds(c.inPoint), outPoint: seconds(c.outPoint), path: path, name: String(c.name)});
            signature.push(String(c.start.ticks) + ':' + String(c.end.ticks) + ':' + String(c.inPoint.ticks) + ':' + path);
            total += seconds(c.end) - seconds(c.start);
        }
        var first = pieces[0], last = pieces[pieces.length - 1];
        var all = trackClips(seq.audioTracks[chosen.track]), next = null, between = 0;
        for (i = 0; i < all.length; i++) {
            var s = seconds(all[i].start), e = seconds(all[i].end), mine = false, k;
            for (k = 0; k < pieces.length; k++) if (near(s, pieces[k].start, frame * .1) && near(e, pieces[k].end, frame * .1)) mine = true;
            if (mine) continue;
            if (s >= last.end - frame * .1 && (next === null || s < next)) next = s;
            if (s < last.end - frame * .1 && e > first.start + frame * .1) between++;
        }
        if (between) fail('Tanlangan kliplar orasida tanlanmagan klip bor. Ketma-ket kliplarni to‘liq tanlang.');
        return {seq: seq, track: chosen.track, clips: chosen.clips, data: {
            sequenceId: String(seq.sequenceID), sequenceName: String(seq.name), track: chosen.track,
            path: first.path, name: first.name, start: first.start, end: last.end,
            inPoint: first.inPoint, outPoint: last.outPoint, duration: total, frame: frame,
            nextStart: next, pieces: pieces, signature: signature.join('|'), linked: linked,
            canMove: has(chosen.clips[0], 'move'), version: String(app.version),
            width: Number(seq.frameSizeHorizontal) || 1920, height: Number(seq.frameSizeVertical) || 1080
        }};
    }

    function inspect() { try { return JSON.stringify(snapshot().data); } catch (e) { return JSON.stringify({error: e.message}); } }

    // Analysis time (selected pieces joined end to end) -> timeline segments.
    function keptSegments(pieces, ranges, frame) {
        var segments = [], offsets = [], cursor = 0, i, k;
        for (i = 0; i < pieces.length; i++) { offsets.push(cursor); cursor += pieces[i].end - pieces[i].start; }
        for (i = 0; i < ranges.length; i++) {
            for (k = 0; k < pieces.length; k++) {
                var a = Math.max(ranges[i].start, offsets[k]), b = Math.min(ranges[i].end, offsets[k] + pieces[k].end - pieces[k].start);
                if (b - a < frame * .5) continue;
                var ta = Math.max(round(pieces[k].start + a - offsets[k], frame), pieces[k].start);
                var tb = Math.min(round(pieces[k].start + b - offsets[k], frame), pieces[k].end);
                if (tb - ta < frame * .5) continue;
                segments.push({a: ta, b: tb, range: i, piece: k});
            }
        }
        return segments;
    }

    function setCTI(seq, time, frame) {
        seq.setPlayerPosition(String(Math.round(time / frame) * Math.round(frame * TICKS)));
    }

    function regionClips(track, pieces, frame) {
        var all = trackClips(track), result = [], i, k;
        for (i = 0; i < all.length; i++) {
            var s = seconds(all[i].start), e = seconds(all[i].end);
            for (k = 0; k < pieces.length; k++) {
                if (s >= pieces[k].start - frame * .25 && e <= pieces[k].end + frame * .25) { result.push(all[i]); break; }
            }
        }
        return result;
    }

    function normalPath(p) { return String(p || '').replace(/\\/g, '/').toLowerCase(); }

    function findBin(name) {
        var root = app.project.rootItem, i;
        for (i = 0; i < root.children.numItems; i++) if (root.children[i].name === name && root.children[i].type === 2) return root.children[i];
        try { root.createBin(name); } catch (e) { return root; }
        for (i = 0; i < root.children.numItems; i++) if (root.children[i].name === name && root.children[i].type === 2) return root.children[i];
        return root;
    }

    function itemByPath(bin, file) {
        var i;
        for (i = 0; i < bin.children.numItems; i++) {
            try { if (normalPath(bin.children[i].getMediaPath()) === normalPath(file)) return bin.children[i]; } catch (e) {}
        }
        return null;
    }

    function freeTrack(seq, start, end, frame) {
        var v, k, clips, busy;
        for (v = seq.videoTracks.numTracks - 1; v >= 0; v--) {
            clips = seq.videoTracks[v].clips; busy = false;
            for (k = 0; k < clips.numItems; k++) {
                if (seconds(clips[k].start) < end - frame * .25 && seconds(clips[k].end) > start + frame * .25) { busy = true; break; }
            }
            if (!busy) return v;
        }
        return -1;
    }

    // A copy of the sequence stays in the project: hundreds of razor/remove/move steps do not fit
    // into Premiere's undo history, so Undo alone cannot always bring the original back.
    function backup(seq) {
        if (!has(seq, 'clone')) return {name: '', note: 'Bu Premiere versiyasi sequence nusxasini skript orqali ololmaydi — zaxira olinmadi.'};
        var id = String(seq.sequenceID), known = {}, list = app.project.sequences, i, copy = null;
        for (i = 0; i < list.numSequences; i++) known[String(list[i].sequenceID)] = true;
        seq.clone();
        list = app.project.sequences;
        for (i = 0; i < list.numSequences; i++) if (!known[String(list[i].sequenceID)]) copy = list[i];
        if (!copy) fail('Sequence zaxira nusxasi yaratilmadi. Hech narsa o‘zgartirilmadi. Qo‘lda Duplicate qiling yoki «zaxira» belgisini olib tashlang.');
        var now = new Date(), two = function (n) { return (n < 10 ? '0' : '') + n; };
        try { copy.name = String(seq.name) + ' — zaxira ' + two(now.getHours()) + '.' + two(now.getMinutes()); } catch (e) {}
        // Cloning may bring the copy to the front: the work continues in the original.
        var active = app.project.activeSequence;
        if (!active || String(active.sequenceID) !== id) {
            try { app.project.activeSequence = seq; } catch (e1) {}
            active = app.project.activeSequence;
            if (!active || String(active.sequenceID) !== id) { try { app.project.openSequence(id); } catch (e2) {} active = app.project.activeSequence; }
            if (!active || String(active.sequenceID) !== id) fail('Zaxira nusxa olindi, lekin ishchi sequence qayta ochilmadi. Uni oching, klipni qayta oling va urinib ko‘ring.');
        }
        return {name: String(copy.name), note: ''};
    }

    // Editable titles are Premiere's own "Basic Title" graphic (or the user's titr.mogrt) with the text replaced.
    function titleTemplate(custom) {
        var names = [], i;
        if (custom) names.push(custom);
        try {
            var base = String(app.path || '').replace(/\\/g, '/').replace(/\/+$/, '');
            if (base) { names.push(base + '/Essential Graphics/Basic Title.mogrt'); names.push(base + '/Essential Graphics/Basic Lower Third.mogrt'); }
        } catch (e) {}
        for (i = 0; i < names.length; i++) { try { var f = new File(names[i]); if (f.exists) return f.fsName || names[i]; } catch (e1) {} }
        return '';
    }

    // The text of a graphic clip is a JSON value ({"textEditValue": ...}) in Premiere's own graphics
    // and a plain string in After Effects templates.
    function setGraphicText(item, text) {
        var groups = [], i, k;
        try { var own = item.getMGTComponent(); if (own) groups.push(own); } catch (e) {}
        try { for (i = 0; i < item.components.numItems; i++) groups.push(item.components[i]); } catch (e1) {}
        for (i = 0; i < groups.length; i++) {
            var props = null, n = 0;
            try { props = groups[i].properties; n = props.numItems; } catch (e2) { continue; }
            for (k = 0; k < n; k++) {
                try {
                    var p = props[k], value = p.getValue();
                    if (typeof value !== 'string') continue;
                    if (value.charAt(0) === '{') {
                        var data = JSON.parse(value), key;
                        if (data.mTextParam && data.mTextParam.mStyleSheet) data.mTextParam.mStyleSheet.mText = text;   // Premiere's own graphic
                        else if (data.textEditValue !== undefined) {                                                      // After Effects template
                            data.textEditValue = text;
                            for (key in data) if (/RunLength$/.test(key) && data[key] && data[key].length === 1) data[key] = [text.length];
                        } else continue;
                        p.setValue(JSON.stringify(data), true);
                        return true;
                    }
                    if (value.length < 400 && !/[\x00-\x08]/.test(value) && /text|текст|matn/i.test(String(p.displayName || ''))) { p.setValue(text, true); return true; }
                } catch (e3) {}
            }
        }
        return false;
    }

    function scaleDown(item, percent) {
        try {
            for (var i = 0; i < item.components.numItems; i++) {
                var c = item.components[i];
                if (String(c.matchName) === 'AE.ADBE Motion') { c.properties[1].setValue(percent, true); return; }
            }
        } catch (e) {}
    }

    function wrapText(label, width) {
        var parts = String(label).split(' + '), lines = [], i, k;
        for (i = 0; i < parts.length; i++) {
            var words = parts[i].split(/\s+/), line = '';
            for (k = 0; k < words.length; k++) {
                if (line && (line + ' ' + words[k]).length > width) { lines.push(line); line = words[k]; }
                else line = line ? line + ' ' + words[k] : words[k];
            }
            if (line) lines.push(line);
        }
        return lines.join('\r');
    }

    function graphicTitle(seq, template, t, v, length, frame, state) {
        if (!template || !has(seq, 'importMGT')) return null;
        var vt = seq.videoTracks[v], before = vt.clips.numItems, placed = null, k;
        try { placed = seq.importMGT(template, String(Math.round(t.time / frame) * Math.round(frame * TICKS)), v, 0); } catch (e) { return null; }
        if (vt.clips.numItems < before + 1) return null;
        if (!placed || !placed.start) { placed = null; for (k = 0; k < vt.clips.numItems; k++) if (near(seconds(vt.clips[k].start), t.time, frame * .6)) placed = vt.clips[k]; }
        if (!placed) return null;
        if (state.ready) return placed;                         // the text is already inside this template file
        if (setGraphicText(placed, wrapText(t.name, 42))) scaleDown(placed, 50); else state.plain++;
        return placed;
    }

    // Titles on a free video track: an editable graphic when Premiere can make one, otherwise a still
    // image with the text; markers if that fails too.
    function placeTitles(seq, list, files, frame, disabled, template, prepared) {
        var left = [], count = 0, note = '', i, k, paths = [], bin = null, state = {plain: 0, graphics: 0, ready: false};
        var stock = template === false ? '' : titleTemplate(template);
        if (!has(seq, 'importMGT')) stock = '';
        template = stock;
        prepared = stock ? prepared || {} : {};
        for (i = 0; i < list.length; i++) {
            var f = files[list[i].name];
            if (f && new File(f).exists) paths.push(f);
        }
        if (!paths.length && !template) return {count: 0, left: list, note: 'Titr rasmlari topilmadi; markerlar qo‘yildi.'};
        if (!template) try {
            bin = findBin('Smart Voice titrlar');
            var missing = [];
            for (i = 0; i < paths.length; i++) {
                var seen = false;
                for (k = 0; k < missing.length; k++) if (normalPath(missing[k]) === normalPath(paths[i])) seen = true;
                if (!seen && !itemByPath(bin, paths[i])) missing.push(paths[i]);
            }
            if (missing.length) app.project.importFiles(missing, true, bin, false);
        } catch (e) { return {count: 0, left: list, note: 'Titr rasmlarini import qilib bo‘lmadi; markerlar qo‘yildi.'}; }
        for (i = 0; i < list.length; i++) {
            var t = list[i], file = files[t.name], item = file && bin ? itemByPath(bin, file) : null;
            var length = Math.max(frame * 2, round(t.duration || 2, frame));
            if (!item && !template) { left.push(t); continue; }
            var v = freeTrack(seq, t.time, t.time + length, frame);
            if (v < 0) {
                try { app.enableQE(); qe.project.getActiveSequence().addTracks(1, seq.videoTracks.numTracks, 0); } catch (e) {}
                v = freeTrack(seq, t.time, t.time + length, frame);
            }
            if (v < 0) { left.push(t); continue; }
            var vt = seq.videoTracks[v], before = vt.clips.numItems, placed = null, own = prepared[t.name];
            if (own && new File(own).exists) { state.ready = true; placed = graphicTitle(seq, own, t, v, length, frame, state); state.ready = false; }
            if (!placed) placed = graphicTitle(seq, template, t, v, length, frame, state);
            if (placed) state.graphics++;
            else {
                if (template && !item && file && new File(file).exists) {      // the graphic failed: use the picture
                    try {
                        if (!bin) bin = findBin('Smart Voice titrlar');
                        if (!itemByPath(bin, file)) app.project.importFiles([file], true, bin, false);
                        item = itemByPath(bin, file);
                    } catch (e) {}
                }
                if (!item) { left.push(t); continue; }
                before = vt.clips.numItems;
                try { vt.overwriteClip(item, t.time); } catch (e) { left.push(t); continue; }
                for (k = 0; k < vt.clips.numItems; k++) if (near(seconds(vt.clips[k].start), t.time, frame * .6)) placed = vt.clips[k];
                if (!placed || vt.clips.numItems < before + 1) { left.push(t); continue; }
            }
            try { placed.end = timeAt(t.time + length); } catch (e) {}
            if (Math.abs(seconds(placed.end) - (t.time + length)) > frame) note = 'Ba’zi titrlar uzunligi bo‘sh joyga moslanmadi.';
            try { placed.name = String(t.name).substring(0, 200); } catch (e) {}
            // A disabled clip is visible on the timeline but never reaches the export.
            if (disabled) { try { placed.disabled = true; } catch (e) {} }
            count++;
        }
        if (state.plain) note += (note ? ' ' : '') + state.plain + ' ta titr matni yozilmadi (klip nomida turibdi) — Essential Graphics’da o‘zingiz yozing.';
        return {count: count, left: left, note: note, graphics: state.graphics};
    }

    // Move every clip on the track that starts at or after `from` right by `amount` (rightmost first).
    // Optional one-frame Constant Power crossfade on every join. Only the QE DOM can add a transition,
    // and nothing here may stop the work: what could not be added is reported in the message.
    function crossfades(qseq, qtrack, track, from, to, frame) {
        var result = {count: 0, joins: 0}, transition = null, names = ['Constant Power', 'Постоянная мощность', 'Constant Gain', 'Постоянное усиление'], i, k;
        try {
            var list = trackClips(track), starts = [];
            for (i = 1; i < list.length; i++) {
                var s = seconds(list[i].start);
                if (s > from + frame * .25 && s < to - frame * .25 && near(seconds(list[i - 1].end), s, frame * .1)) starts.push(s);
            }
            result.joins = starts.length;
            for (i = 0; i < names.length && !transition; i++) { try { transition = qe.project.getAudioTransitionByName(names[i]); } catch (ignoredName) {} }
            if (!transition || !starts.length) return result;
            var one = String(qseq.CTI.timecode).indexOf(';') >= 0 ? '00;00;00;01' : '00:00:00:01';
            for (i = 0; i < qtrack.numItems; i++) {
                var item = qtrack.getItemAt(i);
                if (!item || String(item.type) === 'Empty' || !item.start) continue;
                for (k = 0; k < starts.length; k++) {
                    if (!near(Number(item.start.secs), starts[k], frame * .1)) continue;
                    // (transition, at the clip start, duration, offset, centred on the cut, both sides, not aligned to video)
                    try { if (item.addTransition(transition, true, one, '0', .5, false, false) !== false) result.count++; } catch (ignoredItem) {}
                    break;
                }
            }
        } catch (ignored) {}
        return result;
    }
    function shiftFollowing(track, from, amount, frame) {
        var list = trackClips(track), i, moved = 0;
        for (i = list.length - 1; i >= 0; i--) {
            if (seconds(list[i].start) < from - frame * .1) continue;
            var target = seconds(list[i].start) + amount;
            list[i].move(timeAt(amount));
            var found = near(seconds(list[i].start), target, frame * .1), after = found ? [] : trackClips(track), j;
            for (j = 0; j < after.length; j++) if (near(seconds(after[j].start), target, frame * .1)) found = true;
            if (!found) fail('Keyingi klipni surib bo‘lmadi.');
            moved++;
        }
        return moved;
    }

    // Premiere without move(): a kept piece is laid again at its place, from its own media item with the
    // piece's in/out points, after the old copy is lifted. Right to left, so a piece never lands on one
    // that has not been moved yet. The media item's own in/out marks are put back afterwards.
    function pointsOf(item) {
        var saved = {inPoint: null, outPoint: null};
        try { saved.inPoint = String(item.getInPoint(4).ticks); } catch (e) {}
        try { saved.outPoint = String(item.getOutPoint(4).ticks); } catch (e1) {}
        return saved;
    }
    function restorePoints(item, saved) {
        try { if (saved.inPoint !== null) item.setInPoint(saved.inPoint, 4); else item.clearInPoint(); } catch (e) {}
        try { if (saved.outPoint !== null) item.setOutPoint(saved.outPoint, 4); else item.clearOutPoint(); } catch (e1) {}
    }
    function clipAt(track, start, frame) {
        var list = trackClips(track), i;
        for (i = 0; i < list.length; i++) if (near(seconds(list[i].start), start, frame * .25)) return list[i];
        return null;
    }
    // Lays `item` [inPoint, inPoint + length) at `start`; returns the new clip or null (nothing left behind).
    function layAt(track, item, start, inPoint, length, frame) {
        // The time formats Premiere versions accept differ: ticks first, then seconds.
        var forms = [function (t) { return String(Math.round(t / frame) * Math.round(frame * TICKS)); }, function (t) { return t; }], f;
        for (f = 0; f < forms.length; f++) {
            try {
                item.setInPoint(String(Math.round(inPoint * TICKS)), 4);
                item.setOutPoint(String(Math.round((inPoint + length) * TICKS)), 4);
            } catch (e) { continue; }
            var before = track.clips.numItems;
            try { track.overwriteClip(item, forms[f](start)); } catch (e1) { continue; }
            var placed = clipAt(track, start, frame);
            if (placed && track.clips.numItems === before + 1) {
                if (!near(seconds(placed.end), start + length, frame * .25)) { try { placed.end = timeAt(start + length); } catch (e2) {} }
                if (near(seconds(placed.inPoint), inPoint, frame * .25) && near(seconds(placed.end), start + length, frame * .25)) return placed;
            }
            if (placed && track.clips.numItems > before) { try { placed.remove(false, false); } catch (e3) {} }
        }
        return null;
    }
    function relayPieces(track, keep, origin, frame) {
        // After the ripple delete the kept pieces are the first clips from `origin` on, in order.
        var list = trackClips(track), now = [], i, moved = 0;
        for (i = 0; i < list.length && now.length < keep.length; i++) if (seconds(list[i].start) >= origin - frame * .25) now.push(list[i]);
        for (i = 0; i < keep.length; i++) {
            if (!now[i] || !near(seconds(now[i].end) - seconds(now[i].start), keep[i].length, frame * .25) || !near(seconds(now[i].inPoint), keep[i].inPoint, frame * .25))
                fail('Bo‘sh joy ochishdan oldin bo‘laklar tasdiqlanmadi. Hech narsa ko‘chirilmadi; kesish tugagan — Edit > Undo bilan qaytarish mumkin.');
        }
        for (i = keep.length - 1; i >= 0; i--) {
            var clip = now[i], start = seconds(clip.start), target = keep[i].segment.target + keep[i].offset;
            if (target <= start + frame * .25) continue;
            var item = clip.projectItem, inPoint = seconds(clip.inPoint), length = seconds(clip.end) - start, name = String(clip.name), saved = pointsOf(item);
            var count = track.clips.numItems;
            clip.remove(false, false);
            if (track.clips.numItems !== count - 1) { restorePoints(item, saved); fail('Bo‘sh joy ochish uchun bo‘lakni olib bo‘lmadi (' + start.toFixed(2) + ' s).'); }
            var placed = layAt(track, item, target, inPoint, length, frame);
            if (!placed) {
                var back = layAt(track, item, start, inPoint, length, frame);
                restorePoints(item, saved);
                fail('Premiere bo‘lakni ' + target.toFixed(2) + ' s ga qo‘ymadi' + (back ? '' : ' va u o‘z joyiga ham qaytmadi (' + start.toFixed(2) + ' s) — Edit > Undo bilan qaytaring') + '. ' + moved + ' ta bo‘lak ko‘chirilgan edi.');
            }
            restorePoints(item, saved);
            try { placed.name = name; } catch (e) {}
            moved++;
        }
        return moved;
    }

    function apply(raw) {
        var seq = null, player = null, phase = 'tekshirish', removed = 0, moved = 0, shifted = 0, details = {};
        var clock = new Date().getTime(), times = {};
        function mark(next) { var now = new Date().getTime(); times[phase] = Math.round(((times[phase] || 0) + (now - clock) / 1000) * 10) / 10; clock = now; phase = next; }
        try {
            var request = JSON.parse(raw), expected = request.clip;
            if (!expected) fail('Klip ma’lumoti yo‘q. Klipni qayta oling va tahlil qiling.');
            var state = snapshot(expected);
            if (state.data.signature !== expected.signature || state.data.sequenceId !== expected.sequenceId)
                fail('Sequence yoki tanlov o‘zgargan. Klipni qayta oling va tahlil qiling.');
            seq = state.seq;
            var data = state.data, pieces = data.pieces, frame = data.frame, i, j;
            var ranges = request.ranges, duration = data.duration;
            if (!ranges || !ranges.length || ranges.length > 20000) fail('Kesim rejasi bo‘sh yoki juda katta.');
            var last = 0;
            for (i = 0; i < ranges.length; i++) {
                var r = ranges[i];
                if (!isFinite(r.start) || !isFinite(r.end) || r.start < last - .001 || r.end <= r.start || r.end > duration + .001) fail('Kesim chegaralari noto‘g‘ri.');
                last = r.end;
            }
            var segments = keptSegments(pieces, ranges, frame);
            if (!segments.length) fail('Saqlanadigan qism qolmadi.');
            var useMove = data.canMove && request.useMove !== false;
            if (data.linked) fail('Ovoz klipi video bilan bog‘langan (linked). Video joyida qolishi uchun klipni tanlab, o‘ng tugma → Unlink qiling va qayta urinib ko‘ring.');
            var leadGap = Math.max(0, round(Number(request.leadGap) || 0, frame));
            // Without move() (Premiere 2020 and older) a gap can only be what is left of the removed material,
            // so the space actually opened (the "hold") may be shorter than planned. Titles and markers follow
            // the space that really opens, otherwise every short gap shifts all later titles to the right.
            // The missing part is then opened by laying the following pieces again further right ("relay").
            var shortGaps = 0, relay = false, deficit = 0, gapRoom = data.nextStart === null ? Infinity : data.nextStart - pieces[pieces.length - 1].end;
            if (!useMove) {
                for (i = 0; i < segments.length; i++) {
                    var g = (i + 1 < segments.length && segments[i + 1].range !== segments[i].range) ? Math.max(0, round(Number(ranges[segments[i].range].gapAfter) || 0, frame)) : 0;
                    if (i === 0 && leadGap > 0) {
                        segments[0].leadHold = Math.min(leadGap, Math.max(0, segments[0].a - pieces[segments[0].piece].start));
                        deficit += leadGap - round(segments[0].leadHold, frame);
                    }
                    segments[i].hold = g > 0 && segments[i].piece === segments[i + 1].piece ? Math.max(0, Math.min(g, segments[i + 1].a - segments[i].b)) : 0;
                    if (g > 0) deficit += g - round(segments[i].hold, frame);
                }
                // Laying a piece again needs its media item with settable in/out points (Premiere 13+), and the
                // longer result must still end before the next clip on the track.
                var media = null;
                try { media = state.clips[0].projectItem; } catch (e) {}
                if (deficit > frame * .5 && request.openGaps !== false && has(track0(), 'overwriteClip') && has(media, 'setInPoint') && has(media, 'setOutPoint')) {
                    if (deficit <= gapRoom + frame * .25) relay = true;
                    else details.relayNote = 'Bo‘sh joylarni to‘liq ochish uchun trekdagi keyingi klipgacha ' + (deficit - gapRoom).toFixed(1) + ' s yetmaydi.';
                }
            }
            function track0() { return seq.audioTracks[state.track]; }
            function opened(planned, hold) {
                if (useMove || relay) return planned;
                var real = Math.max(0, round(hold || 0, frame));
                if (real < planned - frame * .5) shortGaps++;
                return real;
            }
            var origin = pieces[0].start, leadReal = leadGap > 0 ? opened(leadGap, segments[0].leadHold) : 0;
            var cursor = origin + leadReal, keptTotal = 0, gapTotal = leadReal, markers = [];
            // A title is at least as long as planned when the real space is too short to read it.
            if (leadGap > 0) markers.push({time: origin, duration: leadReal >= 1 ? leadReal : leadGap, name: request.leadLabel || 'Bo‘sh joy'});
            for (i = 0; i < segments.length; i++) {
                var seg = segments[i];
                seg.target = cursor; cursor += seg.b - seg.a; keptTotal += seg.b - seg.a;
                var lastOfRange = i + 1 === segments.length || segments[i + 1].range !== seg.range;
                if (lastOfRange && i + 1 < segments.length) {
                    var gap = Math.max(0, round(Number(ranges[seg.range].gapAfter) || 0, frame));
                    if (gap > 0) {
                        var real = opened(gap, seg.hold);
                        // Plain space (where a breath was) gets neither a title nor a marker.
                        if (ranges[seg.range].gapPlain !== true) { markers.push({time: cursor, duration: real >= 1 ? real : gap, name: ranges[seg.range].gapLabel || 'Bo‘sh joy'}); gapTotal += real; }
                        cursor += real;
                    }
                }
            }
            var finalEnd = cursor;
            if (request.tailLabel) markers.push({time: finalEnd, duration: 5, name: request.tailLabel});
            var track = seq.audioTracks[state.track];
            if (!has(track.clips[0], 'remove')) fail('Bu Premiere versiyasida klipni skript orqali o‘chirish imkoni yo‘q.');
            if (relay) details.note = 'Premiere move() yo‘q: bo‘sh joylar bo‘laklarni yangi joyga qayta qo‘yish orqali ochildi (qayta qo‘yilgan bo‘laklarda klipga berilgan effekt/ovoz balandligi sozlamasi bo‘lsa, u tushib qoladi).';
            else if (!useMove && shortGaps > 0) details.note = 'Premiere’ning bu versiyasida move() yo‘q: ' + shortGaps + ' ta bo‘sh joy to‘liq ochilmadi (o‘rnida olib tashlanadigan qism yetarli emas). Titrlar haqiqiy joyida turibdi, lekin ularning ostida ovoz bor — kerak bo‘lsa bo‘sh joyni qo‘lda oching.' + (details.relayNote ? ' ' + details.relayNote : '');
            else if (!useMove && gapTotal > 0) details.note = 'Premiere move() yo‘q: bo‘sh joylar faqat olib tashlanadigan qism hisobidan ochildi.';
            var lastEnd = pieces[pieces.length - 1].end;
            if (useMove && data.nextStart !== null && finalEnd > data.nextStart + frame * .25) {
                var need = round(finalEnd - data.nextStart + frame, frame);
                if (request.shiftFollowing !== true)
                    fail('Natija trekdagi keyingi klipgacha sig‘maydi (' + need.toFixed(2) + ' s yetmaydi). «Keyingi kliplarni surish»ni yoqing yoki bo‘sh joylarni kamaytiring.');
            }
            var needShift = useMove && data.nextStart !== null && finalEnd > data.nextStart + frame * .25;
            var saved = {name: '', note: ''};
            if (request.backup === true) { mark('zaxira nusxa'); saved = backup(seq); }
            if (needShift) {
                mark('keyingi kliplarni surish');
                shifted = shiftFollowing(track, data.nextStart, round(finalEnd - data.nextStart + frame, frame), frame);
            }

            // Razor points: kept segment edges that are not already clip edges.
            var cuts = [];
            var edges = [], startClips = regionClips(track, pieces, frame);
            for (i = 0; i < startClips.length; i++) { edges.push(seconds(startClips[i].start)); edges.push(seconds(startClips[i].end)); }
            function isEdge(t) {
                for (var k = 0; k < edges.length; k++) if (near(edges[k], t, frame * .1)) return true;
                return false;
            }
            for (i = 0; i < segments.length; i++) { cuts.push(segments[i].a); cuts.push(segments[i].b); }
            if (!useMove) {
                // Ripple: keep part of the removed material as the gap.
                // The holds were worked out above, together with the title times.
                for (i = 0; i < segments.length; i++) {
                    if (i === 0 && segments[0].leadHold > 0 && segments[0].leadHold < segments[0].a - pieces[segments[0].piece].start) cuts.push(segments[0].a - segments[0].leadHold);
                    if (segments[i].hold > 0 && i + 1 < segments.length && segments[i].hold < segments[i + 1].a - segments[i].b) cuts.push(segments[i].b + segments[i].hold);
                }
            }
            cuts.sort(function (a, b) { return b - a; });
            app.enableQE();
            var qseq = qe.project.getActiveSequence();
            if (!qseq) fail('Premiere QE sequence topilmadi.');
            var qtrack = qseq.getAudioTrackAt(state.track);
            if (!qtrack) fail('Audio trekni bo‘lish vositasi topilmadi.');
            player = seq.getPlayerPosition().ticks;
            mark('klipni bo‘lish');
            for (i = 0; i < cuts.length; i++) {
                if (i && near(cuts[i], cuts[i - 1], frame * .25)) continue;
                if (isEdge(cuts[i])) continue;
                var before = track.clips.numItems;
                setCTI(seq, cuts[i], frame);
                qtrack.razor(qseq.CTI.timecode);
                if (track.clips.numItems !== before + 1) fail('Premiere klipni ' + cuts[i].toFixed(2) + ' soniyada bo‘lmadi. Hech narsa o‘chirilmagan.');
                edges.push(cuts[i]);
            }
            mark('bo‘laklarni tekshirish');
            var region = regionClips(track, pieces, frame), keep = [], drop = [];
            for (i = 0; i < region.length; i++) {
                var cs = seconds(region[i].start), ce = seconds(region[i].end), owner = null;
                for (j = 0; j < segments.length; j++) {
                    if (cs >= segments[j].a - frame * .25 && ce <= segments[j].b + frame * .25) { owner = segments[j]; break; }
                    if (cs < segments[j].b - frame * .25 && ce > segments[j].a + frame * .25) fail('Kesim chegarasi tasdiqlanmadi. Hech narsa o‘chirilmagan.');
                }
                if (owner) keep.push({clip: region[i], segment: owner, offset: cs - owner.a, length: ce - cs, inPoint: seconds(region[i].inPoint)});
                else drop.push(region[i]);
            }
            details.keep = keep.length; details.drop = drop.length;

            if (useMove) {
                mark('ortiqcha qismlarni olib tashlash');
                for (i = drop.length - 1; i >= 0; i--) {
                    var count = track.clips.numItems;
                    drop[i].remove(false, false);
                    if (track.clips.numItems !== count - 1) fail('Premiere bo‘lakni o‘chirmadi.');
                    removed++;
                }
                mark('bo‘laklarni joylashtirish');
                var plan = [];
                for (i = 0; i < keep.length; i++) plan.push({clip: keep[i].clip, start: keep[i].segment.a + keep[i].offset, target: keep[i].segment.target + keep[i].offset});
                // Left movers left-to-right, then right movers right-to-left: never overlapping.
                var order = [];
                for (i = 0; i < plan.length; i++) if (plan[i].target < plan[i].start - frame * .1) order.push(i);
                for (i = plan.length - 1; i >= 0; i--) if (plan[i].target > plan[i].start + frame * .1) order.push(i);
                for (i = 0; i < order.length; i++) {
                    var p = plan[order[i]], item = p.clip, list;
                    if (!near(seconds(item.start), p.start, frame * .1)) {   // the reference went stale: look the clip up
                        item = null; list = trackClips(track);
                        for (j = 0; j < list.length; j++) if (near(seconds(list[j].start), p.start, frame * .1)) { item = list[j]; break; }
                        if (!item) fail('Ko‘chiriladigan bo‘lak topilmadi.');
                    }
                    item.move(timeAt(p.target - p.start));
                    var now = near(seconds(item.start), p.target, frame * .1) ? item : null;
                    if (!now) { list = trackClips(track); for (j = 0; j < list.length; j++) if (near(seconds(list[j].start), p.target, frame * .1)) now = list[j]; }
                    if (!now) fail('Bo‘lak kutilgan joyga ko‘chmadi (' + p.target.toFixed(2) + ' s).');
                    moved++;
                }
            } else {
                mark('ortiqcha qismlarni olib tashlash');
                for (i = drop.length - 1; i >= 0; i--) {
                    var ds = seconds(drop[i].start), de = seconds(drop[i].end), hold = false;
                    for (j = 0; j < segments.length; j++) {
                        if (segments[j].hold && near(ds, segments[j].b, frame * .25) && de <= segments[j].b + segments[j].hold + frame * .25) hold = true;
                        if (j === 0 && segments[0].leadHold && near(de, segments[0].a, frame * .25) && ds >= segments[0].a - segments[0].leadHold - frame * .25) hold = true;
                    }
                    var n = track.clips.numItems;
                    drop[i].remove(!hold, true);
                    if (track.clips.numItems !== n - 1) fail('Premiere ripple-delete amalini bajarmadi.');
                    removed++;
                }
                if (relay) { mark('bo‘sh joylarni ochish'); moved = relayPieces(track, keep, origin, frame); }
            }
            var fades = null;
            if (request.crossfade === true) { mark('crossfade'); fades = crossfades(qseq, qtrack, track, origin, Math.max(finalEnd, lastEnd), frame); }
            mark('titrlar');
            var markerCount = 0, titleCount = 0, titleNote = '';
            if (request.titles !== false && markers.length) {
                var placed = placeTitles(seq, markers, request.titleFiles || {}, frame, request.titlesDisabled === true, request.titleGraphics === false ? false : request.titleTemplate || '', request.titleGraphicFiles);
                details.titleGraphics = placed.graphics || 0;
                titleCount = placed.count; titleNote = placed.note; markers = placed.left;
            }
            if (request.titles !== false && markers.length && seq.markers && has(seq.markers, 'createMarker')) {
                for (i = 0; i < markers.length; i++) {
                    try { var m = seq.markers.createMarker(markers[i].time); m.name = String(markers[i].name).substring(0, 120); m.comments = 'Smart Voice: intervyu/stendap uchun joy'; markerCount++; } catch (ignoredMarker) {}
                }
            }
            var kept = 0, list2 = trackClips(track);
            for (i = 0; i < list2.length; i++) {
                var s2 = seconds(list2[i].start), e2 = seconds(list2[i].end);
                if (s2 >= origin - frame * .25 && e2 <= Math.max(finalEnd, lastEnd) + frame * .25) kept += e2 - s2;
            }
            if (Math.abs(kept - keptTotal) > frame * 2) fail('Yakuniy davomiylik kutilgan qiymatga mos emas (' + kept.toFixed(2) + ' / ' + keptTotal.toFixed(2) + ' s).');
            var removedSeconds = duration - keptTotal;
            mark('tayyor');
            return JSON.stringify({times: times,
                message: 'Tayyor: ' + removedSeconds.toFixed(1) + ' s olib tashlandi (' + removed + ' bo‘lak)' +
                    (gapTotal > 0 ? ', ' + gapTotal.toFixed(1) + ' s bo‘sh joy ochildi' + (titleCount ? ', ' + titleCount + ' ta titr' : '') + (markerCount ? ', ' + markerCount + ' ta marker' : '') : '') +
                    (shifted ? ', keyingi ' + shifted + ' ta klip surildi' : '') + '. ' + (titleNote ? titleNote + ' ' : '') +
                    (useMove ? 'Video va boshqa treklar o‘zgarmadi.' : 'Ripple usuli ishlatildi.') +
                    (fades ? (fades.count ? ' Crossfade: ' + fades.count + '/' + fades.joins + ' ta ulanishga qo‘yildi.' :
                        fades.joins ? ' Crossfade qo‘yilmadi (bu Premiere’da vosita topilmadi) — kerak bo‘lsa kliplarni tanlab Ctrl+Shift+D bosing.' : '') : '') +
                    (saved.name ? ' Asl holat loyihada saqlandi: «' + saved.name + '».' : '') + (saved.note ? ' ' + saved.note : ''),
                removed: removed, moved: moved, shifted: shifted, removedSeconds: removedSeconds, gapSeconds: gapTotal,
                titles: titleCount, titleGraphics: details.titleGraphics || 0, markers: markerCount, crossfades: fades ? fades.count : 0, method: useMove ? 'move' : 'ripple', note: details.note || '', backup: saved.name});
        } catch (e) {
            var failed = phase; mark(failed); details.times = times;
            details.phase = phase; details.removed = removed; details.moved = moved; details.shifted = shifted;
            var done = removed + moved + shifted;
            return JSON.stringify({error: phase + ': ' + e.message + (done ? ' Bajarilgan amallar: ' + done + '. Orqaga qaytish uchun Edit > Undo dan foydalaning.' : ''), details: details});
        } finally {
            if (seq && player !== null) { try { seq.setPlayerPosition(player); } catch (ignored) {} }
        }
    }
    function template() { try { return JSON.stringify({path: titleTemplate('').replace(/\\/g, '/')}); } catch (e) { return JSON.stringify({path: ''}); } }

    return {inspect: inspect, apply: apply, template: template, version: '1.1.8'};
}());
