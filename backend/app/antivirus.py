"""YARA-based malware scanning — scans every uploaded file's raw bytes
against a bundled ruleset before it's ingested.

Replaces the earlier ClamAV integration: yara-python is a pip-installable
C extension with no external daemon/binary and no signature database to
manage, so it works on Render's native Python runtime without needing a
Docker image or apt-installed packages — the one requirement is that a
prebuilt wheel exists for the deployed Python version (true for common
versions on Linux; see README for the local Windows caveat).

Rule files live in backend/app/yara_rules/*.yar and are compiled once,
lazily, on first scan. Drop more .yar files into that directory to extend
coverage — no code changes needed. This starter ruleset (EICAR test-file
detection, embedded PE/ELF/Mach-O headers, suspicious script/macro/webshell
patterns, malicious PDF actions) is deliberately curated and NOT a
substitute for a continuously-updated multi-million-signature AV database —
treat it as one defense-in-depth layer alongside the file-type/magic-byte
and zip-bomb checks that already run before this.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config

logger = logging.getLogger(__name__)

try:
    import yara
    _YARA_IMPORT_ERROR: Optional[str] = None
except ImportError as e:
    yara = None
    _YARA_IMPORT_ERROR = str(e)
    logger.warning("yara-python is not installed (%s) — malware scanning will fail closed until it's installed.", e)

_RULES_DIR = Path(__file__).parent / "yara_rules"
_compiled_rules = None
_compile_error: Optional[str] = None


@dataclass
class ScanResult:
    clean: bool
    message: str


def _get_rules():
    """Compile all *.yar files in _RULES_DIR once and cache the result.
    Caches a compile error too, so a bad rule file doesn't retry-and-fail
    on every single upload."""
    global _compiled_rules, _compile_error
    if _compiled_rules is not None or _compile_error is not None:
        return _compiled_rules

    rule_files = sorted(_RULES_DIR.glob("*.yar"))
    if not rule_files:
        _compile_error = f"No YARA rule files found in {_RULES_DIR}"
        logger.error(_compile_error)
        return None

    try:
        _compiled_rules = yara.compile(filepaths={f.stem: str(f) for f in rule_files})
        logger.info("YARA rules compiled: files=%d names=%s", len(rule_files), [f.stem for f in rule_files])
    except yara.Error as e:
        _compile_error = f"Failed to compile YARA rules: {e}"
        logger.error(_compile_error)
        return None
    return _compiled_rules


def scan_bytes(content: bytes, filename: str) -> ScanResult:
    if not config.YARA_ENABLED:
        logger.warning("Scan skipped (YARA_ENABLED=false): filename=%s", filename)
        return ScanResult(True, "YARA scanning is disabled (YARA_ENABLED=false)")

    if yara is None:
        logger.error("Scan error: yara-python not installed, filename=%s", filename)
        return ScanResult(False, f"YARA scanner not installed (upload rejected): {_YARA_IMPORT_ERROR}")

    rules = _get_rules()
    if rules is None:
        return ScanResult(False, f"YARA scan error (upload rejected): {_compile_error}")

    try:
        matches = rules.match(data=content, timeout=config.YARA_TIMEOUT_SECONDS)
    except yara.Error as e:
        logger.error("Scan error: filename=%s detail=%s", filename, e)
        return ScanResult(False, f"YARA scan error (upload rejected): {e}")

    if matches:
        names = ", ".join(m.rule for m in matches)
        logger.warning("Scan MATCHED (rejected): filename=%s rules=%s", filename, names)
        return ScanResult(False, f"Malicious content detected (matched rule(s): {names})")

    logger.info("Scan clean: filename=%s size_bytes=%d", filename, len(content))
    return ScanResult(True, "clean")
