# PeakCAT Voice AI

An AI voice agent built for Indian EdTech — places outbound calls, handles a full sales conversation (including Hindi / Hinglish), and logs every call to Google Sheets automatically.

Live site: https://shivam-bhansali-v.github.io/AI-VOICE_AGENT/

## What it does

- Places outbound calls using **Vapi** with a sales-trained assistant
- Speaks **multiple Indian languages** (English, Hindi, Hinglish, etc.)
- Handles common objections like pricing, timing, "thoda sochke bataunga"
- Detects call outcome (Enrolled, Demo Booked, Interested, Busy, Not Interested, Wrong Number)
- Logs caller, duration, transcript, summary, outcome, and cost to a Google Sheet the moment the call ends
- Ships a dashboard (`/dashboard.html`) that reads those logs back in real time

## Tech

| Layer | Using |
|---|---|
| Voice orchestration | Vapi |
| LLM | Groq + Llama 3.3 70B |
| Speech-to-text | Deepgram Nova-3 |
| Text-to-speech | Cartesia |
| Backend | FastAPI (Python) |
| Logging | Google Sheets API |
| Deployment | Railway (backend) · GitHub Pages (frontend) |

## Repo layout

```
main.py            FastAPI app — receives Vapi's end-of-call webhook
logger.py          Google Sheets client
index.html         Landing page with demo audio + in-browser call button
dashboard.html     Live call-log dashboard
login.html         Dashboard gate
requirements.txt   Python deps
Procfile           Railway start command
```

## Running locally

You'll need:
- Python 3.9+
- A Google service account JSON (saved as `credentials.json`)
- The target Google Sheet shared with the service account's `client_email`

```powershell
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Expose it publicly so Vapi can hit the webhook:

```powershell
ngrok http 8000
```

Then paste `<ngrok-url>/webhook` into your Vapi assistant's server URL.

## Environment

Copy `.env.example` to `.env` and set:

- `SHEET_NAME` — exact name of the Google Sheet as it appears in Drive

If you're deploying to Railway, set the same vars in the Railway dashboard and upload `credentials.json` (or pipe its contents through an env var — see `credentials_runtime.json` in `logger.py`).

## Security notes

- `credentials.json` contains a private key. Keep it out of public commits.
- The dashboard's username/password are hardcoded on the frontend — fine for a demo, but move to a real auth check before putting it in front of real users.
- Before deploying the landing page publicly, add your domain to the allowed origins list for the Vapi public key. Otherwise anyone can trigger calls that bill to your account.

## Built by

Shivam Bhansali · VIT University  
[LinkedIn](https://www.linkedin.com/in/shivam-bhansali-a868a930b/) · [GitHub](https://github.com/Shivam-Bhansali-V)
