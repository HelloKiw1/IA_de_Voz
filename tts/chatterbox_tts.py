"""Local Brazilian Portuguese V3 synthesis, with optional reference voice."""
import os
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Keep downloaded assets inside this project; do not change global configuration.
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf_cache"))
os.environ.setdefault("NUMBA_CACHE_DIR", str(ROOT / "models" / "numba_cache"))

import numpy as np
import soundfile as sf
import torch
from huggingface_hub import hf_hub_download, model_info
from chatterbox.tts import ChatterboxTTS as OfficialChatterboxTTS
from .reference_audio import VOICE_PROFILES, validate_reference_audio

MODEL_ID = "ResembleAI/Chatterbox-Multilingual-pt-br"
BASE_ID = "ResembleAI/chatterbox"
REFERENCE_URL = "https://storage.googleapis.com/chatterbox-demo-samples/mtl-v3-single-language-prompts/pt-br/pt_br_f2.wav"


def prepare_assets():
    """Download once, pin revisions in a manifest, and reuse local files offline."""
    import json
    import urllib.request

    directory = ROOT / "models" / "pt-br-v3"
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "provenance.json"
    revisions = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {
        MODEL_ID: model_info(MODEL_ID).sha,
        BASE_ID: model_info(BASE_ID).sha,
    }
    manifest.write_text(json.dumps(revisions, indent=2), encoding="utf-8")
    for repo, filenames in ((MODEL_ID, ["t3_pt_br.safetensors", "s3gen_v3.pt", "grapheme_mtl_merged_expanded_v1.json"]), (BASE_ID, ["ve.pt"])):
        for filename in filenames:
            if not (directory / filename).is_file():
                hf_hub_download(repo, filename, revision=revisions[repo], local_dir=directory)
    reference = ROOT / "tts" / "voices" / "pt_br_f2.wav"
    reference.parent.mkdir(parents=True, exist_ok=True)
    if not reference.exists():
        temporary = reference.with_suffix(".download")
        with urllib.request.urlopen(REFERENCE_URL, timeout=120) as response, temporary.open("wb") as output:
            import shutil
            shutil.copyfileobj(response, output)
        temporary.replace(reference)
    return directory, reference


class ChatterboxTTS:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if self.device == "cpu":
            torch.set_num_threads(min(4, os.cpu_count() or 1))
        self._lock = threading.Lock()
        started = time.perf_counter()
        directory, _ = prepare_assets()
        self.default_reference = ROOT / VOICE_PROFILES["neutro"]
        self.model = OfficialChatterboxTTS.from_local(directory, self.device)
        self.sample_rate = self.model.sr
        self.load_seconds = time.perf_counter() - started
        self.last_generation_seconds = None

    def generate(self, text, output_path, reference_audio=None, *, exaggeration=0.5,
                 progress_callback=None, voice="neutro", cfg_weight=0.5, temperature=0.8):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("O texto não pode estar vazio.")
        if voice not in VOICE_PROFILES:
            raise ValueError(f"Perfil desconhecido: {voice}. Use: {', '.join(VOICE_PROFILES)}")
        reference = Path(reference_audio) if reference_audio is not None else ROOT / VOICE_PROFILES[voice]
        if not reference.is_absolute():
            reference = ROOT / reference
        if not reference.is_file():
            raise FileNotFoundError(f"Voz de referência não encontrada: {reference}")
        info = sf.info(reference)
        if info.frames == 0:
            raise ValueError("A voz de referência está vazia.")
        output = Path(output_path)
        if output.suffix.lower() != ".wav":
            raise ValueError("O arquivo de saída deve ter extensão .wav.")
        output.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            started = time.perf_counter()
            token_count = 0
            original_inference = self.model.t3.inference
            hook = None

            def notify(stage):
                if progress_callback:
                    progress_callback(stage, token_count)

            def on_token(_module, _inputs, _output):
                nonlocal token_count
                token_count += 1
                notify("generating")

            def tracked_inference(*args, **kwargs):
                result = original_inference(*args, **kwargs)
                notify("decoding")
                return result

            try:
                notify("reference")
                if progress_callback:
                    hook = self.model.t3.speech_head.register_forward_hook(on_token)
                    self.model.t3.inference = tracked_inference
                with torch.inference_mode():
                    audio = self.model.generate(text.strip(), language_id="pt", audio_prompt_path=str(reference),
                                                exaggeration=exaggeration, cfg_weight=cfg_weight,
                                                temperature=temperature)
                samples = audio.detach().cpu().numpy().reshape(-1)
                if not samples.size or not np.isfinite(samples).all() or not np.any(samples):
                    raise RuntimeError("O modelo retornou áudio vazio, inválido ou silencioso.")
                sf.write(output, samples, self.sample_rate, subtype="PCM_16")
                self.last_generation_seconds = time.perf_counter() - started
            except Exception as exc:
                raise RuntimeError(f"Falha na geração Chatterbox em {self.device}: {exc}") from exc
            finally:
                if hook is not None:
                    hook.remove()
                self.model.t3.inference = original_inference
        return output.resolve()


_default_tts = None


def gerar_audio(texto, arquivo_saida="outputs/audio/teste.wav", reference_audio=None, *, voice="neutro"):
    global _default_tts
    if _default_tts is None:
        _default_tts = ChatterboxTTS()
    return _default_tts.generate(texto, arquivo_saida, reference_audio, voice=voice)
