"""Analysis sessions: recognition once, then fast re-planning while the user reviews."""
import hashlib
import itertools
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np

import asr
import edits
from audio import Acoustics, RATE, assemble, fingerprint, layout, speech_spans, write_wav
from script import SPEAKABLE, parse_script, tokenize
from text import detect_language, tokens

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / '.cache' / 'preview'
SESSIONS = OrderedDict()
SESSION_LIMIT = 2
ORIGINAL_DAYS = 3    # original-*.wav previews are rebuilt on demand
_lock = threading.Lock()
_counter = itertools.count(1)


def silent(_message):
    pass


def analyze(body, report=silent):
    began = time.perf_counter()
    clip = body.get('clip')
    if not isinstance(clip, dict):
        raise ValueError('Avval timeline’dan audio klipni oling.')
    pieces = layout(clip)
    identity = fingerprint(pieces)
    options = {'pauses': body.get('pauses', True) is not False, 'breaths': body.get('breaths', True) is not False,
               'crossfade': body.get('crossfade') is True}
    report('Audio ochilmoqda…')
    audio = assemble(pieces)
    ac = Acoustics(audio)
    result = {'pause_only': bool(body.get('pause_only')), 'duration': round(ac.duration, 3)}
    if body.get('pause_only'):
        report('Pauzalar tovush bo‘yicha o‘lchanmoqda…')
        state = edits.prepare(edits.sound_words(ac), ac, clip)
        result.update(language=None, model='tovush tahlili', device='cpu', cache=False)
    else:
        paths = body.get('scripts') or []
        if not paths:
            raise ValueError('Word yoki matn ssenariysini (.docx, .txt) tanlang.')
        scripts = [parse_script(p) for p in paths]
        spoken = '\n'.join(b['text'] for s in scripts for b in s if b['kind'] in SPEAKABLE)
        if not tokens(spoken):
            raise ValueError('Ssenariyda o‘qiladigan matn topilmadi.')
        # The user names the language; it is guessed from the script only when a caller sends none.
        language = body.get('language')
        if language in (None, '', 'auto'):
            language = detect_language(spoken)
        elif language not in ('uz', 'ru', 'en'):
            raise ValueError('Yozuv tili noto‘g‘ri: o‘zbekcha, ruscha yoki inglizchani tanlang.')
        mode = asr.choose_mode(body.get('mode'), language)
        report('Ovoz faolligi aniqlanmoqda…')
        spans = speech_spans(audio)
        words, info = asr.recognise(audio, identity, mode, body.get('use_gpu', True) is not False, spans, report)
        if not words:
            raise ValueError('Audioda nutq topilmadi.')
        report('Ssenariy bo‘yicha o‘qish kuzatilmoqda…')
        if len(scripts) > 1:
            scripts = order_scripts(scripts, words, language)
        blocks = [dict(b) for s in scripts for b in s]
        script, marks, block_of = tokenize(blocks, language)
        state = edits.prepare(words, ac, clip, script, marks, block_of, blocks, language,
                              strict=body.get('strict', True) is not False)
        reading = state['reading']
        result.update(language=language, mode=mode, model=asr.MODELS[mode]['name'], device=info['device'],
                      cache=info['cache'], recovered_words=info['recovered'],
                      coverage=round(reading['coverage'], 4), low_coverage=reading['low_coverage'],
                      missing=reading['missing'][:300],
                      outside_script_words=reading['outside_script_words'],
                      transcript=' '.join(w['word'].strip() for w in words),
                      parts=[{'kind': b['kind'], 'label': b.get('label') or b['text'][:60], 'voiced': b.get('voiced')}
                             for b in blocks if b['tokens']])
    state['options'] = options
    state['identity'] = identity
    report('Kesimlar hisoblanmoqda…')
    session = store(state)
    result['session'] = session
    result['items'] = [public_item(i) for i in state['items']]
    result['gaps'] = [{'id': g['id'], 'label': g['label'], 'seconds': g['seconds']} for g in state['gap_slots'].values()]
    result['lead_gap'] = state['lead_gap']
    result['tail'] = state['tail']
    report('Eshitish uchun audio tayyorlanmoqda…')
    result['original_preview'] = original_preview(state)
    result['plan'] = plan_for(state, {}, {}, options, render=True)
    result['elapsed_seconds'] = round(time.perf_counter() - began, 1)
    return result


def order_scripts(scripts, words, language):
    """Several Word files read in one recording: order them by where their reading starts."""
    from align import follow
    heard, _ = edits.heard_tokens(words, language)

    def start(item):
        index, blocks = item
        script, _, _ = tokenize([dict(b) for b in blocks], language)
        path, reads = follow(script, heard)
        run = 0
        for k, (p, r) in enumerate(zip(path, reads)):
            run = run + 1 if p >= 0 and r else 0
            if run >= 4:
                return k
        return 10 ** 9 + index
    return [s for _, s in sorted(enumerate(scripts), key=start)]


def public_item(item):
    keys = ('id', 'kind', 'text', 'start', 'end', 'selected', 'review', 'reason', 'confidence')
    return {k: (round(item[k], 3) if isinstance(item.get(k), float) else item.get(k)) for k in keys if k in item}


def store(state):
    with _lock:
        session = 's%d-%s' % (next(_counter), state['identity'][:8])
        SESSIONS[session] = state
        while len(SESSIONS) > SESSION_LIMIT:
            SESSIONS.popitem(last=False)
    return session


def plan(body):
    state = SESSIONS.get(body.get('session'))
    if state is None:
        raise ValueError('Tahlil eskirgan (backend qayta ishga tushgan). Qayta tahlil qiling.')
    options = dict(state['options'], **{k: bool(v) for k, v in (body.get('options') or {}).items()
                                        if k in ('pauses', 'breaths', 'crossfade')})
    return plan_for(state, body.get('decisions') or {}, body.get('gaps') or {}, options,
                    render=body.get('render', False) is True)


def plan_for(state, decisions, gaps, options, render=False):
    result = edits.build(state, decisions, gaps, options)
    # Which junction each proposal falls into (to listen to the joined result).
    for item in state['items']:
        for j in result['junctions']:
            if j['start'] - .05 <= item['start'] and item['end'] <= j['end'] + .3:
                item_junction = j['id']
                break
        else:
            item_junction = None
        result.setdefault('item_junction', {})[item['id']] = item_junction
    if render:
        result['preview'], result['map'] = render_result(state, result, options.get('crossfade') is True)
    return result


def original_preview(state):
    target = PREVIEW / ('original-' + state['identity'][:32] + '.wav')
    prune('original-*.wav', ORIGINAL_DAYS * 86400, keep=target)
    if target.exists():
        try:
            os.utime(target)  # in use again: keep it
        except OSError:
            pass
        return str(target.resolve())
    return write_wav(target, state['acoustics'].audio)


def prune(pattern, seconds, keep=None):
    """Delete preview files older than `seconds`."""
    for old in PREVIEW.glob(pattern):
        try:
            if old != keep and time.time() - old.stat().st_mtime > seconds:
                old.unlink()
        except OSError:
            pass


def crossfade(out, audio, joins, half):
    """Equal-power crossfade centred on each join, like Premiere's Constant Power transition:
    the left clip plays on for `half` samples past the cut while the right one starts `half` early."""
    if half < 1:
        return 0
    t = (np.arange(2 * half, dtype=np.float32) + .5) / (2 * half) * (np.pi / 2)
    down, up, done = np.cos(t), np.sin(t), 0
    for at, end, start in joins:   # result sample of the join, source sample where the left ends / the right starts
        if at - half < 0 or at + half > len(out) or end + half > len(audio) or start - half < 0:
            continue
        out[at - half:at + half] = audio[end - half:end + half] * down + audio[start - half:start + half] * up
        done += 1
    return done


def render_result(state, result, fade=False):
    """WAV of exactly what Premiere will hold (gaps are silence) and result times of each junction."""
    audio = state['acoustics'].audio
    chunks, cursor, seams, size = [], 0., [], 0
    lead = result['lead_gap']
    if lead > 0:
        chunks.append(np.zeros(int(round(lead * RATE)), np.float32))
        cursor += lead
        size += len(chunks[-1])
    joins, previous = {}, None
    for r in result['ranges']:
        a, b = int(round(r['start'] * RATE)), int(round(r['end'] * RATE))
        piece = audio[a:b]
        if previous is not None and a > previous:   # a cut with nothing between the two clips
            seams.append((size, previous, a))
        chunks.append(piece)
        cursor += len(piece) / RATE
        size += len(piece)
        previous = a + len(piece)
        for jid in r.get('joins', []):
            joins[jid] = cursor
        gap = r.get('gapAfter', 0)
        if gap and r is not result['ranges'][-1]:
            chunks.append(np.zeros(int(round(gap * RATE)), np.float32))
            cursor += gap
            size += len(chunks[-1])
            previous = None
    out = np.concatenate(chunks) if chunks else np.zeros(1, np.float32)
    if fade and seams:
        frame = state['grid'].frame
        # Each clip gives at most a third of itself to a fade.
        shortest = min(int(round((r['end'] - r['start']) * RATE)) for r in result['ranges'])
        crossfade(out, audio, seams, min(int(round(frame * RATE / 2)), shortest // 3))
    key = hashlib.sha256(repr(result['ranges']).encode() + str(lead).encode() + (b'x' if fade else b'')).hexdigest()[:20]
    PREVIEW.mkdir(parents=True, exist_ok=True)
    prune('result-*.wav', 600)
    with _lock:  # two renders of the same plan would share one temporary file
        path = write_wav(PREVIEW / ('result-' + key + '.wav'), out)
    return path, {k: round(v, 3) for k, v in joins.items()}
