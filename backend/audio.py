"""Audio of the selected timeline clips and its acoustic analysis (10 ms frames)."""
import hashlib
import json
import os
import wave
from pathlib import Path

import numpy as np

RATE = 16000
HOP = 160  # 10 ms


def layout(clip):
    """[(inPoint, outPoint, path)] of each selected piece in timeline order."""
    pieces = clip.get('pieces') or [{'inPoint': clip['inPoint'], 'outPoint': clip['outPoint']}]
    result = []
    for piece in pieces:
        a, b = float(piece['inPoint']), float(piece['outPoint'])
        path = str(piece.get('path') or clip.get('path') or '')
        if -.1 < a < 0:
            a = 0.   # Premiere sometimes reports an in point a hair before the start of the media
        if not path:
            raise ValueError('Tanlangan klipning manba fayli yo‘q (nested sequence, multicam yoki offline klip bo‘lishi '
                             'mumkin). Oddiy audio faylli klipni tanlang yoki uni Render and Replace qiling.')
        if not (0 <= a < b):
            raise ValueError('Timeline manba chegaralari noto‘g‘ri: klip «%s», kirish %.3f s, chiqish %.3f s. '
                             'Klip teskari (reverse) yoki tezligi o‘zgartirilgan bo‘lsa, avval Render and Replace qiling.'
                             % (piece.get('name') or os.path.basename(path), a, b))
        result.append((a, b, path))
    return result


def fingerprint(pieces):
    """Stable identity of the selection, including the media files' size and date."""
    items = []
    for a, b, path in pieces:
        try:
            stat = os.stat(path)
            media = [os.path.normcase(os.path.abspath(path)), stat.st_size, stat.st_mtime_ns]
        except OSError:
            raise ValueError('Audio fayli topilmadi: ' + path)
        items.append([round(a, 2), round(b, 2)] + media)
    return hashlib.sha256(json.dumps(items).encode()).hexdigest()


PARTIAL_MINIMUM = 600.   # only long media is worth decoding partly
PARTIAL_SHARE = .6       # ...and only when the selection is a smaller part of it
PARTIAL_FORMATS = ('mov', 'mxf', 'wav', 'matroska')  # containers whose timestamps are exact after a seek


def decode_span(path, start, end, margin=2.):
    """(audio from `start`, media length) of a long file without decoding all of it; None: decode it whole.

    A two-hour camera file with five selected minutes would otherwise be decoded completely.
    """
    try:
        import av
        with av.open(path, mode='r', metadata_errors='ignore') as container:
            stream = container.streams.audio[0]
            if not any(name in container.format.name for name in PARTIAL_FORMATS) or not stream.duration:
                return None
            base = float(stream.time_base)
            origin = stream.start_time * base if stream.start_time is not None else 0.
            total = stream.duration * base
            if total < PARTIAL_MINIMUM or end - start > total * PARTIAL_SHARE:
                return None
            container.seek(int((origin + max(0., start - margin)) / base), stream=stream, backward=True)
            resampler = av.audio.resampler.AudioResampler(format='s16', layout='mono', rate=RATE)
            first, chunks = None, []
            for frame in container.decode(stream):
                if frame.pts is None:
                    return None
                at = frame.pts * float(frame.time_base) - origin
                if first is None:
                    first = at
                if at > end + margin:
                    break
                frame.pts = None
                chunks.extend(out.to_ndarray().reshape(-1) for out in resampler.resample(frame))
            chunks.extend(out.to_ndarray().reshape(-1) for out in resampler.resample(None))
        if first is None or first > start + 1e-3:
            return None
        data = np.concatenate(chunks).astype(np.float32) / 32768.
        return data[int(round((start - first) * RATE)):], total
    except Exception:
        return None


def assemble(pieces):
    from faster_whisper.audio import decode_audio
    spans = {}
    for a, b, path in pieces:
        low, high = spans.get(path, (a, b))
        spans[path] = (min(low, a), max(high, b))
    cache, chunks = {}, []
    for a, b, path in pieces:
        if path not in cache:
            part = decode_span(path, *spans[path])
            if part is not None:
                cache[path] = (part[0], spans[path][0], part[1])
            else:
                try:
                    data = decode_audio(path, sampling_rate=RATE)
                except Exception as error:
                    raise ValueError('Audio ochilmadi (' + os.path.basename(path) + '): ' + str(error))
                cache[path] = (data, 0., len(data) / RATE)
        data, base, total = cache[path]
        start, length = round((a - base) * RATE), round((b - a) * RATE)
        if b > total + .05:
            raise ValueError('Timeline bo‘lagi manba fayli uzunligidan tashqarida.')
        chunk = data[start:start + length]
        if len(chunk) < length:
            chunk = np.pad(chunk, (0, length - len(chunk)))
        chunks.append(chunk.astype(np.float32))
    return np.concatenate(chunks)


class Acoustics:
    """Per-frame level, noise floor, speech/silence mask and breaths."""

    def __init__(self, audio):
        self.audio = audio
        self.count = len(audio) // HOP
        self.duration = len(audio) / RATE
        count = self.count
        if count < 10:
            raise ValueError('Audio juda qisqa.')
        frames = audio[:count * HOP].reshape(count, HOP)
        rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
        self.rms = rms
        self.level = 20 * np.log10(rms + 1e-6)
        voice = float(np.quantile(rms, .8))
        noise = float(np.quantile(rms, .15))
        self.threshold = max(.0004, min(voice * .2, max(noise * 1.8, voice * .08)))
        self.speech_level = float(np.quantile(self.level, .9))
        real = self.level[self.level > -90]
        self.floor = float(np.quantile(real, .1)) if len(real) > 100 else -90.
        self.breath_spans = breaths(audio, self.level)
        self.breath = np.zeros(count, bool)
        for a, b in self.breath_spans:
            self.breath[int(a * 100):int(np.ceil(b * 100))] = True
        loud = rms >= self.threshold
        # Close brief dips inside words (stop consonants) and drop isolated clicks.
        loud = close_runs(loud, 6, value=False)
        loud = close_runs(loud, 4, value=True)
        # Speech-like sound. A frame or two left over at the edge of a breath is not a sound of its own.
        self.sound = close_runs(loud & ~self.breath, 4, value=True)
        self.clean = ~loud & ~self.breath       # silence that may stay in a pause

    def frame(self, seconds):
        return int(min(self.count, max(0, round(seconds * 100))))

    def silent_run_after(self, start, limit, minimum=.1):
        """First quiet (non-sound) run of `minimum` s beginning in [start, limit]."""
        a, b = self.frame(start), self.frame(limit)
        need = max(1, int(minimum * 100))
        run = 0
        for k in range(a, min(self.count, b + need)):
            if not self.sound[k]:
                run += 1
                if run >= need and k - run + 1 <= b:
                    return (k - run + 1) / 100
            else:
                if k > b:
                    break
                run = 0
        return None

    def silent_run_before(self, end, limit, minimum=.1):
        """Last quiet run of `minimum` s ending in [limit, end]; returns its end."""
        a, b = self.frame(limit), self.frame(end)
        need = max(1, int(minimum * 100))
        run = 0
        for k in range(min(self.count - 1, b), max(-1, a - need - 1), -1):
            if not self.sound[k]:
                run += 1
                if run >= need and k + run <= b + 1:
                    return (k + run) / 100
            else:
                if k < a:
                    break
                run = 0
        return None

    def quietest(self, start, end):
        """Quietest 20 ms point in [start, end] for a tight cut inside connected speech."""
        a, b = self.frame(start), self.frame(end)
        if b - a < 2:
            return (start + end) / 2
        window = np.convolve(self.rms[a:b + 1], np.ones(2) / 2, mode='valid')
        return (a + int(np.argmin(window)) + 1) / 100

    def clean_after(self, t, limit):
        """Seconds of clean silence directly after t (stops at sound or breath)."""
        a, b = self.frame(t), self.frame(limit)
        k = a
        while k < b and self.clean[k]:
            k += 1
        return (k - a) / 100

    def clean_before(self, t, limit):
        a, b = self.frame(limit), self.frame(t)
        k = b
        while k > a and self.clean[k - 1]:
            k -= 1
        return (b - k) / 100

    def sound_between(self, a, b):
        """Seconds of speech-like sound in [a, b]."""
        return float(self.sound[self.frame(a):self.frame(b)].sum()) / 100

    def longest_sound(self, a, b):
        """Seconds of the longest unbroken speech-like sound in [a, b]."""
        edges = np.diff(np.r_[False, self.sound[self.frame(a):self.frame(b)], False].astype(np.int8))
        runs = np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)
        return float(runs.max()) / 100 if len(runs) else 0.

    def breaths_between(self, a, b):
        return [(s, e) for s, e in self.breath_spans if s < b and e > a]


def close_runs(mask, size, value):
    """Set runs equal to `value` that are at most `size` frames long to `not value`."""
    mask = mask.copy()
    target = mask == value
    edges = np.diff(np.r_[False, target, False].astype(np.int8))
    for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        if 0 < a and b < len(mask) and b - a <= size:
            mask[a:b] = not value
    return mask


WIDE = .8
BANDS = 20     # 0-8 kHz
SEEDS = 8      # breaths needed before their common colour can be trusted


def breaths(audio, level=None):
    """Audible inhalations: quiet, noise-like (energy above 2 kHz), 0.12-1 s. Returns [(start, end)] s."""
    count = len(audio) // HOP
    if count < 100:
        return []
    size = 400
    padded = np.r_[audio, np.zeros(size, dtype=audio.dtype)]
    compute_level = level is None or len(level) != count
    level = np.empty(count) if compute_level else level
    zcr, high, upper = np.empty(count), np.empty(count), np.empty(count)
    bands = np.empty((count, BANDS), np.float32)      # 400 Hz bands: the colour of each frame
    window = np.hanning(size).astype(np.float32)
    split = int(2000 / 8000 * (size // 2 + 1))
    lower = int(1500 / 8000 * (size // 2 + 1))
    for a in range(0, count, 20000):
        index = np.arange(size)[None, :] + HOP * np.arange(a, min(count, a + 20000))[:, None]
        frames = padded[index]
        if compute_level:
            level[a:a + 20000] = 10 * np.log10(np.mean(frames[:, :HOP] ** 2, axis=1) + 1e-10)
        signs = np.signbit(frames)
        zcr[a:a + 20000] = np.mean(signs[:, 1:] != signs[:, :-1], axis=1)
        power = np.abs(np.fft.rfft(frames * window, axis=1)) ** 2
        high[a:a + 20000] = power[:, split:].sum(1) / (power.sum(1) + 1e-12)
        upper[a:a + 20000] = power[:, lower:].sum(1) / (power.sum(1) + 1e-12)
        bands[a:a + 20000] = power[:, :BANDS * 10].reshape(len(power), BANDS, 10).sum(2)
    speech_level = float(np.quantile(level, .9))
    real = level[level > -90]
    if len(real) < 100:
        return []
    floor = float(np.quantile(real, .1))
    if speech_level - floor < 20:
        return []
    quiet = (level < speech_level - 13)
    voiced = (level > speech_level - 12) & (zcr < .2)
    result = []
    # Classic breaths hiss above 2 kHz. Some hiss lower (1.5-2 kHz); the fading end of a word ("х", "с")
    # sounds the same, so a low hiss is a breath only when it stands alone between quiet moments.
    for strong, weak, alone in ((high > .6, high > .45, False), (upper > WIDE, upper > WIDE - .15, True)):
        mark = strong & (level > floor + 2) & quiet
        holes = np.diff(np.r_[False, ~mark, False].astype(np.int8))
        for a, b in zip(np.flatnonzero(holes == 1), np.flatnonzero(holes == -1)):
            if 0 < a and b < len(mark) and b - a <= 3 and level[a:b].max() < speech_level - 13:
                mark[a:b] = True
        soft = weak & (level > floor + 1) & quiet
        edges = np.diff(np.r_[False, mark, False].astype(np.int8))
        found = []
        for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
            for _ in range(20):  # grow over the faint onset and fade of the same breath
                if a > 0 and soft[a - 1] and not voiced[a - 1]:
                    a -= 1
                else:
                    break
            for _ in range(20):
                if b < count and soft[b] and not voiced[b]:
                    b += 1
                else:
                    break
            if found and a / 100 <= found[-1][1] + .03:
                continue
            start, end = a / 100, b / 100
            if not .12 <= end - start <= 1.:
                continue
            median = float(np.median(level[a:b]))
            if median > speech_level - 16:
                continue
            # A fricative inside a word sits between voiced sounds; a breath does not.
            left, right = voiced[max(0, a - 3):a].any(), voiced[b:b + 3].any()
            if left and right:
                continue
            if (left or right) and (end - start < .2 or median > speech_level - 19):
                continue
            # The decaying tail of a word falls from its first frame; an inhalation rises and fades.
            peak = a + int(np.argmax(level[a:b]))
            top = float(level[peak])
            dip = level[max(0, a - 15):a]
            if not ((len(dip) and dip.min() < top - 6) or peak - a >= (b - a) * .25):
                continue
            if top < floor + 8:
                continue
            if alone:
                before, after = level[max(0, a - 8):a], level[b:b + 8]
                if left or right or not (len(before) and len(after)) or                         before.max() > top - 3 or after.max() > top - 3 or peak in (a, b - 1) or                         any(s < end and e > start for s, e in result):
                    continue
            found.append((start, end))
        result.extend(found)
    result = sorted(result)
    return sorted(result + same_voice(result, bands, level, voiced, speech_level, floor))


def colour(bands, a, b):
    """Spectral shape of frames [a, b): dB per band around their mean."""
    shape = 10 * np.log10(bands[a:b].mean(0) + 1e-12)
    return shape - shape.mean()


def same_voice(found, bands, level, voiced, speech_level, floor):
    """Breaths the rules above miss, found by their likeness to the ones they caught.

    A reader who works close to the microphone snatches short, fairly loud breaths right at the end of
    a word. By level and length they pass for the hiss that ends the word, but every breath of one
    reader in one recording has the same colour, and it is not the colour of "с", "ш" or "х".
    """
    if len(found) < SEEDS:
        return []
    shapes = np.array([colour(bands, int(s * 100), int(np.ceil(e * 100))) for s, e in found])
    template = np.median(shapes, axis=0)
    centred = template - template.mean()
    norm = float(np.sqrt((centred ** 2).sum())) + 1e-9

    def likeness(shape):
        return float((shape * centred).sum() / ((np.sqrt((shape ** 2).sum()) + 1e-9) * norm)),             float(np.sqrt(np.mean((shape - template) ** 2)))
    if np.median([likeness(shape)[0] for shape in shapes]) < .8:
        return []  # the caught breaths do not agree with each other: nothing to learn from
    count = len(level)
    smooth = bands.copy()
    smooth[1:-1] += bands[:-2] + bands[2:]
    frames = 10 * np.log10(smooth + 1e-12)
    frames -= frames.mean(1, keepdims=True)
    alike = (frames @ centred) / ((np.sqrt((frames ** 2).sum(1)) + 1e-9) * norm)
    mark = (alike >= .7) & (level > floor + 4) & (level < speech_level - 7) & ~voiced
    mark = close_runs(mark, 2, value=False)
    soft = (alike >= .6) & (level > floor + 2) & (level < speech_level - 7) & ~voiced
    taken = np.zeros(count, bool)
    for s, e in found:
        taken[max(0, int(s * 100) - 3):int(np.ceil(e * 100)) + 3] = True
    edges = np.diff(np.r_[False, mark, False].astype(np.int8))
    result = []
    for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        if not 10 <= b - a <= 100 or taken[a:b].any():
            continue
        match, distance = likeness(colour(bands, a, b))
        median, top = float(np.median(level[a:b])), float(level[a:b].max())
        if match < .82 or distance > 4.5 or median > speech_level - 9 or top < floor + 8:
            continue
        # A breath has a quiet moment on at least one side; a hiss inside a word has speech on both.
        before, after = level[max(0, a - 8):a], level[b:b + 8]
        if not ((len(before) and before.min() < median - 8) or (len(after) and after.min() < median - 8)):
            continue
        for _ in range(10):  # the faint onset and fade of the same breath
            if a > 0 and soft[a - 1] and not taken[a - 1]:
                a -= 1
            else:
                break
        for _ in range(10):
            if b < count and soft[b] and not taken[b]:
                b += 1
            else:
                break
        # Straight out of loud speech with no dip at all: the first moment may be the release of the
        # word's last consonant ("лет", "девочек"), so it stays with the word.
        if a >= 3 and level[a - 3:a].max() > speech_level - 6:
            if b - a < 15:
                continue
            a += 5
        taken[a:b] = True
        result.append((a / 100, b / 100))
    return result


def speech_spans(audio):
    """Voice activity (Silero VAD) in seconds."""
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    spans = get_speech_timestamps(audio, VadOptions(threshold=.35, min_speech_duration_ms=80,
                                                    min_silence_duration_ms=100, speech_pad_ms=40))
    return [(s['start'] / RATE, s['end'] / RATE) for s in spans]


def write_wav(path, audio):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with wave.open(str(temporary), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes((np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes())
    os.replace(temporary, path)
    return str(path.resolve())
