"""Local speech recognition (faster-whisper). Audio never leaves the computer."""
import gc
import hashlib
import http.client
import json
import os
import site
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_VERSION = 'asr-v2'

MODELS = {
    'uzbek_hq': {'name': 'Kotib Medium (o‘zbekcha)', 'path': 'kotib', 'language': 'uz',
                 'options': {'chunk_length': 20, 'without_timestamps': True}},
    # Revisions are pinned: a changed upstream repository can neither change the results nor bring new files.
    'uzbek': {'name': 'Whisper Small (o‘zbekcha)', 'path': 'maqsudxo1ja/uz-whisper-small-stt-v2', 'language': 'uz',
              'revision': 'bf1e5a0866a83277b2f7de1affe82a954710c612',
              'options': {'chunk_length': 12, 'vad_parameters': {'max_speech_duration_s': 12,
                                                                  'min_silence_duration_ms': 300,
                                                                  'speech_pad_ms': 100}}},
    'russian': {'name': 'Whisper Medium (ruscha)', 'path': 'Systran/faster-whisper-medium', 'language': 'ru',
                'revision': '08e178d48790749d25932bbc082711ddcfdfbc4f', 'options': {}},
    # The same multilingual model, told to listen for English.
    'english': {'name': 'Whisper Medium (inglizcha)', 'path': 'Systran/faster-whisper-medium', 'language': 'en',
                'revision': '08e178d48790749d25932bbc082711ddcfdfbc4f', 'options': {}},
}
DEFAULT_MODE = {'uz': 'uzbek_hq', 'ru': 'russian', 'en': 'english'}

KOTIB = {'repo': 'yuldashev222/uzbek_stt_v1-ct2', 'revision': '58e65df776e16f2eae01a483266ef05b17e4588d',
         'size': 3055769749, 'sha256': 'ea3cb9ee1c8685b4e348bc07aef2853947f1a439d341c97884c60da94611f7fa',
         'files': ['config.json', 'tokenizer.json', 'vocabulary.json', 'preprocessor_config.json', 'model.bin']}

_cuda_handles = []
_lock = threading.Lock()


def choose_mode(requested, language):
    if requested in (None, '', 'auto'):
        return DEFAULT_MODE[language]
    if requested not in MODELS:
        raise ValueError('Noma’lum nutq modeli.')
    if MODELS[requested]['language'] != language:   # a model of another language cannot be used
        return DEFAULT_MODE[language]
    return requested


def load_cuda_libraries():
    if os.name != 'nt' or _cuda_handles:
        return
    folders = []
    for base in site.getsitepackages():
        nvidia = Path(base) / 'nvidia'
        if nvidia.exists():
            folders.extend(p for p in nvidia.glob('*/bin') if p.is_dir())
    for folder in folders:
        _cuda_handles.append(os.add_dll_directory(str(folder)))
    if folders:
        os.environ['PATH'] = os.pathsep.join(map(str, folders)) + os.pathsep + os.environ.get('PATH', '')


def gpu_available():
    return gpu_compute_type() is not None


def gpu_compute_type():
    """Fastest GPU arithmetic: half precision on cards that have fast float16 (RTX, GTX 16xx and newer,
    several times faster there), otherwise int8 with float32 (Pascal cards such as the GTX 1050)."""
    try:
        load_cuda_libraries()
        import ctranslate2
        if ctranslate2.get_cuda_device_count() <= 0:
            return None
        supported = ctranslate2.get_supported_compute_types('cuda')
        for kind in ('int8_float16', 'int8_float32'):
            if kind in supported:
                return kind
    except Exception:
        pass
    return None


def kotib_path(report):
    """Pinned Kotib Medium model; downloaded once, checksum verified once."""
    folder = ROOT / '.models' / 'kotib-medium'
    folder.mkdir(parents=True, exist_ok=True)
    for name in KOTIB['files']:
        target = folder / name
        if target.exists() and (name != 'model.bin' or target.stat().st_size == KOTIB['size']):
            continue
        report('Aniq o‘zbek modeli yuklanmoqda: ' + name + ' (asosiy fayl 3.06 GB, faqat bir marta)')
        partial = target.with_suffix(target.suffix + '.partial')
        url = 'https://huggingface.co/%s/resolve/%s/%s?download=true' % (KOTIB['repo'], KOTIB['revision'], name)
        # Only the large file is resumed; small ones are simply fetched again.
        offset = partial.stat().st_size if name == 'model.bin' and partial.exists() else 0
        if offset >= KOTIB['size']:
            if offset > KOTIB['size']:
                partial.unlink()
                raise ValueError('Model fayli buzilgan edi va o‘chirildi. Qayta urinib ko‘ring.')
            os.replace(partial, target)  # fully downloaded earlier (a Range request would get HTTP 416)
            continue
        request = urllib.request.Request(url, headers={'Range': 'bytes=%d-' % offset} if offset else {})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                append = offset and response.status == 206
                size = offset if append else 0
                shown = size
                with partial.open('ab' if append else 'wb') as output:
                    while True:
                        block = response.read(1 << 20)
                        if not block:
                            break
                        output.write(block)
                        size += len(block)
                        if size - shown >= 100 << 20:
                            report('Model: %d MiB yuklandi' % (size >> 20))
                            shown = size
                expected = response.headers.get('Content-Length')
        except (OSError, http.client.HTTPException) as error:  # IncompleteRead is not an OSError
            raise ValueError('Modelni yuklab bo‘lmadi (internet kerak, faqat birinchi marta): ' + (str(error) or type(error).__name__))
        if name == 'model.bin' and partial.stat().st_size != KOTIB['size']:
            raise ValueError('Model to‘liq yuklanmadi. Qayta urinib ko‘ring — yuklash davom ettiriladi.')
        if name != 'model.bin' and expected and not append and partial.stat().st_size != int(expected):
            raise ValueError('Model fayli to‘liq yuklanmadi: ' + name)
        os.replace(partial, target)
    model = folder / 'model.bin'
    stat = model.stat()
    marker = folder / 'verified.json'
    stamp = {'size': stat.st_size, 'mtime': stat.st_mtime_ns, 'sha256': KOTIB['sha256']}
    try:
        if json.loads(marker.read_text(encoding='utf-8')) == stamp:
            return str(folder)
    except (OSError, ValueError):
        pass
    report('Model yaxlitligi tekshirilmoqda (faqat bir marta)…')
    digest = hashlib.sha256()
    with model.open('rb') as source:
        for chunk in iter(lambda: source.read(8 << 20), b''):
            digest.update(chunk)
    if digest.hexdigest() != KOTIB['sha256']:
        raise ValueError('Model fayli buzilgan. .models/kotib-medium/model.bin ni o‘chirib, qayta yuklang.')
    marker.write_text(json.dumps(stamp), encoding='utf-8')
    return str(folder)


HF_FOLDER = ROOT / '.models' / 'hf'


def hub_location(repo, revision):
    """(cache folder, offline) for a Hugging Face model. The offline installer puts the models into the
    program's own `.models/hf`; a computer that already has them in the user cache keeps using that.
    A model already on disk is opened without touching the network (no waiting on a missing connection)."""
    name = 'models--' + repo.replace('/', '--')
    default = Path(os.environ.get('HF_HUB_CACHE') or Path(os.environ.get('HF_HOME') or Path.home() / '.cache' / 'huggingface') / 'hub')
    for folder, root in ((HF_FOLDER, str(HF_FOLDER)), (default, None)):
        if revision and (folder / name / 'snapshots' / revision / 'model.bin').exists():
            return root, True
    return (None, False) if (default / name).exists() else (str(HF_FOLDER), False)


class Engine:
    """One loaded model at a time. A GPU failure (memory, missing DLL) falls back to CPU."""

    def __init__(self):
        self.model = None
        self.key = None
        self.device = 'cpu'
        self.gpu_failed = False

    def load(self, mode, use_gpu, report):
        device = 'cuda' if use_gpu and not self.gpu_failed and gpu_available() else 'cpu'
        key = (mode, device)
        if self.model is not None and self.key == key:
            return
        from faster_whisper import WhisperModel
        self.model = None
        gc.collect()
        spec = MODELS[mode]
        report(spec['name'] + ' modeli yuklanmoqda…')
        path = kotib_path(report) if spec['path'] == 'kotib' else spec['path']
        threads = max(1, min(32, (os.cpu_count() or 2)))      # every core: the analysis is the only heavy job
        pin = {'revision': spec['revision']} if spec.get('revision') else {}
        if spec['path'] != 'kotib':
            cache, offline = hub_location(spec['path'], spec.get('revision'))
            if cache:
                pin['download_root'] = cache
            pin['local_files_only'] = offline
            if not offline:
                report(spec['name'] + ' modeli internetdan yuklanmoqda (faqat bir marta)…')
        try:
            if device == 'cuda':
                self.model = WhisperModel(path, device='cuda', compute_type=gpu_compute_type() or 'int8_float32', **pin)
            else:
                self.model = WhisperModel(path, device='cpu', compute_type='int8', cpu_threads=threads, **pin)
        except Exception as error:
            if device != 'cuda':
                raise ValueError('Nutq modeli yuklanmadi: ' + str(error))
            self._gpu_down(report, error)
            return self.load(mode, use_gpu, report)
        self.key, self.device = key, device

    def _gpu_down(self, report, error):
        report('Videokarta ishlamadi (' + str(error)[:80] + '). CPU rejimiga o‘tilmoqda…')
        self.gpu_failed = True
        self.model = None
        gc.collect()

    def transcribe(self, audio, mode, use_gpu, report, progress=None, **extra):
        """Words [{word, start, end, probability}]; retried on CPU if the GPU fails mid-way."""
        spec = MODELS[mode]
        options = dict(language=spec['language'], word_timestamps=True, vad_filter=True, beam_size=1,
                       best_of=1, temperature=0, condition_on_previous_text=False)
        options.update(spec['options'])
        options.update(extra)
        with _lock:
            for attempt in range(2):
                self.load(mode, use_gpu, report)
                try:
                    segments, _ = self.model.transcribe(audio, **options)
                    words = []
                    for segment in segments:
                        for w in segment.words or []:
                            if w.end > w.start:
                                words.append({'word': w.word, 'start': round(w.start, 3), 'end': round(w.end, 3),
                                              'probability': round(w.probability, 3),
                                              'segment_logprob': round(segment.avg_logprob, 3),
                                              'no_speech': round(segment.no_speech_prob, 3)})
                        if progress:
                            progress(segment.end)
                    return words
                except RuntimeError as error:
                    if self.device != 'cuda' or attempt:
                        raise ValueError('Nutqni tanishda xato: ' + str(error))
                    self._gpu_down(report, error)


ENGINE = Engine()


def spoken_end(word):
    """Whisper stretches a word over the speech it skipped after it; no word lasts that long."""
    return min(word['end'], word['start'] + .4 + .09 * len(word['word'].strip())) if word.get('word') else word['end']


def uncovered(spans, words, minimum=.7, pad=.12):
    """Parts of VAD speech not covered by any recognised word (Whisper often drops a first take)."""
    marks = sorted((w['start'] - pad, spoken_end(w) + pad) for w in words)
    result = []
    for a, b in spans:
        cursor = a
        for s, e in marks:
            if e <= cursor or s >= b:
                continue
            if s - cursor >= minimum:
                result.append((cursor, s))
            cursor = max(cursor, e)
            if cursor >= b:
                break
        if b - cursor >= minimum:
            result.append((cursor, b))
    return result


def recover(audio, words, spans, mode, use_gpu, report, rate=16000, budget=.2):
    """Decode skipped speech islands separately so both takes of a retake are seen."""
    total = len(audio) / rate
    parts = [p for p in uncovered(spans, words) if p[1] - p[0] <= 40]
    limit = max(60., total * budget)
    chosen, used = [], 0.
    for a, b in sorted(parts, key=lambda p: p[1] - p[0], reverse=True):
        if used + (b - a) <= limit:
            chosen.append((a, b))
            used += b - a
    recovered = []
    for index, (a, b) in enumerate(sorted(chosen)):
        report('Tushib qolgan nutq tekshirilmoqda: %d/%d' % (index + 1, len(chosen)))
        left, right = max(0., a - .15), min(total, b + .15)
        found = ENGINE.transcribe(audio[int(left * rate):int(right * rate)], mode, use_gpu, report,
                                  vad_filter=False, beam_size=5, without_timestamps=False, chunk_length=30)
        for w in found:
            if (w['no_speech'] > .6 and w['segment_logprob'] < -.8) or w['segment_logprob'] < -1.2 or w['probability'] < .3:
                continue
            start, end = left + w['start'], left + w['end']
            if a - .05 <= (start + end) / 2 <= b + .05:
                recovered.append(dict(w, start=round(start, 3), end=round(end, 3), recovered=True))
    existing = [(w['start'], spoken_end(w)) for w in words]
    merged = list(words) + [w for w in recovered
                            if not any(s <= (w['start'] + w['end']) / 2 <= e for s, e in existing)]
    return sorted(merged, key=lambda w: (w['start'], w['end'])), len(recovered)


def recognise(audio, identity, mode, use_gpu, spans, report):
    """Cached transcription of the assembled selection."""
    folder = ROOT / '.cache' / 'transcripts'
    key = hashlib.sha256(json.dumps([CACHE_VERSION, identity, mode]).encode()).hexdigest()
    target = folder / (key + '.json')
    try:
        record = json.loads(target.read_text(encoding='utf-8'))
        report('Oldingi tahlildan tanilgan matn olindi.')
        return record['words'], {'cache': True, 'device': record.get('device', ''), 'recovered': record.get('recovered', 0)}
    except (OSError, ValueError, KeyError):
        pass
    duration = len(audio) / 16000
    began = time.perf_counter()
    report('Nutq tanilmoqda: 0%')
    words = ENGINE.transcribe(audio, mode, use_gpu, report,
                              progress=lambda end: report('Nutq tanilmoqda: %d%% · %s' % (
                                  min(100, end / duration * 100), ENGINE.device.upper())))
    words, count = recover(audio, words, spans, mode, use_gpu, report)
    folder.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps({'words': words, 'device': ENGINE.device, 'recovered': count,
                                     'seconds': round(time.perf_counter() - began, 1)}, ensure_ascii=False),
                         encoding='utf-8')
    os.replace(temporary, target)
    return words, {'cache': False, 'device': ENGINE.device, 'recovered': count}
