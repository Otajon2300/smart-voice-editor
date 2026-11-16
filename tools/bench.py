"""Synthetic benchmark on a real voice recording.

Takes a clean reading and its words, builds a "dirty" take with known
retakes (partial restarts, whole repeated sentences, stutters) and long
pauses, runs the full analysis and measures:
  - share of inserted retake audio that is cut (should be ~100%)
  - original words damaged by a cut (should be 0)
  - pause length left where a long pause was inserted
Usage:
  python tools/bench.py --audio evaluation/real/uzb.wav --words evaluation/bench/uzb-words.json --out evaluation/bench/run
"""
import argparse
import json
import random
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.stdout.reconfigure(encoding='utf-8')
RATE = 16000


def docx(paragraphs, path):
    body = ''.join('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % escape(p) for p in paragraphs)
    xml = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"><w:body>%s</w:body></w:document>' % body)
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('word/document.xml', xml)


def sentences(words):
    out, current = [], []
    for i, w in enumerate(words):
        current.append(i)
        if re.search(r'[.!?]\s*$', w['word']):
            out.append(current)
            current = []
    if current:
        out.append(current)
    return out


def room_tone(audio, seconds):
    hop = 160
    rms = np.sqrt(np.mean(audio[:len(audio) // hop * hop].reshape(-1, hop) ** 2, axis=1))
    candidates = np.flatnonzero((rms > 1e-5) & (rms < np.quantile(rms[rms > 1e-5], .08)))
    # Longest run of quiet frames as the tone source.
    best = (0, 0)
    quiet = np.zeros(len(rms), bool)
    quiet[candidates] = True
    k = 0
    while k < len(quiet):
        if quiet[k]:
            j = k
            while j < len(quiet) and quiet[j]:
                j += 1
            if j - k > best[1] - best[0]:
                best = (k, j)
            k = j
        else:
            k += 1
    piece = audio[best[0] * hop:best[1] * hop]
    if len(piece) < 1600:
        piece = np.random.default_rng(0).normal(0, 1e-4, 1600).astype(np.float32)
    reps = int(np.ceil(seconds * RATE / len(piece))) + 1
    return np.tile(piece, reps)[:int(seconds * RATE)]


def build(audio, words, seed=7):
    rng = random.Random(seed)
    sents = [s for s in sentences(words) if len(s) >= 6]
    chosen = rng.sample(range(1, len(sents) - 1), min(len(sents) - 2, 22))
    kinds = ['partial', 'partial', 'full', 'stutter', 'pause', 'pause']
    plan = {}
    for n, index in enumerate(sorted(chosen)):
        plan[sents[index][0]] = kinds[n % len(kinds)]
    pieces, truth, cursor = [], {'retakes': [], 'pauses': [], 'original': []}, 0
    position = 0  # sample position in the source

    def add(chunk):
        nonlocal cursor
        pieces.append(chunk)
        cursor += len(chunk)

    sent_of = {i: s for s in sentences(words) for i in s}
    for i, w in enumerate(words):
        start = int(w['start'] * RATE)
        if i in plan:
            # Everything up to just before this word's onset (incl. the existing pause).
            onset = max(position, start - int(.03 * RATE))
            add(audio[position:onset])
            position = onset
            kind = plan[i]
            sent = sent_of[i]
            if kind == 'partial':
                k = rng.randint(2, 5)
                a, b = int(words[sent[0]]['start'] * RATE) - 480, int(words[sent[k - 1]]['end'] * RATE) + 480
                t0 = cursor
                add(audio[a:b])
                truth['retakes'].append((t0 / RATE, cursor / RATE, 'partial'))
                add(room_tone(audio, .6))
            elif kind == 'full':
                a, b = int(words[sent[0]]['start'] * RATE) - 480, int(words[sent[-1]]['end'] * RATE) + 800
                t0 = cursor
                add(audio[a:b])
                truth['retakes'].append((t0 / RATE, cursor / RATE, 'full'))
                add(room_tone(audio, .8))
            elif kind == 'stutter':
                a, b = int(w['start'] * RATE) - 320, int((w['start'] + min(.25, (w['end'] - w['start']) * .45)) * RATE)
                t0 = cursor
                add(audio[a:b])
                truth['retakes'].append((t0 / RATE, cursor / RATE, 'stutter'))
                add(room_tone(audio, .35))
            elif kind == 'pause':
                t0 = cursor
                add(room_tone(audio, 2.5))
                truth['pauses'].append((t0 / RATE, cursor / RATE, i))
    add(audio[position:])
    dirty = np.concatenate(pieces).astype(np.float32)
    return dirty, truth, plan


def map_words(words, plan, truth):
    """Times of the original words in the dirty recording."""
    inserted = sorted([(a, b) for a, b, _ in truth['retakes']] + [(a, b) for a, b, _ in truth['pauses']])
    # Insertions happen in order; each starts right before a planned word.
    out, shift = [], 0.
    keys = sorted(plan)
    gaps_after = {}
    tone = {'partial': .6, 'full': .8, 'stutter': .35, 'pause': 0.}
    for key, (a, b) in zip(keys, inserted):
        gaps_after[key] = (b - a) + tone[plan[key]]
    for i, w in enumerate(words):
        if i in gaps_after:
            shift += gaps_after[i]
        out.append({'word': w['word'], 'start': w['start'] + shift, 'end': w['end'] + shift})
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audio', required=True)
    parser.add_argument('--words', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--mode', default='auto')
    parser.add_argument('--cpu', action='store_true')
    args = parser.parse_args()
    from faster_whisper.audio import decode_audio
    import service
    from audio import write_wav
    audio = decode_audio(args.audio, sampling_rate=RATE)
    words = json.loads(Path(args.words).read_text(encoding='utf-8'))
    dirty, truth, plan = build(audio, words)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'dirty.wav'
    # Keep the file (and its date) when unchanged, so the recognition cache stays valid.
    wav = str(target.resolve()) if target.exists() and target.stat().st_size == 44 + 2 * len(dirty) else write_wav(target, dirty)
    text = ''.join(w['word'] for w in words).strip()
    paragraphs, current = [], []
    for sentence in re.split(r'(?<=[.!?])\s+', text):
        current.append(sentence)
        if len(current) == 4:
            paragraphs.append(' '.join(current))
            current = []
    if current:
        paragraphs.append(' '.join(current))
    script = out / 'script.docx'
    docx(paragraphs, script)
    duration = len(dirty) / RATE
    clip = {'path': wav, 'name': 'dirty.wav', 'start': 0., 'end': duration, 'inPoint': 0., 'outPoint': duration,
            'frame': .04}
    result = service.analyze({'clip': clip, 'scripts': [str(script)], 'mode': args.mode, 'use_gpu': not args.cpu},
                             lambda m: print('  ·', m, flush=True) if '%' not in m else None)
    (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    ranges = result['plan']['ranges']
    cuts, cursor = [], 0.
    for r in ranges:
        if r['start'] > cursor:
            cuts.append((cursor, r['start']))
        cursor = r['end']
    if cursor < duration:
        cuts.append((cursor, duration))

    def cut_share(a, b):
        return sum(max(0., min(b, e) - max(a, s)) for s, e in cuts) / (b - a)

    print('\n== Takrorlar')
    ok = 0
    for a, b, kind in truth['retakes']:
        share = cut_share(a, b)
        ok += share >= .9
        print('  %-8s %7.2f–%7.2f  kesilgan %3.0f%%' % (kind, a, b, share * 100))
    print('  jami: %d/%d to‘liq kesildi' % (ok, len(truth['retakes'])))
    mapped = map_words(words, plan, truth)
    damaged = []
    for w in mapped:
        inside = sum(max(0., min(w['end'], e) - max(w['start'], s)) for s, e in cuts)
        if inside > .35 * (w['end'] - w['start']) and inside > .06:
            damaged.append((round(w['start'], 2), w['word'].strip(), round(inside, 2)))
    print('\n== Asl so‘zlar kesimga tushgan: %d / %d' % (len(damaged), len(mapped)), damaged[:20])
    print('\n== Qo‘shilgan uzun pauzalar (2.5 s) qanchaga qisqardi')
    for a, b, index in truth['pauses']:
        # Silence left between the previous word and the planned word, in the result.
        prev = mapped[index - 1]['end']
        nxt = mapped[index]['start']
        left = (nxt - prev) - sum(max(0., min(nxt, e) - max(prev, s)) for s, e in cuts)
        print('  %7.2f  oldin %.2f s → qoldi %.2f s' % (a, nxt - prev, left))
    stats = result['plan']['stats']
    print('\n== Natija', stats, 'moslik', result.get('coverage'), 'vaqt', result['elapsed_seconds'], 's')
    kinds = {}
    for item in result['items']:
        kinds[(item['kind'], item['selected'])] = kinds.get((item['kind'], item['selected']), 0) + 1
    print('   takliflar', kinds)
    pauses = [j for j in result['plan']['junctions'] if j['kind'] == 'pause']
    if pauses:
        print('   pauzalar: %d, o‘rtacha qolgan %.2f s, nafasli %d' % (
            len(pauses), np.mean([j['pause'] for j in pauses]), sum(j['breath'] >= .1 for j in pauses)))


if __name__ == '__main__':
    main()
