"""Read-only source audit. No source recordings are altered or copied."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tts.reference_audio import measure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    reports = []
    decoded = {}
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for path in sorted(args.source.iterdir()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        base = dict(name=path.name, bytes=path.stat().st_size, sha256=digest)
        if path.suffix.lower() not in ('.wav', '.m4a'):
            reports.append(base)
            continue
        probe = subprocess.run([ffmpeg, '-hide_banner', '-i', str(path)], capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
        audio_line = next(line for line in probe.splitlines() if 'Audio:' in line)
        rate = int(re.search(r'(\d+) Hz', audio_line)[1])
        channels = 1 if 'mono' in audio_line else 2 if 'stereo' in audio_line else None
        if channels is None:
            raise ValueError(audio_line)
        raw = subprocess.run([ffmpeg, '-v', 'error', '-i', str(path), '-f', 'f32le', '-acodec', 'pcm_f32le', '-'], capture_output=True, check=True).stdout
        samples = np.frombuffer(raw, dtype='<f4').reshape(-1, channels)
        base.update(measure(samples, rate), codec=audio_line.strip(), format=path.suffix[1:])
        if path.suffix.lower() == '.wav':
            base['subtype'] = sf.info(path).subtype
        decoded[path.stem] = (samples, rate)
        reports.append(base)
    comparisons = []
    for profile in ('neutro', 'calmo', 'animado'):
        orig = next(r for r in reports if f'({profile})' in r['name'] and r.get('format') == 'm4a')
        treated = next(r for r in reports if f'({profile})' in r['name'] and r.get('format') == 'wav')
        a, ar = decoded[Path(orig['name']).stem]
        b, br = decoded[Path(treated['name']).stem]
        from scipy.signal import resample_poly, correlate, correlation_lags
        from math import gcd
        target = 8000
        def down(x, rate):
            divisor = gcd(rate, target)
            return resample_poly(x.mean(axis=1), target//divisor, rate//divisor)
        a, b = down(a, ar), down(b, br)
        corr = correlate(b, a, mode='full', method='fft')
        lag = int(correlation_lags(len(b), len(a))[np.argmax(corr)])
        start_a, start_b = max(0, -lag), max(0, lag)
        n = min(len(a)-start_a, len(b)-start_b)
        a, b = a[start_a:start_a+n], b[start_b:start_b+n]
        gain = float(np.dot(a,b)/max(np.dot(a,a), 1e-12))
        residual = float(np.sqrt(np.mean((b-gain*a)**2))/max(np.sqrt(np.mean(b*b)), 1e-12))
        comparisons.append(dict(profile=profile, original=orig['name'], treated=treated['name'],
                                alignment_seconds=lag/target, correlation=float(np.corrcoef(a,b)[0,1]),
                                gain_db=float(20*np.log10(max(abs(gain),1e-12))), relative_residual_rms=residual))
    destination = ROOT/'docs/voices/eduardo'
    destination.mkdir(parents=True, exist_ok=True)
    report = dict(files=reports, comparisons=comparisons, silence_threshold_dbfs=-45,
                  limitations='Métricas não substituem escuta; clipping AAC é aproximado e pode incluir overshoot do codec.')
    (destination/'source_analysis.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
