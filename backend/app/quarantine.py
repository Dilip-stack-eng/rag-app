"""On-disk storage for uploads — quarantine for rejected/suspicious files,
archive for accepted ones. Both:
  - live under backend/data/ (this app never serves static files, so neither
    directory is ever web-reachable — satisfies "store outside the web root"
    even though there's no literal web root here to escape)
  - use a random filename for the actual bytes on disk (never the user's
    filename — defeats overwrite games and keeps the filesystem name from
    ever being attacker-controlled)
  - write a JSON sidecar with the audit trail: sanitized original filename,
    reason, uploader, timestamp, size, sha256
  - log the action

Quarantined bytes are kept for admin review, not auto-deleted — they're
useful for investigating what someone tried to upload and why it was
rejected. Nothing outside app/quarantine.py ever needs to read them back.
"""

import hashlib
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from . import config

logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _store(base_dir: str, content: bytes, original_filename: str, reason: str, uploader: str) -> str:
    os.makedirs(base_dir, exist_ok=True)
    ext = os.path.splitext(original_filename)[1].lower()
    ext = ext if len(ext) <= 10 else ""  # ignore absurd/garbage "extensions"
    random_id = uuid.uuid4().hex
    data_path = Path(base_dir) / f"{random_id}{ext}.bin"
    meta_path = Path(base_dir) / f"{random_id}{ext}.json"

    data_path.write_bytes(content)
    meta = {
        "id": random_id,
        "original_filename": original_filename,
        "reason": reason,
        "uploader": uploader,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "Z",
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return random_id


def quarantine_file(content: bytes, original_filename: str, reason: str, uploader: str) -> str:
    random_id = _store(config.QUARANTINE_DIR, content, original_filename, reason, uploader)
    logger.warning(
        "Quarantined upload: id=%s original_filename=%s reason=%s uploader=%s size_bytes=%d",
        random_id, original_filename, reason, uploader, len(content),
    )
    return random_id


def archive_file(content: bytes, original_filename: str, uploader: str, reason: str = "accepted") -> str:
    random_id = _store(config.UPLOAD_ARCHIVE_DIR, content, original_filename, reason, uploader)
    logger.info(
        "Archived %s upload: id=%s original_filename=%s uploader=%s size_bytes=%d",
        reason, random_id, original_filename, uploader, len(content),
    )
    return random_id


def list_quarantined(limit: int = 100) -> list[dict]:
    quarantine_dir = Path(config.QUARANTINE_DIR)
    if not quarantine_dir.exists():
        return []
    entries = []
    for meta_path in quarantine_dir.glob("*.json"):
        try:
            entries.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return entries[:limit]


def _find_files(file_id: str) -> tuple[Optional[Path], Optional[Path]]:
    # file_id ends up in a glob pattern — reject anything that isn't exactly
    # the uuid4().hex shape _store() generates, so a crafted id can't be used
    # for path traversal or to match unintended files.
    if not _ID_RE.match(file_id):
        return None, None
    quarantine_dir = Path(config.QUARANTINE_DIR)
    if not quarantine_dir.exists():
        return None, None
    data_path = next(iter(quarantine_dir.glob(f"{file_id}*.bin")), None)
    meta_path = next(iter(quarantine_dir.glob(f"{file_id}*.json")), None)
    return data_path, meta_path


def get_quarantined_file(file_id: str) -> Optional[tuple[bytes, dict]]:
    """Returns (raw_bytes, metadata) for manual review, or None if unknown."""
    data_path, meta_path = _find_files(file_id)
    if not data_path or not meta_path:
        return None
    try:
        content = data_path.read_bytes()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return content, meta


def remove_from_quarantine(file_id: str) -> bool:
    """Removes a quarantine entry (both the bytes and the sidecar). Used both
    when a SuperAdmin releases a file for processing after manual review, and
    when one is permanently rejected. Returns False if the id wasn't found."""
    data_path, meta_path = _find_files(file_id)
    if not data_path and not meta_path:
        return False
    for path in (data_path, meta_path):
        if path and path.exists():
            path.unlink()
    logger.info("Quarantine entry removed: id=%s", file_id)
    return True
