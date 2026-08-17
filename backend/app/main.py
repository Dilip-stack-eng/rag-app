import io
import logging
import os
import time
import uuid
from typing import List, Optional

from docx import Document as DocxDocument
from fastapi import Depends, FastAPI, Request, Response, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader

from . import rag, config, alerts, auth, users, antivirus, login_throttle, logging_config, quarantine, token_usage
from .chunking import chunk_text
from .file_validation import (
    check_zip_bomb,
    detect_executable,
    detect_type_mismatch,
    sanitize_filename,
)

ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".pdf", ".docx"}
# Added on top of the estimated prompt cost in the /query pre-flight quota
# check, since even a small prompt can still produce a sizeable response.
_RESPONSE_TOKEN_BUFFER = 100

logger = logging.getLogger(__name__)

app = FastAPI(title="Simple RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.monotonic() - start) * 1000
        logger.exception(
            "%s %s -> unhandled exception (%.1fms) client=%s",
            request.method, request.url.path, duration_ms, request.client.host if request.client else "-",
        )
        raise
    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "%s %s -> %d (%.1fms) client=%s",
        request.method, request.url.path, response.status_code, duration_ms,
        request.client.host if request.client else "-",
    )
    return response


@app.on_event("startup")
def _log_startup_config():
    logger.info(
        "Backend starting: llm_model=%s embed_model=%s prompt_version=%s top_k=%d "
        "yara_enabled=%s jwt_expiry_minutes=%d",
        config.LLM_MODEL, config.EMBED_MODEL, config.PROMPT_VERSION, config.TOP_K,
        config.YARA_ENABLED, config.JWT_EXPIRY_MINUTES,
    )


class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = None
    prompt_version: Optional[str] = None


class RetrievedChunk(BaseModel):
    source: str
    chunk: int
    text: str


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    chunks: List[RetrievedChunk]


class AddUserRequest(BaseModel):
    username: str
    password: str
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class TokenLimitRequest(BaseModel):
    daily_limit: int


ANY_ROLE = Depends(auth.require_role("ADMIN", "SuperAdmin"))
SUPERADMIN_ONLY = Depends(auth.require_role("SuperAdmin"))


def extract_text(filename: str, content: bytes) -> str:
    """Raises ValueError (never the underlying library exception) if the file
    claims an extension it doesn't actually contain valid content for —
    e.g. a corrupt PDF or a renamed non-DOCX file — so callers can turn
    that into a clean 400 instead of a 500."""
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise ValueError(f"Could not read PDF file: {e}") from e

    if ext == ".docx":
        try:
            doc = DocxDocument(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            raise ValueError(f"Could not read DOCX file: {e}") from e

    # .txt — the only extension left once /upload has enforced the whitelist.
    return content.decode("utf-8", errors="ignore")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    locked, remaining_seconds = login_throttle.is_locked(req.username)
    if locked:
        raise HTTPException(429, f"Account locked. Try again in {remaining_seconds}s.")

    role = auth.authenticate_user(req.username, req.password)
    if role is None:
        just_locked, attempts_left = login_throttle.record_failure(req.username)
        if just_locked:
            alerts.send_lockout_alert(req.username)
            raise HTTPException(
                429,
                f"Account locked after {login_throttle.MAX_ATTEMPTS} failed attempts. "
                f"Try again in {login_throttle.LOCKOUT_SECONDS}s.",
            )
        raise HTTPException(401, f"Invalid username or password. {attempts_left} attempt(s) remaining.")

    login_throttle.record_success(req.username)
    token = auth.create_token(req.username, role)
    return LoginResponse(access_token=token, username=req.username, role=role)


@app.post("/upload")
async def upload(file: UploadFile = File(...), _user: dict = SUPERADMIN_ONLY):
    uploader = _user["username"]

    # 1. Filename sanitization first — nothing derived from the raw,
    #    attacker-controlled filename (extension checks, tempfile suffixes,
    #    stored metadata) touches it before this.
    raw_filename = file.filename or ""
    filename = sanitize_filename(raw_filename)
    if filename != raw_filename:
        logger.info("Filename sanitized: raw=%r -> %r", raw_filename, filename)

    # 2. Extension whitelist (executables, scripts, archives etc. are never
    #    accepted — nothing further is needed to "reject executables if not
    #    required", since only .txt/.pdf/.docx can pass this at all).
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        logger.warning("Upload rejected: filename=%s reason=unsupported_extension", filename)
        raise HTTPException(
            415,
            f"Unsupported file type '{ext or '(none)'}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    logger.info(
        "Upload received: filename=%s size_bytes=%d by user=%s", filename, len(content), uploader
    )

    # 3. Size limit — reject before any expensive processing (AV scan,
    #    parsing, embedding) even starts.
    if size_mb > config.MAX_UPLOAD_SIZE_MB:
        logger.warning(
            "Upload rejected: filename=%s reason=too_large size_mb=%.1f limit_mb=%d",
            filename, size_mb, config.MAX_UPLOAD_SIZE_MB,
        )
        raise HTTPException(413, f"File exceeds the {config.MAX_UPLOAD_SIZE_MB}MB upload limit")

    # 4. Executable-signature check — regardless of claimed extension, catches
    #    a disguised binary (e.g. a PE/ELF/script renamed to .pdf).
    exe_kind = detect_executable(content)
    if exe_kind:
        quarantine.quarantine_file(content, filename, f"executable_content:{exe_kind}", uploader)
        logger.warning("Upload rejected: filename=%s reason=executable_content kind=%s", filename, exe_kind)
        raise HTTPException(415, f"Rejected: file contains executable content ({exe_kind})")

    # 5. Magic-byte verification — the claimed extension must match what the
    #    bytes actually are (catches a renamed non-PDF/non-DOCX/binary file).
    mismatch = detect_type_mismatch(ext, content)
    if mismatch:
        quarantine.quarantine_file(content, filename, f"type_mismatch:{mismatch}", uploader)
        logger.warning("Upload rejected: filename=%s reason=type_mismatch detail=%s", filename, mismatch)
        raise HTTPException(415, mismatch)

    # 6. YARA malware scan.
    scan = antivirus.scan_bytes(content, filename)
    if not scan.clean:
        quarantine.quarantine_file(content, filename, f"av_scan:{scan.message}", uploader)
        logger.warning("Upload rejected: filename=%s reason=%s", filename, scan.message)
        raise HTTPException(422, scan.message)

    # 7. Zip-bomb guard for .docx (itself a zip archive).
    if ext == ".docx":
        bomb_reason = check_zip_bomb(content, config.MAX_DOCX_UNCOMPRESSED_MB, config.MAX_ZIP_COMPRESSION_RATIO)
        if bomb_reason:
            quarantine.quarantine_file(content, filename, f"zip_bomb:{bomb_reason}", uploader)
            logger.warning("Upload rejected: filename=%s reason=zip_bomb detail=%s", filename, bomb_reason)
            raise HTTPException(400, bomb_reason)

    try:
        text = extract_text(filename, content)
    except ValueError as e:
        quarantine.quarantine_file(content, filename, f"parse_error:{e}", uploader)
        logger.warning("Upload rejected: filename=%s reason=parse_error detail=%s", filename, e)
        raise HTTPException(400, str(e))

    chunks = chunk_text(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    if not chunks:
        logger.warning("Upload rejected: filename=%s reason=no_extractable_text", filename)
        raise HTTPException(400, "No extractable text in file")

    # 8. Only now, once fully validated, persist a copy under a random
    #    filename (never the user's filename) and ingest.
    quarantine.archive_file(content, filename, uploader)
    doc_id = str(uuid.uuid4())
    rag.add_chunks(doc_id, filename, chunks)
    return {"filename": filename, "chunks_added": len(chunks)}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, _user: dict = ANY_ROLE):
    username = _user["username"]
    truncated = req.question if len(req.question) <= 300 else req.question[:300] + "…"
    logger.info("Query received from user=%s question=%r", username, truncated)

    greeting = rag.greeting_reply(req.question)
    if greeting:
        return QueryResponse(answer=greeting, sources=[], chunks=[])

    remaining = token_usage.remaining_today(username)
    if remaining <= 0:
        limit = token_usage.get_daily_limit()
        logger.warning("Token quota exceeded: user=%s daily_limit=%d", username, limit)
        return QueryResponse(
            answer=(
                f"⚠️ You've reached today's token limit ({limit:,} tokens). "
                "It resets at midnight UTC — or ask a SuperAdmin to raise the limit."
            ),
            sources=[], chunks=[],
        )

    documents, metadatas = rag.query(req.question, req.top_k)
    if not documents:
        return QueryResponse(answer="No documents ingested yet.", sources=[], chunks=[])

    # A "remaining > 0" check alone lets one query fully run and blow past a
    # tiny remaining budget, since the real cost isn't known until after the
    # LLM call — the very next query would then get blocked, but this one
    # wouldn't. Estimate this specific request's cost first and block it
    # up front if it clearly can't fit, instead of only catching it a query late.
    estimated_tokens = rag.estimate_tokens(req.question + "".join(documents)) + _RESPONSE_TOKEN_BUFFER
    if estimated_tokens > remaining:
        limit = token_usage.get_daily_limit()
        logger.warning(
            "Token quota pre-check failed: user=%s remaining=%d estimated_needed=%d",
            username, remaining, estimated_tokens,
        )
        return QueryResponse(
            answer=(
                f"⚠️ This question would need roughly {estimated_tokens:,} tokens, but you only have "
                f"{remaining:,} of your {limit:,} daily tokens left. It resets at midnight UTC — "
                "or ask a SuperAdmin to raise the limit."
            ),
            sources=[], chunks=[],
        )

    answer, tokens_used = rag.generate_answer(req.question, documents, req.prompt_version)
    if tokens_used:
        token_usage.record_usage(username, tokens_used)
    sources = sorted({m["source"] for m in metadatas})
    chunks = [
        RetrievedChunk(source=m["source"], chunk=m["chunk"], text=doc)
        for doc, m in zip(documents, metadatas)
    ]
    return QueryResponse(answer=answer, sources=sources, chunks=chunks)


@app.get("/documents")
def documents(_user: dict = ANY_ROLE):
    return {"sources": rag.list_sources()}


@app.get("/prompt-versions")
def prompt_versions(_user: dict = ANY_ROLE):
    return {"versions": rag.list_prompt_versions(), "default": rag.default_prompt_version()}


@app.delete("/documents")
def clear_documents(_user: dict = SUPERADMIN_ONLY):
    logger.warning("All documents cleared by user=%s", _user["username"])
    rag.delete_all()
    return {"status": "cleared"}


@app.get("/users")
def list_users(_user: dict = SUPERADMIN_ONLY):
    return {"users": users.list_users()}


@app.post("/users")
def add_user(req: AddUserRequest, _user: dict = SUPERADMIN_ONLY):
    try:
        users.add_user(req.username, req.password, req.role)
    except ValueError as e:
        raise HTTPException(400, str(e))
    logger.info("User '%s' (role=%s) created by admin=%s", req.username, req.role, _user["username"])
    return {"status": "created", "username": req.username, "role": req.role}


@app.get("/system-info")
def system_info(_user: dict = SUPERADMIN_ONLY):
    return {
        "llm_model": config.LLM_MODEL,
        "embed_model": config.EMBED_MODEL,
        "llm_num_predict": config.LLM_NUM_PREDICT,
        "chunk_size": config.CHUNK_SIZE,
        "chunk_overlap": config.CHUNK_OVERLAP,
        "top_k": config.TOP_K,
        "default_prompt_version": rag.default_prompt_version(),
        "yara_enabled": config.YARA_ENABLED,
        "jwt_expiry_minutes": config.JWT_EXPIRY_MINUTES,
        "login_max_attempts": login_throttle.MAX_ATTEMPTS,
        "login_lockout_seconds": login_throttle.LOCKOUT_SECONDS,
        "document_count": len(rag.list_sources()),
        "max_upload_size_mb": config.MAX_UPLOAD_SIZE_MB,
        "quarantined_count": len(quarantine.list_quarantined()),
        "daily_token_limit": token_usage.get_daily_limit(),
    }


@app.get("/login-attempts")
def login_attempts(_user: dict = SUPERADMIN_ONLY):
    return {"attempts": login_throttle.list_status()}


@app.get("/token-usage")
def get_token_usage(_user: dict = ANY_ROLE):
    return token_usage.status(_user["username"])


@app.post("/token-limit")
def set_token_limit(req: TokenLimitRequest, _user: dict = SUPERADMIN_ONLY):
    try:
        token_usage.set_daily_limit(req.daily_limit, _user["username"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"daily_limit": req.daily_limit}


@app.get("/logs/recent")
def logs_recent(limit: int = 200, _user: dict = SUPERADMIN_ONLY):
    limit = max(1, min(limit, 1000))
    return {"lines": logging_config.tail(limit)}


@app.get("/quarantine")
def quarantine_list(_user: dict = SUPERADMIN_ONLY):
    return {"files": quarantine.list_quarantined()}


@app.get("/quarantine/{quarantine_id}/download")
def quarantine_download(quarantine_id: str, _user: dict = SUPERADMIN_ONLY):
    result = quarantine.get_quarantined_file(quarantine_id)
    if result is None:
        raise HTTPException(404, "Quarantined file not found")
    content, meta = result
    logger.info(
        "Quarantined file downloaded for manual review: id=%s filename=%s by=%s",
        quarantine_id, meta["original_filename"], _user["username"],
    )
    safe_name = meta["original_filename"].replace('"', "")
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.post("/quarantine/{quarantine_id}/release")
def quarantine_release(quarantine_id: str, _user: dict = SUPERADMIN_ONLY):
    """A SuperAdmin has manually inspected a quarantined file (downloaded and
    reviewed it themselves) and judged it safe despite the automated flag.
    This deliberately does NOT re-run the checks that quarantined it in the
    first place (AV/type/executable/zip-bomb) — that's the whole point of a
    human override. It still has to actually parse as real content, though;
    a file that can't be extracted at all still can't be ingested."""
    result = quarantine.get_quarantined_file(quarantine_id)
    if result is None:
        raise HTTPException(404, "Quarantined file not found")
    content, meta = result
    filename = meta["original_filename"]
    admin = _user["username"]

    logger.warning(
        "Quarantined file MANUALLY RELEASED for processing: id=%s filename=%s "
        "original_reason=%s released_by=%s",
        quarantine_id, filename, meta["reason"], admin,
    )

    try:
        text = extract_text(filename, content)
    except ValueError as e:
        raise HTTPException(400, f"Cannot process this file: {e}")

    chunks = chunk_text(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    if not chunks:
        raise HTTPException(400, "No extractable text in file")

    # Archive the exact released bytes (random filename, same as any other
    # accepted upload) so there's still an on-disk audit trail of what was
    # actually ingested, even after the quarantine entry itself is removed.
    quarantine.archive_file(content, filename, admin, reason=f"released_from_quarantine:{meta['reason']}")
    doc_id = str(uuid.uuid4())
    rag.add_chunks(doc_id, filename, chunks)
    quarantine.remove_from_quarantine(quarantine_id)
    return {"filename": filename, "chunks_added": len(chunks)}


@app.delete("/quarantine/{quarantine_id}")
def quarantine_delete(quarantine_id: str, _user: dict = SUPERADMIN_ONLY):
    removed = quarantine.remove_from_quarantine(quarantine_id)
    if not removed:
        raise HTTPException(404, "Quarantined file not found")
    logger.warning("Quarantined file permanently deleted: id=%s by=%s", quarantine_id, _user["username"])
    return {"status": "deleted"}
