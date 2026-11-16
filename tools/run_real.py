r"""Full analysis of a real recording against Word scripts, without Premiere.

    .venv\Scripts\python.exe tools\run_real.py --audio ovoz.wav --script s1.docx [--script s2.docx] --out evaluation\real\nom

Writes result.json (proposals, junctions, stats) and result.wav (what Premiere would hold).
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audio', required=True)
    parser.add_argument('--script', action='append', default=[])
    parser.add_argument('--out', required=True)
    parser.add_argument('--cpu', action='store_true')
    parser.add_argument('--pause-only', action='store_true')
    parser.add_argument('--mode', default=None)
    args = parser.parse_args()
    from faster_whisper.audio import decode_audio
    import service
    audio = Path(args.audio).resolve()
    duration = len(decode_audio(str(audio), sampling_rate=16000)) / 16000
    clip = {'path': str(audio), 'start': 0., 'inPoint': 0., 'outPoint': duration, 'frame': .04,
            'pieces': [{'start': 0., 'end': duration, 'inPoint': 0., 'outPoint': duration, 'path': str(audio)}]}
    body = {'clip': clip, 'scripts': [str(Path(s).resolve()) for s in args.script], 'use_gpu': not args.cpu,
            'pause_only': args.pause_only, 'mode': args.mode}
    result = service.analyze(body, lambda text: print(text, flush=True))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(result['plan']['preview'], out / 'result.wav')
    (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    print('Natija:', result['plan']['stats'], 'moslik', result.get('coverage'), 'vaqt', result['elapsed_seconds'], 's')
    for item in result['items']:
        print('  %-9s %-5s %8.2f-%8.2f %s | %s' % (item['kind'], item['selected'], item['start'], item['end'],
                                                  item['text'][:50], item['reason']))
    print('Saqlandi:', out)


if __name__ == '__main__':
    main()
