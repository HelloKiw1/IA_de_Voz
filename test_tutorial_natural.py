"""Compare one male reference; optional spoken lead-in is an experiment, not training."""
import json
import random
import time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from tts import ChatterboxTTS

ROOT = Path(__file__).resolve().parent
TEXT = 'Agora, acesse o menu principal. Selecione a opção desejada e clique em salvar para concluir.'
PREFIX = 'Vamos começar.'
CASES = [
    ('tutorial_padrao', dict(exaggeration=.5, cfg_weight=.5, temperature=.8), False),
    ('tutorial_suave', dict(exaggeration=.4, cfg_weight=.35, temperature=.75), False),
    ('tutorial_com_abertura', dict(exaggeration=.4, cfg_weight=.35, temperature=.75), True),
]

def main():
    engine = ChatterboxTTS()
    print(f'Modelo PT-BR carregado. Device: {engine.device}; PyTorch: {torch.__version__}', flush=True)
    for name, parameters, lead_in in CASES:
        output = ROOT / 'outputs/audio' / (name + '.wav')
        metadata = output.with_suffix('.json')
        identity = dict(text=TEXT, prefix=PREFIX if lead_in else '', parameters=parameters, reference='tts/voices/eduardo/calmo.wav', seed=42)
        if output.exists() and metadata.exists() and json.loads(metadata.read_text(encoding='utf-8')).get('experiment') == identity:
            print(f'[OK] Reutilizando {name}', flush=True)
            continue
        random.seed(42); np.random.seed(42); torch.manual_seed(42)
        raw = ROOT / 'outputs/audio/experimento_tutorial' / (name + '_completo.wav')
        text = PREFIX + ' ' + TEXT if lead_in else TEXT
        def progress(stage, tokens):
            if stage != 'generating' or tokens % 100 == 0:
                print(f'{name}: {stage}, tokens={tokens}', flush=True)
        engine.generate(text, raw, voice='calmo', progress_callback=progress, **parameters)
        samples, rate = sf.read(raw, dtype='float32')
        cut = 0
        # Keep the spoken lead-in: no blind time cut can ensure removal without clipping words.
        # The full rendition lets the listener assess whether the following sentence improves.
        sf.write(output, samples, rate, subtype='PCM_16')
        assert samples.size and np.isfinite(samples).all() and np.any(samples)
        info = dict(text=text, voice='Eduardo Calmo · ' + name.removeprefix('tutorial_'),
                    duration_seconds=len(samples)/rate, sample_rate=rate, created=time.time(),
                    generation_seconds=engine.last_generation_seconds, experiment=identity,
                    lead_in_retained=lead_in, cut_seconds=cut, device=engine.device)
        metadata.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'[OK] {output.name}: {len(samples)/rate:.2f}s', flush=True)
    print('3/3 testes concluídos. A abertura permanece audível para avaliação.', flush=True)

if __name__ == '__main__':
    main()
