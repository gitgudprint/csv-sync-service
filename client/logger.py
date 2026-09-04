import json
from datetime import datetime, timezone
from pathlib import Path


class SyncLogger:
    def __init__(self, state_file: str | Path):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _load(self) -> dict:
        if not self.state_file.exists():
            return {}

        try:
            with self.state_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            return {}

        return {}

    def save(self) -> None:
        with self.state_file.open("w", encoding="utf-8") as handle:
            json.dump(self.state, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

    def mark(self, filename: str, server_key: str, status: str, sha256: str | None = None) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = self.state.setdefault(filename, {})
        entry[server_key] = {
            "status": status,
            "sha256": sha256,
            "timestamp": timestamp,
        }
        self.save()

    def get_status(self, filename: str, server_key: str) -> dict | None:
        return self.state.get(filename, {}).get(server_key)
