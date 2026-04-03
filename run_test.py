import subprocess
import time
import requests
import json
import sys

# Start the server
print("Starting FastAPI server...")
proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "logger:app", "--host", "127.0.0.1", "--port", "8000"], 
                       cwd=r"c:\Users\BhansaLi\peakcat-logger1")

# Wait for server to start
time.sleep(4)

try:
    # Load and send test payload
    with open(r"c:\Users\BhansaLi\peakcat-logger1\test_payload.json", "r") as f:
        payload = json.load(f)
    
    print("\n" + "="*60)
    print("SENDING TEST WEBHOOK:")
    print("="*60)
    print(json.dumps(payload, indent=2))
    print("="*60)
    
    # Send POST request
    response = requests.post("http://127.0.0.1:8000/webhook", json=payload, timeout=10)
    
    print("\nRESPONSE from /webhook:")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    print("="*60)
    
    if response.status_code == 200 and response.json().get("status") == "logged":
        print("✓ SUCCESS! Webhook was received and data logged to Google Sheet.")
        print("\nCheck your Google Sheet 'PeekCAT Call Logs' for a new row with:")
        print("  Caller: +919876543210")
        print("  Duration: 2.0 minutes")
        print("  Outcome: Demo Booked (contains 'demo' in transcript)")
        print("  Summary: First 2 lines of transcript")
    else:
        print("⚠ Unexpected response. Check server logs.")
        
finally:
    # Stop the server
    print("\nStopping server...")
    proc.terminate()
    proc.wait(timeout=5)
