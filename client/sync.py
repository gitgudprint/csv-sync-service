import sys
import hashlib
from io import BytesIO
from datetime import datetime, timezone, date
from pathlib import Path

import requests

from config import API_KEY, CSV_DIRECTORY, REQUEST_TIMEOUT, RETRY_COUNT, SERVER_URLS, STATE_FILE, UPLOAD_DIRECTORY
from logger import SyncLogger


ALLOWED_FILENAME_DATE_FORMATS = ("%d-%m", "%d-%m-%Y", "%Y-%m-%d")


def get_server_files(server_url: str, api_key: str, directory: str) -> dict[str, str] | None:
    """
    Query the server for existing files modified today and their checksums.
    Returns a dictionary mapping filename -> sha256, or None on error.
    """
    list_url = server_url.replace('/upload-csv', '/list-csv')
    today = date.today()
    
    try:
        response = requests.get(
            list_url,
            params={"directory": directory},
            headers={"X-API-Key": api_key},
            timeout=REQUEST_TIMEOUT,
            verify=True,
        )
        
        if 200 <= response.status_code < 300:
            try:
                payload = response.json()
                files_dict = {}
                for file_info in payload.get('files', []):
                    filename = file_info.get('filename')
                    sha256 = file_info.get('sha256')
                    modified = file_info.get('modified')
                    if not filename or not sha256 or modified is None:
                        continue

                    # Server pre-check only considers files modified today.
                    file_date = datetime.fromtimestamp(int(modified)).date()
                    if file_date == today:
                        files_dict[filename] = sha256
                return files_dict
            except ValueError:
                return None
        return None
    except requests.RequestException:
        return None


def discover_csv_files(csv_directory: Path) -> list[Path]:
    if not csv_directory.exists():
        return []
    return sorted(
        [path for path in csv_directory.rglob("*.csv") if path.is_file()],
        key=lambda item: str(item).lower(),
    )


def parse_date_from_filename(file_path: Path) -> date | None:
    stem = file_path.stem.strip()

    for fmt in ALLOWED_FILENAME_DATE_FORMATS:
        if fmt == "%d-%m":
            parts = stem.split("-")
            if len(parts) != 2:
                continue
            try:
                day = int(parts[0])
                month = int(parts[1])
                return date(date.today().year, month, day)
            except ValueError:
                continue

        try:
            parsed = datetime.strptime(stem, fmt)
            return parsed.date()
        except ValueError:
            continue

    return None


def filter_today_files(files: list[Path]) -> tuple[list[Path], list[Path]]:
    """
    Validate filename as date and keep only files with date equal to today.
    Returns a tuple: (valid_today_files, invalid_or_not_today_files).
    """
    today = date.today()
    today_files: list[Path] = []
    rejected_files: list[Path] = []

    for file_path in files:
        file_date = parse_date_from_filename(file_path)
        if file_date == today:
            today_files.append(file_path)

        else:
            rejected_files.append(file_path)

    return today_files, rejected_files


def server_label(index: int) -> str:
    return f"server_{index + 1}"


def submit_file(
    file_path: Path,
    file_bytes: bytes,
    server_url: str,
    local_sha256: str,
    logger: SyncLogger,
    server_name: str,
) -> bool:
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            file_stream = BytesIO(file_bytes)
            response = requests.post(
                server_url,
                files={"file": (file_path.name, file_stream, "text/csv")},
                data={"directory": UPLOAD_DIRECTORY},
                headers={"X-API-Key": API_KEY},
                timeout=REQUEST_TIMEOUT,
                verify=True,
            )

            payload = {}
            if response.headers.get("Content-Type", "").startswith("application/json"):
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}

            if 200 <= response.status_code < 300:
                server_sha256 = payload.get("sha256")
                if server_sha256 == local_sha256:
                    logger.mark(file_path.name, server_name, "success", server_sha256)
                    print(f"[{server_name}] SUCCESS - {file_path.name} - sha256 match")
                    return True

                logger.mark(file_path.name, server_name, "failed", server_sha256)
                print(f"[{server_name}] FAILED - {file_path.name} - checksum mismatch")
                print(f"[{server_name}] Local SHA: {local_sha256}")
                print(f"[{server_name}] Server SHA: {server_sha256}")
                if payload:
                    print(f"[{server_name}] Response: {payload}")
                else:
                    print(f"[{server_name}] Response body (first 300 chars): {response.text[:300]}")
                return False

            if response.status_code == 409:
                logger.mark(file_path.name, server_name, "conflict", payload.get("existing_sha256"))
                print(f"[{server_name}] CONFLICT - {file_path.name} - same name with different checksum")
                return False

            if attempt < RETRY_COUNT:
                print(f"[{server_name}] Retry {attempt}/{RETRY_COUNT} - HTTP {response.status_code} for {file_path.name}")
                continue

            logger.mark(file_path.name, server_name, "failed", None)
            print(f"[{server_name}] FAILED - {file_path.name} - HTTP {response.status_code}")
            return False

        except requests.exceptions.Timeout as exc:
            if attempt < RETRY_COUNT:
                print(f"[{server_name}] Retry {attempt}/{RETRY_COUNT} - timeout for {file_path.name}: {exc}")
                continue
            logger.mark(file_path.name, server_name, "failed", None)
            print(f"[{server_name}] FAILED - {file_path.name} - timeout")
            return False

        except requests.exceptions.ConnectionError as exc:
            if attempt < RETRY_COUNT:
                print(f"[{server_name}] Retry {attempt}/{RETRY_COUNT} - connection error for {file_path.name}: {exc}")
                continue
            logger.mark(file_path.name, server_name, "failed", None)
            print(f"[{server_name}] FAILED - {file_path.name} - connection error")
            return False

        except requests.RequestException as exc:
            if attempt < RETRY_COUNT:
                print(f"[{server_name}] Retry {attempt}/{RETRY_COUNT} - request error for {file_path.name}: {exc}")
                continue
            logger.mark(file_path.name, server_name, "failed", None)
            print(f"[{server_name}] FAILED - {file_path.name} - request error: {exc}")
            return False

    logger.mark(file_path.name, server_name, "failed", None)
    return False


def process_files() -> None:
    logger = SyncLogger(STATE_FILE)
    all_files = discover_csv_files(CSV_DIRECTORY)

    if not all_files:
        print(f"No .csv files found in {CSV_DIRECTORY}")
        return

    # Filter to only files whose filename date equals today.
    files, rejected_files = filter_today_files(all_files)

    for file_path in rejected_files:
        print(
            f"[REJECTED] {file_path.name} - format nama tidak sesuai dengan tanggal hari ini"
        )

    if not files:
        print(f"No .csv files with today's date in filename found in {CSV_DIRECTORY}")
        print(f"(Total files in directory: {len(all_files)})")
        return

    print(f"Processing {len(files)} file(s) from today (out of {len(all_files)} total)")

    file_snapshots: list[tuple[Path, bytes, str]] = []
    for file_path in files:
        file_bytes = file_path.read_bytes()
        local_sha256 = hashlib.sha256(file_bytes).hexdigest()
        file_snapshots.append((file_path, file_bytes, local_sha256))

    server_snapshots: dict[str, dict[str, str]] = {}
    for index, server_url in enumerate(SERVER_URLS):
        server_name = server_label(index)
        server_files = get_server_files(server_url, API_KEY, UPLOAD_DIRECTORY)

        if server_files is None:
            print(f"[{server_name}] WARNING - Could not query server folder, will attempt upload")
            server_snapshots[server_name] = {}
            continue

        server_snapshots[server_name] = server_files

    all_synced = True
    for file_path, _, local_sha256 in file_snapshots:
        for index, _ in enumerate(SERVER_URLS):
            server_name = server_label(index)
            server_sha256 = server_snapshots.get(server_name, {}).get(file_path.name)
            if server_sha256 != local_sha256:
                all_synced = False
                break
        if not all_synced:
            break

    if all_synced:
        print(
            f"All {len(file_snapshots)} today's file(s) already synced on "
            f"all {len(SERVER_URLS)} server(s). Nothing to upload."
        )
        return

    for file_path, file_bytes, local_sha256 in file_snapshots:
        file_mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
        print(f"\n=== File: {file_path.name} | SHA256: {local_sha256} | Modified: {file_mod_time.strftime('%Y-%m-%d %H:%M:%S')} ===")

        for index, server_url in enumerate(SERVER_URLS):
            server_name = server_label(index)

            # Check if file exists on server with matching checksum
            server_files = server_snapshots.get(server_name, {})
            if file_path.name in server_files:
                server_sha256 = server_files[file_path.name]
                if server_sha256 == local_sha256:
                    logger.mark(file_path.name, server_name, "success", server_sha256)
                    print(f"[{server_name}] VERIFIED - {file_path.name} already on server (checksum match)")
                    continue
                else:
                    print(f"[{server_name}] MISMATCH - {file_path.name} exists with different checksum")
                    print(f"[{server_name}] Local SHA: {local_sha256}")
                    print(f"[{server_name}] Server SHA: {server_sha256}")
                    logger.mark(file_path.name, server_name, "conflict", server_sha256)
                    continue

            print(f"[{server_name}] Sending to {server_url}")
            uploaded = submit_file(file_path, file_bytes, server_url, local_sha256, logger, server_name)
            if uploaded:
                server_snapshots.setdefault(server_name, {})[file_path.name] = local_sha256

        print("File processing complete")


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting CSV synchronization")
    try:
        if not API_KEY:
            raise ValueError("API_KEY is not configured.")
        if not SERVER_URLS:
            raise ValueError("SERVER_URLS is not configured.")

        process_files()
    except Exception as exc:
        print(f"Synchronization failed: {exc}", file=sys.stderr)
        sys.exit(1)
