import os
import tempfile
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
import httpx

from splitter import (
    create_subtitles, subtitles_to_srt,
    normalize_words, segments_to_words,
)
from database import get_db, User
from auth import hash_password, verify_password, create_token, require_auth

load_dotenv()

app = FastAPI(title="Greek SRT Generator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")

SUPPORTED_EXT = {'.mp3', '.mp4', '.wav', '.m4a', '.ogg', '.flac', '.webm', '.mpeg', '.mpga'}
MAX_MB = 25

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()


def _allowed_emails() -> set:
    raw = os.getenv("ALLOWED_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def check_transcribe_access(email: str):
    allowed = _allowed_emails()
    if allowed and email.lower() not in allowed:
        raise HTTPException(
            403,
            "Your account doesn't have transcription access yet. "
            "Ask the owner to add you.",
        )


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/auth/register")
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not email or not body.password:
        raise HTTPException(400, "Email and password required.")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with that email already exists.")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user.id, user.email), "email": user.email}


@app.post("/auth/login")
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or user.password_hash.startswith("!"):
        raise HTTPException(401, "Invalid email or password.")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password.")
    return {"token": create_token(user.id, user.email), "email": user.email}


@app.get("/auth/me")
async def me(payload: dict = Depends(require_auth)):
    return {"email": payload["email"], "id": int(payload["sub"])}


class GoogleAuthRequest(BaseModel):
    credential: str


@app.post("/auth/google")
async def google_auth(body: GoogleAuthRequest, db: Session = Depends(get_db)):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google sign-in is not configured.")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": body.credential},
        )
    if resp.status_code != 200:
        raise HTTPException(401, "Invalid Google credential.")
    info = resp.json()
    if info.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(401, "Google credential was issued for another app.")
    if info.get("email_verified") not in ("true", True):
        raise HTTPException(401, "Google account email is not verified.")
    email = info["email"].strip().lower()

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, password_hash="!google")  # no password login
        db.add(user)
        db.commit()
        db.refresh(user)
    return {"token": create_token(user.id, user.email), "email": user.email}


@app.get("/auth/config")
async def auth_config():
    return {"google_client_id": GOOGLE_CLIENT_ID}


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
    _auth:             dict  = Depends(require_auth),
):
    check_transcribe_access(_auth["email"])

    # Resolve API key: form field → env var fallback
    env_map = {"elevenlabs": "ELEVENLABS_API_KEY", "groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY"}
    resolved_key = api_key.strip() or os.getenv(env_map.get(provider, ""), "").strip()
    if not resolved_key:
        raise HTTPException(400, f"No API key provided for {provider}.")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_EXT:
        raise HTTPException(400, f"Unsupported file type '{ext}'.")

    # Stream to disk in chunks — never hold the whole upload in RAM
    # (the free 512 MB instance gets OOM-killed by large MP4s otherwise)
    limit = MAX_MB * 1024 * 1024
    size = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp_path = tmp.name
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                tmp.close()
                os.unlink(tmp_path)
                raise HTTPException(413, f"File too large (max {MAX_MB} MB).")
            tmp.write(chunk)

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
