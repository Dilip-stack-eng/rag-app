"""Server-side CAPTCHA generation and verification for POST /auth/login.

The Streamlit frontend's CAPTCHA is checked entirely within Streamlit's own
server-side Python session — safe there because Streamlit runs that code
on a server, not in the browser. A pure browser SPA (the React frontend)
has no equivalent trusted place to hold "the expected answer," so this
module makes the CAPTCHA a real backend-issued, backend-verified challenge
instead: GET /auth/captcha issues an id + image, POST /auth/login checks
the submitted answer against what this module remembers for that id.

Optional on POST /auth/login for backward compatibility with the Streamlit
frontend, which never sends captcha_id/captcha_answer at all (it does its
own equivalent check before ever calling this endpoint) — once Streamlit
is retired, this can be made mandatory.

In-memory and per-process, same trade-off as login_throttle.py: fine at
this app's scale, resets on restart.
"""

import logging
import random
import time
import uuid
from io import BytesIO
from threading import Lock
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no O/0, I/1 — avoids ambiguity
_TTL_SECONDS = 300  # unsolved challenges expire after 5 minutes

_lock = Lock()
_pending: dict[str, dict] = {}  # captcha_id -> {"text": str, "expires_at": float}


def _purge_expired() -> None:
    now = time.time()
    for cid in [cid for cid, entry in _pending.items() if entry["expires_at"] <= now]:
        _pending.pop(cid, None)


def _random_text(length: int = 5) -> str:
    return "".join(random.choice(_CHARS) for _ in range(length))


def _render_image(text: str) -> bytes:
    """Same visual style as the (now-legacy) Streamlit-rendered captcha —
    warm distressed image with rotated, jittered characters and line/dot
    noise, deliberately hard to OCR cleanly but easy to read by eye."""
    width, height = 130, 46
    img = Image.new("RGB", (width, height), color=(240, 238, 230))
    draw = ImageDraw.Draw(img)

    for _ in range(5):
        xy = (random.randint(0, width), random.randint(0, height), random.randint(0, width), random.randint(0, height))
        draw.line(xy, fill=tuple(random.randint(190, 215) for _ in range(3)), width=1)

    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()

    x_cursor = 6
    for ch in text:
        char_img = Image.new("RGBA", (26, 36), (255, 255, 255, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_draw.text((4, 2), ch, font=font, fill=(61, 57, 41))
        char_img = char_img.rotate(random.randint(-20, 20), expand=1, resample=Image.BICUBIC)
        img.paste(char_img, (x_cursor, random.randint(0, 6)), char_img)
        x_cursor += 23

    for _ in range(40):
        x, y = random.randint(0, width - 1), random.randint(0, height - 1)
        draw.point((x, y), fill=tuple(random.randint(140, 190) for _ in range(3)))

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate() -> tuple[str, bytes]:
    """Returns (captcha_id, png_bytes). The answer is remembered server-side
    against captcha_id until verify() consumes it or it expires unsolved."""
    with _lock:
        _purge_expired()
        text = _random_text()
        captcha_id = uuid.uuid4().hex
        _pending[captcha_id] = {"text": text, "expires_at": time.time() + _TTL_SECONDS}
    return captcha_id, _render_image(text)


def verify(captcha_id: Optional[str], answer: Optional[str]) -> bool:
    """Single-use: captcha_id is consumed whether the answer is right or
    wrong, so a challenge can never be brute-forced by repeated guesses
    against the same image. Returns False (never raises) for a missing,
    unknown, expired, or already-used id."""
    if not captcha_id:
        return False
    with _lock:
        entry = _pending.pop(captcha_id, None)
    if entry is None or entry["expires_at"] <= time.time():
        return False
    return bool(answer) and answer.strip().upper() == entry["text"]
