import atexit
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
RATE = 16000


def docx(paragraphs):
    return docx_body(''.join('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % escape(p) for p in paragraphs))


def docx_body(body):
    """Word file with the given WordprocessingML body; removed when the tests end."""
    xml = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
           '<w:body>%s</w:body></w:document>' % body)
    handle = tempfile.NamedTemporaryFile(suffix='.docx', delete=False)
    handle.close()
    atexit.register(_remove, handle.name)
    with zipfile.ZipFile(handle.name, 'w') as archive:
        archive.writestr('word/document.xml', xml)
    return handle.name


def _remove(name):
    try:
        os.unlink(name)
    except OSError:
        pass


class Recording:
    """Synthetic voice: tone bursts as words, low room tone between them, optional breaths."""

    def __init__(self, seed=0):
        self.rng = np.random.default_rng(seed)
        self.chunks, self.words, self.t, self.breaths = [], [], 0., []

    def room(self, seconds):
        self.chunks.append(self.rng.normal(0, .0008, int(seconds * RATE)).astype(np.float32))
        self.t += seconds

    def word(self, text, seconds=.35):
        n = int(seconds * RATE)
        tone = .12 * np.sin(2 * np.pi * 220 * np.arange(n) / RATE) * np.hanning(n) ** .2
        self.chunks.append((tone + self.rng.normal(0, .0008, n)).astype(np.float32))
        self.words.append({'word': ' ' + text, 'start': round(self.t + .01, 3), 'end': round(self.t + seconds - .01, 3)})
        self.t += seconds

    def breath(self, seconds=.4):
        n = int(seconds * RATE)
        noise = np.diff(self.rng.normal(0, 1, n + 1)) * .004
        envelope = np.sin(np.pi * np.arange(n) / n)
        self.chunks.append((noise * envelope + self.rng.normal(0, .0008, n)).astype(np.float32))
        self.breaths.append((self.t, self.t + seconds))
        self.t += seconds

    def say(self, text, gap=.12):
        for k, w in enumerate(text.split()):
            if k:
                self.room(gap)
            self.word(w)

    @property
    def audio(self):
        return np.concatenate(self.chunks)


def clip_for(duration, frame=.04):
    return {'path': 'x.wav', 'start': 0., 'inPoint': 0., 'outPoint': duration, 'frame': frame,
            'pieces': [{'start': 0., 'end': duration, 'inPoint': 0., 'outPoint': duration, 'path': 'x.wav'}]}


def cuts_of(ranges, duration):
    cuts, cursor = [], 0.
    for r in ranges:
        if r['start'] > cursor + 1e-6:
            cuts.append((cursor, r['start']))
        cursor = r['end']
    if cursor < duration - 1e-6:
        cuts.append((cursor, duration))
    return cuts


def removed(cuts, a, b):
    return sum(max(0., min(b, e) - max(a, s)) for s, e in cuts)
