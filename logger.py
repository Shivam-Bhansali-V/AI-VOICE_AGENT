from fastapi import FastAPI, Request, HTTPException
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
import os
import json
import tempfile
from typing import Any, Dict

# Load environment variables from multiple sources
load_dotenv()  # Load from .env (local dev)
load_dotenv('railway.env')  # Load from railway.env (production/deployment)

app = FastAPI()

# Google Sheets scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_sheet() -> Any:
    """Authorize and return the first worksheet of the spreadsheet named in SHEET_NAME."""
    print("[DEBUG] get_sheet() called")
    print(f"[DEBUG] Environment vars - CREDENTIALS_JSON exists: {'CREDENTIALS_JSON' in os.environ}")
    print(f"[DEBUG] Environment vars - SHEET_NAME: {os.getenv('SHEET_NAME')}")
    
    # Try to get credentials from environment variable first (Railway)
    creds_json_str = os.getenv("CREDENTIALS_JSON")
    print(f"[DEBUG] CREDENTIALS_JSON length: {len(creds_json_str) if creds_json_str else 0}")
    
    if creds_json_str and creds_json_str.strip():
        # Parse JSON from environment variable
        try:
            print("[DEBUG] Using CREDENTIALS_JSON from environment variable")
            creds_dict = json.loads(creds_json_str)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            print("[DEBUG] Successfully created credentials from JSON")
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON decode error: {e}")
            print(f"[ERROR] First 100 chars of CREDENTIALS_JSON: {creds_json_str[:100]}")
            raise RuntimeError(f"Invalid JSON in CREDENTIALS_JSON: {str(e)}")
        except Exception as e:
            print(f"[ERROR] Error parsing CREDENTIALS_JSON: {type(e).__name__}: {e}")
            raise RuntimeError(f"Invalid CREDENTIALS_JSON: {str(e)}")
    else:
        # Try credentials_runtime.json (Railway deployment)
        print("[DEBUG] CREDENTIALS_JSON not found or empty, trying credentials_runtime.json")
        if os.path.exists("credentials_runtime.json"):
            try:
                print("[DEBUG] Loading from credentials_runtime.json")
                creds = Credentials.from_service_account_file("credentials_runtime.json", scopes=SCOPES)
                print("[DEBUG] Successfully loaded credentials from credentials_runtime.json")
            except Exception as e:
                print(f"[ERROR] Error reading credentials_runtime.json: {e}")
                raise RuntimeError(f"Error reading credentials_runtime.json: {str(e)}")
        else:
            # Fallback to credentials.json file (local development)
            print("[DEBUG] credentials_runtime.json not found, trying credentials.json file")
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
            if not os.path.exists(creds_path):
                print(f"[ERROR] Credentials file not found at: {creds_path}")
                print(f"[ERROR] Current directory: {os.getcwd()}")
                print(f"[ERROR] Files in current dir: {os.listdir('.')}")
                raise RuntimeError(f"Credentials file not found. Set CREDENTIALS_JSON environment variable or ensure credentials_runtime.json exists.")
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
    """
    Derive outcome label from transcript and end reason.
    
    Logic:
    1. Check NEGATIVE phrases first (highest priority)
    2. Check DEMO with negation detection
    3. Check POSITIVE phrases
    4. Check for empty/short transcripts
    5. Default to Unknown
    """
    if not transcript or len(transcript.strip()) < 10:
        return "Wrong Number"

    t = transcript.lower()

    # ❌ NEGATIVE DETECTION - Check first (highest priority)
    negative_phrases = [
        "not interested",
        "don't want",
        "do not want",
        "no thanks",
        "not now",
        "already enrolled",
        "wrong number",
        "not suitable",
        "can't help",
        "busy now",
        "call later",
        "remove me",
        "stop calling"
    ]
    if any(phrase in t for phrase in negative_phrases):
        print(f"[DEBUG] Detected 'Not Interested' - matched negative phrase")
        return "Not Interested"

    # ✅ DEMO DETECTION - with negation checks
    if "demo" in t:
        # Check if demo is negated
        if "no demo" not in t and "don't want demo" not in t and "do not want demo" not in t and "without demo" not in t:
            print(f"[DEBUG] Detected 'Demo Booked' - found demo keyword")
            return "Demo Booked"

    # ✅ POSITIVE PHRASES DETECTION
    positive_phrases = [
        "interested",
        "tell me more",
        "sounds good",
        "call back",
        "want to know",
        "yes please",
        "absolutely",
        "definitely",
        "count me in",
        "sign me up",
        "book a demo",
        "scheduled",
        "confirmed"
    ]
    if any(phrase in t for phrase in positive_phrases):
        print(f"[DEBUG] Detected 'Interested' - matched positive phrase")
        return "Interested"

    # If call was ended by customer but no other signals detected
    # Don't auto-assume "Not Interested" - be conservative
    if end_reason == "customer-ended-call":
        print(f"[DEBUG] Call ended by customer but no outcome detected - marking Unknown")
        # Could be "Not Interested", but without explicit signals, mark Unknown
        # This avoids false negatives
        return "Unknown"

    print(f"[DEBUG] No outcome detected - marking Unknown")
    return "Unknown"


def create_summary(transcript: str) -> str:
    """
    Create a short summary from transcript.
    
    Logic:
    - Takes LAST 2 meaningful lines (end of call has actual outcome)
    - Not first 2 (which are usually "User: Hello" / "Agent: Hi")
    - Falls back to last 200 chars if not enough lines
    - Meaningful = lines with >10 characters
    """
    if not transcript or not transcript.strip():
        return "No conversation recorded"

    lines = [ln.strip() for ln in transcript.splitlines() if ln.strip()]
    meaningful = [l for l in lines if len(l) > 10]
    
    if meaningful:
        # Take LAST 2 meaningful lines (reversed), then reverse back to maintain order
        last_two = meaningful[-2:] if len(meaningful) >= 2 else meaningful
        summary = " | ".join(last_two)
        print(f"[DEBUG] Summary from last {len(last_two)} lines: {summary[:100]}")
        return summary[:200]

    # Fallback to last 200 chars
    return transcript.strip()[-200:] if len(transcript.strip()) > 200 else transcript.strip()


@app.post("/webhook")
async def vapi_webhook(request: Request) -> Dict[str, Any]:
    # Receive and parse JSON
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # ⚠️ IMPORTANT: Log full payload on first call to verify Vapi's exact structure
    print("\n" + "="*80)
    print("FULL WEBHOOK PAYLOAD FROM VAPI:")
    print(json.dumps(body, indent=2))
    print("="*80 + "\n")

    # Expecting structure with top-level "message"
    message = body.get("message") or {}
    if not message or message.get("type") != "end-of-call-report":
        print("[DEBUG] Ignoring non-call-report message")
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
    
    # ⚠️ COST FIELD: Log what we find for verification
    cost = 0.0
    cost_raw = message.get("cost", None)
    print(f"[DEBUG] Cost field from Vapi: {cost_raw} (type: {type(cost_raw).__name__})")
    if cost_raw is not None:
        try:
            cost = round(float(cost_raw), 4)
            print(f"[DEBUG] Successfully parsed cost as: {cost}")
        except Exception as e:
            print(f"[ERROR] Could not parse cost '{cost_raw}': {e}")
            cost = 0.0
    else:
        # Try alternative cost field names that Vapi might use
        for alt_field in ["totalCost", "callCost", "price", "amount"]:
            alt_cost = message.get(alt_field)
            if alt_cost is not None:
                print(f"[DEBUG] Found cost in alternative field '{alt_field}': {alt_cost}")
                try:
                    cost = round(float(alt_cost), 4)
                    break
                except Exception:
                    pass

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