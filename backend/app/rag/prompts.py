"""Versioned prompt templates for the RAG pipeline.

The actual prompt text lives in prompts.json (data, not code) so it can be
edited or inspected without touching Python, and so the Streamlit UI can
list versions via the API instead of hardcoding them.

Never edit an existing version's text in prompts.json after it has
shipped, since that defeats the point of being able to roll back. Add a
new version instead and point PROMPT_VERSION (backend/.env) — or the
per-request prompt_version — at it to roll forward.

History:
  v1 - Plain Q&A prompt, no privacy handling at all.
  v2 - Added a "STRICT PRIVACY RULE" instructing the model to refuse
       (say "I don't know") when asked about restricted personal fields,
       backed by a deterministic keyword guard so the refusal doesn't
       depend on the model following instructions.
  v3 - Replaced the flat refusal with an in-prompt masking instruction
       (mask with '#', format emails as a Markdown mailto link).
       Deprecated: local models are unreliable at character-level string
       manipulation and produced garbage instead of masking real values,
       and the mailto example leaked the real address in the link target.
  v4 - Current default. The LLM's only job is to extract the raw value;
       masking itself happens deterministically in Python
       (see rag._mask_value), so the output is consistent regardless of
       what the model does.
"""

import json
from pathlib import Path

_DATA = json.loads((Path(__file__).parent / "prompts.json").read_text(encoding="utf-8"))

RESTRICTED_FIELDS = _DATA["restricted_fields"]
DEFAULT_VERSION = _DATA["default_version"]


def _restricted_lines() -> str:
    return "\n".join(
        f'- {field} (also asked as: {", ".join(aliases)})'
        for field, aliases in RESTRICTED_FIELDS.items()
    )


def _build_versions() -> dict:
    restricted_lines = _restricted_lines()
    versions = {}
    for key, raw in _DATA["versions"].items():
        bundle = dict(raw)
        bundle["qa"] = bundle["qa"].replace("{restricted_lines}", restricted_lines)
        if "extract" in bundle:
            bundle["extract"] = bundle["extract"].replace("{restricted_lines}", restricted_lines)
        versions[key] = bundle
    return versions


# mode controls how rag.generate_answer branches for restricted-field questions:
#   "plain"             - no privacy handling; qa prompt used for everything.
#   "refuse"            - deterministic guard short-circuits to "I don't know".
#   "mask_in_prompt"     - no guard; qa prompt (unified for all questions) asks the
#                          LLM to mask inline. Deprecated, kept for reference only.
#   "extract_and_mask"  - deterministic guard triggers a narrow extraction prompt,
#                          then Python masks the result.
PROMPTS = _build_versions()


def get_version(version: str | None = None) -> dict:
    version = version or DEFAULT_VERSION
    try:
        return PROMPTS[version]
    except KeyError:
        raise ValueError(f"Unknown PROMPT_VERSION {version!r}. Available: {sorted(PROMPTS)}")


def list_versions() -> list[dict]:
    """[{key, label, mode, description}, ...] in insertion order — for the Streamlit dropdown."""
    return [
        {"key": key, "label": v["label"], "mode": v["mode"], "description": v["description"]}
        for key, v in PROMPTS.items()
    ]

