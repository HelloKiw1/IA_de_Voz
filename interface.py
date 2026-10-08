"""Local IA Voz UI. Run with the project's virtualenv Python."""
from __future__ import annotations
import argparse
import json
import math
import mimetypes
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
LOCK = threading.RLock()
JOBS = {}
ENGINE = None
ACTIVE = None
VOICES = [
    {"id": "brisa", "name": "Brisa", "label": "Voz feminina · PT-BR", "file": "pt_br_f2.wav", "preview_file": "tutorial_brisa.wav"},
    {"id": "neutro", "name": "Eduardo · Neutro", "label": "Voz masculina · PT-BR", "file": "eduardo/neutro.wav", "preview_file": "teste_neutro.wav", "preview_directory": "outputs/audio", "preview_prefix": "/audio/"},
    {"id": "calmo", "name": "Eduardo · Calmo", "label": "Voz masculina · PT-BR", "file": "eduardo/calmo.wav", "preview_file": "teste_calmo.wav", "preview_directory": "outputs/audio", "preview_prefix": "/audio/"},
    {"id": "animado", "name": "Eduardo · Animado", "label": "Voz masculina · PT-BR", "file": "eduardo/animado.wav", "preview_file": "teste_animado.wav", "preview_directory": "outputs/audio", "preview_prefix": "/audio/"},
    {"id": "campo", "name": "Campo", "label": "Voz masculina · PT-BR", "file": "pt_m1.wav", "preview_file": "tutorial_campo.wav"},
    {"id": "aurora", "name": "Aurora", "label": "Voz alternativa · PT-BR", "file": "pt_prompts1.wav", "preview_file": "tutorial_aurora.wav"},
]


def duration(path):
    import wave
    with wave.open(str(path)) as wav:
        return wav.getnframes() / wav.getframerate()


def voice_list():
    result = []
    for voice in VOICES:
        path = ROOT / "tts/voices" / voice["file"]
        if path.exists():
            preview = ROOT / voice.get("preview_directory", "tts/voices") / voice["preview_file"]
            url = voice.get("preview_prefix", "/voices/") + preview.name
            if not preview.is_file():
                preview = path
                url = "/voices/" + voice["file"]
            result.append({**voice, "url": url, "duration": duration(preview)})
    return result


def history():
    result = []
    for metadata in sorted((ROOT / "outputs/audio").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            item = json.loads(metadata.read_text(encoding="utf-8"))
            wav = metadata.with_suffix(".wav")
            if wav.exists():
                result.append({"id": metadata.stem, "url": "/audio/" + wav.name,
                               "duration": item.get("duration_seconds", duration(wav)),
                               "text": item.get("text", "Teste do Chatterbox em português brasileiro"),
                               "voice": item.get("voice", "Brisa"),
                               "created": item.get("created", wav.stat().st_mtime)})
        except (ValueError, OSError, KeyError):
            continue
    return result[:20]


def estimate(text):
    """Use prior measured synthesis timings, including the installation smoke test."""
    rates = []
    for path in (ROOT / "outputs/audio").glob("*.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            chars = item.get("characters", 160 if path.stem == "teste_chatterbox" else 0)
            if chars and item.get("generation_seconds"):
                rates.append(item["generation_seconds"] / chars)
        except (OSError, ValueError):
            pass
    rate = sum(rates[-10:]) / len(rates[-10:]) if rates else 3.3
    return max(20, len(text) * rate)


def worker(job_id, text, voice, expressiveness):
    global ENGINE, ACTIVE
    try:
        if ENGINE is None:
            from tts.chatterbox_tts import ChatterboxTTS
            ENGINE = ChatterboxTTS()
        started = time.monotonic()
        with LOCK:
            JOBS[job_id].update(stage="generating", message="Gerando a fala", generation_started=started)

        def progress(stage, tokens=0):
            with LOCK:
                job = JOBS[job_id]
                if stage != job["stage"]:
                    job["stage_started"] = time.monotonic()
                if stage == "generating" and "sampling_started" not in job:
                    job["sampling_started"] = time.monotonic()
                job.update(stage=stage, tokens=tokens)
                job["message"] = "Preparando a voz" if stage == "reference" else "Gerando a fala" if stage == "generating" else "Finalizando o áudio"
                job["progress"] = min(85, 8 + tokens / max(60, len(text) * 1.8) * 77) if stage == "generating" else 5 if stage == "reference" else 90

        output = ROOT / "outputs/audio" / (job_id + ".wav")
        ENGINE.generate(text, output, ROOT / "tts/voices" / voice["file"],
                        exaggeration=expressiveness, progress_callback=progress)
        info = {"text": text, "characters": len(text), "voice": voice["name"],
                "duration_seconds": duration(output), "sample_rate": ENGINE.sample_rate,
                "generation_seconds": ENGINE.last_generation_seconds,
                "device": ENGINE.device, "created": time.time()}
        output.with_suffix(".json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        with LOCK:
            JOBS[job_id].update(stage="done", progress=100, message="Seu áudio está pronto", remaining=0,
                                result={"url": "/audio/" + output.name, "duration": info["duration_seconds"],
                                        "voice": voice["name"], "text": text})
    except Exception as exc:
        with LOCK:
            JOBS[job_id].update(stage="error", message="Não foi possível gerar o áudio. Tente novamente.", error=str(exc))
        import traceback
        traceback.print_exc()
    finally:
        with LOCK:
            ACTIVE = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, path):
        if not path.is_file():
            return self.respond(404, {"error": "Arquivo não encontrado"})
        size = path.stat().st_size
        start, end = 0, size - 1
        requested = self.headers.get("Range")
        if requested:
            try:
                left, right = requested.removeprefix("bytes=").split("-", 1)
                if left:
                    start = int(left)
                    end = min(end, int(right)) if right else end
                else:
                    start = max(0, size - int(right))
                if start > end or start < 0:
                    raise ValueError()
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
        self.send_response(206 if requested else 200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        if requested:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with path.open("rb") as file:
                file.seek(start)
                remaining = end - start + 1
                while remaining:
                    block = file.read(min(65536, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/voices":
            return self.respond(200, voice_list())
        if path == "/api/history":
            return self.respond(200, history())
        if path == "/api/status":
            with LOCK:
                return self.respond(200, {"active": ACTIVE, "loaded": ENGINE is not None})
        if path.startswith("/api/waveform/"):
            name = path.rsplit("/", 1)[-1]
            if name != Path(name).name or ".." in name or "\\" in name or not name.endswith(".wav"):
                return self.respond(400, {"error": "Caminho inválido"})
            audio_path = ROOT / "outputs/audio" / name
            if not audio_path.is_file():
                return self.respond(404, {"error": "Áudio não encontrado"})
            import array
            import wave
            with wave.open(str(audio_path)) as wav:
                if wav.getsampwidth() != 2:
                    return self.respond(200, [])
                samples = array.array("h", wav.readframes(wav.getnframes()))
            stride = max(1, len(samples) // 100)
            peaks = [max((abs(s) for s in samples[i * stride:(i + 1) * stride]), default=0) for i in range(100)]
            maximum = max(peaks) or 1
            return self.respond(200, [value / maximum for value in peaks])
        if path.startswith("/api/jobs/"):
            with LOCK:
                job = JOBS.get(path.rsplit("/", 1)[-1])
                if job is None:
                    return self.respond(404, {"error": "Geração não encontrada"})
                result = dict(job)
                result["elapsed"] = time.monotonic() - job["started"]
                if job["stage"] not in ("done", "error", "loading"):
                    result["remaining"] = max(0, job["estimate"] - (time.monotonic() - job["generation_started"]))
                    if job["stage"] == "generating" and job["tokens"] >= 5:
                        tokens_left = max(0, max(60, len(job["text"]) * 1.8) - job["tokens"])
                        seconds_per_token = (time.monotonic() - job["sampling_started"]) / job["tokens"]
                        result["remaining"] = tokens_left * seconds_per_token + max(15, job["estimate"] * .2)
                    elif job["stage"] == "decoding":
                        result["remaining"] = max(0, max(15, job["estimate"] * .2) - (time.monotonic() - job["stage_started"]))
                return self.respond(200, result)
        if path in ("/", "/index.html"):
            return self.serve_file(ROOT / "ui/index.html")
        for voice in VOICES:
            if path == "/voices/" + voice["file"]:
                return self.serve_file(ROOT / "tts/voices" / voice["file"])
        for prefix, directory in (("/ui/", "ui"), ("/voices/", "tts/voices"), ("/audio/", "outputs/audio")):
            if path.startswith(prefix):
                name = path[len(prefix):]
                if not name or name != Path(name).name or ".." in name or "\\" in name:
                    return self.respond(400, {"error": "Caminho inválido"})
                return self.serve_file(ROOT / directory / name)
        self.respond(404, {"error": "Não encontrado"})

    def do_POST(self):
        global ACTIVE
        # Only same-origin requests can start local inference.
        if self.path != "/api/generate":
            return self.respond(404, {"error": "Não encontrado"})
        host = self.headers.get("Host", "")
        if self.headers.get("Origin") not in (None, "http://" + host):
            return self.respond(403, {"error": "Origem não autorizada"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 16000:
                raise ValueError("Requisição inválida")
            data = json.loads(self.rfile.read(length))
            text = data.get("text", "")
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 300:
                raise ValueError("Escreva entre 1 e 300 caracteres.")
            voice = next((v for v in VOICES if v["id"] == data.get("voice")), None)
            if not voice or not (ROOT / "tts/voices" / voice["file"]).is_file():
                raise ValueError("Escolha uma voz disponível.")
            expression = float(data.get("expressiveness", 0.5))
            if not math.isfinite(expression) or not 0.25 <= expression <= 1:
                raise ValueError("Expressividade inválida.")
        except (ValueError, TypeError, AttributeError) as exc:
            return self.respond(400, {"error": str(exc)})
        with LOCK:
            if ACTIVE:
                return self.respond(409, {"error": "Aguarde a geração atual terminar.", "active": ACTIVE})
            job_id = "voz_" + uuid.uuid4().hex[:12]
            ACTIVE = job_id
            JOBS[job_id] = {"id": job_id, "stage": "loading" if ENGINE is None else "reference",
                            "message": "Carregando a voz" if ENGINE is None else "Preparando a voz",
                            "progress": 0, "started": time.monotonic(), "estimate": estimate(text.strip()),
                            "remaining": None, "tokens": 0, "text": text.strip()}
            threading.Thread(target=worker, args=(job_id, text.strip(), voice, expression), daemon=True).start()
        self.respond(202, {"id": job_id})


class LocalServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        import socket
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Open the local interface in the default browser")
    args = parser.parse_args()
    try:
        server = LocalServer(("127.0.0.1", args.port), Handler)
    except OSError:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/api/status", timeout=3) as response:
            existing = json.load(response)
        if not isinstance(existing, dict) or "active" not in existing or "loaded" not in existing:
            raise RuntimeError("A porta está sendo utilizada por outro programa.")
        if args.open:
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{args.port}")
        print(f"O estúdio já está aberto: http://127.0.0.1:{args.port}")
        raise SystemExit(0)
    print(f"IA Voz: http://127.0.0.1:{args.port}", flush=True)
    if args.open:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
