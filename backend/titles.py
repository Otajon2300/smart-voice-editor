"""Editable titles: a copy of Premiere's own "Basic Title" template with the text already written into it.

Premiere cannot reliably change the text of its own graphics from a script, so the text is put into the
template file itself (the JSON of the Source Text parameter) before Premiere imports it.
"""
import base64
import gzip
import hashlib
import io
import json
import re
import struct
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

VALUE = re.compile(r'(<StartKeyframeValue Encoding="base64" BinaryHash=")([^"]*)(">)([^<]*)(</StartKeyframeValue>)')
MARK = '"mTextParam"'.encode('utf-16-le')
NAME = re.compile(r'(<InstanceName>)([^<]*)(</InstanceName>\s*<Bypass>[^<]*</Bypass>\s*<Intrinsic>[^<]*</Intrinsic>\s*</Component>'
                  r'\s*<PremiereFilterPrivateData[^>]*>[^<]*</PremiereFilterPrivateData>\s*<MatchName>AE\.ADBE Text</MatchName>)')
FONT = 'ArialMT'          # has Cyrillic and the Uzbek letters on every Windows and macOS
WRAP = 38


def wrap(label, width=WRAP):
    lines = []
    for part in str(label).split(' + '):
        line = ''
        for word in part.split():
            if line and len(line) + 1 + len(word) > width:
                lines.append(line)
                line = word
            else:
                line = (line + ' ' + word).strip()
        if line:
            lines.append(line)
    return '\r'.join(lines[:7])


def binary_hash(data):
    """Premiere's attribute: a content hash whose last field is the size of the value plus twelve."""
    h = hashlib.md5(data).hexdigest()
    return '%s-%s-%s-%s-%s%08x' % (h[:8], h[8:12], h[12:16], h[16:20], h[20:24], len(data) + 12)


def rewrite_project(xml, text, size):
    # The parameter's name is translated in the localised copies; its value is recognised by content.
    found = raw = None
    for candidate in VALUE.finditer(xml):
        data = base64.b64decode(candidate.group(4))
        if MARK in data[:200]:
            found, raw = candidate, data
            break
    if not found:
        raise ValueError('Shablonda matn qatlami topilmadi.')
    value = json.loads(raw[8:].decode('utf-16-le'))
    sheet = value['mTextParam']['mStyleSheet']
    sheet['mText'] = text
    sheet['mFontSize']['mParamValues'] = [[0, size]]
    sheet['mFontName']['mParamValues'] = [[0, FONT]]
    body = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-16-le')
    data = struct.pack('<II', len(body), 0) + body
    xml = xml[:found.start()] + found.group(1) + binary_hash(data) + found.group(3) + \
        base64.b64encode(data).decode('ascii') + '\n\t\t' + found.group(5) + xml[found.end():]
    return NAME.sub(lambda m: m.group(1) + escape(text.replace('\r', ' ')[:80]) + m.group(3), xml, count=1)


def rewrite_graphic(data, text, size):
    """project*.prgraphic is a zip with one gzipped Premiere project."""
    source, out = zipfile.ZipFile(io.BytesIO(data)), io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename.lower().endswith('.prproj'):
                packed = content[:2] == b'\x1f\x8b'
                xml = (gzip.decompress(content) if packed else content).decode('utf-8')
                xml = rewrite_project(xml, text, size).encode('utf-8')
                content = gzip.compress(xml, mtime=0) if packed else xml
            target.writestr(item.filename, content)
    return out.getvalue()


def make(template, label, folder, size=54):
    """Write `<folder>/titr-<hash>.mogrt` with `label` as its text; returns the path."""
    text = wrap(label)
    key = hashlib.sha256(('v1|%s|%s|%d' % (Path(template).stat().st_size, text, size)).encode()).hexdigest()
    target = Path(folder) / ('titr-%s.mogrt' % key[:16])
    if target.exists() and zipfile.is_zipfile(target):
        return str(target)
    source = zipfile.ZipFile(template)
    definition = json.loads(source.read('definition.json').decode('utf-8-sig'))
    if definition.get('authorApp') != 'ppro':
        raise ValueError('Shablon Premiere grafikasi emas.')
    definition['capsuleID'] = str(uuid.UUID(key[:32]))          # its own identity: Premiere caches by this id
    for control in definition.get('clientControls') or []:
        if control.get('type') == 6:
            for entry in (control.get('value') or {}).get('strDB') or []:
                entry['str'] = text
    Path(folder).mkdir(parents=True, exist_ok=True)
    out = io.BytesIO()                                          # built in memory: the file appears complete or not at all
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for item in source.infolist():
            name = item.filename
            if name == 'definition.json':
                archive.writestr(name, json.dumps(definition, ensure_ascii=False).encode('utf-8'))
            elif name.endswith('.prgraphic'):
                archive.writestr(name, rewrite_graphic(source.read(name), text, size))
            else:
                archive.writestr(name, source.read(name))
    target.write_bytes(out.getvalue())
    return str(target)


def make_all(template, labels, folder):
    result = {}
    for label in labels:
        if label and label not in result:
            result[label] = make(template, label, folder).replace('\\', '/')
    return result
