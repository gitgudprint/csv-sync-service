# Local API Smoke Test

Run the Laravel API smoke test on macOS:

```bash
cd /Users/codero/File\ Sync\ +\ FAST\ API
chmod +x scripts/local_api_smoke_test.sh
scripts/local_api_smoke_test.sh
```

Environment overrides (optional):

- `PHP_BIN` (default: `/opt/homebrew/bin/php`)
- `API_KEY` (default: `local-test-key`)
- `UPLOAD_DIR` (default: `csv`)

Example:

```bash
API_KEY=my-local-key PHP_BIN=/opt/homebrew/bin/php scripts/local_api_smoke_test.sh
```

## Upload Real CSV to Dummy Server Directory

Use this when you want to test with an actual CSV file and verify it is stored in a dummy destination folder that simulates a server path.

```bash
cd /Users/codero/File\ Sync\ +\ FAST\ API
chmod +x scripts/upload_real_file_test.sh
scripts/upload_real_file_test.sh /tmp/test.csv dummy-server-inbox
```

Result checks:

- API response status is `success` or `already_exists`
- API `sha256` matches local file checksum
- File exists in dummy directory under `/tmp/csv-sync-upload/<dummy-directory>/`
- Stored file checksum matches local checksum

Optional overrides:

- `API_KEY`
- `PORT`
- `UPLOAD_ROOT` (default `/tmp/csv-sync-upload`)
- `PHP_BIN`
- `PYTHON_BIN`
