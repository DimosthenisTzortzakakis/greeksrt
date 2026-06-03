# Greek SRT Generator

MP3 → SRT subtitles with smart Greek grammar-aware splitting.

## Quick Start

```bash
cd greek-srt-app
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Optional: save your Groq API key so you don't type it every time
cp .env.example .env
# edit .env and paste your key

uvicorn app:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

## Get a free Groq API key

1. Go to https://console.groq.com/keys
2. Sign up (free)
3. Create an API key
4. Paste it in the app (or in `.env`)

## Deploy to Railway (free hosting)

1. Push this folder to a GitHub repo
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Add env var `GROQ_API_KEY` in Railway settings
4. Done — Railway auto-detects Python and runs `uvicorn`

Add a `Procfile` for Railway:
```
web: uvicorn app:app --host 0.0.0.0 --port $PORT
```

## How the Greek splitting works

- Uses Groq's Whisper large-v3 with **word-level timestamps**
- Never breaks a line before: `και`, `αλλά`, `ή`, `όμως`, `να`, `θα`, `που`, `με`, `σε`, `για`, `ωστόσο`, …
- Never breaks a line after: articles (`ο`, `η`, `το`, …), prepositions, demonstratives
- Soft character limit — goes slightly over if needed to keep a phrase together
- Hard ceiling at ~2× the target to avoid very long subtitles
- 2-line formatting: long subtitle cards split into two balanced lines at a grammatically safe point
- **Keep connected** mode: subtitle N ends exactly when subtitle N+1 starts (no blank screen), except across long pauses
