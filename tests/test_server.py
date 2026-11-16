import json
import shutil
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from helpers import Recording, clip_for
from audio import write_wav
import server
import service


def recording_file(folder):
    rec = Recording(7)
    rec.room(.4)
    rec.say('bir ikki uch')
    rec.room(3.)
    rec.say('tort besh')
    rec.room(.4)
    path = Path(tempfile.mkdtemp(dir=folder)) / 'voice.wav'
    write_wav(path, rec.audio)
    clip = clip_for(len(rec.audio) / 16000)
    clip['path'] = clip['pieces'][0]['path'] = str(path)
    return clip


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Previews go to a temporary folder, not to the project's .cache.
        cls.folder = tempfile.mkdtemp()
        cls.preview, service.PREVIEW = service.PREVIEW, Path(cls.folder) / 'preview'
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = 'http://127.0.0.1:%d' % cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        service.PREVIEW = cls.preview
        service.SESSIONS.clear()
        shutil.rmtree(cls.folder, ignore_errors=True)

    def call(self, path, body=None, token=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data,
                                         headers={'Authorization': 'Bearer ' + (token or server.TOKEN),
                                                  'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read().decode('utf-8')

    def test_health_needs_token(self):
        self.assertEqual(json.loads(self.call('/health'))['version'], server.VERSION)
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/health', token='wrong')

    def test_pause_only_analysis_and_replan(self):
        lines = [json.loads(line) for line in self.call('/analyze', {'clip': recording_file(self.folder), 'pause_only': True}).splitlines()]
        self.assertTrue(any('progress' in line for line in lines))
        result = lines[-1].get('result')
        self.assertIsNotNone(result, lines[-1])
        self.assertTrue(Path(result['plan']['preview']).exists())
        self.assertEqual(Path(result['plan']['preview']).parent, service.PREVIEW.resolve())
        self.assertEqual(Path(result['original_preview']).parent, service.PREVIEW.resolve())
        removed = result['plan']['stats']['removed_seconds']
        self.assertGreater(removed, 1.5)
        pause = max((j for j in result['plan']['junctions'] if j['kind'] == 'pause'), key=lambda j: j['end'] - j['start'])
        again = json.loads(self.call('/plan', {'session': result['session'], 'decisions': {pause['id']: False}}))
        self.assertLess(again['stats']['removed_seconds'], removed - 1)
        # With crossfades the result has the same cuts and length, but another sound at the joins.
        faded = json.loads(self.call('/plan', {'session': result['session'], 'render': True, 'options': {'crossfade': True}}))
        self.assertEqual(faded['ranges'], result['plan']['ranges'])
        self.assertNotEqual(faded['preview'], result['plan']['preview'])
        plain, mixed = Path(result['plan']['preview']).read_bytes(), Path(faded['preview']).read_bytes()
        self.assertEqual(len(plain), len(mixed))
        self.assertNotEqual(plain, mixed)

    def test_unknown_session(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.call('/plan', {'session': 'nope'})
        self.assertIn('Qayta tahlil', caught.exception.read().decode('utf-8'))

    def test_missing_script(self):
        lines = self.call('/analyze', {'clip': recording_file(self.folder)}).splitlines()
        self.assertIn('ssenariy', json.loads(lines[-1])['error'])


if __name__ == '__main__':
    unittest.main()
