import os
import shutil
import tempfile
import unittest

import numpy as np

from helpers import Recording
import asr
import audio
from audio import Acoustics, assemble, decode_span, write_wav


class DecodeTests(unittest.TestCase):
    """A selection from a long file is decoded without reading the whole file, sample for sample."""

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp()
        rng = np.random.default_rng(3)
        cls.samples = (rng.normal(0, .05, 16000 * 40)).astype(np.float32)
        cls.path = write_wav(os.path.join(cls.folder, 'long.wav'), cls.samples)
        cls.minimum, audio.PARTIAL_MINIMUM = audio.PARTIAL_MINIMUM, 20.

    @classmethod
    def tearDownClass(cls):
        audio.PARTIAL_MINIMUM = cls.minimum
        shutil.rmtree(cls.folder, ignore_errors=True)

    def test_partial_decode_equals_whole_decode(self):
        from faster_whisper.audio import decode_audio
        whole = decode_audio(self.path, sampling_rate=16000)
        for a, b in ((12.37, 18.9), (0., 5.), (33.123, 39.5)):
            part = decode_span(self.path, a, b)
            self.assertIsNotNone(part, (a, b))
            data, total = part
            self.assertAlmostEqual(total, 40., places=2)
            n = int((b - a) * 16000)
            start = int(round(a * 16000))
            self.assertTrue(np.array_equal(data[:n], whole[start:start + n]), (a, b))

    def test_large_selection_and_short_files_are_decoded_whole(self):
        self.assertIsNone(decode_span(self.path, 1., 30.))      # most of the file
        audio.PARTIAL_MINIMUM = 600.
        try:
            self.assertIsNone(decode_span(self.path, 12., 18.))  # short file
        finally:
            audio.PARTIAL_MINIMUM = 20.
        self.assertIsNone(decode_span(os.path.join(self.folder, 'missing.wav'), 1., 2.))

    def test_assemble_joins_pieces_of_one_file(self):
        joined = assemble([(12., 14., self.path), (20.5, 21., self.path)])
        self.assertEqual(len(joined), 16000 * 2 + 8000)
        expected = np.round(np.clip(self.samples, -1, 1) * 32767).astype(np.int16)[16000 * 12:16000 * 14] / 32768.
        self.assertLess(float(np.abs(joined[:32000] - expected).max()), 1e-3)
        with self.assertRaises(ValueError):
            assemble([(39., 45., self.path)])


class AcousticsTests(unittest.TestCase):
    def test_sound_between_counts_speech_not_breaths(self):
        rec = Recording(11)
        rec.room(.5)
        rec.say('bugun yangi loyiha boshlandi')
        rec.room(.4)
        rec.breath(.45)
        rec.room(.4)
        start = rec.t
        rec.word('yoshlar', .5)
        end = rec.t
        rec.room(.5)
        rec.say('ishtirok etdi bugun ham')
        rec.room(.5)
        ac = Acoustics(rec.audio)
        self.assertAlmostEqual(ac.sound_between(start, end), end - start, delta=.08)
        breath = rec.breaths[0]
        self.assertLess(ac.sound_between(breath[0] - .3, breath[1] + .3), .1)


class CrossfadeTests(unittest.TestCase):
    def test_equal_power_fade_centred_on_the_join(self):
        from service import crossfade
        # The cut goes through sound: both clips still sound for 100 samples on the removed side.
        source = np.concatenate([np.full(1100, .5, np.float32), np.zeros(800, np.float32), np.full(1100, -.5, np.float32)])
        out = np.concatenate([source[:1000], source[2000:]])          # the silent middle is cut out
        before = out.copy()
        self.assertEqual(crossfade(out, source, [(1000, 1000, 2000)], 100), 1)
        self.assertEqual(len(out), 2000)
        self.assertTrue(np.array_equal(out[:900], before[:900]) and np.array_equal(out[1100:], before[1100:]))
        # The left clip fades out over its own tail, the right one fades in from 100 samples early.
        self.assertAlmostEqual(float(out[900]), .5, places=2)
        self.assertAlmostEqual(float(out[1099]), -.5, places=2)
        self.assertLess(float(np.abs(np.diff(out[880:1120])).max()), .01)   # no step left at the join
        self.assertAlmostEqual(float(np.abs(np.diff(before[880:1120])).max()), 1.)   # the click a hard cut makes

    def test_joins_without_room_are_left_alone(self):
        from service import crossfade
        source = np.ones(300, np.float32)
        out = source[:200].copy()
        self.assertEqual(crossfade(out, source, [(50, 50, 150), (100, 250, 280)], 100), 0)
        self.assertEqual(crossfade(out, source, [(100, 100, 200)], 0), 0)
        self.assertTrue(np.array_equal(out, source[:200]))


class RecoveryTests(unittest.TestCase):
    def test_language_is_the_users_choice(self):
        self.assertEqual([asr.choose_mode('auto', l) for l in ('uz', 'ru', 'en')], ['uzbek_hq', 'russian', 'english'])
        self.assertEqual(asr.choose_mode('uzbek', 'uz'), 'uzbek')
        self.assertEqual(asr.choose_mode('uzbek', 'ru'), 'russian')      # a model of another language is never used
        self.assertEqual(asr.choose_mode('russian', 'en'), 'english')
        self.assertEqual(asr.MODELS['english']['language'], 'en')

    def test_model_revisions_are_pinned(self):
        for mode, spec in asr.MODELS.items():
            if spec['path'] != 'kotib':
                self.assertRegex(spec.get('revision', ''), r'^[0-9a-f]{40}$', mode)
                self.assertIn('/', spec['path'], mode)   # a full repository name, not a size alias
        self.assertRegex(asr.KOTIB['revision'], r'^[0-9a-f]{40}$')

    def test_uncovered_speech_is_found(self):
        words = [{'start': 1., 'end': 1.4}, {'start': 1.5, 'end': 2.}, {'start': 6., 'end': 6.5}]
        spans = [(.9, 2.1), (3., 5.), (5.9, 6.6), (8., 8.3)]
        self.assertEqual(asr.uncovered(spans, words), [(3., 5.)])   # 0.3 s of noise is not worth a second pass

    def test_mode_follows_the_script_language(self):
        self.assertEqual(asr.choose_mode('auto', 'uz'), 'uzbek_hq')
        self.assertEqual(asr.choose_mode(None, 'ru'), 'russian')
        self.assertEqual(asr.choose_mode('uzbek', 'ru'), 'russian')
        with self.assertRaises(ValueError):
            asr.choose_mode('nope', 'uz')


if __name__ == '__main__':
    unittest.main()
