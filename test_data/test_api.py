"""End-to-end tests against a running Athena backend — exercises the
existing feature set (auth, upload validation/YARA, RAG query, quarantine)
plus the AI features (quarantine AI triage and the AI security digest).

These are integration tests, not unit tests: they need a real backend
process already running, talking to a real Gemini API key, with its own
real Chroma/quarantine/login-throttle state. They mutate that state
(uploads add real chunks to the vector store, failed logins are recorded
by the real login-throttle) — run them against a dev/test backend, not a
production one you care about staying pristine.

Run with (from the repo root):
    uv run pytest test_data/test_api.py -v

Config (env vars, all optional — defaults match this repo's own .env.example):
    ATHENA_TEST_BACKEND_URL       default http://localhost:8000
    ATHENA_TEST_SUPERADMIN_USERNAME / ATHENA_TEST_SUPERADMIN_PASSWORD
    ATHENA_TEST_ADMIN_USERNAME / ATHENA_TEST_ADMIN_PASSWORD

AI-dependent tests (quarantine explain, security digest) call pytest.skip()
rather than failing outright if the backend reports the feature
unavailable (HTTP 503) — a missing GEMINI_API_KEY is a supported degraded
mode for this app (every AI feature here is designed to fail closed to a
plain/deterministic fallback), not a bug worth a red X.

Deliberately never uses the real SUPERADMIN_/ADMIN username for a *wrong*-
password attempt — every failed-login test uses a random throwaway
username instead, so running this suite repeatedly can never accidentally
burn through the real account's 3-attempt lockout budget.
"""

import os
import uuid
from pathlib import Path

import pytest
import requests

BACKEND_URL = os.getenv("ATHENA_TEST_BACKEND_URL", "http://localhost:8000")
SUPERADMIN_USERNAME = os.getenv("ATHENA_TEST_SUPERADMIN_USERNAME", "SuperAdmin")
SUPERADMIN_PASSWORD = os.getenv("ATHENA_TEST_SUPERADMIN_PASSWORD", "12345")
ADMIN_USERNAME = os.getenv("ATHENA_TEST_ADMIN_USERNAME", "ADMIN")
ADMIN_PASSWORD = os.getenv("ATHENA_TEST_ADMIN_PASSWORD", "12345")

FIXTURES = Path(__file__).parent / "fixtures"

_SECURITY_LOG_KEYWORDS = (
    "Authentication failed", "Authentication succeeded", "Account locked",
    "Lockout expired", "Token rejected", "Invalid authentication token",
    "Session expired", "Request rejected", "Authorization denied",
    "Failed login recorded", "Scan INFECTED", "Scan error", "Sending lockout alert",
    "Quarantined upload", "Filename sanitized",
)


def _login(username: str, password: str) -> requests.Response:
    return requests.post(
        f"{BACKEND_URL}/auth/login", json={"username": username, "password": password}, timeout=10
    )


def _upload(headers: dict, filename: str, content: bytes) -> requests.Response:
    return requests.post(
        f"{BACKEND_URL}/upload", files={"file": (filename, content)}, headers=headers, timeout=30
    )


@pytest.fixture(scope="session")
def superadmin_headers() -> dict:
    resp = _login(SUPERADMIN_USERNAME, SUPERADMIN_PASSWORD)
    assert resp.status_code == 200, f"SuperAdmin login failed — check ATHENA_TEST_SUPERADMIN_* env vars: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_headers() -> dict:
    resp = _login(ADMIN_USERNAME, ADMIN_PASSWORD)
    assert resp.status_code == 200, f"ADMIN login failed — check ATHENA_TEST_ADMIN_* env vars: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------- Health ----------


def test_health():
    resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------- Auth ----------


def test_login_success(superadmin_headers):
    assert "Authorization" in superadmin_headers  # fixture already asserted the login itself


def test_login_wrong_password_rejected():
    # Random throwaway username — never the real SUPERADMIN_/ADMIN account,
    # so repeated test runs can't accumulate toward its real lockout.
    resp = _login(f"pytest_baduser_{uuid.uuid4().hex[:8]}", "wrong-password")
    assert resp.status_code == 401


def test_protected_endpoint_requires_auth():
    resp = requests.get(f"{BACKEND_URL}/documents", timeout=5)
    assert resp.status_code == 401


def test_login_lockout_after_three_failures():
    """3 fast wrong-password attempts against the SAME username should
    lock it (429), matching login_throttle.MAX_ATTEMPTS — using a random
    throwaway username, never a real account."""
    username = f"pytest_lockout_{uuid.uuid4().hex[:8]}"
    statuses = [_login(username, "wrong").status_code for _ in range(3)]
    assert statuses[-1] == 429, f"expected the 3rd attempt to be locked (429), got {statuses}"


# ---------- Upload / YARA / validation pipeline ----------


def test_upload_clean_txt_succeeds(superadmin_headers):
    content = (FIXTURES / "sample_doc.txt").read_bytes()
    resp = _upload(superadmin_headers, f"pytest_sample_{uuid.uuid4().hex[:6]}.txt", content)
    assert resp.status_code == 200, resp.text
    assert resp.json()["chunks_added"] > 0


def test_upload_clean_docx_succeeds(superadmin_headers):
    content = (FIXTURES / "sample_doc.docx").read_bytes()
    resp = _upload(superadmin_headers, f"pytest_sample_{uuid.uuid4().hex[:6]}.docx", content)
    assert resp.status_code == 200, resp.text
    assert resp.json()["chunks_added"] > 0


def test_upload_eicar_rejected_by_yara(superadmin_headers):
    content = (FIXTURES / "eicar_test.txt").read_bytes()
    resp = _upload(superadmin_headers, f"pytest_eicar_{uuid.uuid4().hex[:6]}.txt", content)
    assert resp.status_code == 422, resp.text
    assert "EICAR" in resp.text or "Malicious" in resp.text


def test_upload_type_mismatch_rejected(superadmin_headers):
    content = (FIXTURES / "type_mismatch.pdf").read_bytes()
    resp = _upload(superadmin_headers, f"pytest_fake_{uuid.uuid4().hex[:6]}.pdf", content)
    assert resp.status_code == 415, resp.text
    assert "PDF" in resp.text


def test_upload_fake_executable_rejected(superadmin_headers):
    content = (FIXTURES / "fake_executable.txt").read_bytes()
    resp = _upload(superadmin_headers, f"pytest_fakeexe_{uuid.uuid4().hex[:6]}.txt", content)
    assert resp.status_code == 415, resp.text
    assert "executable" in resp.text.lower()


def test_upload_requires_superadmin(admin_headers):
    """ADMIN (not SuperAdmin) must be forbidden from /upload."""
    content = (FIXTURES / "sample_doc.txt").read_bytes()
    resp = _upload(admin_headers, f"pytest_admin_attempt_{uuid.uuid4().hex[:6]}.txt", content)
    assert resp.status_code == 403


# ---------- RAG query ----------


def test_query_answers_from_uploaded_doc(superadmin_headers):
    # Re-uploading is idempotent enough for this check (just adds another
    # copy of the same chunks) — guarantees the fixture content is actually
    # in the vector store regardless of test execution order.
    content = (FIXTURES / "sample_doc.txt").read_bytes()
    _upload(superadmin_headers, f"pytest_sample_{uuid.uuid4().hex[:6]}.txt", content)

    resp = requests.post(
        f"{BACKEND_URL}/query",
        json={"question": "How many days per week can employees work remotely?"},
        headers=superadmin_headers,
        timeout=60,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answer"]
    assert body["sources"], "expected at least one cited source"


def test_query_greeting_shortcut_skips_retrieval(superadmin_headers):
    resp = requests.post(
        f"{BACKEND_URL}/query", json={"question": "hello"}, headers=superadmin_headers, timeout=15
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sources"] == []
    assert body["chunks"] == []


# ---------- Quarantine + AI malware triage ----------


def test_quarantine_list(superadmin_headers):
    resp = requests.get(f"{BACKEND_URL}/quarantine", headers=superadmin_headers, timeout=10)
    assert resp.status_code == 200
    assert "files" in resp.json()


def test_quarantine_ai_explain(superadmin_headers):
    """Upload something guaranteed to be quarantined, then ask for the AI
    explanation of it. Skipped (not failed) if Gemini isn't configured."""
    content = (FIXTURES / "eicar_test.txt").read_bytes()
    upload_resp = _upload(superadmin_headers, f"pytest_eicar_{uuid.uuid4().hex[:6]}.txt", content)
    assert upload_resp.status_code == 422

    q_resp = requests.get(f"{BACKEND_URL}/quarantine", headers=superadmin_headers, timeout=10)
    files = q_resp.json()["files"]
    assert files, "expected at least one quarantined file after the EICAR upload above"
    quarantine_id = files[0]["id"]

    explain_resp = requests.post(
        f"{BACKEND_URL}/quarantine/{quarantine_id}/explain", headers=superadmin_headers, timeout=30
    )
    if explain_resp.status_code == 503:
        pytest.skip("AI quarantine explanation unavailable (GEMINI_API_KEY not configured on backend)")
    assert explain_resp.status_code == 200, explain_resp.text
    body = explain_resp.json()
    assert body["confidence"] in ("high", "medium", "low")
    assert body["explanation"]


# ---------- AI security digest ----------


def test_security_digest(superadmin_headers):
    """Generates a bit of fresh security-relevant log activity, fetches +
    filters recent logs exactly like the frontend's Security page does,
    then asks for an AI digest and checks it's non-empty text. Skipped
    (not failed) if Gemini isn't configured on the backend."""
    _login(f"pytest_digest_probe_{uuid.uuid4().hex[:6]}", "wrong")

    logs_resp = requests.get(
        f"{BACKEND_URL}/logs/recent", params={"limit": 300}, headers=superadmin_headers, timeout=10
    )
    assert logs_resp.status_code == 200
    lines = logs_resp.json()["lines"]
    security_lines = [line for line in lines if any(k in line for k in _SECURITY_LOG_KEYWORDS)]
    assert security_lines, "expected at least one security-relevant log line"

    resp = requests.post(
        f"{BACKEND_URL}/security/digest",
        json={"log_lines": security_lines},
        headers=superadmin_headers,
        timeout=30,
    )
    if resp.status_code == 503:
        pytest.skip("AI security digest unavailable (GEMINI_API_KEY not configured on backend)")
    assert resp.status_code == 200, resp.text
    digest = resp.json()["digest"]
    assert isinstance(digest, str) and len(digest) > 20


def test_security_digest_empty_log_lines_rejected(superadmin_headers):
    resp = requests.post(
        f"{BACKEND_URL}/security/digest", json={"log_lines": []}, headers=superadmin_headers, timeout=10
    )
    assert resp.status_code == 503


def test_security_digest_requires_superadmin(admin_headers):
    resp = requests.post(
        f"{BACKEND_URL}/security/digest", json={"log_lines": ["dummy"]}, headers=admin_headers, timeout=10
    )
    assert resp.status_code == 403


# ---------- Token usage ----------


def test_token_usage_status(superadmin_headers):
    resp = requests.get(f"{BACKEND_URL}/token-usage", headers=superadmin_headers, timeout=10)
    assert resp.status_code == 200
    body = resp.json()
    assert {"used", "limit", "remaining"} <= body.keys()


# ---------- System info ----------


def test_system_info(superadmin_headers):
    resp = requests.get(f"{BACKEND_URL}/system-info", headers=superadmin_headers, timeout=10)
    assert resp.status_code == 200
    assert resp.json()["yara_enabled"] is True
