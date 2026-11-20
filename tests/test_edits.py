import unittest

import numpy as np

from helpers import Recording, docx, clip_for, cuts_of, removed
from audio import Acoustics
from edits import Grid, prepare, build, ranges_from, sound_words
from script import parse_script, tokenize


def plan(rec, paragraphs, words=None, decisions=None, **options):
    blocks = parse_script(docx(paragraphs))
    script, marks, owner = tokenize(blocks, 'uz')
    ac = Acoustics(rec.audio)
    state = prepare(rec.words if words is None else words, ac, clip_for(ac.duration), script, marks, owner, blocks, 'uz')
    result = build(state, decisions, options=options or None)
    return state, result, cuts_of(result['ranges'], ac.duration), ac.duration


def junction(result, kind):
    found = [j for j in result['junctions'] if j['kind'] == kind]
    return found[0] if found else None


class UnrecognisedSoundTests(unittest.TestCase):
    """Speech the ASR did not write down must never disappear inside a "pause" or an edge trim."""
    TEXT = ['Bugun mamlakatimizda yangi loyiha ishga tushirildi. Unda yuzlab talabalar qatnashdi. '
            'Yoshlar faol ishtirok etdi va sovrinlar oldi.']

    def recording(self):
        rec = Recording(7)
        rec.room(.4)
        rec.say('bugun mamlakatimizda yangi loyiha ishga tushirildi')
        rec.room(.5)
        start = rec.t
        rec.say('unda yuzlab talabalar qatnashdi')
        end = rec.t
        rec.room(.5)
        rec.say('yoshlar faol ishtirok etdi va sovrinlar oldi')
        rec.room(.4)
        return rec, start, end

    def test_missed_sentence_between_words_is_kept_and_listed(self):
        rec, start, end = self.recording()
        heard = [w for w in rec.words if not start <= w['start'] < end]
        state, result, cuts, duration = plan(rec, self.TEXT, heard)
        self.assertEqual(removed(cuts, start, end), 0)
        found = junction(result, 'unheard')
        self.assertIsNotNone(found, result['junctions'])
        self.assertFalse(found['enabled'])
        self.assertFalse(found['default'])
        self.assertGreater(found['sound'], 1.)
        self.assertEqual(result['stats']['unheard'], 1)
        # The user may still ask for the cut after listening.
        state, result, cuts, duration = plan(rec, self.TEXT, heard, decisions={found['id']: True})
        self.assertGreater(removed(cuts, start, end), (end - start) * .9)
        self.assertTrue(junction(result, 'unheard')['enabled'])

    def test_missed_speech_at_the_edges_is_kept(self):
        rec = Recording(8)
        rec.room(.4)
        lead = rec.t
        rec.say('assalomu alaykum aziz')
        body = rec.t
        rec.room(.3)
        rec.say('bugun yangi loyiha boshlandi yoshlar ishtirok etdi')
        rec.room(.3)
        tail = rec.t
        rec.say('katta rahmat sizga')
        end = rec.t
        rec.room(.4)
        heard = [w for w in rec.words if body <= w['start'] < tail]
        text = ['Assalomu alaykum aziz. Bugun yangi loyiha boshlandi yoshlar ishtirok etdi. Katta rahmat sizga.']
        state, result, cuts, duration = plan(rec, text, heard)
        self.assertEqual(removed(cuts, lead, body), 0)
        self.assertEqual(removed(cuts, tail, end), 0)
        edges = {j['id']: j for j in result['junctions'] if j['kind'] == 'edge'}
        self.assertEqual(sorted(edges), ['lead', 'tail'])
        self.assertFalse(edges['lead']['enabled'] or edges['tail']['enabled'])
        state, result, cuts, duration = plan(rec, text, heard, decisions={'tail': True})
        self.assertGreater(removed(cuts, tail, end), (end - tail) * .9)
        self.assertEqual(removed(cuts, lead, body), 0)

    def test_silent_edges_are_trimmed_only_with_pause_cleanup(self):
        rec = Recording(9)
        rec.room(2.)
        rec.say('bugun yangi loyiha boshlandi yoshlar ishtirok etdi')
        rec.room(2.)
        text = ['Bugun yangi loyiha boshlandi yoshlar ishtirok etdi.']
        state, result, cuts, duration = plan(rec, text)
        self.assertGreater(removed(cuts, 0, 2.), 1.4)
        self.assertGreater(removed(cuts, duration - 2., duration), 1.2)
        state, result, cuts, duration = plan(rec, text, pauses=False, breaths=False)
        self.assertEqual(cuts, [])

    def test_short_sound_where_the_script_expects_a_word_is_kept(self):
        rec = Recording(9)
        rec.room(.4)
        rec.say('bugun yangi loyiha')
        rec.room(.15)
        start = rec.t
        rec.word('va', .2)
        end = rec.t
        rec.room(.3)
        rec.say('boshlandi yoshlar ishtirok etdi')
        rec.room(.4)
        heard = [w for w in rec.words if w['word'].strip() != 'va']
        # "va" is in the script: the sound is probably that word.
        state, result, cuts, duration = plan(rec, ['Bugun yangi loyiha va boshlandi yoshlar ishtirok etdi.'], heard)
        self.assertEqual(removed(cuts, start, end), 0)
        self.assertFalse(junction(result, 'unheard')['enabled'])
        # Not in the script: a stumble fragment. It is cut, but listed and can be kept.
        text = ['Bugun yangi loyiha boshlandi yoshlar ishtirok etdi.']
        state, result, cuts, duration = plan(rec, text, heard)
        self.assertGreater(removed(cuts, start, end), (end - start) * .9)
        found = junction(result, 'stumble')
        self.assertTrue(found['enabled'] and found['default'] and not found['forced'])
        state, result, cuts, duration = plan(rec, text, heard, decisions={found['id']: False})
        self.assertEqual(removed(cuts, start, end), 0)

    def test_wrong_script_selects_nothing(self):
        rec = Recording(10)
        rec.room(.4)
        rec.say('bugun yangi loyiha')
        rec.room(.5)
        rec.say('bugun yangi loyiha boshlandi')
        rec.room(.5)
        rec.say('yoshlar faol ishtirok etdi')
        rec.room(.4)
        # The same retake is proposed when the script fits...
        state, result, cuts, duration = plan(rec, ['Bugun yangi loyiha boshlandi. Yoshlar faol ishtirok etdi.'])
        self.assertFalse(state['reading']['low_coverage'])
        self.assertTrue(any(i['selected'] for i in state['items']), state['items'])
        # ...but not when most of the script between the matching words was never read.
        other = 'Mutlaqo boshqa hujjat matni shu yerda uzoq davom etadi hamda tugamaydi. ' * 3
        state, result, cuts, duration = plan(rec, ['Bugun yangi loyiha boshlandi. ' + other + 'Yoshlar faol ishtirok etdi.'])
        self.assertTrue(state['reading']['low_coverage'], state['reading']['coverage'])
        self.assertFalse(any(i['selected'] for i in state['items']), state['items'])
        self.assertTrue(all(i['review'] for i in state['items'] if i['kind'] == 'repeat'))


def low_hiss(rec, seconds=.2, level=.006):
    """A breath whose noise sits at 1.5-2.5 kHz (below the classic 2 kHz hiss), like a real recording sent in."""
    n = int(seconds * 16000)
    spectrum = np.fft.rfft(rec.rng.normal(0, 1, n))
    freq = np.fft.rfftfreq(n, 1 / 16000)
    spectrum[(freq < 1500) | (freq > 2500)] = 0
    noise = np.fft.irfft(spectrum, n)
    noise *= level / np.sqrt(np.mean(noise ** 2))
    rec.chunks.append((noise * np.sin(np.pi * np.arange(n) / n) + rec.rng.normal(0, .0008, n)).astype(np.float32))
    rec.breaths.append((rec.t, rec.t + seconds))
    rec.t += seconds


class BreathTests(unittest.TestCase):
    TEXT = ['Bugun yangi loyiha boshlandi yoshlar faol ishtirok etdi va sovrinlar oldi.']

    def recording(self, breath, room=.06):
        rec = Recording(12)
        rec.room(.4)
        rec.say('bugun yangi loyiha boshlandi')
        rec.room(room)
        breath(rec)
        rec.room(room)
        rec.say('yoshlar faol ishtirok etdi va sovrinlar oldi')
        rec.room(.4)
        return rec

    def test_low_hissing_breath_is_found_and_cut(self):
        rec = self.recording(low_hiss, room=.25)
        ac = Acoustics(rec.audio)
        a, b = rec.breaths[0]
        self.assertTrue(any(s < b - .05 and e > a + .05 for s, e in ac.breath_spans), ac.breath_spans)
        state, result, cuts, duration = plan(rec, self.TEXT)
        self.assertGreater(removed(cuts, a, b), (b - a) * .7)

    def test_breath_under_a_stretched_word_is_cut(self):
        # The recogniser often ends a word where the next one begins, so the pause and the breath lie "inside" it.
        rec = self.recording(lambda r: r.breath(.4), room=.25)
        a, b = rec.breaths[0]
        words = [dict(w) for w in rec.words]
        words[3]['end'] = round(words[4]['start'] - .01, 3)
        state, result, cuts, duration = plan(rec, self.TEXT, words=words)
        self.assertGreater(removed(cuts, a, b), (b - a) * .7)
        for w in rec.words:                                   # no word loses its sound
            self.assertLess(removed(cuts, w['start'], w['end']), .03, w)
        # ...or even past the start of the next word: the breath still marks where the word really ended.
        words[3]['end'] = round(words[4]['start'] + .15, 3)
        words[4]['start'] = words[3]['end']
        state, result, cuts, duration = plan(rec, self.TEXT, words=words)
        self.assertGreater(removed(cuts, a, b), (b - a) * .7)
        for w in rec.words:
            self.assertLess(removed(cuts, w['start'], w['end']), .03, w)

    def test_breath_at_the_start_of_a_word_is_cut(self):
        # ...and the next word is often started at the breath taken before it, or in the pause before that.
        for early in (.0, .12):
            rec = self.recording(lambda r: r.breath(.3), room=.1)
            a, b = rec.breaths[0]
            words = [dict(w) for w in rec.words]
            words[3]['end'] = words[4]['start'] = round(a - early, 3)
            state, result, cuts, duration = plan(rec, self.TEXT, words=words)
            self.assertGreater(removed(cuts, a, b), (b - a) * .7, early)
            for w in rec.words:
                self.assertLess(removed(cuts, w['start'], w['end']), .03, w)

    def test_cut_breath_leaves_open_space(self):
        # Almost no room tone around the breath: without the space the two words would run together.
        rec = self.recording(lambda r: r.breath(.4))
        a, b = rec.breaths[0]
        state, result, cuts, duration = plan(rec, self.TEXT)
        self.assertGreater(removed(cuts, a, b), (b - a) * .7)
        before = [r for r in result['ranges'] if r.get('gapPlain')]
        self.assertEqual(len(before), 1, result['ranges'])
        found = [j for j in result['junctions'] if j['breath'] >= .1][0]
        self.assertAlmostEqual(found['pause'], .2, delta=.011)
        self.assertGreater(before[0]['gapAfter'], .03)
        self.assertLessEqual(before[0]['gapAfter'], .2)
        self.assertAlmostEqual(before[0]['gapAfter'] / .04, round(before[0]['gapAfter'] / .04), places=6)  # whole frames
        self.assertNotIn('gapLabel', before[0])
        self.assertAlmostEqual(result['stats']['space_seconds'], before[0]['gapAfter'], places=2)
        self.assertEqual(result['stats']['gap_seconds'], 0)
        # Enough room tone: the pause is made of it and nothing is left empty.
        state, result, cuts, duration = plan(self.recording(lambda r: r.breath(.4), room=.3), self.TEXT)
        self.assertFalse(any(r.get('gapPlain') for r in result['ranges']))
        # Breaths are not cut: nothing changes.
        state, result, cuts, duration = plan(rec, self.TEXT, breaths=False, pauses=False)
        self.assertFalse(any(r.get('gapPlain') for r in result['ranges']))


class AsideTests(unittest.TestCase):
    TEXT = ['Bugun yangi loyiha boshlandi. Yoshlar faol ishtirok etdi va sovrinlar oldi.']

    def recording(self, room):
        rec = Recording(5)
        rec.room(.4)
        rec.say('bugun yangi loyiha boshlandi')
        rec.room(room)
        at = rec.t
        rec.word('yotal', .5)
        rec.words.pop()                      # the recogniser wrote nothing for this sound
        rec.room(room)
        rec.say('yoshlar faol ishtirok etdi va sovrinlar oldi')
        rec.room(.4)
        return rec, at

    def test_lone_sound_in_a_pause_is_cut_when_the_script_goes_on(self):
        rec, at = self.recording(1.5)
        state, result, cuts, duration = plan(rec, self.TEXT)
        found = junction(result, 'unheard')
        self.assertTrue(found['aside'] and found['enabled'] and found['default'], found)
        __import__('json').dumps(result)     # the plan goes to the panel as JSON
        self.assertGreater(removed(cuts, at, at + .5), .45)
        self.assertLess(found['pause'], 1.)
        state, result, cuts, duration = plan(rec, self.TEXT, decisions={found['id']: False})   # the user keeps it
        self.assertEqual(removed(cuts, at, at + .5), 0)

    def test_sound_next_to_a_word_or_a_missing_script_word_stays(self):
        rec, at = self.recording(.15)        # touches the words: may be part of them
        state, result, cuts, duration = plan(rec, self.TEXT)
        found = junction(result, 'unheard')
        self.assertFalse(found['aside'] or found['enabled'], found)
        rec, at = self.recording(1.5)        # the script has a word there that nobody recognised
        text = [self.TEXT[0].replace('boshlandi. Yoshlar', 'boshlandi. Shunda yoshlar')]
        state, result, cuts, duration = plan(rec, text)
        found = junction(result, 'unheard')
        self.assertFalse(found['aside'] or found['enabled'], found)
        self.assertEqual(removed(cuts, at, at + .5), 0)


class GridTests(unittest.TestCase):
    def test_one_frame_cut_survives_float_rounding(self):
        grid = Grid(clip_for(10.))
        self.assertLess(.36 - .32, .04)  # the reason for the tolerance
        ranges = ranges_from([{'start': .32, 'end': .36, 'junction': 'j1'}], 10., grid)
        self.assertEqual([(r['start'], r['end']) for r in ranges], [(0., .32), (.36, 10.)])

    def test_gap_is_kept_when_its_cut_is_shorter_than_a_frame(self):
        grid, gap = Grid(clip_for(10.)), {'seconds': 4., 'label': 'СНХР'}
        ranges = ranges_from([{'start': .33, 'end': .35, 'gap': gap, 'junction': 'j1'}], 10., grid)
        self.assertEqual(ranges[0]['gapAfter'], 4.)
        self.assertEqual(ranges[0]['end'], ranges[1]['start'])  # nothing removed, the gap opens at the frame
        self.assertAlmostEqual(sum(r['end'] - r['start'] for r in ranges), 10.)


class EditTests(unittest.TestCase):
    def test_long_pause_is_shortened_without_fill(self):
        rec = Recording()
        rec.room(.4)
        rec.say('bugun yangi loyiha boshlandi')
        start = rec.t
        rec.room(2.5)
        end = rec.t
        rec.say('yoshlar ishtirok etdi')
        rec.room(.4)
        state, result, cuts, duration = plan(rec, ['Bugun yangi loyiha boshlandi. Yoshlar ishtirok etdi.'])
        left = (end - start) - removed(cuts, start, end)
        self.assertGreater(left, .2)
        self.assertLess(left, 1.)
        # Every kept range is original audio: the ranges never overlap and only shrink the clip.
        for a, b in zip(result['ranges'], result['ranges'][1:]):
            self.assertLessEqual(a['end'], b['start'] + 1e-6)
        self.assertNotIn('fill', str(result['ranges']))

    def test_breath_is_cut(self):
        rec = Recording(1)
        rec.room(.4)
        rec.say('bugun yangi loyiha boshlandi')
        rec.room(.3)
        rec.breath(.45)
        rec.room(.3)
        rec.say('yoshlar ishtirok etdi')
        rec.room(.4)
        state, result, cuts, duration = plan(rec, ['Bugun yangi loyiha boshlandi, yoshlar ishtirok etdi.'])
        a, b = rec.breaths[0]
        self.assertGreater(removed(cuts, a, b), (b - a) * .8)
        state, result, cuts, duration = plan(rec, ['Bugun yangi loyiha boshlandi, yoshlar ishtirok etdi.'], breaths=False,
                                              pauses=False)
        self.assertLess(removed(cuts, a, b), (b - a) * .5)

    def test_restart_is_removed(self):
        rec = Recording(2)
        rec.room(.4)
        rec.say('bugun yangi loyiha')
        first = rec.t
        rec.room(.5)
        rec.say('yangi loyiha boshlandi')
        rec.room(.4)
        state, result, cuts, duration = plan(rec, ['Bugun yangi loyiha boshlandi.'])
        abandoned = [w for w in rec.words if w['end'] <= first and w['word'].strip() in ('yangi', 'loyiha')]
        for w in abandoned:
            self.assertGreater(removed(cuts, w['start'], w['end']), .8 * (w['end'] - w['start']), w)
        for w in rec.words[3:]:
            self.assertEqual(removed(cuts, w['start'] + .02, w['end'] - .02), 0, w)

    def test_sync_opens_gap(self):
        rec = Recording(3)
        rec.room(.4)
        rec.say('bugun yangi loyiha boshlandi')
        rec.room(.6)
        rec.say('yoshlar ishtirok etdi')
        rec.room(.4)
        state, result, cuts, duration = plan(rec, ['Диктор: Bugun yangi loyiha boshlandi.', 'СНХР: Ali Valiyev',
                                                   '- Bu juda yaxshi loyiha bo‘ldi deb o‘ylayman.',
                                                   'Диктор: Yoshlar ishtirok etdi.'])
        gaps = [r.get('gapAfter', 0) for r in result['ranges']]
        self.assertTrue(any(g > 0 for g in gaps), result['ranges'])
        self.assertGreater(result['stats']['gap_seconds'], 0)

    def test_pause_only_mode(self):
        rec = Recording(4)
        rec.room(.4)
        rec.say('bir ikki uch')
        start = rec.t
        rec.room(3.)
        end = rec.t
        rec.say('tort besh')
        rec.room(.4)
        ac = Acoustics(rec.audio)
        state = prepare(sound_words(ac), ac, clip_for(ac.duration))
        result = build(state)
        cuts = cuts_of(result['ranges'], ac.duration)
        self.assertGreater(removed(cuts, start, end), 1.5)
        for w in rec.words:
            self.assertEqual(removed(cuts, w['start'] + .03, w['end'] - .03), 0, w)

    def test_pause_can_be_kept_by_user(self):
        rec = Recording(5)
        rec.room(.4)
        rec.say('bugun yangi loyiha boshlandi')
        rec.room(2.)
        rec.say('yoshlar ishtirok etdi')
        rec.room(.4)
        state, result, cuts, duration = plan(rec, ['Bugun yangi loyiha boshlandi. Yoshlar ishtirok etdi.'])
        pause = max((j for j in result['junctions'] if j['kind'] == 'pause'), key=lambda j: j['end'] - j['start'])
        again = build(state, decisions={pause['id']: False})
        self.assertLess(again['stats']['removed_seconds'], result['stats']['removed_seconds'] - 1)

    def test_gap_before_everything_becomes_lead_gap(self):
        grid, gap = Grid(clip_for(10.)), {'seconds': 4., 'label': 'СНХР'}
        leading = []
        ranges = ranges_from([{'start': 0., 'end': 1., 'gap': gap, 'junction': 'j0'}], 10., grid, leading)
        self.assertEqual(ranges, [{'start': 1., 'end': 10.}])
        self.assertEqual(leading, [gap])

    def test_lead_gap_is_limited(self):
        rec = Recording(6)
        rec.room(.4)
        rec.say('yoshlar ishtirok etdi')
        rec.room(.4)
        state, result, cuts, duration = plan(rec, ['Стендап', '- Bu juda yaxshi loyiha bo‘ldi deb o‘ylayman.',
                                                   'Диктор: Yoshlar ishtirok etdi.'])
        if state['lead_gap']:
            again = build(state, gap_settings={'lead': {'seconds': 1e9}})
            self.assertEqual(again['lead_gap'], 300.)
            self.assertEqual(build(state, gap_settings={'lead': {'seconds': -5}})['lead_gap'], 0.)
        else:
            self.skipTest('no lead gap for this script')


if __name__ == '__main__':
    unittest.main()
