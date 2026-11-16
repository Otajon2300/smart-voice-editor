"""Downloads speech models ahead of the first analysis (used by the online installer).
    python -s tools/fetch_models.py uz ru
uz: Kotib Medium (Uzbek, 3.06 GB, SHA256 checked); ru: Whisper Medium (Russian and English, 1.5 GB)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
import asr  # noqa: E402


def say(text):
    print(text, flush=True)


def hub(mode):
    spec = asr.MODELS[mode]
    cache, offline = asr.hub_location(spec['path'], spec['revision'])
    if offline:
        say(spec['name'] + ': allaqachon bor.')
        return
    say(spec['name'] + ' yuklanmoqda (~1.5 GB)…')
    from faster_whisper.utils import download_model
    download_model(spec['path'], cache_dir=cache, revision=spec['revision'])
    say(spec['name'] + ': tayyor.')


def main(wanted):
    if 'uz' in wanted:
        asr.kotib_path(say)
        say('O‘zbekcha model: tayyor.')
    if 'ru' in wanted or 'en' in wanted:
        hub('russian')


if __name__ == '__main__':
    try:
        main(set(sys.argv[1:]))
    except Exception as error:
        say('XATO: ' + str(error))
        sys.exit(1)
