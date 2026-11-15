"""Voice memos and other audio: transcribe to text so they become ordinary tasks.

Backends, first available wins (override with OPENJAMES_STT=whisper-cli|whisper|openai):
  whisper-cli  whisper.cpp (needs ffmpeg + a ggml model in $OPENJAMES_WHISPER_MODEL), local, free
  whisper      openai-whisper python CLI, local, free
  openai       OpenAI transcription API, only when OPENAI_API_KEY is set (paid, sends the audio out)
"""
from __future__ import annotations
import os, shutil, subprocess, tempfile, pathlib
import httpx

AUDIO_EXT = {".ogg", ".oga", ".opus", ".mp3", ".m4a", ".wav", ".aac", ".flac", ".mp4", ".mov", ".webm", ".amr"}


def is_audio(name: str = "", mime: str = "") -> bool:
    return mime.startswith(("audio/", "video/")) or pathlib.Path(name).suffix.lower() in AUDIO_EXT


def backend() -> str | None:
    want = os.environ.get("OPENJAMES_STT")
    if want: return want
    if shutil.which("whisper-cli") and shutil.which("ffmpeg") and os.environ.get("OPENJAMES_WHISPER_MODEL"): return "whisper-cli"
    if shutil.which("whisper"): return "whisper"
    if os.environ.get("OPENAI_API_KEY"): return "openai"
    return None


def transcribe(path) -> str:
    """Return the transcript, or raise RuntimeError with a human-readable reason."""
    p = pathlib.Path(path); b = backend()
    if b is None:
        raise RuntimeError("no speech-to-text backend: install whisper.cpp (whisper-cli + ffmpeg, set OPENJAMES_WHISPER_MODEL), "
                           "openai-whisper, or set OPENAI_API_KEY")
    if b == "openai":
        r = httpx.post("https://api.openai.com/v1/audio/transcriptions", timeout=120, follow_redirects=False, trust_env=False,
                       headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                       data={"model": os.environ.get("OPENJAMES_STT_MODEL", "whisper-1")},
                       files={"file": (p.name, p.read_bytes())})
        r.raise_for_status(); return r.json()["text"].strip()
    with tempfile.TemporaryDirectory() as d:
        if b == "whisper-cli":
            wav = pathlib.Path(d) / "a.wav"
            subprocess.run(["ffmpeg", "-y", "-i", str(p), "-ar", "16000", "-ac", "1", str(wav)], check=True, capture_output=True, timeout=120)
            r = subprocess.run(["whisper-cli", "-m", os.environ["OPENJAMES_WHISPER_MODEL"], "-f", str(wav), "-nt", "-np"],
                               check=True, capture_output=True, text=True, timeout=600)
            return r.stdout.strip()
        if b == "whisper":
            subprocess.run(["whisper", str(p), "--output_format", "txt", "--output_dir", d], check=True, capture_output=True, timeout=900)
            return (pathlib.Path(d) / (p.stem + ".txt")).read_text().strip()
    raise RuntimeError(f"unknown STT backend {b}")


def describe(path, kind="voice memo") -> str:
    """Task text for an audio file: the transcript, or an honest note when transcription is impossible."""
    try: t = transcribe(path)
    except Exception as e:
        return f"[{kind} received but not transcribed: {e if isinstance(e, RuntimeError) else type(e).__name__}. File: {path}]"
    return f"[{kind}, transcribed]\n{t}" if t else f"[{kind} received, no speech detected. File: {path}]"
