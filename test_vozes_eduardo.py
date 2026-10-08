"""Real three-profile generation, identical text, seeds and library defaults."""
import hashlib
import importlib.metadata
import inspect
import json
import random
import time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from tts import ChatterboxTTS, VOICE_PROFILES, validate_reference_audio
from tts.chatterbox_tts import ROOT, MODEL_ID, OfficialChatterboxTTS

TEXT = "Olá. Neste tutorial, vamos aprender como utilizar algumas das principais funções do sistema. Primeiro, acesse o menu principal. Em seguida, selecione a opção desejada. Durante o processo, observe atentamente as informações exibidas na tela. Ao finalizar as alterações, clique em salvar para concluir a operação."
# Identical sentence boundaries keep each request below the 1000 speech-token cap.
CHUNKS = ["Olá. Neste tutorial, vamos aprender como utilizar algumas das principais funções do sistema.",
          "Primeiro, acesse o menu principal. Em seguida, selecione a opção desejada.",
          "Durante o processo, observe atentamente as informações exibidas na tela.",
          "Ao finalizar as alterações, clique em salvar para concluir a operação."]
assert ' '.join(CHUNKS) == TEXT


def main():
    print('================================\nIA_Voz - Chatterbox PT-BR\n================================', flush=True)
    environment = dict(torch=torch.__version__, chatterbox=importlib.metadata.version('ia-voz-chatterbox-ptbr'),
                       model=MODEL_ID, device='cuda' if torch.cuda.is_available() else 'cpu',
                       gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'Sem GPU CUDA',
                       api=str(inspect.signature(OfficialChatterboxTTS.generate)))
    print(json.dumps(environment, ensure_ascii=False, indent=2), flush=True)
    references = {voice:validate_reference_audio(path, voice) for voice,path in VOICE_PROFILES.items()}
    engine = ChatterboxTTS()
    print(f'[OK] Modelo carregado em {engine.load_seconds:.1f}s', flush=True)
    reports = []
    for voice in VOICE_PROFILES:
        print(f'\nGerando {voice.upper()}...', flush=True)
        parts = []
        metadata = []
        for index, chunk in enumerate(CHUNKS):
            cache = ROOT/f'outputs/audio/eduardo_parts/{voice}_{index+1}.wav'
            cache.parent.mkdir(parents=True, exist_ok=True)
            ref_hash = hashlib.sha256((ROOT/VOICE_PROFILES[voice]).read_bytes()).hexdigest()
            identity = dict(text=chunk, seed=42+index, reference_sha256=ref_hash, model=MODEL_ID,
                            defaults=dict(exaggeration=.5, cfg_weight=.5, temperature=.8))
            sidecar = cache.with_suffix('.json')
            if cache.exists() and sidecar.exists() and json.loads(sidecar.read_text(encoding='utf-8')).get('identity') == identity:
                report = json.loads(sidecar.read_text(encoding='utf-8'))
                print(f'Reutilizando parte validada {index+1}', flush=True)
            else:
                random.seed(42+index)
                np.random.seed(42+index)
                torch.manual_seed(42+index)
                count = [0]
                def progress(stage, tokens):
                    count[0] = tokens
                    if stage == 'reference' or stage == 'decoding' or (tokens and tokens % 100 == 0):
                        print(f'{voice} parte {index+1}/{len(CHUNKS)}: {stage}, tokens={tokens}', flush=True)
                engine.generate(chunk, cache, voice=voice, progress_callback=progress)
                if count[0] >= 1000:
                    raise RuntimeError('Limite de tokens atingido; reduzir trecho antes de continuar')
                report = dict(identity=identity, tokens=count[0], generation_seconds=engine.last_generation_seconds)
                sidecar.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            samples, rate = sf.read(cache, dtype='float32')
            assert rate == engine.sample_rate and samples.size and np.isfinite(samples).all() and np.any(samples)
            parts.append(samples)
            metadata.append(report)
        output = ROOT/f'outputs/audio/teste_{voice}.wav'
        pause = np.zeros(int(engine.sample_rate*.25), dtype='float32')
        samples = np.concatenate([x for i,p in enumerate(parts) for x in ((pause,p) if i else (p,))])
        sf.write(output, samples, engine.sample_rate, subtype='PCM_16')
        validation = validate_reference_audio(output, voice, show=False)
        assert validation['bytes'] > 44 and validation['duration_seconds'] > 0
        report = dict(voice=voice, text=TEXT, reference=references[voice], output=validation, parts=metadata)
        output.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        reports.append(report)
        print(f"[OK] {output.relative_to(ROOT)} ({validation['duration_seconds']:.2f}s)", flush=True)
    (ROOT/'outputs/audio/testes_eduardo.json').write_text(json.dumps(dict(environment=environment, results=reports), ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n3/3 áudios gerados com sucesso.', flush=True)


if __name__ == '__main__':
    main()
