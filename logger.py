from fastapi import FastAPI, Request, HTTPException
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
import os
import json
import tempfile
from typing import Any, Dict

load_dotenv()

app = FastAPI()

# Google Sheets scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_sheet() -> Any:
    """Authorize and return the first worksheet of the spreadsheet named in SHEET_NAME."""
    # Try to get credentials from environment variable first (Railway)
    creds_json_str = os.getenv("CREDENTIALS_JSON")
    
    if creds_json_str:
        # Parse JSON from environment variable
        try:
            print("[DEBUG] Using CREDENTIALS_JSON from environment variable")
            creds_dict = json.loads(creds_json_str)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            print("[DEBUG] Successfully created credentials from JSON")
        except Exception as e:
            print(f"[ERROR] Error parsing CREDENTIALS_JSON: {e}")
            raise RuntimeError(f"Invalid CREDENTIALS_JSON environment variable: {str(e)}")
    else:
        # Fallback to credentials.json file (local development)
        print("[DEBUG] CREDENTIALS_JSON not found, trying credentials.json file")
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
        if not os.path.exists(creds_path):
            print(f"[ERROR] Credentials file not found at: {creds_path}")
            raise RuntimeError(f"Credentials file not found: {creds_path}. Set CREDENTIALS_JSON environment variable for Railway.")
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        print(f"[DEBUG] Successfully loaded credentials from {creds_path}")
    
    client = gspread.authorize(creds)
    sheet_name = os.getenv("SHEET_NAME")
    if not sheet_name:
        raise RuntimeError("SHEET_NAME environment variable is not set")
    print(f"[DEBUG] Connecting to sheet: {sheet_name}")
    sheet = client.open(sheet_name).sheet1
    print("[DEBUG] Successfully connected to Google Sheet")
    return sheet


def detect_outcome(transcript: str, end_reason: str) -> str:
    """Derive a simple outcome label from transcript and end reason."""
    if not transcript or not transcript.strip():
        return "Wrong Number"

    t = transcript.lower()

    # Check for demo booked
    if "demo" in t:
        return "Demo Booked"

    # Check for interested
    if "interested" in t:
        return "Interested"

    # If the call was explicitly ended by customer, mark Not Interested
    if end_reason == "customer-ended-call":
        return "Not Interested"

    return "Unknown"


def create_summary(transcript: str) -> str:
    """Create a short summary: first 2 meaningful lines or first 200 chars."""
    if not transcript or not transcript.strip():
        return "No conversation recorded"

    lines = [ln.strip() for ln in transcript.splitlines() if ln.strip()]
    meaningful = [l for l in lines if len(l) > 10]
    if meaningful:
        summary = " | ".join(meaningful[:2])
        return summary[:200]

    # fallback to first 200 chars
    return transcript.strip()[:200]


@app.post("/webhook")
async def vapi_webhook(request: Request) -> Dict[str, Any]:
    # Receive and parse JSON
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    print("FULL DATA:", body)

    # Expecting structure with top-level "message"
    message = body.get("message") or {}
    if not message or message.get("type") != "end-of-call-report":
        return {"status": "ignored"}

    # Extract fields from message
    call = message.get("call", {})
    caller_number = call.get("customer", {}).get("number", "Unknown")

    duration_seconds = message.get("durationSeconds", 0)
    try:
        duration_seconds = float(duration_seconds)
    except Exception:
        duration_seconds = 0.0
    duration_mins = round(duration_seconds / 60.0, 2)

    transcript = message.get("transcript", "") or ""
    end_reason = message.get("endedReason", "unknown")
    try:
        cost = round(float(message.get("cost", 0)), 4)
    except Exception:
        cost = 0.0

    outcome = detect_outcome(transcript, end_reason)
    summary = create_summary(transcript)

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    # Append to Google Sheet
    try:
        sheet = get_sheet()
        row = [
            date_str,
            time_str,
            caller_number,
            duration_mins,
            outcome,
            summary,
            cost,
            transcript[:10000],
        ]
        # Use USER_ENTERED so numbers/dates are parsed by Sheets
        sheet.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        print(f"Sheet error: {e}")
        return {"status": "sheet_error", "error": str(e)}

    print(f"Logged call — {caller_number} | {outcome}")
    return {"status": "logged"}


@app.get("/")
def home() -> Dict[str, str]:
    return {"status": "PeakCAT Call Logger is running"}


@app.get("/debug")
def debug() -> Dict[str, str]:
    """Debug endpoint to check environment variables"""
    creds_json = os.getenv("CREDENTIALS_JSON")
    sheet_name = os.getenv("SHEET_NAME")
    return {
        "status": "debug",
        "SHEET_NAME": sheet_name or "NOT SET",
        "CREDENTIALS_JSON_length": str(len(creds_json)) if creds_json else "NOT SET",
        "PORT": os.getenv("PORT", "NOT SET")
    }