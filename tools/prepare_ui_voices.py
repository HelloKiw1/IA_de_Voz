"""Download official demo references and create short WAV previews."""
import json
import urllib.request
from pathlib import Path
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "tts/voices"
SAMPLES = {
    "pt_m1": "https://storage.googleapis.com/chatterbox-demo-samples/mtl_prompts/pt_m1.flac",
    "pt_prompts1": "https://storage.googleapis.com/chatterbox-demo-samples/mtl_prompts/pt/pt_prompts1.flac",
}

DIRECTORY.mkdir(parents=True, exist_ok=True)
for name, url in SAMPLES.items():
    target = DIRECTORY / (name + ".wav")
    if target.exists():
        continue
    source = DIRECTORY / (name + ".flac")
    if not source.exists():
        with urllib.request.urlopen(url, timeout=120) as response, source.open("wb") as output:
            import shutil
            shutil.copyfileobj(response, output)
    data, rate = sf.read(source)
    if data.ndim > 1:
        data = data.mean(axis=1)
    sf.write(target, data[:rate * 10], rate, subtype="PCM_16")
    print(f"Reference ready: {target.name}", flush=True)
(DIRECTORY / "ui_sources.json").write_text(json.dumps({"samples": SAMPLES, "note": "Official reference recordings; UI names are illustrative, not model names."}, indent=2), encoding="utf-8")
