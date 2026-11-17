"""Local HTTP backend for the Premiere panel (127.0.0.1, random port, bearer token).

Exits by itself after IDLE_MINUTES without requests so the speech model does
not stay in memory after Premiere is closed.
"""
import json
import os
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
# numpy/scipy's Intel Fortran runtime aborts the process when the console window closes
# ("forrtl: error (200)"), skipping cleanup and leaving a stale .runtime.json. Must be set before numpy loads.
os.environ.setdefault('FOR_DISABLE_CONSOLE_CTRL_HANDLER', '1')

# The panel redirects output to backend.log; the Windows code page there (cp1252) cannot hold every
# character of a message or a file name, and a failed print would abort the analysis.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass  # pythonw without redirection has no streams

VERSION = '1.1.7'
ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime.json'
IDLE_MINUTES = 30
TOKEN = secrets.token_urlsafe(32)
BUSY = threading.Lock()
LAST_REQUEST = [time.monotonic()]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def authorized(self):
        if self.headers.get('Authorization') != 'Bearer ' + TOKEN:
            self.send_error(403)
            return False
        LAST_REQUEST[0] = time.monotonic()
        return True

    def reply(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def emit(self, event):
        self.wfile.write((json.dumps(event, ensure_ascii=False) + '\n').encode('utf-8'))
        self.wfile.flush()

    def do_GET(self):
        if self.path != '/health' or not self.authorized():
            if self.path != '/health':
                self.send_error(404)
            return
        self.reply(200, {'ok': True, 'version': VERSION, 'pid': os.getpid(), 'busy': BUSY.locked()})

    def do_POST(self):
        if not self.authorized():
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size < 5_000_000:
                raise ValueError('So‘rov hajmi noto‘g‘ri.')
            body = json.loads(self.rfile.read(size))
        except ValueError as error:
            return self.reply(400, {'error': str(error)})
        if self.path == '/shutdown':
            self.reply(200, {'ok': True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path == '/plan':
            import service
            try:
                return self.reply(200, service.plan(body))
            except Exception as error:
                return self.reply(400, {'error': message(error)})
        if self.path == '/titles':
            import titles
            try:
                return self.reply(200, {'files': titles.make_all(str(body.get('template') or ''), body.get('labels') or [],
                                                                 ROOT / '.cache' / 'titles')})
            except Exception as error:
                return self.reply(400, {'error': message(error)})
        if self.path != '/analyze':
            return self.reply(404, {'error': 'Noma’lum amal.'})
        # Analysis streams progress lines (NDJSON) and ends with the result or an error.
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson; charset=utf-8')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        if not BUSY.acquire(blocking=False):
            return self.safe_emit({'error': 'Boshqa tahlil davom etmoqda. Uning tugashini kuting.'})
        try:
            import service

            def progress(text):
                print(text, flush=True)
                LAST_REQUEST[0] = time.monotonic()
                self.emit({'progress': text})
            self.safe_emit({'result': service.analyze(body, progress)})
        except ConnectionError:   # panel closed mid-analysis; on Windows this is ConnectionAbortedError
            pass
        except Exception as error:
            import traceback
            traceback.print_exc()
            self.safe_emit({'error': message(error)})
        finally:
            BUSY.release()

    def safe_emit(self, event):
        try:
            self.emit(event)
        except ConnectionError:
            pass


def message(error):
    if isinstance(error, (ValueError, FileNotFoundError)):
        return str(error)
    return type(error).__name__ + ': ' + str(error)


def watch_idle(server):
    while True:
        time.sleep(30)
        if not BUSY.locked() and time.monotonic() - LAST_REQUEST[0] > IDLE_MINUTES * 60:
            print('Uzoq vaqt ishlatilmadi — backend yopilmoqda.', flush=True)
            server.shutdown()
            return


def main():
    from filelock import FileLock, Timeout
    lock = FileLock(str(ROOT / '.backend.lock'))
    try:
        lock.acquire(timeout=0)
    except Timeout:
        print('Smart Voice backend allaqachon ishlayapti.', flush=True)
        return
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    # Written whole, then renamed: the panel polls this file while the backend starts.
    runtime = json.dumps({'port': server.server_port, 'token': TOKEN, 'pid': os.getpid(), 'version': VERSION})
    draft = RUNTIME.with_suffix('.json.%d' % os.getpid())
    try:
        draft.write_text(runtime, encoding='utf-8')
        os.replace(draft, RUNTIME)
    except OSError:
        # A stale file left by another Windows account can be overwritten but not replaced.
        RUNTIME.write_text(runtime, encoding='utf-8')
        try:
            draft.unlink()
        except OSError:
            pass
    threading.Thread(target=watch_idle, args=(server,), daemon=True).start()
    print('Smart Voice backend %s tayyor: %d' % (VERSION, server.server_port), flush=True)
    try:
        server.serve_forever()
    finally:
        try:
            if json.loads(RUNTIME.read_text(encoding='utf-8')).get('pid') == os.getpid():
                RUNTIME.unlink()
        except (OSError, ValueError):
            pass
        lock.release()


if __name__ == '__main__':
    main()
