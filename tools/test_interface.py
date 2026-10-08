"""HTTP end-to-end verification with a real local Chatterbox generation."""
import json
import time
import urllib.request
import urllib.error
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8765"


def request(path, data=None, headers=None, expected=200):
    payload = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(URL + path, data=payload, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        response = urllib.request.urlopen(request, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    assert response.status == expected, (path, response.status, response.read())
    return response.read(), response.headers


def main():
    assert b"Seu texto" in request("/")[0]
    voices = json.loads(request("/api/voices")[0])
    assert len(voices) == 6 and all(v["duration"] > 0 for v in voices)
    assert [v["id"] for v in voices][1:4] == ["neutro", "calmo", "animado"]
    for voice in voices:
        body, headers = request(voice["url"], headers={"Range": "bytes=0-43"}, expected=206)
        assert len(body) == 44 and body[:4] == b"RIFF"
    request("/api/generate", {"text": "", "voice": "brisa"}, expected=400)
    request("/api/generate", {"text": "Teste", "voice": "brisa"}, headers={"Origin": "http://example.com"}, expected=403)
    request("/api/generate", {"text": "Teste", "voice": "missing"}, expected=400)
    print("OK: interface, six voices, WAV range playback and validation", flush=True)
    response, _ = request("/api/generate", {"text": "Olá! Sua voz está pronta.", "voice": "brisa", "expressiveness": 0.5}, expected=202)
    job_id = json.loads(response)["id"]
    request("/api/generate", {"text": "Teste", "voice": "brisa"}, expected=409)
    stages = set()
    deadline = time.monotonic() + 1800
    last_stage = None
    while time.monotonic() < deadline:
        job = json.loads(request("/api/jobs/" + job_id)[0])
        stages.add(job["stage"])
        if job["stage"] != last_stage:
            print(f"Stage: {job['stage']}; elapsed: {job['elapsed']:.1f}s", flush=True)
            last_stage = job["stage"]
        if job["stage"] == "error":
            raise RuntimeError(job.get("error"))
        if job["stage"] == "done":
            break
        time.sleep(2)
    else:
        raise TimeoutError("Inference did not finish within 30 minutes")
    assert "generating" in stages and "decoding" in stages
    body, _ = request(job["result"]["url"])
    assert len(body) > 44 and body[:4] == b"RIFF"
    peaks = json.loads(request("/api/waveform/" + job_id + ".wav")[0])
    assert len(peaks) == 100 and max(peaks) > 0
    with wave.open(str(ROOT / "outputs/audio" / (job_id + ".wav"))) as audio:
        print(f"OK: real WAV; duration={audio.getnframes()/audio.getframerate():.2f}s; rate={audio.getframerate()}Hz; bytes={len(body)}", flush=True)
    assert any(row["id"] == job_id for row in json.loads(request("/api/history")[0]))
    print("OK: progress, playback, waveform and persisted history", flush=True)


if __name__ == "__main__":
    main()
