import unittest

import helpers  # noqa: F401  (backend path)
from align import follow, abandoned
from text import tokens

SCRIPT = ('bugun mamlakatimizda yangi loyiha ishga tushirildi unda yuzlab yoshlar ishtirok etdi '
          'loyiha davomida ular zamonaviy kasblarni organishadi va tajriba orttirishadi')


def run(heard_text, script_text=SCRIPT):
    script, heard = tokens(script_text), tokens(heard_text)
    path, reads = follow(script, heard)
    dropped = abandoned(path, reads, [k * .4 for k in range(len(heard))])
    kept = [t for t, d in zip(heard, dropped) if not d]
    return heard, path, reads, dropped, kept


class AlignTests(unittest.TestCase):
    def test_clean_reading_keeps_everything(self):
        heard, path, reads, dropped, kept = run(SCRIPT)
        self.assertEqual(kept, heard)
        self.assertEqual(path, list(range(len(heard))))

    def test_partial_restart_keeps_last_take(self):
        heard, path, reads, dropped, kept = run(
            'bugun mamlakatimizda yangi loyiha boshlandi yoq yangi loyiha ishga tushirildi unda yuzlab yoshlar ishtirok etdi')
        self.assertEqual(' '.join(kept), 'bugun mamlakatimizda yangi loyiha ishga tushirildi unda yuzlab yoshlar ishtirok etdi')
        self.assertEqual(dropped[:4], [False, False, True, True])

    def test_whole_sentence_read_twice(self):
        sentence = 'unda yuzlab yoshlar ishtirok etdi'
        heard, path, reads, dropped, kept = run('yangi loyiha ishga tushirildi ' + sentence + ' ' + sentence + ' loyiha davomida ular')
        self.assertEqual(' '.join(kept), 'yangi loyiha ishga tushirildi ' + sentence + ' loyiha davomida ular')
        first = heard.index('unda')
        self.assertTrue(all(dropped[first:first + 5]))

    def test_several_failed_attempts(self):
        heard, path, reads, dropped, kept = run(
            'unda yuzlab yosh unda yuzlab yoshlar ish unda yuzlab yoshlar ishtirok etdi')
        self.assertEqual(' '.join(kept), 'unda yuzlab yoshlar ishtirok etdi')

    def test_unscripted_words_stay(self):
        heard, path, reads, dropped, kept = run('bugun mamlakatimizda albatta yangi loyiha ishga tushirildi')
        self.assertEqual(kept, heard)
        self.assertFalse(reads[heard.index('albatta')])

    def test_repeated_text_in_script_is_not_a_retake(self):
        script = 'u keldi va ketdi u keldi va ketdi deb yozdi'
        heard, path, reads, dropped, kept = run(script, script)
        self.assertEqual(kept, heard)

    def test_long_skip_does_not_lose_the_beginning(self):
        # The recording skips a long unvoiced standup in the middle of the script.
        standup = ' '.join('stendap%d' % k for k in range(120))
        script = SCRIPT + ' ' + standup + ' oxirgi qism shu yerda tugaydi va hammasi yaxshi'
        heard, path, reads, dropped, kept = run(SCRIPT + ' oxirgi qism shu yerda tugaydi va hammasi yaxshi', script)
        self.assertEqual(kept, heard)
        self.assertTrue(all(p >= 0 for p in path))

    def test_partial_recording_of_long_script(self):
        script = ' '.join('soz%d' % k for k in range(600))
        heard_text = ' '.join('soz%d' % k for k in range(300, 340))
        heard, path, reads, dropped, kept = run(heard_text, script)
        self.assertEqual(path[0], 300)
        self.assertEqual(kept, heard)


if __name__ == '__main__':
    unittest.main()
