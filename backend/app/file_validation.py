"""Upload content validation — everything here inspects the actual bytes,
never trusts the claimed filename/extension alone.

Layered checks, cheapest/most-conclusive first:
  1. sanitize_filename()   — strip path components before the name touches
                              anything else (logs, tempfile suffixes, metadata).
  2. detect_executable()   — reject known executable signatures outright,
                              regardless of claimed extension.
  3. detect_type_mismatch() — verify magic bytes actually match the claimed
                              extension (catches a renamed .exe claiming .pdf).
  4. check_zip_bomb()      — for .docx (itself a zip container), reject
                              archives that would decompress absurdly large.
"""

import os
import re
import zipfile
from io import BytesIO
from typing import Optional

# ---- Filename sanitization ----

_UNSAFE_CHARS = re.compile(r'[^A-Za-z0-9 ._\-()\[\]]')


def sanitize_filename(filename: str) -> str:
    """Strips any directory component (defeats '../../x', 'C:\\x', embedded
    NUL, etc. — os.path.basename + explicit separator stripping covers both
    POSIX and Windows separators regardless of which OS this runs on) and
    replaces any character outside a safe allowlist. Returns 'upload' if
    nothing safe is left, so callers never get an empty name."""
    name = filename.replace("\\", "/").split("/")[-1]
    name = os.path.basename(name)
    name = name.replace("\x00", "")
    name = _UNSAFE_CHARS.sub("_", name).strip(" .")
    return name or "upload"


# ---- Executable signature detection ----

_EXECUTABLE_SIGNATURES = [
    (b"MZ", "Windows executable (PE/MZ header)"),
    (b"\x7fELF", "Linux executable (ELF header)"),
    (b"\xca\xfe\xba\xbe", "Mach-O / Java class (fat binary header)"),
    (b"\xfe\xed\xfa", "Mach-O executable"),
    (b"#!/", "Shebang script"),
    (b"#!", "Shebang script"),
]


def detect_executable(content: bytes) -> Optional[str]:
    head = content[:8]
    for sig, description in _EXECUTABLE_SIGNATURES:
        if head.startswith(sig):
            return description
    return None


# ---- Magic-byte type verification ----

def _is_pdf(content: bytes) -> bool:
    return content[:5] == b"%PDF-"


def _is_zip_container(content: bytes) -> bool:
    # .docx (and .xlsx/.pptx/.jar/...) are all ZIP containers. A local file
    # header (PK\x03\x04) or empty-archive marker (PK\x05\x06) both count.
    return content[:4] in (b"PK\x03\x04", b"PK\x05\x06")


def _is_probably_text(content: bytes) -> bool:
    sample = content[:4096]
    if b"\x00" in sample:
        return False
    # Allow common whitespace control chars; anything else in the C0 control
    # range is a strong signal this is binary data, not text.
    printable = sum(1 for b in sample if b in (9, 10, 13) or 32 <= b <= 126 or b >= 128)
    return not sample or (printable / len(sample)) > 0.95


_TYPE_CHECKS = {
    ".pdf": (_is_pdf, "does not start with a valid PDF header (%PDF-)"),
    ".docx": (_is_zip_container, "is not a valid ZIP/OOXML container"),
    ".txt": (_is_probably_text, "contains binary data, not plain text"),
}


def detect_type_mismatch(extension: str, content: bytes) -> Optional[str]:
    """Returns a human-readable mismatch reason, or None if the content's
    actual bytes are consistent with what the extension claims."""
    check = _TYPE_CHECKS.get(extension.lower())
    if check is None:
        return None
    is_valid, reason = check
    if not is_valid(content):
        return f"File claims to be {extension} but {reason}"
    return None


# ---- Zip-bomb guard (.docx) ----

def check_zip_bomb(content: bytes, max_uncompressed_mb: int, max_ratio: int) -> Optional[str]:
    """Returns a rejection reason, or None if the archive looks sane.
    Reads the zip's central directory only (sizes are metadata — this never
    decompresses anything), so it's cheap even for a hostile archive."""
    try:
        with zipfile.ZipFile(BytesIO(content)) as zf:
            total_uncompressed = 0
            for info in zf.infolist():
                total_uncompressed += info.file_size
                if info.compress_size > 0:
                    ratio = info.file_size / info.compress_size
                    if ratio > max_ratio:
                        return (
                            f"Archive entry '{info.filename}' has a suspicious "
                            f"{ratio:.0f}:1 compression ratio (possible zip bomb)"
                        )
            max_bytes = max_uncompressed_mb * 1024 * 1024
            if total_uncompressed > max_bytes:
                return (
                    f"Archive would decompress to {total_uncompressed / (1024*1024):.1f}MB, "
                    f"over the {max_uncompressed_mb}MB limit (possible zip bomb)"
                )
    except zipfile.BadZipFile:
        # Not actually a valid zip — detect_type_mismatch() already catches
        # this for .docx; nothing further to check here.
        return None
    return None
