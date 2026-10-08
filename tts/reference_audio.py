"""Non-destructive reference measurements (silence threshold: -45 dBFS)."""
from pathlib import Path
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
VOICE_PROFILES = {name: f"tts/voices/eduardo/{name}.wav" for name in ("neutro", "calmo", "animado")}


def measure(samples, rate):
    samples = np.asarray(samples)
    if samples.ndim == 1:
        samples = samples[:, None]
    if not samples.size or not np.isfinite(samples).all():
        raise ValueError("Áudio vazio ou com amostras inválidas")
    peak = float(np.abs(samples).max())
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    window = max(1, int(rate * .02))
    energy = np.array([np.sqrt(np.mean(samples[i:i+window].astype(np.float64)**2)) for i in range(0, len(samples), window)])
    active = np.flatnonzero(energy > 10 ** (-45/20))
    db = lambda x: float(20*np.log10(max(x, 1e-12)))
    return dict(duration_seconds=len(samples)/rate, sample_rate=rate, channels=samples.shape[1],
                peak_dbfs=db(peak), rms_dbfs=db(rms), clipping_samples=int(np.sum(np.abs(samples) >= 1-1/32768)),
                initial_silence_seconds=float(active[0]*window/rate) if active.size else len(samples)/rate,
                final_silence_seconds=max(0., (len(samples)-(active[-1]+1)*window)/rate) if active.size else len(samples)/rate,
                silent_windows_percent=float(np.mean(energy <= 10**(-45/20))*100))


def validate_reference_audio(path, profile=None, *, show=True):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    samples, rate = sf.read(path, always_2d=True)
    report = measure(samples, rate)
    info = sf.info(path)
    report.update(file=path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
                  bytes=path.stat().st_size, format=info.format, subtype=info.subtype)
    report['status'] = 'OK' if report['duration_seconds'] >= 1 and report['rms_dbfs'] > -60 and not report['clipping_samples'] else 'ATENÇÃO'
    if show:
        print(f"\n=== Referência de voz ===\nPerfil: {profile or path.stem}\nArquivo: {report['file']}\n"
              f"Duração: {report['duration_seconds']:.2f} segundos\nSample rate: {rate} Hz\n"
              f"Canais: {report['channels']}\nPico: {report['peak_dbfs']:.2f} dBFS\nRMS: {report['rms_dbfs']:.2f} dBFS\n"
              f"Clipping: {'Sim' if report['clipping_samples'] else 'Não'}\nStatus: {report['status']}", flush=True)
    return report
