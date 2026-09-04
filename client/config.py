import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().with_name(".env"))


def _parse_csv_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


CSV_DIRECTORY = Path(os.getenv("CSV_DIRECTORY", r"C:\data\csv")).expanduser()
SERVER_URLS = _parse_csv_list(os.getenv("SERVER_URLS"))
API_KEY = os.getenv("API_KEY", "")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))
RETRY_COUNT = int(os.getenv("RETRY_COUNT", "3"))
STATE_FILE = Path(os.getenv("STATE_FILE", "sync_status.json")).expanduser()
UPLOAD_DIRECTORY = os.getenv("UPLOAD_DIRECTORY", "csv")
