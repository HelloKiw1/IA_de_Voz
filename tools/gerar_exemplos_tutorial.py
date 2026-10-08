"""Generate the same complete tutorial in the three UI voices, with resumable parts."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEXT_PATH = ROOT / "tts/voices/tutorial.txt"
VOICES = {"brisa": "pt_br_f2.wav", "campo": "pt_m1.wav", "aurora": "pt_prompts1.wav"}


def split_text(text, limit=220):
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > limit:
            raise ValueError("Paragraph exceeds the safe chunk length")
        combined = (current + " " + paragraph).strip()
        if current and len(combined) > limit:
            chunks.append(current)
            current = paragraph
        else:
            current = combined
    if current:
        chunks.append(current)
    return chunks


def main():
    import numpy as np
    import soundfile as sf
    import torch
    from tts.chatterbox_tts import ChatterboxTTS

    text = TEXT_PATH.read_text(encoding="utf-8").replace("**", "").strip()
    chunks = split_text(text)
    cache = ROOT / "outputs/audio/voice_examples"
    cache.mkdir(parents=True, exist_ok=True)
    print(f"Tutorial: {len(text)} characters, {len(chunks)} parts per voice", flush=True)
    started = time.perf_counter()
    engine = ChatterboxTTS()
    print(f"Model ready: {engine.device}", flush=True)
    summaries = []
    for voice, reference in VOICES.items():
        output = ROOT / "tts/voices" / ("tutorial_" + voice + ".wav")
        metadata_path = output.with_suffix(".json")
        if output.exists() and metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("text") == text:
                summaries.append(metadata)
                print(f"Already ready: {voice}", flush=True)
                continue
        voice_started = time.perf_counter()
        print(f"Voice: {voice}; preparing reference", flush=True)
        engine.model.prepare_conditionals(str(ROOT / "tts/voices" / reference), exaggeration=0.5)
        parts = []
        part_reports = []
        for index, chunk in enumerate(chunks):
            part_path = cache / f"tutorial_{voice}_{index + 1}.wav"
            part_metadata = part_path.with_suffix(".json")
            if part_path.exists() and part_metadata.exists() and json.loads(part_metadata.read_text(encoding="utf-8")).get("text") == chunk:
                samples, rate = sf.read(part_path, dtype="float32")
                assert rate == engine.sample_rate
                report = json.loads(part_metadata.read_text(encoding="utf-8"))
                print(f"Reuse: {voice} part {index + 1}", flush=True)
            else:
                print(f"Generating: {voice} part {index + 1}/{len(chunks)} ({len(chunk)} characters)", flush=True)
                tokens = [0]
                def progress(module, inputs, outputs):
                    tokens[0] += 1
                    if tokens[0] % 40 == 0:
                        print(f"Progress: {voice} part {index + 1}, {tokens[0]} speech tokens", flush=True)
                hook = engine.model.t3.speech_head.register_forward_hook(progress)
                part_started = time.perf_counter()
                try:
                    torch.manual_seed(42 + index)
                    with torch.inference_mode():
                        audio = engine.model.generate(chunk, language_id="pt", audio_prompt_path=None, exaggeration=0.5)
                finally:
                    hook.remove()
                if tokens[0] >= 1000:
                    raise RuntimeError("Speech token limit reached; split this chunk before continuing")
                samples = audio.detach().cpu().numpy().reshape(-1)
                if not samples.size or not np.isfinite(samples).all() or not np.any(samples):
                    raise RuntimeError(f"Invalid audio: {voice} part {index + 1}")
                sf.write(part_path, samples, engine.sample_rate, subtype="PCM_16")
                report = {"text": chunk, "tokens": tokens[0], "duration": len(samples)/engine.sample_rate,
                          "generation_seconds": time.perf_counter() - part_started}
                part_metadata.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Part ready: {voice} {index + 1}, {report['duration']:.2f}s", flush=True)
            parts.append(samples)
            part_reports.append(report)
        silence = np.zeros(int(engine.sample_rate * .4), dtype="float32")
        combined = np.concatenate([segment for i, part in enumerate(parts) for segment in ((silence, part) if i else (part,))])
        temporary = output.with_suffix(".tmp.wav")
        sf.write(temporary, combined, engine.sample_rate, subtype="PCM_16")
        temporary.replace(output)
        info = sf.info(output)
        assert info.frames > 0 and info.samplerate == engine.sample_rate and output.stat().st_size > 44
        metadata = {"voice": voice, "text": text, "reference": reference, "sample_rate": info.samplerate,
                    "duration_seconds": info.duration, "bytes": output.stat().st_size,
                    "generation_seconds": time.perf_counter() - voice_started, "parts": part_reports}
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        summaries.append(metadata)
        print(f"VOICE READY: {voice}, {info.duration:.2f}s, {output.stat().st_size} bytes", flush=True)
    (cache / "tutorial_summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ALL THREE VOICES READY. Total: {time.perf_counter() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
