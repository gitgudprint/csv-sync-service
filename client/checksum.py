import hashlib
from pathlib import Path


def sha256_file(file_path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
