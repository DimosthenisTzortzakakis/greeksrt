import os
import tempfile
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx

from splitter import (
    create_subtitles, subtitles_to_srt,
    normalize_words, segments_to_words,
)

load_dotenv()

app = FastAPI(title="Greek SRT Generator")
app.mount("/static", StaticFiles(directory="static"), name="static")

SUPPORTED_EXT = {'.mp3', '.mp4', '.wav', '.m4a', '.ogg', '.flac', '.webm', '.mpeg', '.mpga'}
MAX_MB = 25


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/env-key")
async def env_key():
    return {
        "groq":       bool(os.getenv("GROQ_API_KEY", "").strip()),
        "elevenlabs": bool(os.getenv("ELEVENLABS_API_KEY", "").strip()),
        "openai":     bool(os.getenv("OPENAI_API_KEY", "").strip()),
    }


async def _transcribe_elevenlabs(tmp_path: str, filename: str, api_key: str, language: str) -> list:
    async with httpx.AsyncClient(timeout=600) as client:
        with open(tmp_path, 'rb') as f:
            data = {"model_id": "scribe_v1", "timestamps_granularity": "word"}
            if language != "auto":
                data["language_code"] = language
            resp = await client.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers={"xi-api-key": api_key},
                files={"file": (filename, f, "audio/mpeg")},
                data=data,
            )
    if resp.status_code != 200:
        try:    detail = resp.json().get("detail", resp.text)
        except: detail = resp.text
        raise HTTPException(resp.status_code, f"ElevenLabs error: {detail}")
    return resp.json().get("words", [])


async def _transcribe_groq(tmp_path: str, filename: str, api_key: str, language: str, vocab_hint: str = "") -> list:
    async with httpx.AsyncClient(timeout=600) as client:
        with open(tmp_path, 'rb') as f:
            form: dict = {
                "model": (None, "whisper-large-v3"),
                "response_format": (None, "verbose_json"),
                "timestamp_granularities[]": (None, "word"),
            }
            if language != "auto":
                form["language"] = (None, language)
            if vocab_hint.strip():
                form["prompt"] = (None, vocab_hint.strip())
            resp = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={**form, "file": (filename, f, "audio/mpeg")},
            )
    if resp.status_code != 200:
        try:    detail = resp.json().get("error", {}).get("message", resp.text)
        except: detail = resp.text
        raise HTTPException(resp.status_code, f"Groq error: {detail}")
    data = resp.json()
    return data.get("words") or segments_to_words(data.get("segments", []))


async def _transcribe_openai(tmp_path: str, filename: str, api_key: str, language: str, vocab_hint: str = "") -> list:
    async with httpx.AsyncClient(timeout=600) as client:
        with open(tmp_path, 'rb') as f:
            form: dict = {
                "model": (None, "whisper-1"),
                "response_format": (None, "verbose_json"),
                "timestamp_granularities[]": (None, "word"),
            }
            if language != "auto":
                form["language"] = (None, language)
            if vocab_hint.strip():
                form["prompt"] = (None, vocab_hint.strip())
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={**form, "file": (filename, f, "audio/mpeg")},
            )
    if resp.status_code != 200:
        try:    detail = resp.json().get("error", {}).get("message", resp.text)
        except: detail = resp.text
        raise HTTPException(resp.status_code, f"OpenAI error: {detail}")
    data = resp.json()
    return data.get("words") or segments_to_words(data.get("segments", []))


@app.post("/transcribe")
async def transcribe(
    file:              UploadFile = File(...),
    provider:          str = Form(default="elevenlabs"),
    api_key:           str = Form(default=""),
    language:          str = Form(default="el"),
    silence_threshold: float = Form(default=0.5),
    max_chars:         int   = Form(default=80),
    keep_connected:    str   = Form(default="true"),
    vocab_hint:        str   = Form(default=""),
):
    # Resolve API key: form field → env var fallback
    env_map = {"elevenlabs": "ELEVENLABS_API_KEY", "groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY"}
    resolved_key = api_key.strip() or os.getenv(env_map.get(provider, ""), "").strip()
    if not resolved_key:
        raise HTTPException(400, f"No API key provided for {provider}.")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_EXT:
        raise HTTPException(400, f"Unsupported file type '{ext}'.")

    content = await file.read()
    if len(content) > MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {MAX_MB} MB).")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if provider == "elevenlabs":
            raw_words = await _transcribe_elevenlabs(tmp_path, file.filename, resolved_key, language)
        elif provider == "groq":
            raw_words = await _transcribe_groq(tmp_path, file.filename, resolved_key, language, vocab_hint)
        elif provider == "openai":
            raw_words = await _transcribe_openai(tmp_path, file.filename, resolved_key, language, vocab_hint)
        else:
            raise HTTPException(400, f"Unknown provider: {provider}")

        words = normalize_words(raw_words)
        if not words:
            raise HTTPException(422, "No speech detected in the audio.")

        connected = keep_connected.lower() in ('true', 'on', '1', 'yes')
        subtitles = create_subtitles(words, silence_threshold, max_chars, language)
        srt = subtitles_to_srt(subtitles, connected, silence_threshold)

        return JSONResponse({
            "subtitles": subtitles,
            "srt": srt,
            "word_count": len(words),
            "subtitle_count": len(subtitles),
        })

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
