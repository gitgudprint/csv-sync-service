# Windows CSV Sync Client

This client scans a local CSV directory and uploads each file to both configured HTTPS endpoints.

## Requirements

- Python 3.11+
- Windows 10 or 11
- `requests`
- Access to the target HTTPS API

## Setup

1. Create a virtual environment

```powershell
cd C:\tools\csv-sync
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and update the values

```env
CSV_DIRECTORY=C:\data\csv
SERVER_URLS=https://server-1.example.com/api/v1/upload-csv,https://server-2.example.com/api/v1/upload-csv
API_KEY=replace-with-a-long-random-api-key
REQUEST_TIMEOUT=60
RETRY_COUNT=3
STATE_FILE=sync_status.json
UPLOAD_DIRECTORY=csv
```

3. Run manually

```powershell
python sync.py
```

## Daily automatic execution

Use Windows Task Scheduler to run the script every day at a selected time.

Example task:

- Trigger: Daily at 01:00
- Action: Start a program
- Program/script: `C:\tools\csv-sync\.venv\Scripts\python.exe`
- Add arguments: `C:\tools\csv-sync\sync.py`
- Start in: `C:\tools\csv-sync`

## Retry and timeout behavior

- Timeout is 60 seconds by default
- If upload fails, the script retries up to `RETRY_COUNT`
- Successful uploads are validated against the SHA-256 checksum returned by the server
- If checksum does not match, the file is marked as failed

## Logging format

The client writes a JSON file named `sync_status.json` with the following structure:

```json
{
  "data.csv": {
    "server_1": {
      "status": "success",
      "sha256": "...",
      "timestamp": "2026-09-04T12:00:00+00:00"
    },
    "server_2": {
      "status": "failed",
      "sha256": null,
      "timestamp": "2026-09-04T12:05:00+00:00"
    }
  }
}
```

The client avoids re-uploading to a server that is already marked as successful.
