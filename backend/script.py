"""Word script -> parts of a TV report.

Narration (correspondent / diktor) and sync translations are voiced in the
recording. Standups, sounds, bumpers and captions are not: the timeline gets
an open gap there so the editor can drop in the interview or the picture.
"""
import re
import zipfile
import xml.etree.ElementTree as ET

from text import marked_tokens

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MC = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
BREAKS = {W + 'br', W + 'cr'}
# A message header pasted together with the text: "[19.11.2026 11:45] Name:".
CHAT_HEADER = re.compile(r'^\s*\[\d{1,2}[./]\d{1,2}[./]\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?\]\s*[^:]{0,60}:\s*')
# Credits ("Tasvirchi: J. Sultonov") and picture remarks ("Koson tumani kadrlari") are not read.
CREDIT = re.compile(r'^\s*(?:tasvirchi|montaj\w*|operator|rejiss[yo]+r|muharrir|muallif|оператор|монтаж\w*|режисс[её]р|'
                    r'редактор|тасвирчи|муҳаррир|муаллиф|автор)\s*[:\-–—]', re.I)
FOOTAGE = re.compile(r'(?:kadrlar\w*|tasvirlar\w*|кадры|кадрлар\w*|тасвирлар\w*)\s*[.:]?\s*$', re.I)
INITIAL = re.compile(r'(?:^|\s)[^\W\d_]\.\s*[^\W\d_]')
# Tracked deletions and moves, field codes, and the legacy copy of a text box are not script text.
SKIPPED = {W + 'del', W + 'delText', W + 'moveFrom', W + 'instrText', MC + 'Fallback'}
LABELS = [
    ('narration', r'(?:корреспондент|корр\.?|диктор|ведущий|ведущая|голос\s*за\s*кадром|за\s*кадром|закадр|зк|'
                  r'мухбир|muxbir|diktor|boshlovchi|бошловчи|кадр\s*ортидан|reporter|narrator|voice\s*over)'),
    ('sync', r'(?:снхр|снх|синхрон|синх|sinxron|sinxr|snxr|snx|sinx|интервью|интервю|интервьюер|интервиу|инт|'
             r'intervyu|interviyu|intervyuu|intervu|interview|int|суҳбат|сухбат|suhbat|sot)'),
    ('standup', r'(?:стендап|стенд-ап|стэндап|stendap|stend-ap|stand-?up)'),
    ('sound', r'(?:звук|лайф|зтм|интершум|шум|музыка|песня|овоз|мусиқа|musiqa|ovoz|zvuk|ztm|live|nat\s*sound)'),
    ('bumper', r'(?:отбивка|заставка|шпигель|рубрика|otbivka|zastavka|bumper)'),
    ('note', r'(?:визуал|кадр|видео|титр|графика|архив|vizual|kadr|video|titr|grafika|arxiv)'),
]
SPEAKABLE = {'narration', 'sync', 'standup'}
INSERT_KINDS = {'sound', 'bumper', 'title', 'caption'}
PLACE = re.compile(r'(?:област|район|город|г\.\s|посёл|посел|махалл|шаҳ|туман|вилоят|ҳудуд|viloyat|tuman|shahar|'
                   r'mahalla|qishlog|қишлоғ|республик|respublika)', re.I)
TIMECODE = re.compile(r'\d{1,2}:\d{2}')
NAMES = {'sync': 'СНХР', 'standup': 'Стендап', 'sound': 'Звук', 'bumper': 'Отбивка', 'title': 'Титр',
         'caption': 'Титр', 'narration': 'Матн'}
WORDS_PER_SECOND = 2.4


def paragraphs(path):
    name = str(path).lower()
    if name.endswith('.txt'):
        return text_paragraphs(path)
    if not name.endswith('.docx'):
        raise ValueError('Ssenariy .docx yoki .txt formatida bo‘lishi kerak (eski .doc ni Word’da .docx qilib saqlang).')
    try:
        with zipfile.ZipFile(path) as doc:
            root = ET.fromstring(doc.read('word/document.xml'))
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError):
        raise ValueError('Word fayli ochilmadi: ' + str(path))
    result = []
    _collect(root, None, result)
    lines = [line for parts in result for line in _lines(''.join(parts))]
    return [text for text in (re.sub(r'[\s ]+', ' ', CHAT_HEADER.sub('', line)).strip() for line in lines) if text]


def _lines(text):
    """Lines of one Word paragraph. A break in the middle of a sentence (the next line goes on in
    lower case) is only a wrapped line; any other break starts a new script line."""
    result = []
    for line in text.split('\n'):
        previous = result[-1].rstrip() if result else ''
        if previous and line.strip() and line.strip()[0].islower() and not re.search(r'[.!?…:;»"”)]$', previous):
            result[-1] = previous + ' ' + line
        else:
            result.append(line)
    return result


def text_paragraphs(path):
    """Plain text script: one paragraph per line (UTF-8, or the Windows Cyrillic code page)."""
    try:
        with open(path, 'rb') as source:
            data = source.read()
    except OSError:
        raise ValueError('Matn fayli ochilmadi: ' + str(path))
    for encoding in ('utf-8-sig', 'utf-16', 'cp1251'):
        try:
            if encoding == 'utf-16' and not data.startswith((b'\xff\xfe', b'\xfe\xff')):
                continue
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError('Matn fayli kodlanishi tanilmadi (UTF-8 qilib saqlang): ' + str(path))
    return [line for line in (re.sub(r'[\s ]+', ' ', CHAT_HEADER.sub('', raw)).strip() for raw in text.splitlines()) if line]


def _collect(node, parts, result):
    """Text runs of every paragraph, in document order. A text box paragraph is its own paragraph."""
    for child in node:
        if child.tag in SKIPPED:
            continue
        if child.tag == W + 'p':
            own = []
            result.append(own)
            _collect(child, own, result)
        elif parts is not None and child.tag == W + 't':
            parts.append(child.text or '')
        elif parts is not None and child.tag in BREAKS:
            parts.append('\n')  # Shift+Enter (text pasted from a messenger): the next line may be a label
        elif parts is not None and child.tag == W + 'tab':
            parts.append(' ')
        elif parts is not None and child.tag == W + 'noBreakHyphen':
            parts.append('-')  # "2024‑yil" typed with a non-breaking hyphen is still two words
        else:
            _collect(child, parts, result)


def label_of(text):
    for kind, pattern in LABELS:
        match = re.match(r'^\s*' + pattern + r'(?![\w-])', text, re.I)
        if not match:
            continue
        rest = text[match.end():]
        # "ВИЗУАЛ/КАДР: ..." — several label words, then the delimiter.
        delimiter = re.match(r'^(?:\s*/\s*[\w-]+)*(?:\s*\([^)]{0,80}\))?\s*[:\-–—−]+\s*', rest)
        rest = rest[delimiter.end():] if delimiter else rest
        # Ordinary sentences may begin with the same word ("Ovoz berish ..."). An interview or a stand-up is
        # often marked without any delimiter: "INT Aliyev Vali", "INTERVIYU ALIYEV VALI".
        short_line = not re.search(r'[.!?…]$', rest.strip())
        if delimiter or not rest.strip() or (kind not in SPEAKABLE and len(rest.split()) <= 6 and short_line) or                 (kind in ('sync', 'standup') and len(rest.split()) <= 8 and short_line):
            if kind == 'narration':
                # "ДИКТОР: БОШЛОВЧИ (камера олдида): ..." — a second label and a stage remark are not read.
                inner, inner_rest = label_of(rest)
                if inner == 'narration':
                    rest = inner_rest
                rest = re.sub(r'^\s*\([^)]{0,80}\)\s*[:\-–—−]*\s*', '', rest)
            return kind, rest.strip()
    return None, text


def classify(text, has_labels):
    """(kind, spoken text, label)."""
    if len(text.split()) <= 8 and not re.search(r'[.!?…]$', text.strip()) and (CREDIT.match(text) or FOOTAGE.search(text)):
        return 'note', '', text
    kind, rest = label_of(text)
    if kind == 'narration' and 0 < len(rest.split()) <= 4 and INITIAL.search(rest) and not re.search(r'[!?…]$', rest):
        return 'note', '', text   # "Muxbir: X. Shomurodov" — a credit, not narration
    if kind == 'sync':
        # "СНХР: Name – position (на узб.яз.)" names the speaker; the words follow.
        spoken = rest if len(rest.split()) > 25 and re.search(r'[.!?]\s', rest) else ''
        return kind, spoken, rest
    if kind in ('narration', 'standup'):
        return kind, re.sub(r'^[\-–—]\s*', '', rest), rest
    if kind:
        return kind, '', rest
    words = text.split()
    if TIMECODE.search(text) and len(words) <= 14:
        return 'heading', '', text
    if re.match(r'^\s*(?:\d+\s*-?\s*)?(?:акт|akt|қисм|qism|часть|блок|kirish|кириш|хулоса|xulosa|финал|final)\b',
                text, re.I) and len(words) <= 14:
        return 'heading', '', text
    if len(words) <= 6 and PLACE.search(text) and not re.search(r'[.!?]$', text):
        return 'caption', '', text
    if text.startswith(('«', '"', '“')) and text.rstrip().endswith(('»', '"', '”')) and len(words) <= 14:
        return 'title', '', text.strip('«»"“”„ ')
    if has_labels:
        return 'continue', re.sub(r'^[\-–—]\s*', '', text), ''
    return 'narration', text, ''


def parse_script(path):
    items = paragraphs(path)
    has_labels = any(label_of(p)[0] in SPEAKABLE for p in items)
    blocks, current = [], None
    for paragraph in items:
        kind, spoken, label = classify(paragraph, has_labels)
        if kind == 'continue':
            if current is None:
                blocks.append({'kind': 'header', 'text': '', 'label': paragraph})
                continue
            kind = current
        if kind in SPEAKABLE:
            if blocks and blocks[-1]['kind'] == kind == current and not label:
                blocks[-1]['text'] += '\n' + spoken
            else:
                blocks.append({'kind': kind, 'text': spoken, 'label': label})
            current = kind
        else:
            if not any(b['kind'] in SPEAKABLE for b in blocks):
                kind = 'header'  # programme title, date, topic
            blocks.append({'kind': kind, 'text': '', 'label': label or paragraph})
            if kind == 'note' and has_labels:
                current = None
    for block in blocks:
        block['source'] = str(path)
    return blocks


def tokenize(blocks, language):
    """Script tokens with punctuation marks and the block each token belongs to."""
    script, marks, owner = [], [], []
    for index, block in enumerate(blocks):
        block['start_token'] = len(script)
        items = marked_tokens(block['text'], language) if block['kind'] in SPEAKABLE and block['text'].strip() else []
        for token, mark in items:
            script.append(token)
            marks.append(mark)
            owner.append(index)
        block['tokens'] = len(items)
    return script, marks, owner


def short(text, size=70):
    text = re.sub(r'\s+', ' ', text or '').strip()
    return text if len(text) <= size else text[:size - 1].rstrip() + '…'


def describe(block):
    detail = block.get('label') or block.get('text') or ''
    if block['kind'] in ('caption', 'title'):
        return short(detail)
    name = NAMES.get(block['kind'], block['kind'])
    return short(name + (': ' + detail if detail else ''))


def estimate_seconds(block):
    if block['kind'] in SPEAKABLE:
        return min(90., max(3., round(len(block['text'].split()) / WORDS_PER_SECOND + 1.)))
    return {'sound': 5., 'bumper': 3., 'title': 3., 'caption': 0.}.get(block['kind'], 0.)
