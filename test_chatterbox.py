"""Real end-to-end smoke test; includes model loading and WAV validation."""
import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from tts.chatterbox_tts import ChatterboxTTS, MODEL_ID

TEXT = "Olá! Este é um teste do Chatterbox em português brasileiro dentro do projeto IA Voz. Se você está ouvindo esta mensagem, a instalação foi concluída com sucesso."


def main():
    print(f"PyTorch: {torch.__version__}; CUDA: {torch.cuda.is_available()}", flush=True)
    print("Carregando modelo oficial PT-BR V3...", flush=True)
    started = time.perf_counter()
    tts = ChatterboxTTS()
    print(f"Modelo carregado em {tts.device}; gerando áudio...", flush=True)
    torch.manual_seed(42)
    output = tts.generate(TEXT, Path(__file__).resolve().parent / "outputs/audio/teste_chatterbox.wav")
    samples, rate = sf.read(output)
    assert output.stat().st_size > 44 and samples.size > 0
    assert np.isfinite(samples).all() and np.any(samples)
    report = {"chatterbox": "OK", "torch": torch.__version__, "device": tts.device,
              "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
              "model": MODEL_ID, "output": str(output), "bytes": output.stat().st_size,
              "duration_seconds": len(samples) / rate, "sample_rate": rate,
              "generation_seconds": tts.last_generation_seconds,
              "load_seconds": tts.load_seconds, "total_seconds": time.perf_counter() - started}
    output.with_suffix(".json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
