import base64
import gzip
import io
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

import helpers  # noqa: F401  (adds the backend to the path)
import titles


def value(text):
    body = json.dumps({'mTextParam': {'mAlignment': 2, 'mStyleSheet': {
        'mFontName': {'mParamValues': [[0, 'MyriadPro-Regular']]}, 'mFontSize': {'mParamValues': [[0, 100]]},
        'mText': text}}, 'mVersion': 1}).encode('utf-16-le')
    return base64.b64encode(struct.pack('<II', len(body), 0) + body).decode()


def template(folder, name='Basic Title.mogrt', author='ppro'):
    xml = ('<PremiereData><StartKeyframeValue Encoding="base64" BinaryHash="aa-00000010">AAAAAA==</StartKeyframeValue>'
           '<Component><InstanceName>Your Title Here</InstanceName>\n<Bypass>false</Bypass>\n<Intrinsic>false</Intrinsic>\n</Component>\n'
           '<PremiereFilterPrivateData Encoding="base64" BinaryHash="x">AA==\n</PremiereFilterPrivateData>\n<MatchName>AE.ADBE Text</MatchName>'
           '<Name>Исходный текст</Name><StartKeyframeValue Encoding="base64" BinaryHash="old-00000850">%s\n</StartKeyframeValue>'
           '</PremiereData>' % value('Your Title Here'))
    graphic = io.BytesIO()
    with zipfile.ZipFile(graphic, 'w') as z:
        z.writestr('Delivery.prproj', gzip.compress(xml.encode()))
    path = Path(folder) / name
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('definition.json', json.dumps({'authorApp': author, 'capsuleID': 'old', 'clientControls': [
            {'type': 6, 'value': {'strDB': [{'localeString': 'en_US', 'str': 'Your Title Here'}]}}]}))
        z.writestr('project.prgraphic', graphic.getvalue())
        z.writestr('thumb.png', b'png')
    return str(path)


def text_of(path):
    z = zipfile.ZipFile(path)
    inner = zipfile.ZipFile(io.BytesIO(z.read('project.prgraphic')))
    xml = gzip.decompress(inner.read('Delivery.prproj')).decode()
    for found in titles.VALUE.finditer(xml):
        raw = base64.b64decode(found.group(4))
        if titles.MARK in raw:
            size, zero = struct.unpack('<II', raw[:8])
            assert size == len(raw) - 8 and zero == 0
            assert found.group(2).endswith('%08x' % (len(raw) + 12)), found.group(2)
            return json.loads(raw[8:].decode('utf-16-le'))['mTextParam']['mStyleSheet'], xml, json.loads(z.read('definition.json'))
    raise AssertionError('no text value')


class TitleTemplateTests(unittest.TestCase):
    def test_text_is_written_into_a_copy_of_the_template(self):
        with tempfile.TemporaryDirectory() as folder:
            source = template(folder)
            label = 'Звук: песни и дутара + СНХР: Санжар бахши Чубаев (на узб.яз.) — tarjima ovozi keyin'
            made = titles.make_all(source, [label, 'СНХР: Ali', label, ''], Path(folder) / 'out')
            self.assertEqual(sorted(made), sorted([label, 'СНХР: Ali']))
            sheet, xml, definition = text_of(made[label])
            self.assertEqual(sheet['mText'], 'Звук: песни и дутара\rСНХР: Санжар бахши Чубаев (на узб.яз.)\r— tarjima ovozi keyin')
            self.assertEqual(sheet['mFontSize']['mParamValues'], [[0, 54]])
            self.assertIn('<InstanceName>Звук: песни и дутара СНХР', xml)
            self.assertIn('AAAAAA==', xml)                                     # other values are left alone
            self.assertEqual(definition['clientControls'][0]['value']['strDB'][0]['str'], sheet['mText'])
            other = text_of(made['СНХР: Ali'])
            self.assertEqual(other[0]['mText'], 'СНХР: Ali')
            self.assertNotEqual(other[2]['capsuleID'], definition['capsuleID'])  # each title is its own template
            self.assertNotEqual(definition['capsuleID'], 'old')
            self.assertEqual(titles.make(source, label, Path(folder) / 'out').replace('\\', '/'), made[label])   # reused
            self.assertEqual(zipfile.ZipFile(made[label]).read('thumb.png'), b'png')

    def test_a_template_of_another_kind_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                titles.make(template(folder, 'ae.mogrt', 'aefx'), 'СНХР: Ali', folder)


if __name__ == '__main__':
    unittest.main()
