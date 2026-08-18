# test_data

Fixtures and an end-to-end pytest suite for exercising Athena's API
directly — existing features (auth, upload validation/YARA, RAG query,
quarantine) plus the AI features (quarantine AI triage, AI security
digest).

## Fixtures (`fixtures/`)

| File | Purpose |
|---|---|
| `sample_doc.txt` | Clean text document — normal RAG upload/query path |
| `sample_doc.docx` | Clean `.docx` — exercises the docx extraction path |
| `eicar_test.txt` | Standard EICAR antivirus test string — YARA should reject it (`av_scan`), same as real malware would be, without using actual malware |
| `type_mismatch.pdf` | Plain text wearing a `.pdf` extension — should trip the magic-byte check before ever reaching YARA |
| `fake_executable.txt` | Starts with a Windows `MZ` header despite the `.txt` name — should trip `detect_executable()` regardless of claimed extension |

You can also upload these by hand through the Knowledge Base page to see
the same checks fire in the UI.

## Automated tests (`test_api.py`)

Integration tests against a **real, running backend** — not mocks. Run
from the repo root:

```
uv run pytest test_data/test_api.py -v
```

Needs:
- The backend running (default `http://localhost:8000`; override with `ATHENA_TEST_BACKEND_URL`)
- SuperAdmin/ADMIN credentials matching that backend (defaults: `SuperAdmin`/`12345`, `ADMIN`/`12345` — override with `ATHENA_TEST_SUPERADMIN_USERNAME` / `ATHENA_TEST_SUPERADMIN_PASSWORD` / `ATHENA_TEST_ADMIN_USERNAME` / `ATHENA_TEST_ADMIN_PASSWORD`)
- `GEMINI_API_KEY` configured on that backend for the AI-dependent tests (quarantine explain, security digest) — those `pytest.skip()` rather than fail if it's missing, since that's a supported degraded mode for every AI feature in this app, not a bug

Things worth knowing before you run it:
- **Mutates real state.** Uploads add real chunks to the vector store, failed logins are recorded by the real login-throttle. Point it at a dev backend, not one you need to stay pristine.
- **Never touches the real SuperAdmin/ADMIN account's lockout budget.** Every failed-login test uses a random throwaway username instead — running the suite repeatedly can't accidentally lock you out of your own account.
- **No cleanup step.** There's no "delete a single document" endpoint to undo test uploads with (only delete-*all*, which the suite deliberately never calls), so repeated runs accumulate a few extra chunks/quarantine entries over time. Harmless for a dev backend.

**Last verified:** all 20 tests pass against a live backend with `GEMINI_API_KEY` configured (2026-08-17).
