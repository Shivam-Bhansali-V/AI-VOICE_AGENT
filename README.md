# PeakCAT Call Logger — quick start

This project exposes a webhook (`/webhook`) that logs incoming call reports to a Google Sheet.

Prerequisites
- Python 3.9+ installed
- Google service account JSON in `credentials.json` (already present in the repo)
- Share the target Google Sheet with the service account email from `credentials.json`

Install dependencies (PowerShell):

```powershell
python -m pip install --upgrade pip; python -m pip install -r requirements.txt
```

Create a `.env` file (copy `.env.example`) and set `SHEET_NAME` to the exact name of your Google Sheet (the name shown in Google Drive).

Run the app (PowerShell):

```powershell
# From project root
$env:PORT = (Get-Content .env | Select-String "PORT").ToString().Split('=')[1].Trim()  # optional
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Expose the local server publicly (ngrok):

```powershell
ngrok http 8000
```

Use the ngrok public URL + `/webhook` as the webhook URL in your vapi provider.

Notes & checks
- Ensure `credentials.json` is not shared publicly. It contains a private key.
- Share the target Google Sheet with the `client_email` value in `credentials.json` (e.g. `peakcat-logger@...`)
- If your provider sends a different JSON shape, adapt `main.py`/`logger.py` to match the keys.

If you want, I can:
- Update `main.py` to read credentials from an env var instead of a file.
- Add better error handling and tests.
- Deploy this to a small cloud VM or serverless endpoint so you don’t need ngrok.
