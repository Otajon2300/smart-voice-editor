"""Edit plan: which words stay, and one cut at every junction between kept words.

Every junction between two kept words is handled by the same rule: the cut
starts a little after the acoustic end of the left word and stops a little
before the acoustic start of the right word. What stays of the pause is
clean original silence chosen by the context (paragraph, sentence, comma,
phrase). Dropped takes, breaths and excess silence all fall inside that one
cut, so there is no empty "digital" silence and no overlapping cuts.
"""
import math

import numpy as np
from rapidfuzz.fuzz import ratio, partial_ratio

from text import tokens as text_tokens
from script import INSERT_KINDS, describe, estimate_seconds

KEEP = {'P': .65, '.': .5, ',': .3, '': .2}   # seconds of pause kept after a word
SLACK = .15            # shorten a pause only when at least this much would go
GAP_SIDE = .25         # pause kept on each side of an opened insert gap
EDGE_KEEP = (.3, .5)   # silence kept before the first and after the last word
MIN_SILENCE = .1       # a real pause between words is at least this long
SEPARATOR = 2.0        # gap at a sync boundary without other insert content
BREATH_SPACE = .2      # a cut breath leaves at least this much pause; what the room tone lacks is left empty
UNHEARD = .35          # this much unrecognised sound inside a cut is speech the ASR missed: never cut silently
AUDIBLE = .06          # shortest sound that may be a word
LOW_COVERAGE = .5      # below this the script probably does not belong to the recording
CONTEXT_NAMES = {'P': 'Bo‘lim oxiri', '.': 'Gap oxiri', ',': 'Vergul', '': 'Ibora ichida'}


# ---------------------------------------------------------------- words

def heard_tokens(words, language):
    heard, owners = [], []
    for index, word in enumerate(words):
        # The next word decides how a number is read ("2024" + "года"), exactly as in the script.
        following = words[index + 1]['word'] if index + 1 < len(words) else ''
        for token in text_tokens(word['word'], language, following):
            heard.append(token)
            owners.append(index)
    return heard, owners


def word_states(words, owners, path, reads, dropped):
    """'read' (scripted, kept), 'retake' (abandoned take) or 'free' (not in the script)."""
    states = ['free'] * len(words)
    by_word = {}
    for t, w in enumerate(owners):
        by_word.setdefault(w, []).append(t)
    for w in range(len(words)):
        ts = by_word.get(w, [])
        if not ts:
            states[w] = 'empty'
        elif any(path[t] >= 0 and reads[t] and not dropped[t] for t in ts):
            states[w] = 'read'
        elif any(dropped[t] for t in ts):
            states[w] = 'retake'
    for w, state in enumerate(states):  # punctuation-only "words" follow their neighbours
        if state == 'empty':
            left = states[w - 1] if w else 'free'
            right = states[w + 1] if w + 1 < len(states) else 'free'
            states[w] = 'retake' if left == right == 'retake' else 'free'
    return states, by_word


def norm(word):
    return ' '.join(text_tokens(word['word'], None))


def mark_stutters(words, states):
    """Stumbles: an unscripted word that repeats (or starts) its scripted neighbour.

    The earlier of the two is dropped. When the scripted copy is the earlier
    one, the later copy takes over its script position (transfer).
    """
    stutter, transfer = set(), {}
    for i, state in enumerate(states):
        if state != 'free':
            continue
        a = norm(words[i])
        if len(a) < 2:
            continue
        j = i + 1
        if j < len(words) and states[j] == 'read' and words[j]['start'] - words[i]['end'] < 2.:
            b = norm(words[j])
            if b.startswith(a) or ratio(a, b) >= 85:
                stutter.add(i)
                continue
        p = i - 1
        if p >= 0 and states[p] == 'read' and p not in transfer.values() and words[i]['start'] - words[p]['end'] < 1.5:
            b = norm(words[p])
            if a == b or (len(a) >= 4 and ratio(a, b) >= 90):
                stutter.add(p)
                transfer[i] = p
    for i in stutter:
        states[i] = 'retake'
    for i in transfer:
        states[i] = 'read'
    return stutter, transfer


def join_fragments(words):
    """ASR splits words at apostrophes ("ma" + "'lum"): join them back."""
    result = []
    for original in words:
        word = dict(original)
        raw = word['word'].lstrip()
        if result and raw[:1] in "'‘’ʻʼ`" and word['start'] - result[-1]['end'] <= .15:
            result[-1]['word'] = result[-1]['word'].rstrip() + raw.strip()
            result[-1]['end'] = max(result[-1]['end'], word['end'])
        else:
            result.append(word)
    return result


def anchors(states, info, rank=None):
    """First and last word of the continuous scripted reading.

    rank maps a script position to its index among the parts the reader voices,
    so an unvoiced sync or standup between two narration parts is not a jump.
    """
    read = [w for w, s in enumerate(states) if s == 'read' and info[w]['pos'] is not None]
    if len(read) < 4:
        return None, None
    rank = rank or (lambda p: p)

    def steady(seq):
        for k in range(len(seq) - 3):
            pos = [rank(info[w]['pos']) for w in seq[k:k + 4]]
            if all(0 <= b - a <= 4 for a, b in zip(pos, pos[1:])) or all(0 <= a - b <= 4 for a, b in zip(pos, pos[1:])):
                return seq[k]
        return None
    return steady(read), steady(read[::-1])


# ---------------------------------------------------------------- analysis

def analyse_reading(words, script, marks, block_of, blocks, language, strict=True):
    """Static part of the plan: word states, items (proposals) and per-word script info."""
    from align import follow, abandoned
    heard, owners = heard_tokens(words, language)
    path, reads = follow(script, heard)
    times = [words[o]['start'] for o in owners]
    dropped = abandoned(path, reads, times)
    states, by_word = word_states(words, owners, path, reads, dropped)
    stutters, transfer = mark_stutters(words, states)

    # Per word: script position (last kept token), punctuation mark and block.
    info = []
    for w, word in enumerate(words):
        ts = [t for t in by_word.get(w, []) if path[t] >= 0 and reads[t] and not dropped[t]]
        pos = path[ts[-1]] if ts else None
        if pos is not None:
            mark = marks[pos]
        else:
            text = word['word'].strip()
            mark = '.' if text.endswith(('.', '!', '?', '…')) else ',' if text.endswith((',', ';', ':')) else ''
        info.append({'pos': pos, 'mark': mark, 'block': block_of[pos] if pos is not None else None})
    for i, p in transfer.items():
        info[i] = dict(info[p])
    # Blocks actually voiced in this recording.
    read_positions = {path[t] for t in range(len(path)) if path[t] >= 0 and reads[t] and not dropped[t]}
    for b in blocks:
        hits = sum(1 for p in range(b['start_token'], b['start_token'] + b['tokens']) if p in read_positions)
        b['voiced'] = b['tokens'] > 0 and hits >= max(2, b['tokens'] * .3)
    excluded = {p for b in blocks if b['kind'] in ('sync', 'standup') and not b['voiced']
                for p in range(b['start_token'], b['start_token'] + b['tokens'])}
    compact = np.cumsum([p not in excluded for p in range(len(script))]) if script else []
    first, last = anchors(states, info, lambda p: int(compact[p]))
    inside = sorted(p for p in read_positions if p not in excluded)
    if inside:
        window = (inside[0], inside[-1])
        size = sum(1 for p in range(window[0], window[1] + 1) if p not in excluded)
        coverage = len(inside) / max(1, size)
    else:
        window, coverage = None, 0.
    missing = [script[p] for p in range(window[0], window[1] + 1)
               if p not in read_positions and p not in excluded] if window else []

    # Proposals.
    kinds = []
    for w, state in enumerate(states):
        if first is not None and (w < first or w > last):
            kinds.append('outside')
        elif state == 'retake':
            kinds.append('repeat')
        elif state == 'free':
            kinds.append('uncertain')
        else:
            kinds.append(None)
    items = []
    w = 0
    while w < len(words):
        kind = kinds[w]
        if kind is None:
            w += 1
            continue
        end = w
        while end + 1 < len(words) and kinds[end + 1] == kind:
            end += 1
        items.append(make_item(len(items), kind, w, end, words, info, states, stutters, by_word, path, reads,
                               dropped, script, strict))
        w = end + 1
    classify_between(items, words, info, script)
    low = coverage < LOW_COVERAGE
    if low:  # probably the wrong script: propose nothing by default
        for item in items:
            if item['selected']:
                item.update(selected=False, review=True,
                            reason=item['reason'] + ' · ssenariy bilan moslik past, eshitib tekshiring')
    return {'low_coverage': low, 'states': states, 'info': info, 'items': items, 'coverage': coverage, 'window': window,
            'missing': missing, 'script_words': len(script), 'heard_words': len(heard),
            'outside_script_words': len(script) - (window[1] - window[0] + 1 if window else 0)}


def make_item(index, kind, a, b, words, info, states, stutters, by_word, path, reads, dropped, script, strict):
    text = ' '.join(words[k]['word'].strip() for k in range(a, b + 1))
    item = {'id': 'i%d' % index, 'kind': kind, 'first': a, 'last': b, 'text': text[:400],
            'start': words[a]['start'], 'end': words[b]['end'], 'selected': False, 'review': False}
    if kind == 'outside':
        edge = 'boshidan oldingi' if all(info[k]['pos'] is None for k in range(0, a)) else 'tugaganidan keyingi'
        item['selected'] = bool(strict)
        item['reason'] = 'Ssenariy ' + edge + ' nutq'
    elif kind == 'uncertain':
        item['reason'] = 'Ssenariyda yo‘q so‘zlar — odatda saqlanadi'
    else:
        item['selected'] = True
        if all(k in stutters for k in range(a, b + 1)):
            item['reason'] = 'Duduqlanish: so‘z boshidan qayta aytilgan'
        else:
            item['reason'] = 'Qayta o‘qilgan joy; oxirgi variant saqlanadi'
            # The abandoned take must really be read again right after it.
            taken = {path[t] for k in range(a, b + 1) for t in by_word.get(k, []) if dropped[t] and reads[t] and path[t] >= 0}
            later = set()
            count = 0
            for k in range(b + 1, len(words)):
                if states[k] == 'read':
                    later.update(path[t] for t in by_word[k] if reads[t] and not dropped[t])
                    count += 1
                    if count > max(40, len(taken) * 2):
                        break
            again = len(taken & later) / len(taken) if taken else 1.
            item['confidence'] = round(again, 2)
            if again < .6:
                item['selected'] = False
                item['review'] = True
                item['reason'] += ' · keyingi variant aniq topilmadi, eshitib tekshiring'
        if words[b]['end'] - words[a]['start'] > 60:
            item['selected'] = False
            item['review'] = True
            item['reason'] += ' · juda uzun (>60 s), eshitib tekshiring'
    return item


def classify_between(items, words, info, script):
    """Unscripted talk exactly between two script parts (not a missed start of the next part)."""
    for item in items:
        if item['kind'] != 'uncertain':
            continue
        before = next((info[k]['block'] for k in range(item['first'] - 1, -1, -1) if info[k]['block'] is not None), None)
        after_word = next((k for k in range(item['last'] + 1, len(words)) if info[k]['block'] is not None), None)
        after = info[after_word]['block'] if after_word is not None else None
        if before is None or after is None or before == after:
            continue
        start = info[after_word]['pos']
        nearby = ' '.join(script[max(0, start - 25):start + 25])
        if partial_ratio(' '.join(text_tokens(item['text'], None)), nearby) >= 75:
            continue
        item['kind'] = 'between'
        item['selected'] = True
        item['reason'] = 'Ssenariy bo‘limlari orasidagi ortiqcha gap yoki shovqin'


# ---------------------------------------------------------------- inserts (gaps)

def insert_plan(blocks):
    """Gaps between voiced parts: {(left block, right block): gap}, lead gap, tail labels."""
    gaps, pending, previous = {}, [], None
    lead, closed = None, False
    for index, block in enumerate(blocks):
        if block.get('voiced'):
            content = [b for b in pending if is_insert(b)]
            if previous is None:
                if content:
                    lead = gap_record(content, None, block)
            else:
                changed = block['kind'] != blocks[previous]['kind'] or block['kind'] == 'sync'
                if content or changed:
                    gaps[(previous, index)] = gap_record(content, blocks[previous], block)
            previous, pending, closed = index, [], False
        elif is_insert(block):
            if not closed:
                pending.append(block)
        elif block['kind'] == 'narration' and block['tokens']:
            if previous is None:
                pending = []
            else:
                closed = True  # narration missing from this recording: later inserts are not ours
    tail = [describe(b) for b in pending if is_insert(b)] if previous is not None else []
    return gaps, lead, tail


def is_insert(block):
    return block['kind'] in INSERT_KINDS or (block['kind'] in ('sync', 'standup') and not block.get('voiced'))


def gap_record(content, before, after):
    seconds = sum(estimate_seconds(b) for b in content)
    labels = [describe(b) for b in content]
    if after['kind'] == 'sync':
        labels.append(describe(after) + ' — tarjima ovozi keyin')
    if before is not None and before['kind'] == 'sync' and not content:
        labels.insert(0, describe(before) + ' tugadi')
    return {'seconds': float(max(SEPARATOR, round(seconds))), 'label': ' + '.join(labels) or 'Bo‘lim chegarasi'}


# ---------------------------------------------------------------- junctions

def speaker_scale(words):
    """Slow readers keep slightly longer pauses, fast readers shorter ones."""
    rates = [a['end'] - a['start'] for a, b in zip(words, words[1:]) if b['start'] - a['end'] < .25]
    if len(rates) < 30:
        return 1.
    return float(np.clip(np.median(rates) / .32, .85, 1.2))


def end_of(words, i, ac):
    """Acoustic end of word i: start of the first real silence after it (or a tight cut point)."""
    w = words[i]
    following = words[i + 1]['start'] if i + 1 < len(words) else ac.duration
    limit = min(max(following, w['end']) + .1, w['end'] + .8)
    # The ASR often stretches a word over the pause (and the breath) that follows it:
    # the word really ends where its last sound does.
    k = stop = ac.frame(min(w['end'], ac.duration))
    low = ac.frame(w['start'] + min(.1, (w['end'] - w['start']) / 2))
    while k > low and not ac.sound[k - 1]:
        k -= 1
    if stop - k >= MIN_SILENCE * 100:
        return k / 100, False
    # ...or even over the beginning of the next word: a breath inside the word marks its real end.
    for s, e in ac.breaths_between(low / 100, stop / 100):
        k = ac.frame(s)
        if k <= low or ac.sound[k - 1 if k else 0] and ac.sound[min(ac.count - 1, ac.frame(e))] and e - s < MIN_SILENCE:
            continue
        while k > low and not ac.sound[k - 1]:
            k -= 1
        if k > low:
            return k / 100, False
    found = ac.silent_run_after(max(w['start'], w['end'] - .06), limit, MIN_SILENCE)
    if found is not None:
        return found, False
    return ac.quietest(w['end'] - .06, max(w['end'] + .02, min(following, w['end'] + .2) + .06)), True


def start_of(words, i, ac, earliest=None):
    """Acoustic onset of word i: (time, tight cut, a stumble fragment precedes it).
    `earliest` is the acoustic end of the word before it, when that lies before its ASR end."""
    w = words[i]
    preceding = words[i - 1]['end'] if i else 0.
    if earliest is not None:
        preceding = min(preceding, earliest)
    limit = max(min(preceding, w['start']) - .1, w['start'] - .8)
    found = ac.silent_run_before(min(w['end'], w['start'] + .06), limit, MIN_SILENCE)
    if found is None:
        return ac.quietest(min(w['start'] - .02, max(preceding, w['start'] - .2) - .06), w['start'] + .06), True, False
    # The ASR start may fall inside the silence: move on to the real onset.
    k, stop = ac.frame(found), ac.frame(w['end'])
    while k < stop and not ac.sound[k]:
        k += 1
    if k < stop:
        found = k / 100
    real = fragment_end(ac, found, w['end'])
    return (real, False, True) if real is not None else (found, False, False)


def foreign_sound(ac, a, b, longest=.3, pause=.2):
    """A short untranscribed sound between two words followed by a clear pause (a stumble)."""
    k, stop = ac.frame(a), ac.frame(b)
    while k < stop:
        if ac.sound[k]:
            j = k
            while j < stop and ac.sound[j]:
                j += 1
            if .06 <= (j - k) / 100 <= longest and (stop - j) / 100 >= pause:
                return True
            k = j
        else:
            k += 1
    return False


def fragment_end(ac, onset, end, longest=.3, pause=.2):
    """ASR often glues a stumble ("ya-… ya'ni") to the word: a short sound, a clear pause, then the word."""
    a, b = ac.frame(onset), ac.frame(end)
    k = a
    while k < b and ac.sound[k]:
        k += 1
    if k == a or k - a > longest * 100:
        return None
    quiet = k
    while k < b and not ac.sound[k]:
        k += 1
    if k - quiet < pause * 100 or k >= b - 10:  # the word itself must still follow
        return None
    return k / 100


def share(target, avail_l, avail_r):
    """Split the kept pause between the two sides, using clean silence only."""
    want_l = target * .55
    want_r = target - want_l
    l, r = min(want_l, avail_l), min(want_r, avail_r)
    l = min(avail_l, l + (want_r - r))
    r = min(avail_r, r + (want_l - l))
    return l, r


def junctions(words, kept, info, ac, gap_at, scale, options):
    """One record per gap between consecutive kept words, plus the recording edges."""
    result = []
    if not kept:
        return result
    first, last = kept[0], kept[-1]
    start_first = start_of(words, first, ac)[0]
    keep = min(EDGE_KEEP[0], ac.clean_before(start_first, 0.))
    if start_first - keep > .05 and (first > 0 or options['pauses']):
        result.append(edge('lead', (0., start_first - keep), first > 0, keep, start_first, ac))
    for left, right in zip(kept, kept[1:]):
        a, tight_a = end_of(words, left, ac)
        b, tight_b, stumble = start_of(words, right, ac, a if right == left + 1 else None)
        dropped = right - left > 1
        gap = gap_at.get((left, right))
        stumble = (stumble or foreign_sound(ac, a, b)) and not dropped and not gap
        jid = 'j%d' % left
        if b < a:  # overlapping word times: leave as it is
            if dropped or gap:
                b = a = (a + b) / 2
            else:
                continue
        silence = b - a
        context = info[left]['mark']
        target = GAP_SIDE * 2 if gap else KEEP[context] * scale
        if not gap and context == '' and silence >= 1.2:
            target = KEEP[','] * scale  # a long hesitation inside a phrase is usually a breath
        breath = sum(min(e, b) - max(s, a) for s, e in ac.breaths_between(a, b))
        sound = ac.sound_between(a, b)
        # Sound nobody transcribed. A long one is speech the ASR missed; a short one where the script
        # still expects a word is probably that word. Both stay unless the user asks for the cut.
        unheard = not dropped and not gap and (sound >= UNHEARD or (sound >= AUDIBLE and expects_word(info, left, right)))
        # ...except a sound standing alone in a pause where the script goes on without a missing word:
        # a cough, a page, a word to somebody else. It is shown in the list, but cut.
        aside = bool(unheard and follows_script(info, left, right) and stands_alone(ac, a, b))
        kind = 'gap' if gap else 'retake' if dropped else 'unheard' if unheard else 'stumble' if stumble else 'pause'
        record = {'id': jid, 'kind': kind, 'left': left, 'right': right,
                  'context': context, 'silence': round(silence, 3), 'breath': round(breath, 3),
                  'sound': round(sound, 3), 'tight': tight_a or tight_b, 'gap': gap, 'dropped': dropped,
                  'forced': bool(dropped or gap), 'default': not unheard or aside, 'aside': bool(aside)}
        needs = dropped or gap or stumble or unheard or (options['pauses'] and silence >= target + SLACK) or \
            (options['breaths'] and breath >= .1)
        if not needs:
            continue
        if not dropped and not gap and not stumble and not options['pauses']:
            target = silence  # breaths only: keep the whole pause length minus the breath
        avail_l = ac.clean_after(a, b)
        avail_r = ac.clean_before(b, a)
        if dropped or gap or stumble:
            avail_l, avail_r = min(avail_l, silence), min(avail_r, silence)
        l, r = share(min(target, silence), avail_l, avail_r)
        if not dropped and not gap and not stumble and not unheard and breath < .1 and silence - (l + r) < SLACK:
            continue
        cut = (a + l, b - r)
        if cut[1] < cut[0]:
            mid = (a + b) / 2
            cut = (mid, mid)
        # Room tone next to a breath is often too short for a pause: the rest is left as empty space,
        # so the words do not run together where the breath was.
        space = 0.
        if options['breaths'] and breath >= .1 and not gap and cut[1] > cut[0]:
            space = max(0., BREATH_SPACE - (l + r))
        record.update(cut=cut, pause=round(l + r + space, 3), space=round(space, 3))
        result.append(record)
    end_last, _ = end_of(words, last, ac)
    keep = min(EDGE_KEEP[1], ac.clean_after(end_last, ac.duration))
    if ac.duration - (end_last + keep) > .05 and (last < len(words) - 1 or options['pauses']):
        result.append(edge('tail', (end_last + keep, ac.duration), last < len(words) - 1, keep,
                           ac.duration - end_last, ac))
    return result


def edge(name, cut, dropped, keep, silence, ac):
    """Trim before the first / after the last kept word. Unrecognised speech there is never cut silently."""
    sound = ac.sound_between(*cut)
    return {'id': name, 'kind': 'edge', 'cut': cut, 'dropped': dropped, 'pause': keep, 'silence': round(silence, 3),
            'breath': 0., 'sound': round(sound, 3), 'tight': False, 'forced': bool(dropped),
            'default': bool(dropped or sound < UNHEARD)}


def follows_script(info, left, right):
    """The two kept words are neighbours in the script: nothing of it is missing between them."""
    a, b = info[left]['pos'], info[right]['pos']
    return a is not None and b is not None and b - a == 1


def stands_alone(ac, a, b, margin=.3):
    """All sound in [a, b] is at least `margin` away from both words."""
    found = np.flatnonzero(ac.sound[ac.frame(a):ac.frame(b)])
    if not len(found):
        return False
    return bool(found[0] >= margin * 100 and ac.frame(b) - ac.frame(a) - 1 - found[-1] >= margin * 100)


def expects_word(info, left, right):
    """The script has an unread word between these two kept words."""
    a, b = info[left]['pos'], info[right]['pos']
    return a is not None and b is not None and b - a >= 2


# ---------------------------------------------------------------- grid and ranges

class Grid:
    """Sequence frame grid, per selected piece (pieces may sit anywhere on the timeline)."""

    def __init__(self, clip):
        self.frame = float(clip.get('frame') or .04)
        if not .001 <= self.frame <= 1:
            raise ValueError('Sequence kadr tezligi noto‘g‘ri.')
        self.pieces, offset = [], 0.
        for piece in clip.get('pieces') or [{'start': clip.get('start', 0.), 'inPoint': clip['inPoint'],
                                             'outPoint': clip['outPoint']}]:
            length = float(piece['outPoint']) - float(piece['inPoint'])
            self.pieces.append((offset, float(piece.get('start', 0.)), length))
            offset += length

    def snap(self, t, up):
        for offset, start, length in self.pieces:
            if t <= offset + length + 1e-9:
                frames = (start + t - offset) / self.frame
                frames = math.ceil(frames - 1e-6) if up else math.floor(frames + 1e-6)
                return min(offset + length, max(offset, frames * self.frame - start + offset))
        return t


def ranges_from(cuts, duration, grid, leading=None):
    """Kept ranges (with gapAfter at insert points) from non-overlapping cuts.

    A gap with nothing kept before it cannot be a gapAfter; it is appended to `leading`.
    """
    ranges, cursor = [], 0.
    for cut in sorted(cuts, key=lambda c: c['start']):
        a, b = grid.snap(cut['start'], True), grid.snap(cut['end'], False)
        # Frame multiples are not exact in floating point (0.36 - 0.32 < 0.04).
        if b - a < grid.frame - 1e-6:
            if not cut.get('gap'):
                continue
            a = b = grid.snap((cut['start'] + cut['end']) / 2, True)  # nothing to cut, but the gap still opens here
        if a > cursor + 1e-6:
            ranges.append({'start': round(cursor, 4), 'end': round(a, 4)})
        if ranges and cut.get('junction'):
            ranges[-1].setdefault('joins', []).append(cut['junction'])
        if cut.get('gap') and ranges:
            ranges[-1]['gapAfter'] = cut['gap']['seconds']
            ranges[-1]['gapLabel'] = cut['gap']['label']
        elif cut.get('gap') and leading is not None:
            leading.append(cut['gap'])
        elif cut.get('space', 0) > 1e-6 and ranges:
            # Plain empty space (no title, no marker), in whole frames.
            ranges[-1]['gapAfter'] = round(math.ceil(cut['space'] / grid.frame - 1e-6) * grid.frame, 4)
            ranges[-1]['gapPlain'] = True
        cursor = max(cursor, b)
    if cursor < duration - 1e-6:
        ranges.append({'start': round(cursor, 4), 'end': round(duration, 4)})
    return ranges


# ---------------------------------------------------------------- plan

def build(state, decisions=None, gap_settings=None, options=None):
    """Cuts and kept ranges for the current choices (fast; no recognition)."""
    decisions = decisions or {}
    gap_settings = gap_settings or {}
    options = dict({'pauses': True, 'breaths': True}, **(options or {}))
    words, ac, info = state['words'], state['acoustics'], state['info']
    removed = set()
    for item in state['items']:
        chosen = decisions.get(item['id'], item['selected'])
        if chosen:
            removed.update(range(item['first'], item['last'] + 1))
    kept = [w for w in range(len(words)) if w not in removed]
    gap_at = {}
    for key, gap in state['gap_slots'].items():
        setting = gap_settings.get(gap['id'], {})
        if setting.get('enabled', True) is False:
            continue
        seconds = float(setting.get('seconds', gap['seconds']))
        located = locate_gap(kept, info, key)
        if located and seconds > 0:
            gap_at[located] = dict(gap, seconds=max(0., min(300., seconds)))
    found = junctions(words, kept, info, ac, gap_at, state['scale'], options)
    # Retakes and insert gaps are always cut; everything else follows the user's choice or the default.
    active = set()
    for j in found:
        choice = decisions.get(j['id'])
        if j['forced'] or (choice if isinstance(choice, bool) else j['default']):
            active.add(j['id'])
    cuts = [{'start': j['cut'][0], 'end': j['cut'][1], 'gap': j.get('gap'), 'junction': j['id'], 'space': j.get('space', 0.)}
            for j in found if j['id'] in active]
    leading = []
    ranges = ranges_from(cuts, ac.duration, state['grid'], leading)
    lead = state.get('lead_gap')
    lead_setting = gap_settings.get('lead', {}) if lead else {}
    lead_seconds = float(lead_setting.get('seconds', lead['seconds'])) if lead and lead_setting.get('enabled', True) else 0.
    lead_seconds = max(0., min(300., lead_seconds + sum(g['seconds'] for g in leading)))
    lead_label = ' + '.join(([lead['label']] if lead else []) + [g['label'] for g in leading])
    kept_seconds = sum(r['end'] - r['start'] for r in ranges)
    space_seconds = sum(r['gapAfter'] for r in ranges[:-1] if r.get('gapPlain'))
    gap_seconds = sum(r.get('gapAfter', 0) for r in ranges[:-1]) + lead_seconds
    return {
        'ranges': ranges, 'lead_gap': lead_seconds, 'lead_label': lead_label,
        'tail_label': ' + '.join(state.get('tail') or []),
        'junctions': [public_junction(j, words, j['id'] not in active) for j in found],
        'stats': {'kept_seconds': round(kept_seconds, 2), 'removed_seconds': round(ac.duration - kept_seconds, 2),
                  'gap_seconds': round(gap_seconds - space_seconds, 2), 'space_seconds': round(space_seconds, 2),
                  'result_seconds': round(kept_seconds + gap_seconds, 2),
                  'pauses': len([j for j in found if j['kind'] == 'pause' and j['id'] in active]),
                  'breaths': len([j for j in found if j.get('breath', 0) >= .1 and j['id'] in active]),
                  'unheard': len([j for j in found if not j['default'] and j['id'] not in active]),
                  'cuts': len(cuts)},
    }


def locate_gap(kept, info, key):
    """Junction (left word, right word) where reading passes from block key[0] to block key[1]."""
    left_block, right_block = key
    current = None
    for index, w in enumerate(kept):
        block = info[w]['block']
        if block is None:
            continue
        if current == left_block and block == right_block and index:
            # Unscripted words just before the new part stay with the new part.
            k = index
            while k > 1 and info[kept[k - 1]]['block'] is None:
                k -= 1
            return (kept[k - 1], kept[k])
        current = block
    return None


def public_junction(j, words, disabled):
    out = {'id': j['id'], 'kind': j['kind'], 'start': round(j['cut'][0], 3), 'end': round(j['cut'][1], 3),
           'pause': j.get('pause'), 'silence': j.get('silence'), 'breath': j.get('breath', 0.),
           'tight': j.get('tight', False), 'enabled': not disabled, 'sound': j.get('sound', 0.),
           'forced': j.get('forced', False), 'default': j.get('default', True), 'aside': j.get('aside', False)}
    if 'left' in j:
        out['context'] = CONTEXT_NAMES.get(j['context'], '')
        out['left_word'] = words[j['left']]['word'].strip()
        out['right_word'] = words[j['right']]['word'].strip()
    if j.get('gap'):
        out['gap'] = j['gap']['id']
    return out


def prepare(words, ac, clip, script=None, marks=None, block_of=None, blocks=None, language='uz', strict=True):
    """Everything that does not change when the user toggles proposals."""
    words = join_fragments(sorted((dict(w) for w in words), key=lambda w: (w['start'], w['end'])))
    state = {'words': words, 'acoustics': ac, 'grid': Grid(clip), 'scale': speaker_scale(words),
             'gap_slots': {}, 'lead_gap': None, 'tail': []}
    if script is None:
        state.update(info=[{'pos': None, 'mark': w.get('mark', ','), 'block': None} for w in words], items=[],
                     reading={})
        return state
    reading = analyse_reading(words, script, marks, block_of, blocks, language, strict)
    state.update(info=reading.pop('info'), items=reading.pop('items'), reading=reading)
    for item in state['items']:
        # ASR sometimes writes one word twice; a real stumble has a break before the next word.
        if item['kind'] == 'repeat' and item['reason'].startswith('Duduqlanish') and item['last'] + 1 < len(words):
            nxt = words[item['last'] + 1]['start']
            k = ac.frame(words[item['last']]['start'] - .05)
            while k < ac.count - 1 and not ac.sound[k] and k / 100 < nxt:
                k += 1  # acoustic onset of the dropped copy
            if ac.silent_run_after(k / 100 + .05, nxt + .12, .06) is None:
                item.update(selected=False, review=True,
                            reason='Bir xil so‘z ikki marta tanildi, lekin tovush uzluksiz — ehtimol bitta so‘z; eshitib tekshiring')
    slots, lead, tail = insert_plan(blocks)
    for n, (key, gap) in enumerate(sorted(slots.items())):
        gap['id'] = 'g%d' % n
        slots[key] = gap
    state['gap_slots'] = slots
    if lead:
        lead['id'] = 'lead'
    state['lead_gap'], state['tail'] = lead, tail
    return state


def sound_words(ac, join=.25, minimum=.08):
    """Pseudo-words from acoustic sound runs (pause-only mode without a script)."""
    sound = ac.sound.copy()
    for s, e in ac.breath_spans:           # a breath is never part of a word, even when it touches one
        sound[ac.frame(s):ac.frame(e) + 1] = False
    edges = np.diff(np.r_[False, sound, False].astype(np.int8))
    runs = [(a / 100, b / 100) for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))]
    merged = []
    for a, b in runs:
        if merged and a - merged[-1][1] < join and not ac.breaths_between(merged[-1][1], a):
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    merged = [(a, b) for a, b in merged if b - a >= minimum]
    words = []
    for k, (a, b) in enumerate(merged):
        following = merged[k + 1][0] - b if k + 1 < len(merged) else 0
        words.append({'word': '', 'start': a, 'end': b, 'mark': '.' if following >= .9 else ','})
    return words
