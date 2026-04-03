from fastapi import FastAPI, Request
import gspread
from google.oauth2.service_account import Credentials
import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Google Sheets setup
scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
client = gspread.authorize(creds)

sheet = client.open(os.getenv("SHEET_NAME")).sheet1


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    # Extract values safely
    caller = data.get("caller", "Unknown")
    duration = data.get("duration", 0)
    outcome = data.get("outcome", "Unknown")
    summary = data.get("summary", "No summary")
    cost = data.get("cost", 0)
    transcript = data.get("transcript", "")

    now = datetime.datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")

    # Append to Google Sheet
    sheet.append_row([
        date,
        time,
        caller,
        duration,
        outcome,
        summary,
        cost,
        transcript
    ])

    return {"status": "success"}