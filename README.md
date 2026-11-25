# CSV Sync Service

A Windows machine exports CSV reports every day, and one or more Linux servers need a copy. This project moves those files automatically. A Python client picks up the day's CSV files and uploads them to a Laravel API on each server. The server checks every file with a SHA-256 checksum, so a report is never stored twice and a corrupted upload is caught.

I built it while working on HR data automation, where daily exports from one system had to reach other servers without someone copying them by hand.

## Built with

Python 3.11 (`requests`, `python-dotenv`) for the client, which runs on Windows through Task Scheduler. Laravel 11 on PHP 8.3 for the server API, behind Nginx on Ubuntu.

## How it works

1. Windows Task Scheduler starts `client/sync.py` once a day.
2. The client finds CSV files whose name is today's date (`DD-MM`, `DD-MM-YYYY` or `YYYY-MM-DD`) and skips the rest.
3. For each server, it asks the API which of today's files it already has and their checksums, then uploads only what is missing.
4. The server saves the file and returns its SHA-256. The client compares it with its own checksum and marks the upload as failed if they differ.
5. Results are written to a local JSON state file, so a second run the same day does not upload a file again to a server that already confirmed it.

## What makes it more than a copy script

- It uploads to several servers in one run and tracks success separately for each one.
- Failed requests (timeouts, connection errors, server errors) are retried up to a configurable number of times.
- Uploads are idempotent. Sending the same file again returns `already_exists`. A different file with the same name is rejected as a conflict instead of overwriting the original.
- The API accepts requests only with a valid `X-API-Key` header and only from whitelisted IP addresses.
- The server validates that uploads are CSV and blocks path traversal in file names.

The client is about 370 lines of Python. The API is a Laravel controller with two endpoints (`GET /api/v1/list-csv`, `POST /api/v1/upload-csv`), two middleware classes for the API key and the IP whitelist, and a checksum service.

## Repository layout

```
client/          Python sync client (sync.py, config.py, checksum.py, logger.py)
server/          Laravel API code to copy into a Laravel 11 project on the server
server-local/    Full Laravel project used for local testing
scripts/         Shell scripts for local smoke tests of the API
```

## Running it

Client (Windows):

```powershell
cd client
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then set CSV_DIRECTORY, SERVER_URLS and API_KEY
python sync.py
```

Server setup, including the Nginx and PHP packages and the `.env` values for the API key and allowed IPs, is in [`server/README.md`](server/README.md). Local API tests are described in [`scripts/README.md`](scripts/README.md).
