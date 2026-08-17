import logging
import random
import re
from typing import Optional

import chromadb
from google import genai
from google.genai import types as genai_types

from . import config
from .prompts import RESTRICTED_FIELDS, DEFAULT_VERSION, get_version, list_versions

logger = logging.getLogger(__name__)

_client = chromadb.PersistentClient(path=config.CHROMA_DIR)
_collection = _client.get_or_create_collection(name=config.COLLECTION_NAME)
_genai: Optional[genai.Client] = None


def _get_genai() -> genai.Client:
    """Lazily construct the Gemini client — genai.Client() raises immediately
    on a missing API key, so building it at import time would crash the whole
    app before it ever serves a request. Deferring it lets non-LLM endpoints
    (health, login, etc.) keep working until a key is configured."""
    global _genai
    if _genai is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set — add it to backend/.env to use the LLM/embeddings.")
        _genai = genai.Client(api_key=config.GEMINI_API_KEY)
    return _genai


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    response = _get_genai().models.embed_content(model=config.EMBED_MODEL, contents=texts)
    return [e.values for e in response.embeddings]


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters/token, the standard heuristic for
    English text) — used to pre-flight-check a query against a user's
    remaining daily token budget *before* spending an actual LLM call on it.
    Deliberately approximate and typically an undercount for the full
    request (it doesn't know the prompt template's own boilerplate); the
    real, authoritative count always comes from Gemini's own usage_metadata
    after the call actually runs."""
    return max(1, len(text) // 4)


def add_chunks(doc_id: str, filename: str, chunks: list[str]) -> None:
    if not chunks:
        return
    embeddings = embed_texts(chunks)
    ids = [f"{doc_id}-{i}" for i in range(len(chunks))]
    metadatas = [{"source": filename, "chunk": i} for i in range(len(chunks))]
    _collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    logger.info("Ingested document: filename=%s doc_id=%s chunks=%d", filename, doc_id, len(chunks))


_GREETINGS = {
    "hi", "hii", "hello", "helo", "hey", "heyy", "heya", "hiya", "yo", "sup",
    "howdy", "hola", "namaste", "greetings",
    "good morning", "good afternoon", "good evening", "good day",
    "morning", "evening", "afternoon",
    "hi there", "hello there", "hey there", "hiya there",
    "whats up", "sup there", "whats good",
    "how are you", "how are you doing", "how you doing", "hows it going",
    "how do you do",
}

_GREETING_REPLIES = [
    "Hello! 👋 How can I help you with your documents today?",
    "Hi there! What would you like to know?",
    "Hey! Ready whenever you are — ask me anything about your documents.",
    "Greetings! What can I look up for you?",
    "Hello! Good to see you. What are you curious about today?",
    "Hi! Feel free to ask me anything about your uploaded files.",
    "Hey there! What can I help you find today?",
]


def _is_greeting(question: str) -> bool:
    normalized = re.sub(r"[^\w\s]", "", question.lower())
    normalized = " ".join(normalized.split())
    # Collapse casual letter elongation so "hiiiii" / "heyyyy" / "helloooo"
    # match without having to enumerate every stretched-out spelling.
    normalized = re.sub(r"(.)\1{2,}", r"\1", normalized)
    return normalized in _GREETINGS


def greeting_reply(question: str) -> Optional[str]:
    """A varied, human-sounding reply for plain greetings — same for every user/role,
    and deliberately skips document retrieval since there's nothing to look up."""
    if _is_greeting(question):
        logger.info("Greeting shortcut used, retrieval skipped")
        return random.choice(_GREETING_REPLIES)
    return None


def query(question: str, top_k: Optional[int] = None):
    top_k = top_k or config.TOP_K
    query_embedding = embed_texts([question])[0]
    results = _collection.query(query_embeddings=[query_embedding], n_results=top_k)
    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    logger.info("Retrieval: top_k=%d chunks_returned=%d", top_k, len(documents))
    return documents, metadatas


def _mentions_restricted_field(question: str) -> bool:
    normalized = " ".join(question.lower().replace("_", " ").replace("-", " ").replace("'", "").split())
    for field, aliases in RESTRICTED_FIELDS.items():
        if field.replace("_", " ") in normalized:
            return True
        if any(alias in normalized for alias in aliases):
            return True
    return False


_EMAIL_RE = re.compile(r"^([^@\s]+)@([\w.-]+)\.([A-Za-z]{2,})$")


def _mask_value(raw_value: str) -> str:
    """Deterministic masking — never trust the LLM to do character arithmetic."""
    value = raw_value.strip()
    email_match = _EMAIL_RE.match(value)
    if email_match:
        local, _domain, tld = email_match.groups()
        prefix = local[:2]
        hash_count = max(len(local) - len(prefix), 3)
        return f"{prefix}{'#' * hash_count}.{tld}"

    prefix = value[:2]
    hash_count = max(len(value) - len(prefix), 3)
    return f"{prefix}{'#' * hash_count}"


def _generate(prompt: str) -> tuple[str, int]:
    response = _get_genai().models.generate_content(
        model=config.LLM_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(max_output_tokens=config.LLM_NUM_PREDICT),
    )
    usage = response.usage_metadata
    tokens = ((usage.prompt_token_count or 0) + (usage.candidates_token_count or 0)) if usage else 0
    return response.text or "", tokens


def generate_short_text(prompt: str, max_tokens: int = 150) -> Optional[str]:
    """Best-effort short Gemini completion for callers outside the RAG flow
    (e.g. an AI-written blurb in a security alert email). Unlike _generate(),
    never raises — returns None if no API key is configured or the call
    fails, so a caller can treat this as optional enrichment and fall back
    to a plain, non-AI message rather than breaking whatever triggered it."""
    if not config.GEMINI_API_KEY:
        return None
    try:
        response = _get_genai().models.generate_content(
            model=config.LLM_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(max_output_tokens=max_tokens),
        )
        return (response.text or "").strip() or None
    except Exception:
        logger.exception("generate_short_text failed")
        return None


def _extract_raw_value(question: str, context: str, template: str) -> tuple[Optional[str], int]:
    prompt = template.format(context=context, question=question)
    raw, tokens = _generate(prompt)
    value = raw.strip().strip('"').strip()
    if not value or value.upper() == "NOT_FOUND":
        return None, tokens
    return value, tokens


def generate_answer(
    question: str, context_chunks: list[str], prompt_version: Optional[str] = None
) -> tuple[str, int]:
    """Returns (answer_text, tokens_used) — tokens_used is 0 for any path
    that never calls the LLM (restricted-field refusal), so callers can
    charge a user's daily quota only for what actually cost inference time."""
    context = "\n\n".join(context_chunks)
    version = get_version(prompt_version or config.PROMPT_VERSION)
    mode = version["mode"]
    restricted = _mentions_restricted_field(question)
    logger.info("Generating answer: prompt_version=%s mode=%s restricted_field_detected=%s", prompt_version or config.PROMPT_VERSION, mode, restricted)

    if mode == "refuse" and restricted:
        logger.warning("Restricted field refused (mode=refuse)")
        return "I don't know", 0

    if mode == "extract_and_mask" and restricted:
        # Never log raw_value — it's exactly the value the masking system exists to protect.
        raw_value, tokens = _extract_raw_value(question, context, version["extract"])
        if raw_value is None:
            logger.info("Restricted field requested but not found in context")
            return "The question is out of context.", tokens
        logger.warning("Restricted field requested and masked before returning")
        return _mask_value(raw_value), tokens

    prompt = version["qa"].format(context=context, question=question)
    answer, tokens = _generate(prompt)
    logger.info("Answer generated: length=%d tokens=%d", len(answer), tokens)
    return answer, tokens


def list_prompt_versions() -> list[dict]:
    return list_versions()


def default_prompt_version() -> str:
    return config.PROMPT_VERSION or DEFAULT_VERSION


def list_sources() -> list[str]:
    data = _collection.get()
    metadatas = data.get("metadatas") or []
    return sorted({m["source"] for m in metadatas})


def delete_all() -> None:
    global _collection
    logger.warning("Deleting all ingested documents (collection=%s)", config.COLLECTION_NAME)
    _client.delete_collection(config.COLLECTION_NAME)
    _collection = _client.get_or_create_collection(name=config.COLLECTION_NAME)
