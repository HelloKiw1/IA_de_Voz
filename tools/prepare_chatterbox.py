"""Fetch the official PT-BR inference source; never execute the Gradio app."""
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPACE = "ResembleAI/Chatterbox-Multilingual-TTS-pt-br"
REVISION = "9e515821e826e207cd617a0fdd0223899ed108ea"


def fetch(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return response.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def main():
    metadata = json.loads(fetch(f"https://huggingface.co/api/spaces/{SPACE}/revision/{REVISION}"))
    destination = ROOT / "vendor" / "chatterbox"
    for item in metadata["siblings"]:
        name = item["rfilename"]
        if name.startswith("chatterbox/src/") and name.endswith(".py"):
            target = destination / name.removeprefix("chatterbox/")
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(fetch(f"https://huggingface.co/spaces/{SPACE}/resolve/{REVISION}/{name}"))
    (destination / "pyproject.toml").write_text('''[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"
[project]
name = "ia-voz-chatterbox-ptbr"
version = "0.1.0"
requires-python = ">=3.10"
[tool.setuptools.packages.find]
where = ["src"]
''', encoding="utf-8")
    license_path = destination / "LICENSE"
    if not license_path.exists():
        license_path.write_bytes(fetch("https://raw.githubusercontent.com/resemble-ai/chatterbox/master/LICENSE"))
    (destination / "provenance.json").write_text(json.dumps({"source": SPACE, "revision": REVISION}, indent=2), encoding="utf-8")
    print(f"Official inference source ready: {destination}")


if __name__ == "__main__":
    main()
