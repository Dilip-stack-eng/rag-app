import datetime
import os
import random
import time
from io import BytesIO
from zoneinfo import ZoneInfo

import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_SECONDS = 60

# Only used by the login page's "quick sign-in" buttons (see _quick_login) —
# read server-side so the real password is sent straight to POST /auth/login
# without ever being rendered into the page's HTML, unlike filling a
# password input would. Leave unset to hide the buttons entirely.
QUICK_LOGIN_ADMIN_USERNAME = os.getenv("APP_USERNAME", "ADMIN")
QUICK_LOGIN_ADMIN_PASSWORD = os.getenv("APP_PASSWORD", "")
QUICK_LOGIN_SUPERADMIN_USERNAME = os.getenv("SUPERADMIN_USERNAME", "SuperAdmin")
QUICK_LOGIN_SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "")

st.set_page_config(page_title="Athena", page_icon="✻", layout="wide")

# Placeholder logo mark (no external asset yet) — swap the <path> for a real
# brand SVG/PNG when one is available.
def athena_logo(size=28):
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 32 32"
        xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Athena logo"
        style="flex-shrink:0;">
        <rect width="32" height="32" rx="9" fill="#D97757"/>
        <path d="M16 7.5 L23.5 24.5 H19.8 L18.3 20.8 H13.7 L12.2 24.5 H8.5 L16 7.5 Z
                 M16 12.8 L14.4 17.8 H17.6 L16 12.8 Z" fill="#FFFFFF"/>
    </svg>"""

COUNTRY_TIMEZONES = {
    "India": "Asia/Kolkata",
    "United States (New York)": "America/New_York",
    "United States (Los Angeles)": "America/Los_Angeles",
    "United Kingdom": "Europe/London",
    "France": "Europe/Paris",
    "Germany": "Europe/Berlin",
    "Italy": "Europe/Rome",
    "Spain": "Europe/Madrid",
    "Netherlands": "Europe/Amsterdam",
    "Switzerland": "Europe/Zurich",
    "Sweden": "Europe/Stockholm",
    "Russia (Moscow)": "Europe/Moscow",
    "Turkey": "Europe/Istanbul",
    "United Arab Emirates": "Asia/Dubai",
    "Saudi Arabia": "Asia/Riyadh",
    "Israel": "Asia/Jerusalem",
    "Egypt": "Africa/Cairo",
    "South Africa": "Africa/Johannesburg",
    "Nigeria": "Africa/Lagos",
    "Pakistan": "Asia/Karachi",
    "Bangladesh": "Asia/Dhaka",
    "Sri Lanka": "Asia/Colombo",
    "China": "Asia/Shanghai",
    "Japan": "Asia/Tokyo",
    "South Korea": "Asia/Seoul",
    "Singapore": "Asia/Singapore",
    "Malaysia": "Asia/Kuala_Lumpur",
    "Indonesia": "Asia/Jakarta",
    "Thailand": "Asia/Bangkok",
    "Vietnam": "Asia/Ho_Chi_Minh",
    "Philippines": "Asia/Manila",
    "Australia (Sydney)": "Australia/Sydney",
    "New Zealand": "Pacific/Auckland",
    "Canada (Toronto)": "America/Toronto",
    "Mexico": "America/Mexico_City",
    "Brazil": "America/Sao_Paulo",
    "Argentina": "America/Argentina/Buenos_Aires",
    "Chile": "America/Santiago",
    "Colombia": "America/Bogota",
}

CLAUDE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:wght@400;600&display=swap');

:root {
    --claude-bg: #FAF9F5;
    --claude-sidebar-bg: #F0EEE6;
    --claude-accent: #D97757;
    --claude-accent-hover: #C6673F;
    --claude-text: #3D3929;
    --claude-text-soft: #6B6658;
    --claude-border: #E5E1D6;
    --claude-bubble: #F0EEE6;
    --claude-danger: #A3432F;
    --claude-success: #2E5339;
    --claude-warning: #B45309;
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: var(--claude-text);
}

.stApp {
    background-color: var(--claude-bg);
}

/* ---------- Sidebar "taskbar" ---------- */
[data-testid="stSidebar"] {
    background-color: var(--claude-sidebar-bg);
    border-right: 1px solid var(--claude-border);
}
[data-testid="stSidebar"] > div {
    padding-top: 1rem;
}

.claude-brand {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--claude-text);
    padding: 0.1rem 0 1.1rem 0.1rem;
}

.sidebar-section-label {
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
    font-weight: 600;
    color: var(--claude-text-soft);
    margin: 1.2rem 0 0.4rem 0.15rem;
}

.sidebar-file-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.87rem;
    color: var(--claude-text);
    padding: 0.45rem 0.6rem;
    border-radius: 8px;
    margin-bottom: 0.15rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.sidebar-file-row:hover {
    background-color: rgba(217, 119, 87, 0.1);
}

.sidebar-footer {
    margin-top: 1.5rem;
    padding-top: 0.9rem;
    border-top: 1px solid var(--claude-border);
    font-size: 0.78rem;
    color: var(--claude-text-soft);
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

/* New-chat button (nav-style row, not a filled CTA) */
.new-chat-marker + div .stButton > button {
    background-color: #FFFFFF;
    color: var(--claude-text);
    border: 1px solid var(--claude-border);
    justify-content: flex-start;
    font-weight: 500;
    border-radius: 10px;
}
.new-chat-marker + div .stButton > button:hover {
    background-color: var(--claude-bubble);
    border-color: var(--claude-accent);
    color: var(--claude-accent);
}

/* Destructive / clear-documents row */
.clear-docs-marker + div .stButton > button {
    background-color: transparent;
    color: var(--claude-danger);
    border: 1px solid var(--claude-border);
    font-weight: 500;
}
.clear-docs-marker + div .stButton > button:hover {
    background-color: rgba(163, 67, 47, 0.08);
    border-color: var(--claude-danger);
}

/* ---------- Main column ---------- */
.block-container {
    max-width: 820px;
    /* Streamlit's own fixed top header bar is taller than this used to
       account for, so the first line of page content (e.g. the Query
       Trace caption) was rendering partly underneath it — ascenders of
       the very first line got visually clipped. */
    padding-top: 3.5rem;
}
.block-container:has(.login-page-marker) {
    max-width: 1560px;
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
}

/* Hide Streamlit's own top toolbar on the login page only — reclaims
   vertical space so the whole card fits one screen with no scrolling. */
.stApp:has(.login-page-marker) [data-testid="stHeader"] {
    display: none;
}

h1 {
    font-family: 'Source Serif 4', Georgia, serif !important;
    color: var(--claude-text) !important;
    font-weight: 600 !important;
}

/* Landing ("open page") greeting, vertically centered like claude.ai */
.landing-marker + div {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 50vh;
    text-align: center;
}
.claude-greeting {
    font-family: 'Source Serif 4', Georgia, serif !important;
    font-size: 2.15rem !important;
    font-weight: 600 !important;
    color: var(--claude-text) !important;
    margin-bottom: 0.35rem !important;
}
.claude-subgreeting {
    color: var(--claude-text-soft);
    font-size: 1rem;
    margin-bottom: 1.7rem;
}

/* Suggestion chips on the landing page */
.suggestion-marker + div .stButton > button {
    background-color: #FFFFFF;
    color: var(--claude-text);
    border: 1px solid var(--claude-border);
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 500;
    padding: 0.5rem 1rem;
}
.suggestion-marker + div .stButton > button:hover {
    border-color: var(--claude-accent);
    color: var(--claude-accent);
}

/* Default buttons (Ingest, etc.) */
.stButton > button, .stDownloadButton > button {
    background-color: var(--claude-accent);
    color: #fff;
    border: none;
    border-radius: 10px;
    padding: 0.5rem 1.1rem;
    font-weight: 500;
    transition: background-color 0.15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    background-color: var(--claude-accent-hover);
    color: #fff;
}

/* File uploader */
[data-testid="stFileUploaderDropzone"] {
    background-color: var(--claude-bg);
    border: 1.5px dashed var(--claude-border);
    border-radius: 12px;
}

/* Chat messages */
[data-testid="stChatMessage"] {
    background-color: transparent;
    border-radius: 14px;
    padding: 0.5rem 0.25rem;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background-color: var(--claude-bubble);
    border-radius: 14px;
    padding: 0.75rem 1rem;
}

/* Chat input */
[data-testid="stChatInput"] {
    background-color: #FFFFFF;
    border: 1px solid var(--claude-border);
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(61, 57, 41, 0.08);
}
[data-testid="stChatInput"]:focus-within {
    border-color: var(--claude-accent);
}

/* Alerts */
[data-testid="stAlertContentSuccess"] { color: var(--claude-success); }
[data-testid="stAlertContentError"] { color: var(--claude-danger); }

hr, [data-testid="stDivider"] {
    border-color: var(--claude-border) !important;
}

::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-thumb { background-color: var(--claude-border); border-radius: 8px; }

/* ---------- Login page ----------
   Split shell: rotating AI-scenario visual pane (left) + plain white
   sign-in card (right) — the pane's own box (background, radius, shadow)
   lives on the shell/column, so the card marker itself stays flat here
   to avoid a double border/shadow. */
.login-page-marker + div {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: calc(100vh - 1rem);
    padding-top: 0;
}

.login-split-marker + div[data-testid="stHorizontalBlock"] {
    max-width: 1320px;
    width: 100%;
    margin: 0 auto;
    border-radius: 24px;
    overflow: hidden;
    box-shadow: 0 32px 90px rgba(61, 57, 41, 0.22);
    gap: 0 !important;
    align-items: stretch;
}
[data-testid="stColumn"]:has(.login-visual-marker) {
    background:
        radial-gradient(circle at 18% 18%, rgba(217, 119, 87, 0.28), transparent 55%),
        radial-gradient(circle at 82% 88%, rgba(217, 119, 87, 0.20), transparent 50%),
        linear-gradient(160deg, #2A2620 0%, #3D3929 55%, #2A2620 100%);
    padding: 0 !important;
    position: relative;
    min-height: min(640px, calc(100vh - 2rem));
    max-height: calc(100vh - 2rem);
    display: flex;
    align-items: center;
    justify-content: center;
}
[data-testid="stColumn"]:has(.login-form-marker) {
    background-color: #FFFFFF;
    padding: 1.5rem 2.6rem !important;
    max-height: calc(100vh - 2rem);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.login-visual-brand {
    position: absolute;
    top: 2rem;
    left: 2.2rem;
    display: flex;
    align-items: center;
    gap: 0.55rem;
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 1.15rem;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.92);
    letter-spacing: 0.02em;
}
.login-visual-brand-accent { color: var(--claude-accent); }

.login-visual-trust {
    position: absolute;
    bottom: 2rem;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 0.78rem;
    font-weight: 500;
    letter-spacing: 0.03em;
    color: rgba(255, 255, 255, 0.5);
}
.login-visual-trust span { margin: 0 0.6rem; }

.login-scene-stack {
    position: relative;
    width: 100%;
    height: 100%;
    min-height: min(640px, calc(100vh - 2rem));
}
.login-scene {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    text-align: center;
    opacity: 0;
}
.login-scene svg {
    width: 140px;
    height: 140px;
    margin-bottom: 1.4rem;
}
.login-scene-title {
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 1.5rem;
    font-weight: 600;
    color: #FFFFFF;
    margin-bottom: 0.5rem;
}
.login-scene-subtitle {
    font-size: 0.95rem;
    color: rgba(255, 255, 255, 0.65);
    max-width: 320px;
    line-height: 1.6;
}
/* Each scene is visible for a 1/5 slice of a 750s (12.5-minute) loop, i.e.
   ~2.5 minutes each — pure CSS, so it keeps rotating even while the page
   sits idle with no Streamlit rerun (a rerun can't drive a wall-clock
   timer on its own). */
.login-scene[data-idx="0"] { animation: login-scene-0 750s linear infinite; }
.login-scene[data-idx="1"] { animation: login-scene-1 750s linear infinite; }
.login-scene[data-idx="2"] { animation: login-scene-2 750s linear infinite; }
.login-scene[data-idx="3"] { animation: login-scene-3 750s linear infinite; }
.login-scene[data-idx="4"] { animation: login-scene-4 750s linear infinite; }
@keyframes login-scene-0 {
    0%, 19.5% { opacity: 1; }
    20%, 100% { opacity: 0; }
}
@keyframes login-scene-1 {
    0%, 19.5% { opacity: 0; }
    20%, 39.5% { opacity: 1; }
    40%, 100% { opacity: 0; }
}
@keyframes login-scene-2 {
    0%, 39.5% { opacity: 0; }
    40%, 59.5% { opacity: 1; }
    60%, 100% { opacity: 0; }
}
@keyframes login-scene-3 {
    0%, 59.5% { opacity: 0; }
    60%, 79.5% { opacity: 1; }
    80%, 100% { opacity: 0; }
}
@keyframes login-scene-4 {
    0%, 79.5% { opacity: 0; }
    80%, 99.5% { opacity: 1; }
    100% { opacity: 0; }
}

[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .login-card-marker) {
    background-color: transparent;
    border: none !important;
    box-shadow: none !important;
    padding: 0;
    gap: 0.5rem !important;
}
.login-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    margin-bottom: 0.3rem;
}
.login-logo-name {
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--claude-text);
}
.login-logo-name-accent {
    color: var(--claude-accent);
}
.login-eyebrow {
    text-align: center;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--claude-accent);
    margin-bottom: 0.3rem;
}
.login-title {
    font-family: 'Source Serif 4', Georgia, serif !important;
    font-size: 1.5rem !important;
    font-weight: 600 !important;
    color: var(--claude-text) !important;
    text-align: center;
    margin-bottom: 0.2rem !important;
}
.login-subtitle {
    color: var(--claude-text-soft);
    font-size: 0.85rem;
    text-align: center;
    margin-bottom: 0.4rem;
}
.login-subtitle b { color: var(--claude-text); }

.lang-bar-marker + div {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 0.6rem;
}
.lang-bar-marker + div [data-baseweb="select"] {
    min-width: 150px;
}
.lang-bar-marker + div [data-baseweb="select"] > div {
    background-color: #FFFFFF;
    border: 1px solid var(--claude-border) !important;
    border-radius: 999px;
    min-height: 2.1rem;
    font-size: 0.82rem;
    color: var(--claude-text-soft);
    box-shadow: none !important;
}
.captcha-marker + div [data-testid="stImage"] img {
    border-radius: 10px;
    border: 1px solid var(--claude-border);
    max-width: 160px;
    width: 100%;
}
.captcha-refresh-marker + div .stButton > button {
    background-color: #FFFFFF;
    color: var(--claude-text-soft);
    border: 1px solid var(--claude-border);
    border-radius: 10px;
    height: 2.2rem;
    min-height: 2.2rem;
    font-size: 1.05rem;
    padding: 0;
}
.captcha-refresh-marker + div .stButton > button:hover {
    border-color: var(--claude-accent);
    color: var(--claude-accent);
}

.login-card-marker ~ div [data-testid="stTextInput"] input {
    border-radius: 10px;
    padding: 0.5rem 0.85rem;
    font-size: 0.92rem;
}
.login-card-marker ~ div [data-testid="stWidgetLabel"] p {
    font-size: 0.85rem;
}
.login-card-marker ~ div [data-baseweb="select"] > div {
    border-radius: 10px;
    min-height: 2.4rem;
    font-size: 0.92rem;
    box-shadow: none !important;
}

.email-continue-marker + div .stButton > button {
    background-color: var(--claude-accent);
    color: #fff;
    border: none;
    border-radius: 10px;
    padding: 0.55rem 1.1rem;
    font-size: 0.95rem;
    font-weight: 600;
}
.email-continue-marker + div .stButton > button:hover {
    background-color: var(--claude-accent-hover);
}

.quick-login-marker + div {
    margin-top: 0.1rem;
}
.quick-login-marker + div [data-testid="stCaptionContainer"] {
    text-align: center;
    font-size: 0.78rem;
}
.quick-login-marker ~ div .stButton > button {
    background-color: #FFFFFF;
    color: var(--claude-text-soft);
    border: 1px dashed var(--claude-border);
    border-radius: 10px;
    font-weight: 500;
    font-size: 0.82rem;
    padding: 0.4rem 0.7rem;
}
.quick-login-marker ~ div .stButton > button:hover {
    border-color: var(--claude-accent);
    color: var(--claude-accent);
}

.login-footer {
    text-align: center;
    color: var(--claude-text-soft);
    font-size: 0.68rem;
    line-height: 1.35;
    max-width: 480px;
    margin: 0.4rem auto 0;
}
.login-footer a { color: var(--claude-text-soft); text-decoration: underline; }

/* ---------- Responsive: login page ----------
   Below 900px the two-column shell doesn't have room to breathe, so the
   visual pane is dropped entirely and the form column becomes its own
   plain centered card instead (rather than squeezing both side by side). */
@media (max-width: 900px) {
    .login-split-marker + div[data-testid="stHorizontalBlock"] {
        box-shadow: none;
        border-radius: 0;
        max-width: 560px;
    }
    [data-testid="stColumn"]:has(.login-visual-marker) {
        display: none;
    }
    [data-testid="stColumn"]:has(.login-form-marker) {
        border: 1px solid var(--claude-border);
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(61, 57, 41, 0.14);
        padding: 2.2rem 2.4rem !important;
    }
}
@media (max-width: 480px) {
    [data-testid="stColumn"]:has(.login-form-marker) {
        padding: 1.2rem 1.1rem !important;
    }
    .login-logo-name { font-size: 1.3rem; }
}

/* ---------- Responsive: main app ---------- */
@media (max-width: 640px) {
    .claude-greeting { font-size: 1.65rem !important; }
    .claude-subgreeting { font-size: 0.92rem; }
    .landing-marker + div { min-height: 35vh; }
    .kv-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 400px) {
    .kv-grid { grid-template-columns: 1fr; }
}

/* ---------- Code (retrieved chunks) view ---------- */
[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .chunk-marker) {
    border-radius: 12px !important;
    border-color: var(--claude-border) !important;
    padding: 0 !important;
    overflow: hidden;
    margin-bottom: 0.9rem;
}
.chunk-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background-color: var(--claude-sidebar-bg);
    padding: 0.5rem 0.9rem;
    font-size: 0.8rem;
    color: var(--claude-text-soft);
    font-weight: 500;
}
/* The retrieved-chunk text itself: wrap long lines instead of relying on
   horizontal scroll, which was getting clipped by the card's own
   overflow:hidden (needed to keep header-bar corners rounded) — words were
   being cut off mid-word at the card edge with no way to see the rest. */
.chunk-marker ~ div [data-testid="stCodeBlock"] pre,
.chunk-marker ~ div [data-testid="stCodeBlock"] code {
    white-space: pre-wrap !important;
    word-break: break-word !important;
}
.chunk-card-header b { color: var(--claude-text); }

/* ---------- Main-page navigation (vertical list, left side) ---------- */
.main-nav-marker ~ div .stButton {
    margin-bottom: 0.15rem;
}
.main-nav-marker ~ div button[kind="secondary"] {
    background-color: transparent !important;
    color: var(--claude-text) !important;
    border: 1px solid transparent !important;
    font-weight: 500 !important;
    justify-content: flex-start !important;
    text-align: left !important;
    padding: 0.5rem 0.7rem !important;
}
.main-nav-marker ~ div button[kind="secondary"]:hover {
    background-color: var(--claude-bubble) !important;
    color: var(--claude-accent) !important;
}
.main-nav-marker ~ div button[kind="primary"] {
    background-color: var(--claude-bubble) !important;
    color: var(--claude-accent) !important;
    border: 1px solid transparent !important;
    font-weight: 600 !important;
    justify-content: flex-start !important;
    text-align: left !important;
    padding: 0.5rem 0.7rem !important;
    box-shadow: none !important;
}

/* ---------- Log tail viewer (Training log / Security tabs) ---------- */
.log-line {
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 0.78rem;
    color: var(--claude-text-soft);
    padding: 0.3rem 0.6rem;
    border-bottom: 1px solid var(--claude-border);
    white-space: pre-wrap;
    word-break: break-word;
}
.log-line:last-child { border-bottom: none; }
.log-line.level-WARNING { color: var(--claude-warning); }
.log-line.level-ERROR { color: var(--claude-danger); font-weight: 600; }

/* ---------- Key/value summary grid (Control panel / Security) ---------- */
.kv-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 0.75rem;
    margin-bottom: 1rem;
}
.kv-card {
    background-color: #FFFFFF;
    border: 1px solid var(--claude-border);
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
}
.kv-card .kv-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--claude-text-soft);
    margin-bottom: 0.2rem;
}
.kv-card .kv-value {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--claude-text);
}

/* ---------- Daily token usage card (Home page) ---------- */
.token-usage-card {
    border: 1px solid var(--claude-border);
    border-radius: 14px;
    background-color: #FFFFFF;
    padding: 0.9rem 1.1rem 1rem;
    margin-bottom: 1.1rem;
}
.token-usage-card .tuc-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.45rem;
}
.token-usage-card .tuc-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--claude-text-soft);
}
.token-usage-card .tuc-pct {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--claude-text-soft);
}
.token-usage-card .tuc-value {
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 1.55rem;
    font-weight: 600;
    color: var(--claude-text);
    line-height: 1.2;
    margin-bottom: 0.6rem;
}
.token-usage-card .tuc-value .tuc-sep {
    color: var(--claude-text-soft);
    font-weight: 400;
    font-size: 1.15rem;
    margin: 0 0.3rem;
}
.token-usage-card .tuc-unit {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--claude-text-soft);
    margin-left: 0.3rem;
}
.token-usage-track {
    width: 100%;
    height: 8px;
    border-radius: 999px;
    background-color: var(--claude-sidebar-bg);
    overflow: hidden;
}
.token-usage-fill {
    height: 100%;
    border-radius: 999px;
    background-color: var(--claude-accent);
    transition: width 0.3s ease;
}
.token-usage-card.over-limit .tuc-pct {
    color: var(--claude-danger);
}
.token-usage-card.over-limit .token-usage-fill {
    background-color: var(--claude-danger);
}
.token-usage-card.over-limit {
    border-color: var(--claude-danger);
}

/* ---------- World clock (sidebar, above the ATHENA brand) ---------- */
[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .world-clock-marker) {
    background-color: #FFFFFF;
    border: 1px solid var(--claude-border) !important;
    border-radius: 14px !important;
    box-shadow: none !important;
    padding: 0.5rem 0.8rem 0.7rem !important;
    margin-bottom: 0.9rem;
}
.world-clock-header {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--claude-text-soft);
    margin-bottom: 0.35rem;
}
.world-clock-marker ~ div [data-baseweb="select"] > div {
    background-color: var(--claude-bg);
    border: 1px solid var(--claude-border) !important;
    border-radius: 8px;
    min-height: 1.9rem;
    font-size: 0.78rem;
    box-shadow: none !important;
}
.world-clock-time {
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 1.35rem;
    font-weight: 600;
    color: var(--claude-text);
    margin-top: 0.45rem;
    line-height: 1.2;
}
.world-clock-date {
    font-size: 0.74rem;
    color: var(--claude-text-soft);
    margin-top: 0.1rem;
}
</style>
"""
st.markdown(CLAUDE_CSS, unsafe_allow_html=True)

if "history" not in st.session_state:
    st.session_state.history = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "login_username" not in st.session_state:
    st.session_state.login_username = ""
if "is_superadmin" not in st.session_state:
    st.session_state.is_superadmin = False
if "login_error" not in st.session_state:
    st.session_state.login_error = ""
if "login_attempts" not in st.session_state:
    st.session_state.login_attempts = 0
if "login_locked" not in st.session_state:
    st.session_state.login_locked = False
if "login_locked_at" not in st.session_state:
    st.session_state.login_locked_at = None
if "login_lock_reason" not in st.session_state:
    st.session_state.login_lock_reason = None
if "last_chunks" not in st.session_state:
    st.session_state.last_chunks = []
if "last_question" not in st.session_state:
    st.session_state.last_question = ""
if "login_language" not in st.session_state:
    st.session_state.login_language = "🌐 English"
if "world_clock_country" not in st.session_state:
    st.session_state.world_clock_country = "India"
if "auth_token" not in st.session_state:
    st.session_state.auth_token = ""

LANG_CODES = {
    "🌐 English": "en",
    "🌐 Español": "es",
    "🌐 Français": "fr",
    "🌐 Deutsch": "de",
    "🌐 हिन्दी": "hi",
    "🌐 தமிழ்": "ta",
    "🌐 తెలుగు": "te",
    "🌐 ಕನ್ನಡ": "kn",
    "🌐 മലയാളം": "ml",
    "🌐 中文": "zh",
    "🌐 日本語": "ja",
    "🌐 العربية": "ar",
}

TRANSLATIONS = {
    "welcome_back": {
        "en": "Welcome back.", "es": "Bienvenido de nuevo.", "fr": "Content de vous revoir.",
        "de": "Willkommen zurück.", "hi": "वापसी पर स्वागत है.", "ta": "மீண்டும் வரவேற்கிறோம்.",
        "te": "మళ్ళీ స్వాగతం.", "kn": "ಮತ್ತೆ ಸ್ವಾಗತ.", "ml": "വീണ്ടും സ്വാഗതം.",
        "zh": "欢迎回来。", "ja": "おかえりなさい。", "ar": "مرحبًا بعودتك.",
    },
    "login_subtitle": {
        "en": "Sign in to Athena to chat with your documents.",
        "es": "Inicia sesión en Athena para chatear con tus documentos.",
        "fr": "Connectez-vous à Athena pour discuter avec vos documents.",
        "de": "Melde dich bei Athena an, um mit deinen Dokumenten zu chatten.",
        "hi": "अपने दस्तावेज़ों से चैट करने के लिए Athena में साइन इन करें.",
        "ta": "உங்கள் ஆவணங்களுடன் அரட்டையடிக்க Athena-வில் உள்நுழையவும்.",
        "te": "మీ పత్రాలతో చాట్ చేయడానికి Athena‌లోకి సైన్ ఇన్ చేయండి.",
        "kn": "ನಿಮ್ಮ ದಾಖಲೆಗಳೊಂದಿಗೆ ಚಾಟ್ ಮಾಡಲು Athena ಗೆ ಸೈನ್ ಇನ್ ಮಾಡಿ.",
        "ml": "നിങ്ങളുടെ ഡോക്യുമെന്റുകളുമായി ചാറ്റ് ചെയ്യാൻ Athena-യിൽ സൈൻ ഇൻ ചെയ്യുക.",
        "zh": "登录 Athena，与您的文档聊天。", "ja": "ドキュメントとチャットするには Athena にサインインしてください。",
        "ar": "سجّل الدخول إلى Athena للدردشة مع مستنداتك.",
    },
    "lockout_message": {
        "en": "🔒 Locked after 3 failed attempts. Auto-releases in ~{secs}s.",
        "es": "🔒 Bloqueado tras 3 intentos fallidos. Se desbloquea automáticamente en ~{secs}s.",
        "fr": "🔒 Verrouillé après 3 tentatives échouées. Déverrouillage automatique dans ~{secs}s.",
        "de": "🔒 Gesperrt nach 3 fehlgeschlagenen Versuchen. Automatische Freigabe in ~{secs}s.",
        "hi": "🔒 3 असफल प्रयासों के बाद लॉक। लगभग {secs} सेकंड में अपने आप अनलॉक होगा.",
        "ta": "🔒 3 தோல்வியுற்ற முயற்சிகளுக்குப் பிறகு பூட்டப்பட்டது. சுமார் {secs} வினாடிகளில் தானாக திறக்கும்.",
        "te": "🔒 3 విఫల ప్రయత్నాల తర్వాత లాక్ చేయబడింది. సుమారు {secs} సెకన్లలో స్వయంచాలకంగా అన్‌లాక్ అవుతుంది.",
        "kn": "🔒 3 ವಿಫಲ ಪ್ರಯತ್ನಗಳ ನಂತರ ಲಾಕ್ ಆಗಿದೆ. ಸುಮಾರು {secs} ಸೆಕೆಂಡುಗಳಲ್ಲಿ ಸ್ವಯಂಚಾಲಿತವಾಗಿ ಬಿಡುಗಡೆಯಾಗುತ್ತದೆ.",
        "ml": "🔒 3 പരാജയപ്പെട്ട ശ്രമങ്ങൾക്ക് ശേഷം ലോക്ക് ചെയ്തു. ഏകദേശം {secs} സെക്കൻഡിൽ സ്വയമേവ അൺലോക്ക് ആകും.",
        "zh": "🔒 已连续 3 次登录失败，账户已锁定。约 {secs} 秒后自动解锁。",
        "ja": "🔒 3回のログイン失敗によりロックされました。約{secs}秒後に自動解除されます。",
        "ar": "🔒 تم القفل بعد 3 محاولات فاشلة. سيُفتح تلقائيًا خلال ~{secs} ثانية.",
    },
    "lockout_reason_fallback": {
        "en": "3 failed sign-in attempts in a row.", "es": "3 intentos de inicio de sesión fallidos seguidos.",
        "fr": "3 tentatives de connexion échouées d'affilée.", "de": "3 fehlgeschlagene Anmeldeversuche in Folge.",
        "hi": "लगातार 3 असफल साइन-इन प्रयास.", "ta": "தொடர்ந்து 3 உள்நுழைவு முயற்சிகள் தோல்வி.",
        "te": "వరుసగా 3 సైన్-ఇన్ ప్రయత్నాలు విఫలమయ్యాయి.", "kn": "ಸತತ 3 ಸೈನ್-ಇನ್ ಪ್ರಯತ್ನಗಳು ವಿಫಲವಾಗಿವೆ.",
        "ml": "തുടർച്ചയായി 3 സൈൻ-ഇൻ ശ്രമങ്ങൾ പരാജയപ്പെട്ടു.", "zh": "连续 3 次登录尝试失败。",
        "ja": "3回連続でサインインに失敗しました。", "ar": "3 محاولات تسجيل دخول فاشلة متتالية.",
    },
    "check_again": {
        "en": "Check again", "es": "Comprobar de nuevo", "fr": "Vérifier à nouveau", "de": "Erneut prüfen",
        "hi": "फिर से जाँचें", "ta": "மீண்டும் சரிபார்க்கவும்", "te": "మళ్లీ తనిఖీ చేయండి",
        "kn": "ಮತ್ತೆ ಪರಿಶೀಲಿಸಿ", "ml": "വീണ്ടും പരിശോധിക്കുക", "zh": "重新检查", "ja": "再確認", "ar": "تحقق مرة أخرى",
    },
    "username": {
        "en": "Username", "es": "Usuario", "fr": "Nom d'utilisateur", "de": "Benutzername",
        "hi": "उपयोगकर्ता नाम", "ta": "பயனர்பெயர்", "te": "వినియోగదారు పేరు", "kn": "ಬಳಕೆದಾರಹೆಸರು",
        "ml": "ഉപയോക്തൃനാമം", "zh": "用户名", "ja": "ユーザー名", "ar": "اسم المستخدم",
    },
    "password": {
        "en": "Password", "es": "Contraseña", "fr": "Mot de passe", "de": "Passwort", "hi": "पासवर्ड",
        "ta": "கடவுச்சொல்", "te": "పాస్‌వర్డ్", "kn": "ಪಾಸ್‌ವರ್ಡ್", "ml": "പാസ്‌വേഡ്",
        "zh": "密码", "ja": "パスワード", "ar": "كلمة المرور",
    },
    "log_in": {
        "en": "Log in", "es": "Iniciar sesión", "fr": "Se connecter", "de": "Anmelden",
        "hi": "लॉग इन करें", "ta": "உள்நுழையவும்", "te": "లాగిన్ చేయండి", "kn": "ಲಾಗಿನ್ ಮಾಡಿ",
        "ml": "ലോഗിൻ ചെയ്യുക", "zh": "登录", "ja": "ログイン", "ar": "تسجيل الدخول",
    },
    "invalid_login": {
        "en": "Invalid username or password. {remaining} attempt(s) remaining.",
        "es": "Usuario o contraseña incorrectos. Quedan {remaining} intento(s).",
        "fr": "Nom d'utilisateur ou mot de passe invalide. {remaining} tentative(s) restante(s).",
        "de": "Ungültiger Benutzername oder Passwort. Noch {remaining} Versuch(e).",
        "hi": "अमान्य उपयोगकर्ता नाम या पासवर्ड. {remaining} प्रयास शेष.",
        "ta": "தவறான பயனர்பெயர் அல்லது கடவுச்சொல். {remaining} முயற்சிகள் மீதம்.",
        "te": "చెల్లని వినియోగదారు పేరు లేదా పాస్‌వర్డ్. {remaining} ప్రయత్నాలు మిగిలి ఉన్నాయి.",
        "kn": "ಅಮಾನ್ಯ ಬಳಕೆದಾರಹೆಸರು ಅಥವಾ ಪಾಸ್‌ವರ್ಡ್. {remaining} ಪ್ರಯತ್ನಗಳು ಬಾಕಿ ಇವೆ.",
        "ml": "അസാധുവായ ഉപയോക്തൃനാമം അല്ലെങ്കിൽ പാസ്‌വേഡ്. {remaining} ശ്രമങ്ങൾ ബാക്കി.",
        "zh": "用户名或密码无效。还剩 {remaining} 次尝试机会。",
        "ja": "ユーザー名またはパスワードが正しくありません。残り{remaining}回。",
        "ar": "اسم المستخدم أو كلمة المرور غير صحيحة. تبقّى {remaining} محاولة.",
    },
    "login_footer": {
        "en": "By continuing, you agree to Athena's Consumer Terms and acknowledge their Privacy Policy.",
        "es": "Al continuar, aceptas las Condiciones de uso de Athena y reconoces su Política de privacidad.",
        "fr": "En continuant, vous acceptez les Conditions d'utilisation d'Athena et reconnaissez sa Politique de confidentialité.",
        "de": "Wenn du fortfährst, stimmst du den Nutzungsbedingungen von Athena zu und bestätigst die Kenntnisnahme der Datenschutzrichtlinie.",
        "hi": "जारी रखकर, आप Athena की उपयोगकर्ता शर्तों से सहमत होते हैं और उनकी गोपनीयता नीति को स्वीकार करते हैं.",
        "ta": "தொடர்வதன் மூலம், Athena-வின் நுகர்வோர் விதிமுறைகளை ஏற்கிறீர்கள் மற்றும் அவர்களின் தனியுரிமைக் கொள்கையை ஒப்புக்கொள்கிறீர்கள்.",
        "te": "కొనసాగించడం ద్వారా, మీరు Athena యొక్క వినియోగదారు నిబంధనలను అంగీకరిస్తున్నారు మరియు వారి గోప్యతా విధానాన్ని అంగీకరిస్తున్నారు.",
        "kn": "ಮುಂದುವರಿಸುವ ಮೂಲಕ, ನೀವು Athena ನ ಗ್ರಾಹಕ ನಿಯಮಗಳನ್ನು ಒಪ್ಪುತ್ತೀರಿ ಮತ್ತು ಅವರ ಗೌಪ್ಯತಾ ನೀತಿಯನ್ನು ಒಪ್ಪಿಕೊಳ್ಳುತ್ತೀರಿ.",
        "ml": "തുടരുന്നതിലൂടെ, നിങ്ങൾ Athena-യുടെ ഉപഭോക്തൃ നിബന്ധനകൾ അംഗീകരിക്കുകയും അവരുടെ സ്വകാര്യതാ നയം അംഗീകരിക്കുകയും ചെയ്യുന്നു.",
        "zh": "继续即表示您同意 Athena 的《消费者条款》并确认已知悉其《隐私政策》。",
        "ja": "続行すると、Athena の利用規約に同意し、プライバシーポリシーを確認したものとみなされます。",
        "ar": "بالمتابعة، فإنك توافق على شروط استخدام Athena وتقر بالاطلاع على سياسة الخصوصية الخاصة بها.",
    },
    "tab_home": {
        "en": "Home", "es": "Inicio", "fr": "Accueil", "de": "Start", "hi": "होम", "ta": "முகப்பு",
        "te": "హోమ్", "kn": "ಮುಖಪುಟ", "ml": "ഹോം", "zh": "主页", "ja": "ホーム", "ar": "الرئيسية",
    },
    "tab_query_trace": {
        "en": "Query Trace", "es": "Rastreo de consulta", "fr": "Trace de requête",
        "de": "Abfrage-Trace", "hi": "क्वेरी ट्रेस", "ta": "வினவல் தடமறிதல்",
        "te": "క్వరీ ట్రేస్", "kn": "ಕ್ವೆರಿ ಟ್ರೇಸ್", "ml": "ക്വറി ട്രെയ്സ്",
        "zh": "查询追踪", "ja": "クエリトレース", "ar": "تتبع الاستعلام",
    },
    "new_chat": {
        "en": "＋  New chat", "es": "＋  Nuevo chat", "fr": "＋  Nouvelle discussion", "de": "＋  Neuer Chat",
        "hi": "＋  नई चैट", "ta": "＋  புதிய அரட்டை", "te": "＋  కొత్త చాట్", "kn": "＋  ಹೊಸ ಚಾಟ್",
        "ml": "＋  പുതിയ ചാറ്റ്", "zh": "＋  新对话", "ja": "＋  新しいチャット", "ar": "＋  محادثة جديدة",
    },
    "documents_label": {
        "en": "Documents", "es": "Documentos", "fr": "Documents", "de": "Dokumente", "hi": "दस्तावेज़",
        "ta": "ஆவணங்கள்", "te": "పత్రాలు", "kn": "ದಾಖಲೆಗಳು", "ml": "ഡോക്യുമെന്റുകൾ",
        "zh": "文档", "ja": "ドキュメント", "ar": "المستندات",
    },
    "upload_label": {
        "en": "Upload a .txt, .pdf, or .docx file", "es": "Sube un archivo .txt, .pdf o .docx",
        "fr": "Téléversez un fichier .txt, .pdf ou .docx", "de": "Lade eine .txt-, .pdf- oder .docx-Datei hoch",
        "hi": "एक .txt, .pdf, या .docx फ़ाइल अपलोड करें",
        "ta": "ஒரு .txt, .pdf, அல்லது .docx கோப்பைப் பதிவேற்றவும்",
        "te": "ఒక .txt, .pdf, లేదా .docx ఫైల్‌ను అప్‌లోడ్ చేయండి",
        "kn": "ಒಂದು .txt, .pdf, ಅಥವಾ .docx ಫೈಲ್ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ",
        "ml": "ഒരു .txt, .pdf, അല്ലെങ്കിൽ .docx ഫയൽ അപ്‌ലോഡ് ചെയ്യുക", "zh": "上传 .txt、.pdf 或 .docx 文件",
        "ja": ".txt、.pdf、または .docx ファイルをアップロード", "ar": "قم بتحميل ملف .txt أو .pdf أو .docx",
    },
    "ingest_btn": {
        "en": "Ingest", "es": "Procesar", "fr": "Ingérer", "de": "Importieren", "hi": "इनजेस्ट करें",
        "ta": "உள்ளிடு", "te": "ఇన్‌జెస్ట్", "kn": "ಇಂಜೆಸ್ಟ್", "ml": "ഇൻജെസ്റ്റ്",
        "zh": "导入", "ja": "取り込む", "ar": "استيعاب",
    },
    "ingesting": {
        "en": "Ingesting...", "es": "Procesando...", "fr": "Ingestion en cours...", "de": "Wird importiert...",
        "hi": "इनजेस्ट हो रहा है...", "ta": "உள்ளிடப்படுகிறது...", "te": "ఇన్‌జెస్ట్ చేస్తోంది...",
        "kn": "ಇಂಜೆಸ್ಟ್ ಮಾಡಲಾಗುತ್ತಿದೆ...", "ml": "ഇൻജെസ്റ്റ് ചെയ്യുന്നു...", "zh": "正在导入…",
        "ja": "取り込み中...", "ar": "جارٍ الاستيعاب...",
    },
    "added_chunks": {
        "en": "Added {n} chunks from {filename}", "es": "Se agregaron {n} fragmentos de {filename}",
        "fr": "{n} fragments ajoutés depuis {filename}", "de": "{n} Abschnitte aus {filename} hinzugefügt",
        "hi": "{filename} से {n} खंड जोड़े गए", "ta": "{filename} இலிருந்து {n} பகுதிகள் சேர்க்கப்பட்டன",
        "te": "{filename} నుండి {n} భాగాలు జోడించబడ్డాయి", "kn": "{filename} ನಿಂದ {n} ಭಾಗಗಳನ್ನು ಸೇರಿಸಲಾಗಿದೆ",
        "ml": "{filename} ൽ നിന്ന് {n} ഭാഗങ്ങൾ ചേർത്തു", "zh": "已从 {filename} 添加 {n} 个片段",
        "ja": "{filename} から {n} 個のチャンクを追加しました", "ar": "تمت إضافة {n} جزءًا من {filename}",
    },
    "ingested_files_label": {
        "en": "Ingested files", "es": "Archivos procesados", "fr": "Fichiers ingérés", "de": "Importierte Dateien",
        "hi": "इनजेस्ट की गई फ़ाइलें", "ta": "உள்ளிடப்பட்ட கோப்புகள்", "te": "ఇన్‌జెస్ట్ చేసిన ఫైల్‌లు",
        "kn": "ಇಂಜೆಸ್ಟ್ ಮಾಡಿದ ಫೈಲ್‌ಗಳು", "ml": "ഇൻജെസ്റ്റ് ചെയ്ത ഫയലുകൾ", "zh": "已导入的文件",
        "ja": "取り込み済みファイル", "ar": "الملفات المستوعبة",
    },
    "no_documents": {
        "en": "No documents ingested yet.", "es": "Aún no se han procesado documentos.",
        "fr": "Aucun document ingéré pour le moment.", "de": "Noch keine Dokumente importiert.",
        "hi": "अभी तक कोई दस्तावेज़ इनजेस्ट नहीं हुआ.", "ta": "இதுவரை ஆவணங்கள் எதுவும் உள்ளிடப்படவில்லை.",
        "te": "ఇంకా పత్రాలు ఏవీ ఇన్‌జెస్ట్ చేయబడలేదు.", "kn": "ಇನ್ನೂ ಯಾವುದೇ ದಾಖಲೆಗಳನ್ನು ಇಂಜೆಸ್ಟ್ ಮಾಡಿಲ್ಲ.",
        "ml": "ഇതുവരെ ഡോക്യുമെന്റുകളൊന്നും ഇൻജെസ്റ്റ് ചെയ്തിട്ടില്ല.", "zh": "尚未导入任何文档。",
        "ja": "まだドキュメントが取り込まれていません。", "ar": "لم يتم استيعاب أي مستندات بعد.",
    },
    "backend_unreachable": {
        "en": "Backend not reachable. Is it running?", "es": "No se puede acceder al backend. ¿Está en ejecución?",
        "fr": "Backend inaccessible. Est-il en cours d'exécution ?", "de": "Backend nicht erreichbar. Läuft es?",
        "hi": "बैकएंड तक नहीं पहुँचा जा सका. क्या यह चल रहा है?",
        "ta": "பேக்எண்டை அணுக முடியவில்லை. அது இயங்குகிறதா?",
        "te": "బ్యాకెండ్ చేరుకోలేకపోయింది. అది నడుస్తోందా?",
        "kn": "ಬ್ಯಾಕೆಂಡ್ ತಲುಪಲಾಗುತ್ತಿಲ್ಲ. ಅದು ಚಾಲನೆಯಲ್ಲಿದೆಯೇ?",
        "ml": "ബാക്കെൻഡ് എത്തിച്ചേരാനായില്ല. അത് പ്രവർത്തിക്കുന്നുണ്ടോ?",
        "zh": "无法连接到后端服务，它正在运行吗？", "ja": "バックエンドに接続できません。起動していますか？",
        "ar": "تعذّر الوصول إلى الخادم الخلفي. هل هو قيد التشغيل؟",
    },
    "clear_all_docs": {
        "en": "🗑️  Clear all documents", "es": "🗑️  Borrar todos los documentos",
        "fr": "🗑️  Effacer tous les documents", "de": "🗑️  Alle Dokumente löschen",
        "hi": "🗑️  सभी दस्तावेज़ हटाएँ", "ta": "🗑️  அனைத்து ஆவணங்களையும் அழி",
        "te": "🗑️  అన్ని పత్రాలను తొలగించండి", "kn": "🗑️  ಎಲ್ಲಾ ದಾಖಲೆಗಳನ್ನು ಅಳಿಸಿ",
        "ml": "🗑️  എല്ലാ ഡോക്യുമെന്റുകളും മായ്ക്കുക", "zh": "🗑️  清除所有文档",
        "ja": "🗑️  すべてのドキュメントを削除", "ar": "🗑️  حذف جميع المستندات",
    },
    "role_local": {
        "en": "Local", "es": "Local", "fr": "Local", "de": "Lokal", "hi": "स्थानीय", "ta": "உள்ளூர்",
        "te": "స్థానిక", "kn": "ಸ್ಥಳೀಯ", "ml": "ലോക്കൽ", "zh": "本地", "ja": "ローカル", "ar": "محلي",
    },
    "log_out": {
        "en": "Log out", "es": "Cerrar sesión", "fr": "Se déconnecter", "de": "Abmelden", "hi": "लॉग आउट",
        "ta": "வெளியேறு", "te": "లాగ్ అవుట్", "kn": "ಲಾಗ್ ಔಟ್", "ml": "ലോഗ് ഔട്ട്",
        "zh": "退出登录", "ja": "ログアウト", "ar": "تسجيل الخروج",
    },
    "chat_placeholder": {
        "en": "Ask a question about your documents...", "es": "Haz una pregunta sobre tus documentos...",
        "fr": "Posez une question sur vos documents...", "de": "Stelle eine Frage zu deinen Dokumenten...",
        "hi": "अपने दस्तावेज़ों के बारे में एक प्रश्न पूछें...", "ta": "உங்கள் ஆவணங்கள் பற்றி ஒரு கேள்வி கேளுங்கள்...",
        "te": "మీ పత్రాల గురించి ప్రశ్న అడగండి...", "kn": "ನಿಮ್ಮ ದಾಖಲೆಗಳ ಬಗ್ಗೆ ಪ್ರಶ್ನೆ ಕೇಳಿ...",
        "ml": "നിങ്ങളുടെ ഡോക്യുമെന്റുകളെക്കുറിച്ച് ഒരു ചോദ്യം ചോദിക്കുക...", "zh": "就您的文档提出问题…",
        "ja": "ドキュメントについて質問してください...", "ar": "اطرح سؤالاً حول مستنداتك...",
    },
    "thinking": {
        "en": "Thinking...", "es": "Pensando...", "fr": "Réflexion en cours...", "de": "Denke nach...",
        "hi": "सोच रहा है...", "ta": "சிந்திக்கிறது...", "te": "ఆలోచిస్తోంది...", "kn": "ಯೋಚಿಸುತ್ತಿದೆ...",
        "ml": "ചിന്തിക്കുന്നു...", "zh": "思考中…", "ja": "考え中...", "ar": "يفكر...",
    },
    "sources_label": {
        "en": "Sources:", "es": "Fuentes:", "fr": "Sources :", "de": "Quellen:", "hi": "स्रोत:",
        "ta": "ஆதாரங்கள்:", "te": "మూలాలు:", "kn": "ಮೂಲಗಳು:", "ml": "സ്രോതസ്സുകൾ:",
        "zh": "来源：", "ja": "出典：", "ar": "المصادر:",
    },
    "greeting": {
        "en": "What can I help you find?", "es": "¿Qué puedo ayudarte a encontrar?",
        "fr": "Que puis-je vous aider à trouver ?", "de": "Wobei kann ich dir helfen?",
        "hi": "मैं आपकी किस चीज़ को खोजने में मदद कर सकता हूँ?", "ta": "நான் எதைக் கண்டறிய உதவ முடியும்?",
        "te": "నేను మీకు దేనిని కనుగొనడంలో సహాయపడగలను?", "kn": "ನಾನು ನಿಮಗೆ ಏನನ್ನು ಹುಡುಕಲು ಸಹಾಯ ಮಾಡಬಹುದು?",
        "ml": "എന്ത് കണ്ടെത്താൻ എനിക്ക് നിങ്ങളെ സഹായിക്കാം?", "zh": "我能帮您找到什么？",
        "ja": "何をお探しですか？", "ar": "بماذا يمكنني مساعدتك في العثور عليه؟",
    },
    "subgreeting": {
        "en": "Ask a question about your ingested documents.", "es": "Haz una pregunta sobre tus documentos procesados.",
        "fr": "Posez une question sur vos documents ingérés.", "de": "Stelle eine Frage zu deinen importierten Dokumenten.",
        "hi": "अपने इनजेस्ट किए गए दस्तावेज़ों के बारे में एक प्रश्न पूछें.",
        "ta": "உள்ளிடப்பட்ட ஆவணங்கள் பற்றி ஒரு கேள்வி கேளுங்கள்.",
        "te": "మీ ఇన్‌జెస్ట్ చేసిన పత్రాల గురించి ప్రశ్న అడగండి.",
        "kn": "ಇಂಜೆಸ್ಟ್ ಮಾಡಿದ ದಾಖಲೆಗಳ ಬಗ್ಗೆ ಪ್ರಶ್ನೆ ಕೇಳಿ.",
        "ml": "ഇൻജെസ്റ്റ് ചെയ്ത ഡോക്യുമെന്റുകളെക്കുറിച്ച് ഒരു ചോദ്യം ചോദിക്കുക.",
        "zh": "就已导入的文档提出问题。", "ja": "取り込んだドキュメントについて質問してください。",
        "ar": "اطرح سؤالاً حول المستندات المستوعبة.",
    },
    "suggestion_1": {
        "en": "Summarize the documents", "es": "Resumir los documentos", "fr": "Résumer les documents",
        "de": "Dokumente zusammenfassen", "hi": "दस्तावेज़ों का सारांश दें", "ta": "ஆவணங்களை சுருக்கவும்",
        "te": "పత్రాలను సారాంశం చేయండి", "kn": "ದಾಖಲೆಗಳನ್ನು ಸಾರಾಂಶಗೊಳಿಸಿ", "ml": "ഡോക്യുമെന്റുകൾ സംഗ്രഹിക്കുക",
        "zh": "总结文档", "ja": "ドキュメントを要約する", "ar": "تلخيص المستندات",
    },
    "suggestion_2": {
        "en": "What are the key points?", "es": "¿Cuáles son los puntos clave?", "fr": "Quels sont les points clés ?",
        "de": "Was sind die wichtigsten Punkte?", "hi": "मुख्य बिंदु क्या हैं?", "ta": "முக்கிய அம்சங்கள் என்ன?",
        "te": "ముఖ్యాంశాలు ఏమిటి?", "kn": "ಪ್ರಮುಖ ಅಂಶಗಳು ಯಾವುವು?", "ml": "പ്രധാന പോയിന്റുകൾ എന്തൊക്കെയാണ്?",
        "zh": "关键要点是什么？", "ja": "重要なポイントは何ですか？", "ar": "ما هي النقاط الرئيسية؟",
    },
    "suggestion_3": {
        "en": "List all sources", "es": "Listar todas las fuentes", "fr": "Lister toutes les sources",
        "de": "Alle Quellen auflisten", "hi": "सभी स्रोत सूचीबद्ध करें", "ta": "அனைத்து ஆதாரங்களையும் பட்டியலிடுங்கள்",
        "te": "అన్ని మూలాలను జాబితా చేయండి", "kn": "ಎಲ್ಲಾ ಮೂಲಗಳನ್ನು ಪಟ್ಟಿ ಮಾಡಿ", "ml": "എല്ലാ സ്രോതസ്സുകളും ലിസ്റ്റ് ചെയ്യുക",
        "zh": "列出所有来源", "ja": "すべての出典を一覧表示", "ar": "سرد جميع المصادر",
    },
    "code_tab_hint": {
        "en": "Ask a question on Home to see the raw retrieved context chunks here.",
        "es": "Haz una pregunta en Inicio para ver aquí los fragmentos de contexto recuperados.",
        "fr": "Posez une question dans Accueil pour voir ici les fragments de contexte récupérés.",
        "de": "Stelle eine Frage auf der Startseite, um hier die abgerufenen Kontextabschnitte zu sehen.",
        "hi": "यहाँ प्राप्त संदर्भ खंड देखने के लिए होम पर एक प्रश्न पूछें.",
        "ta": "இங்கு பெறப்பட்ட சூழல் பகுதிகளைப் பார்க்க முகப்பில் ஒரு கேள்வி கேளுங்கள்.",
        "te": "ఇక్కడ పొందిన సందర్భ భాగాలను చూడటానికి హోమ్‌లో ప్రశ్న అడగండి.",
        "kn": "ಇಲ್ಲಿ ಪಡೆದ ಸಂದರ್ಭ ಭಾಗಗಳನ್ನು ನೋಡಲು ಮುಖಪುಟದಲ್ಲಿ ಪ್ರಶ್ನೆ ಕೇಳಿ.",
        "ml": "ഇവിടെ ലഭിച്ച കോൺടെക്സ്റ്റ് ഭാഗങ്ങൾ കാണാൻ ഹോമിൽ ഒരു ചോദ്യം ചോദിക്കുക.",
        "zh": "在主页提出问题，即可在此查看检索到的原始上下文片段。",
        "ja": "ホームで質問すると、取得された生のコンテキストチャンクがここに表示されます。",
        "ar": "اطرح سؤالاً في الرئيسية لرؤية أجزاء السياق المسترجعة هنا.",
    },
    "context_retrieved": {
        "en": 'Context retrieved for: "{q}"', "es": 'Contexto recuperado para: "{q}"',
        "fr": 'Contexte récupéré pour : "{q}"', "de": 'Kontext abgerufen für: "{q}"',
        "hi": 'इसके लिए संदर्भ प्राप्त हुआ: "{q}"', "ta": '"{q}" க்கான சூழல் பெறப்பட்டது',
        "te": '"{q}" కోసం సందర్భం పొందబడింది', "kn": '"{q}" ಗಾಗಿ ಸಂದರ್ಭ ಪಡೆಯಲಾಗಿದೆ',
        "ml": '"{q}" എന്നതിനായി കോൺടെക്സ്റ്റ് ലഭിച്ചു', "zh": '已检索到上下文，问题为："{q}"',
        "ja": '"{q}" に対して取得されたコンテキスト', "ar": 'تم استرجاع السياق لـ: "{q}"',
    },
    "chunk_label": {
        "en": "chunk {n}", "es": "fragmento {n}", "fr": "fragment {n}", "de": "Abschnitt {n}",
        "hi": "खंड {n}", "ta": "பகுதி {n}", "te": "భాగం {n}", "kn": "ಭಾಗ {n}", "ml": "ഭாഗം {n}",
        "zh": "片段 {n}", "ja": "チャンク {n}", "ar": "الجزء {n}",
    },
    "language_bar_label": {
        "en": "Language", "es": "Idioma", "fr": "Langue", "de": "Sprache", "hi": "भाषा", "ta": "மொழி",
        "te": "భాష", "kn": "ಭಾಷೆ", "ml": "ഭാഷ", "zh": "语言", "ja": "言語", "ar": "اللغة",
    },
    "captcha_label": {
        "en": "Security code", "es": "Código de seguridad", "fr": "Code de sécurité",
        "de": "Sicherheitscode", "hi": "सुरक्षा कोड", "ta": "பாதுகாப்பு குறியீடு",
        "te": "భద్రతా కోడ్", "kn": "ಭದ್ರತಾ ಕೋಡ್", "ml": "സുരക്ഷാ കോഡ്",
        "zh": "安全码", "ja": "セキュリティコード", "ar": "رمز الأمان",
    },
    "captcha_placeholder": {
        "en": "Enter the code shown above", "es": "Introduce el código mostrado arriba",
        "fr": "Saisissez le code affiché ci-dessus", "de": "Gib den oben angezeigten Code ein",
        "hi": "ऊपर दिखाया गया कोड दर्ज करें", "ta": "மேலே காட்டப்பட்ட குறியீட்டை உள்ளிடவும்",
        "te": "పైన చూపిన కోడ్‌ను నమోదు చేయండి", "kn": "ಮೇಲೆ ತೋರಿಸಿರುವ ಕೋಡ್ ಅನ್ನು ನಮೂದಿಸಿ",
        "ml": "മുകളിൽ കാണിച്ചിരിക്കുന്ന കോഡ് നൽകുക", "zh": "输入上方显示的验证码",
        "ja": "上に表示されたコードを入力してください", "ar": "أدخل الرمز الموضح أعلاه",
    },
    "captcha_mismatch": {
        "en": "The code didn't match. Please try again.", "es": "El código no coincide. Inténtalo de nuevo.",
        "fr": "Le code ne correspond pas. Veuillez réessayer.",
        "de": "Der Code stimmt nicht überein. Bitte versuche es erneut.",
        "hi": "कोड मेल नहीं खाया. कृपया पुनः प्रयास करें.",
        "ta": "குறியீடு பொருந்தவில்லை. மீண்டும் முயற்சிக்கவும்.",
        "te": "కోడ్ సరిపోలలేదు. దయచేసి మళ్లీ ప్రయత్నించండి.",
        "kn": "ಕೋಡ್ ಹೊಂದಾಣಿಕೆಯಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        "ml": "കോഡ് പൊരുത്തപ്പെട്ടില്ല. വീണ്ടും ശ്രമിക്കുക.",
        "zh": "验证码不匹配，请重试。", "ja": "コードが一致しませんでした。もう一度お試しください。",
        "ar": "الرمز غير مطابق. حاول مرة أخرى.",
    },
}


def current_lang():
    return LANG_CODES.get(st.session_state.login_language, "en")


def t(key, **kwargs):
    entry = TRANSLATIONS.get(key, {})
    template = entry.get(current_lang()) or entry.get("en", key)
    return template.format(**kwargs) if kwargs else template


def language_selector():
    st.markdown('<div class="lang-bar-marker"></div>', unsafe_allow_html=True)
    st.selectbox(
        t("language_bar_label"),
        list(LANG_CODES.keys()),
        key="login_language",
        label_visibility="collapsed",
    )


def render_world_clock():
    with st.container(border=True):
        st.markdown('<div class="world-clock-marker"></div>', unsafe_allow_html=True)
        st.markdown('<div class="world-clock-header">🕒 World clock</div>', unsafe_allow_html=True)
        country = st.selectbox(
            "Country",
            list(COUNTRY_TIMEZONES.keys()),
            key="world_clock_country",
            label_visibility="collapsed",
        )
        now = datetime.datetime.now(ZoneInfo(COUNTRY_TIMEZONES[country]))
        st.markdown(
            f'<div class="world-clock-time">{now.strftime("%I:%M:%S %p")}</div>'
            f'<div class="world-clock-date">{now.strftime("%A, %d %B %Y")}</div>',
            unsafe_allow_html=True,
        )


_CAPTCHA_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no O/0, I/1 — avoids ambiguity


def _random_captcha_text(length: int = 5) -> str:
    return "".join(random.choice(_CAPTCHA_CHARS) for _ in range(length))


def _render_captcha_image(text: str) -> bytes:
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


# Rotating AI-themed visuals for the login page's left panel — each tied to
# something Athena actually does, not generic stock art. Rotation itself is
# pure CSS (see .login-scene keyframes in CLAUDE_CSS), so it keeps cycling
# every ~2.5 minutes even while the page sits idle with no Streamlit rerun.
_LOGIN_SCENES = [
    {
        "title": "Powered by Athena",
        "subtitle": "Advanced language understanding behind every answer.",
        "svg": """<svg viewBox="0 0 220 220" fill="none" xmlns="http://www.w3.org/2000/svg">
            <line x1="110" y1="60" x2="60" y2="110" stroke="rgba(217,119,87,0.45)" stroke-width="1.5"/>
            <line x1="110" y1="60" x2="160" y2="110" stroke="rgba(217,119,87,0.45)" stroke-width="1.5"/>
            <line x1="110" y1="60" x2="110" y2="150" stroke="rgba(217,119,87,0.45)" stroke-width="1.5"/>
            <line x1="60" y1="110" x2="110" y2="150" stroke="rgba(217,119,87,0.3)" stroke-width="1.5"/>
            <line x1="160" y1="110" x2="110" y2="150" stroke="rgba(217,119,87,0.3)" stroke-width="1.5"/>
            <line x1="60" y1="110" x2="160" y2="110" stroke="rgba(217,119,87,0.3)" stroke-width="1.5"/>
            <circle cx="110" cy="60" r="9" fill="#D97757"/>
            <circle cx="60" cy="110" r="7" fill="#E8A283"/>
            <circle cx="160" cy="110" r="7" fill="#E8A283"/>
            <circle cx="110" cy="150" r="7" fill="#E8A283"/>
        </svg>""",
    },
    {
        "title": "Retrieval-Augmented Answers",
        "subtitle": "Grounded in the documents you upload, not guesswork.",
        "svg": """<svg viewBox="0 0 220 220" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="60" y="70" width="70" height="90" rx="8" fill="rgba(255,255,255,0.06)" stroke="rgba(232,162,131,0.5)" stroke-width="1.5"/>
            <rect x="50" y="60" width="70" height="90" rx="8" fill="rgba(255,255,255,0.08)" stroke="rgba(232,162,131,0.6)" stroke-width="1.5"/>
            <rect x="40" y="50" width="70" height="90" rx="8" fill="#2A2620" stroke="#D97757" stroke-width="1.5"/>
            <line x1="55" y1="70" x2="95" y2="70" stroke="rgba(217,119,87,0.7)" stroke-width="2"/>
            <line x1="55" y1="85" x2="95" y2="85" stroke="rgba(217,119,87,0.45)" stroke-width="2"/>
            <line x1="55" y1="100" x2="85" y2="100" stroke="rgba(217,119,87,0.45)" stroke-width="2"/>
            <circle cx="150" cy="130" r="24" fill="none" stroke="#D97757" stroke-width="4"/>
            <line x1="168" y1="148" x2="188" y2="168" stroke="#D97757" stroke-width="5" stroke-linecap="round"/>
        </svg>""",
    },
    {
        "title": "Ask Anything",
        "subtitle": "Chat naturally with your knowledge base, in any language.",
        "svg": """<svg viewBox="0 0 220 220" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="30" y="60" width="105" height="52" rx="18" fill="rgba(255,255,255,0.08)" stroke="rgba(232,162,131,0.5)" stroke-width="1.5"/>
            <circle cx="58" cy="86" r="3" fill="rgba(232,162,131,0.85)"/>
            <circle cx="73" cy="86" r="3" fill="rgba(232,162,131,0.85)"/>
            <circle cx="88" cy="86" r="3" fill="rgba(232,162,131,0.85)"/>
            <rect x="85" y="120" width="105" height="52" rx="18" fill="#D97757"/>
            <path d="M172 34 l4.5 11 l11 4.5 l-11 4.5 l-4.5 11 l-4.5 -11 l-11 -4.5 l11 -4.5 z" fill="#E8A283"/>
        </svg>""",
    },
    {
        "title": "YARA-Scanned Uploads",
        "subtitle": "Every file screened for malware before it's ever ingested.",
        "svg": """<svg viewBox="0 0 220 220" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M110 40 L165 60 V110 C165 145 140 168 110 180 C80 168 55 145 55 110 V60 Z"
                  fill="rgba(255,255,255,0.06)" stroke="#D97757" stroke-width="3"/>
            <path d="M85 108 L102 126 L138 88" fill="none" stroke="#D97757" stroke-width="7"
                  stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
    },
    {
        "title": "Vector Search",
        "subtitle": "Fast, semantic retrieval across everything you've indexed.",
        "svg": """<svg viewBox="0 0 220 220" fill="none" xmlns="http://www.w3.org/2000/svg">
            <ellipse cx="78" cy="86" rx="35" ry="30" fill="none" stroke="rgba(217,119,87,0.35)" stroke-width="1.5" stroke-dasharray="3 3"/>
            <ellipse cx="152" cy="145" rx="30" ry="25" fill="none" stroke="rgba(217,119,87,0.35)" stroke-width="1.5" stroke-dasharray="3 3"/>
            <circle cx="70" cy="70" r="4" fill="#E8A283"/>
            <circle cx="90" cy="85" r="4" fill="#D97757"/>
            <circle cx="65" cy="95" r="4" fill="#E8A283"/>
            <circle cx="150" cy="130" r="4" fill="#E8A283"/>
            <circle cx="165" cy="150" r="4" fill="#D97757"/>
            <circle cx="140" cy="155" r="4" fill="#E8A283"/>
            <circle cx="120" cy="60" r="4" fill="rgba(232,162,131,0.6)"/>
            <circle cx="60" cy="150" r="4" fill="rgba(232,162,131,0.6)"/>
        </svg>""",
    },
]


def _login_visual_html() -> str:
    scenes = "".join(
        f'<div class="login-scene" data-idx="{i}">{s["svg"]}'
        f'<div class="login-scene-title">{s["title"]}</div>'
        f'<div class="login-scene-subtitle">{s["subtitle"]}</div></div>'
        for i, s in enumerate(_LOGIN_SCENES)
    )
    return (
        '<div class="login-visual-marker"></div>'
        f'<div class="login-visual-brand">{athena_logo(26)}'
        '<span>ATHENA <span class="login-visual-brand-accent">AI</span></span></div>'
        f'<div class="login-scene-stack">{scenes}</div>'
        '<div class="login-visual-trust">🔒 YARA-scanned uploads'
        '<span>&middot;</span>⚡ Powered by Athena'
        '<span>&middot;</span>🔐 Role-based access</div>'
    )


def _reset_lockout():
    st.session_state.login_attempts = 0
    st.session_state.login_locked = False
    st.session_state.login_locked_at = None
    st.session_state.login_lock_reason = None


def _check_credentials(username, password):
    """Returns (ok, is_superadmin, message). The backend is the single source of
    truth for both credentials AND login-attempt throttling (it tracks failures
    per-account regardless of which client hits it) — its message, when present,
    should be shown instead of a locally-computed one, and a 429 means the
    account is locked backend-side even if this browser session's own attempt
    counter hasn't reached the limit yet."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"username": username, "password": password},
            timeout=5,
        )
    except requests.exceptions.RequestException:
        return False, False, None
    if resp.ok:
        data = resp.json()
        st.session_state.auth_token = data["access_token"]
        return True, data["role"] == "SuperAdmin", None
    try:
        message = resp.json().get("detail")
    except ValueError:
        message = None
    return False, False, message


def _quick_login(username: str, password: str) -> None:
    """One-click sign-in for the login page's ADMIN/SuperAdmin quick-access
    buttons. Goes through the same real /auth/login call as typing
    credentials in by hand — this does not bypass the backend's lockout
    throttling or audit logging, it only skips the manual typing step."""
    if not password:
        st.session_state.login_error = (
            f"Quick sign-in for {username} isn't configured "
            "(missing password env var on the frontend service)."
        )
        st.rerun()
        return
    ok, is_superadmin, message = _check_credentials(username, password)
    if ok:
        st.session_state.authenticated = True
        st.session_state.login_username = username
        st.session_state.is_superadmin = is_superadmin
        st.session_state.login_error = ""
        _reset_lockout()
        st.session_state.pop("captcha_text", None)
        st.rerun()
    else:
        st.session_state.login_error = message or f"Quick sign-in for {username} failed."
        st.rerun()


def _auth_headers():
    token = st.session_state.get("auth_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def render_login():
    st.markdown('<div class="login-page-marker"></div>', unsafe_allow_html=True)

    # Auto-release the lock once it has been in place for LOCKOUT_SECONDS.
    if st.session_state.login_locked and st.session_state.login_locked_at is not None:
        if time.time() - st.session_state.login_locked_at >= LOCKOUT_SECONDS:
            _reset_lockout()

    st.markdown('<div class="login-split-marker"></div>', unsafe_allow_html=True)
    visual_col, mid = st.columns([5, 6])
    with visual_col:
        st.markdown(_login_visual_html(), unsafe_allow_html=True)
    with mid:
        st.markdown('<div class="login-form-marker"></div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('<div class="login-card-marker"></div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="login-logo">{athena_logo(32)}'
                '<span class="login-logo-name">ATHENA <span class="login-logo-name-accent">AI</span></span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="login-eyebrow">Secure Sign-In</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="login-title">{t("welcome_back")}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="login-subtitle">{t("login_subtitle")}</div>',
                unsafe_allow_html=True,
            )

            if st.session_state.login_locked:
                elapsed = time.time() - st.session_state.login_locked_at
                remaining_secs = max(0, int(LOCKOUT_SECONDS - elapsed))
                st.error(t("lockout_message", secs=remaining_secs))
                st.caption(f"Reason: {st.session_state.login_lock_reason or t('lockout_reason_fallback')}")
                if st.button(t("check_again"), key="lockout_recheck"):
                    st.rerun()
            else:
                if "captcha_text" not in st.session_state:
                    st.session_state.captcha_text = _random_captcha_text()

                username = st.text_input(t("username"), placeholder=t("username"), key="username_input")
                password = st.text_input(
                    t("password"), type="password", placeholder=t("password"), key="password_input"
                )

                if QUICK_LOGIN_ADMIN_PASSWORD or QUICK_LOGIN_SUPERADMIN_PASSWORD:
                    st.markdown('<div class="quick-login-marker"></div>', unsafe_allow_html=True)
                    st.caption("Quick sign-in")
                    qa_col, qs_col = st.columns(2)
                    with qa_col:
                        if st.button("ADMIN", key="quick_login_admin", use_container_width=True):
                            _quick_login(QUICK_LOGIN_ADMIN_USERNAME, QUICK_LOGIN_ADMIN_PASSWORD)
                    with qs_col:
                        if st.button("SuperAdmin", key="quick_login_superadmin", use_container_width=True):
                            _quick_login(QUICK_LOGIN_SUPERADMIN_USERNAME, QUICK_LOGIN_SUPERADMIN_PASSWORD)

                cap_col, refresh_col = st.columns([1, 1])
                with cap_col:
                    st.markdown('<div class="captcha-marker"></div>', unsafe_allow_html=True)
                    st.image(_render_captcha_image(st.session_state.captcha_text), use_container_width=True)
                with refresh_col:
                    st.markdown('<div class="captcha-refresh-marker"></div>', unsafe_allow_html=True)
                    if st.button("🔄", key="captcha_refresh", use_container_width=True):
                        st.session_state.captcha_text = _random_captcha_text()
                        st.rerun()
                captcha_input = st.text_input(
                    t("captcha_label"), placeholder=t("captcha_placeholder"), key="captcha_input"
                )

                st.markdown('<div class="email-continue-marker"></div>', unsafe_allow_html=True)
                submitted = st.button(t("log_in"), use_container_width=True, key="login_submit_btn")

                if submitted:
                    if captcha_input.strip().upper() != st.session_state.captcha_text.upper():
                        st.session_state.captcha_text = _random_captcha_text()
                        st.session_state.login_error = t("captcha_mismatch")
                        st.rerun()
                    else:
                        ok, is_superadmin, message = _check_credentials(username, password)
                        if ok:
                            st.session_state.authenticated = True
                            st.session_state.login_username = username
                            st.session_state.is_superadmin = is_superadmin
                            st.session_state.login_error = ""
                            _reset_lockout()
                            st.session_state.pop("captcha_text", None)
                            st.rerun()
                        else:
                            st.session_state.captcha_text = _random_captcha_text()
                            st.session_state.login_attempts += 1
                            remaining = MAX_LOGIN_ATTEMPTS - st.session_state.login_attempts
                            # The backend enforces the real, authoritative lockout (it tracks
                            # failures per-account regardless of client) and already sent the
                            # alert email itself — a 429 means it's locked even if this
                            # browser session's own counter hasn't reached 0 yet.
                            backend_locked = bool(message) and "locked" in message.lower()
                            if remaining <= 0 or backend_locked:
                                st.session_state.login_locked = True
                                st.session_state.login_locked_at = time.time()
                                # Strip the trailing "Try again in Xs." clause — the countdown
                                # above already shows a live, ticking remaining time, so keeping
                                # a second, frozen-at-lock-time second count here would drift out
                                # of sync with it and look like two different numbers/bugs.
                                st.session_state.login_lock_reason = (
                                    message.split(". Try again")[0].strip() + "."
                                    if backend_locked and message else None
                                )
                            else:
                                st.session_state.login_error = message or t("invalid_login", remaining=remaining)
                            st.rerun()

                if st.session_state.login_error:
                    st.error(st.session_state.login_error)

        st.markdown(
            f'<div class="login-footer">{t("login_footer")}</div>',
            unsafe_allow_html=True,
        )


if not st.session_state.authenticated:
    render_login()
    st.stop()

# ---------------- Sidebar ("taskbar") ----------------
with st.sidebar:
    render_world_clock()

    st.markdown(
        f'<div class="claude-brand">{athena_logo(24)}ATHENA</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="new-chat-marker"></div>', unsafe_allow_html=True)
    if st.button(t("new_chat"), use_container_width=True, key="new_chat"):
        st.session_state.history = []
        st.session_state.pending_question = None
        st.rerun()

    if "prompt_version" not in st.session_state:
        st.session_state.prompt_version = "v4"

    NAV_ITEMS = [("home", t("tab_home")), ("query_trace", t("tab_query_trace"))]
    if st.session_state.is_superadmin:
        NAV_ITEMS += [
            ("knowledge_base", "Knowledge base"),
            ("training_log", "Training log"),
            ("quarantine", "Quarantine"),
            ("prompts", "Prompts"),
            ("security", "Security"),
            ("alert_logs", "Alert logs"),
            ("users", "Users"),
            ("control_panel", "Control panel"),
        ]

    if "main_nav" not in st.session_state or st.session_state.main_nav not in dict(NAV_ITEMS):
        st.session_state.main_nav = "home"

    st.markdown('<div class="main-nav-marker"></div>', unsafe_allow_html=True)
    for key, label in NAV_ITEMS:
        if st.button(
            label,
            key=f"nav_{key}",
            use_container_width=True,
            type="primary" if st.session_state.main_nav == key else "secondary",
        ):
            st.session_state.main_nav = key
            st.rerun()

    role_label = "SuperAdmin" if st.session_state.is_superadmin else st.session_state.login_username or t("role_local")
    st.markdown(
        f'<div class="sidebar-footer">🔒&nbsp; {role_label} '
        '&middot; Gemini + Chroma</div>',
        unsafe_allow_html=True,
    )
    language_selector()
    if st.button(t("log_out"), key="logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.login_username = ""
        st.session_state.is_superadmin = False
        st.session_state.login_error = ""
        st.session_state.login_attempts = 0
        st.session_state.login_locked = False
        st.session_state.login_locked_at = None
        st.session_state.auth_token = ""
        st.session_state.pop("captcha_text", None)
        st.rerun()

# ---------------- Main-page navigation (vertical, left side) ----------------
_TRAINING_LOG_KEYWORDS = (
    "Ingested document", "Upload received", "Upload rejected",
    "Scan clean", "Scan INFECTED", "Scan error",
    "Deleting all ingested documents",
)
_SECURITY_LOG_KEYWORDS = (
    "Authentication failed", "Authentication succeeded", "Account locked",
    "Lockout expired", "Token rejected", "Invalid authentication token",
    "Session expired", "Request rejected", "Authorization denied",
    "Failed login recorded", "Scan INFECTED", "Scan error", "Sending lockout alert",
    "Quarantined upload", "Filename sanitized",
)
_ALERT_LOG_KEYWORDS = (
    "Sending lockout alert", "Alert email sent", "SMTP not configured; skipping alert",
    "Failed to send alert email", "ALERT_MOBILE_GATEWAY_DOMAIN not set",
    "Account locked", "Lockout extended by AI risk assessment", "Lockout expired",
)


def _render_log_lines(lines, keywords):
    matched = [line for line in lines if any(k in line for k in keywords)]
    if not matched:
        st.caption("No matching log entries yet.")
        return
    rows = []
    for line in reversed(matched):  # newest first
        level = "WARNING" if "| WARNING " in line else "ERROR" if "| ERROR " in line else "INFO"
        rows.append(f'<div class="log-line level-{level}">{line}</div>')
    st.markdown("".join(rows), unsafe_allow_html=True)


def _error_detail(resp):
    """Best-effort human-readable message from a failed response — the
    backend's JSON {"detail": ...} body when there is one, otherwise the
    raw response text (e.g. a plain-text 502 from a proxy in front of it)."""
    try:
        return resp.json().get("detail", resp.text)
    except ValueError:
        return resp.text


def _kv_grid(pairs):
    cards = "".join(
        f'<div class="kv-card"><div class="kv-label">{label}</div><div class="kv-value">{value}</div></div>'
        for label, value in pairs
    )
    st.markdown(f'<div class="kv-grid">{cards}</div>', unsafe_allow_html=True)


def _get_json(path, params=None):
    """GET path from the backend with auth headers. Returns (data, error_message) —
    exactly one is None. Never raises: a non-200 response or unreachable backend
    both come back as a normal error message instead of an uncaught exception."""
    try:
        resp = requests.get(f"{BACKEND_URL}{path}", headers=_auth_headers(), params=params, timeout=5)
    except requests.exceptions.RequestException:
        return None, t("backend_unreachable")
    if not resp.ok:
        try:
            return None, resp.json().get("detail", resp.text)
        except ValueError:
            return None, resp.text
    return resp.json(), None


question = None
if st.session_state.main_nav == "home":
    question = st.chat_input(t("chat_placeholder"))
    if st.session_state.pending_question:
        question = st.session_state.pending_question
        st.session_state.pending_question = None

if question:
    st.session_state.history.append(("user", question))
    with st.spinner(t("thinking")):
        try:
            resp = requests.post(
                f"{BACKEND_URL}/query",
                json={"question": question, "prompt_version": st.session_state.prompt_version},
                headers=_auth_headers(),
                timeout=120,
            )
        except requests.exceptions.RequestException:
            resp = None
    if resp is None:
        st.session_state.history.append(("assistant", f"⚠️ {t('backend_unreachable')}"))
    elif resp.status_code == 401:
        st.session_state.authenticated = False
        st.session_state.auth_token = ""
        st.session_state.login_error = "Your session expired. Please log in again."
        st.rerun()
    elif resp.ok:
        data = resp.json()
        answer = data["answer"]
        if data["sources"]:
            answer += f"\n\n**{t('sources_label')}** " + ", ".join(data["sources"])
        st.session_state.history.append(("assistant", answer))
        st.session_state.last_chunks = data.get("chunks", [])
        st.session_state.last_question = question
    else:
        st.session_state.history.append(("assistant", f"⚠️ {resp.text}"))

if st.session_state.main_nav == "home":
    usage_data, usage_error = _get_json("/token-usage")
    if not usage_error:
        used, limit = usage_data["used"], usage_data["limit"]
        pct = min(1.0, used / limit) if limit else 0.0
        over = used >= limit
        pct_label = "Limit reached" if over else f"{pct * 100:.0f}%"
        st.markdown(
            f'<div class="token-usage-card{" over-limit" if over else ""}">'
            f'<div class="tuc-header">'
            f'<span class="tuc-label">🔢 Daily token usage</span>'
            f'<span class="tuc-pct">{pct_label}</span>'
            f'</div>'
            f'<div class="tuc-value">{used:,}<span class="tuc-sep">/</span>{limit:,}'
            f'<span class="tuc-unit">tokens today</span></div>'
            f'<div class="token-usage-track"><div class="token-usage-fill" '
            f'style="width:{pct * 100:.1f}%"></div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if not st.session_state.history:
        st.markdown('<div class="landing-marker"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown(f'<div class="claude-greeting">{t("greeting")}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="claude-subgreeting">{t("subgreeting")}</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="suggestion-marker"></div>', unsafe_allow_html=True)
            cols = st.columns(3)
            suggestions = [t("suggestion_1"), t("suggestion_2"), t("suggestion_3")]
            for i, (col, suggestion) in enumerate(zip(cols, suggestions)):
                with col:
                    if st.button(suggestion, use_container_width=True, key=f"sugg_{i}"):
                        st.session_state.pending_question = suggestion
                        st.rerun()
    else:
        for role, text in st.session_state.history:
            with st.chat_message(role):
                st.write(text)

if st.session_state.main_nav == "query_trace":
    # ---- Query Trace: raw context chunks retrieved for the last question ----
    if not st.session_state.last_chunks:
        st.info(t("code_tab_hint"))
    else:
        st.caption(t("context_retrieved", q=st.session_state.last_question))
        for c in st.session_state.last_chunks:
            with st.container(border=True):
                st.markdown(
                    '<div class="chunk-marker"></div>'
                    f'<div class="chunk-card-header"><span>📄&nbsp;<b>{c["source"]}</b></span>'
                    f'<span>{t("chunk_label", n=c["chunk"])}</span></div>',
                    unsafe_allow_html=True,
                )
                st.code(c["text"], language=None)

# ---- Knowledge base: document upload / ingest / list / clear ----
if st.session_state.main_nav == "knowledge_base":
    st.markdown(f'<div class="sidebar-section-label">{t("documents_label")}</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(t("upload_label"), type=["txt", "pdf", "docx"], label_visibility="collapsed")
    if uploaded and st.button(t("ingest_btn"), key="ingest"):
        with st.spinner(t("ingesting")):
            files = {"file": (uploaded.name, uploaded.getvalue())}
            resp = requests.post(f"{BACKEND_URL}/upload", files=files, headers=_auth_headers())
        if resp.ok:
            data = resp.json()
            st.success(t("added_chunks", n=data["chunks_added"], filename=data["filename"]))
        else:
            st.error(_error_detail(resp))

    st.markdown(f'<div class="sidebar-section-label">{t("ingested_files_label")}</div>', unsafe_allow_html=True)
    kb_data, kb_error = _get_json("/documents")
    if kb_error:
        st.error(kb_error)
    elif kb_data.get("sources"):
        for d in kb_data["sources"]:
            st.markdown(f'<div class="sidebar-file-row">📄&nbsp;{d}</div>', unsafe_allow_html=True)
    else:
        st.caption(t("no_documents"))

# ---- Training log: tail of ingestion-related backend log lines ----
if st.session_state.main_nav == "training_log":
    st.caption("Recent document ingestion activity (uploads, scans, ingestion, deletions).")
    log_data, log_error = _get_json("/logs/recent", params={"limit": 300})
    if log_error:
        st.error(log_error)
    else:
        _render_log_lines(log_data.get("lines", []), _TRAINING_LOG_KEYWORDS)

# ---- Prompts: version picker + full descriptions of all versions ----
if st.session_state.main_nav == "prompts":
    pv_data, pv_error = _get_json("/prompt-versions")
    if pv_error:
        st.error(pv_error)
        pv_options, pv_default = [], "v4"
    else:
        pv_options = pv_data.get("versions", [])
        pv_default = pv_data.get("default", "v4")

    pv_keys = [v["key"] for v in pv_options] or ["v1", "v2", "v3", "v4"]
    pv_labels = {v["key"]: v["label"] for v in pv_options}
    if st.session_state.prompt_version not in pv_keys:
        st.session_state.prompt_version = pv_default if pv_default in pv_keys else pv_keys[0]

    st.markdown('<div class="sidebar-section-label">Active version</div>', unsafe_allow_html=True)
    st.selectbox(
        "Prompt version",
        pv_keys,
        format_func=lambda k: pv_labels.get(k, k.upper()),
        key="prompt_version",
        label_visibility="collapsed",
    )
    if pv_options:
        st.markdown('<div class="sidebar-section-label">All versions</div>', unsafe_allow_html=True)
        for v in pv_options:
            active = " (active)" if v["key"] == st.session_state.prompt_version else ""
            with st.container(border=True):
                st.markdown(f"**{v['label']}{active}**")
                st.caption(v["description"])

# ---- Security: config summary + tail of security-related log lines ----
if st.session_state.main_nav == "security":
    sec_info, sec_error = _get_json("/system-info")
    if sec_error:
        st.error(sec_error)
    else:
        _kv_grid([
            ("YARA scanning", "Enabled" if sec_info["yara_enabled"] else "Disabled"),
            ("JWT expiry", f"{sec_info['jwt_expiry_minutes']} min"),
            ("Login lockout", f"{sec_info['login_max_attempts']} attempts / {sec_info['login_lockout_seconds']}s"),
            ("Max upload size", f"{sec_info['max_upload_size_mb']} MB"),
            ("Quarantined files", sec_info["quarantined_count"]),
        ])

    st.markdown('<div class="sidebar-section-label">Activity log</div>', unsafe_allow_html=True)
    st.caption("Recent authentication, authorization, and scan-rejection events.")
    log_data, log_error = _get_json("/logs/recent", params={"limit": 300})
    if log_error:
        st.error(log_error)
    else:
        security_lines = [line for line in log_data.get("lines", []) if any(k in line for k in _SECURITY_LOG_KEYWORDS)]

        if st.button("🤖 Generate AI security digest", key="security_digest_btn"):
            if not security_lines:
                st.session_state["security_digest"] = {"error": "No security log entries to summarize yet."}
            else:
                try:
                    resp = requests.post(
                        f"{BACKEND_URL}/security/digest",
                        json={"log_lines": security_lines},
                        headers=_auth_headers(),
                        timeout=30,
                    )
                    if resp.ok:
                        st.session_state["security_digest"] = {"text": resp.json()["digest"]}
                    else:
                        st.session_state["security_digest"] = {"error": _error_detail(resp)}
                except requests.exceptions.RequestException:
                    st.session_state["security_digest"] = {"error": t("backend_unreachable")}
            st.rerun()

        if "security_digest" in st.session_state:
            result = st.session_state["security_digest"]
            if "error" in result:
                st.error(result["error"])
            else:
                st.info(f"🤖 **AI security digest**\n\n{result['text']}")

        _render_log_lines(log_data.get("lines", []), _SECURITY_LOG_KEYWORDS)

# ---- Alert logs: tail of login-lockout alert lines (email/SMS delivery, AI-extended lockouts) ----
if st.session_state.main_nav == "alert_logs":
    st.caption("Recent account-lockout alerts, including admin email/SMS notifications and AI-extended lockout durations.")
    log_data, log_error = _get_json("/logs/recent", params={"limit": 300})
    if log_error:
        st.error(log_error)
    else:
        _render_log_lines(log_data.get("lines", []), _ALERT_LOG_KEYWORDS)

# ---- Quarantine: files YARA/validation flagged, pending manual review ----
if st.session_state.main_nav == "quarantine":
    st.caption(
        "Files rejected by YARA or the upload validators, held here for manual review. "
        "Download and inspect a file yourself before deciding — Accept ingests it normally; "
        "Delete removes it permanently."
    )
    q_data, q_error = _get_json("/quarantine")
    if q_error:
        st.error(q_error)
    elif not q_data.get("files"):
        st.caption("No quarantined files. 🎉")
    else:
        for qf in q_data["files"]:
            qid = qf["id"]
            is_av_hit = qf["reason"].startswith("av_scan")
            with st.container(border=True):
                st.markdown(f"**{qf['original_filename']}**  ·  {qf['timestamp']}")
                st.caption(
                    f"Reason: {qf['reason']}  ·  {qf['size_bytes']:,} bytes  ·  "
                    f"uploaded by {qf['uploader']}  ·  sha256: {qf['sha256'][:16]}…"
                )
                if is_av_hit:
                    st.warning("⚠️ YARA flagged this as malicious. Only accept if you've verified it yourself.")

                explain_key = f"qexplain_{qid}"
                if explain_key in st.session_state:
                    result = st.session_state[explain_key]
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        icon = {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(result["confidence"], "⚪")
                        st.info(
                            f"{icon} **AI confidence this is a genuine threat: {result['confidence'].upper()}** "
                            f"— {result['explanation']}"
                        )

                explain_col, dl_col, accept_col, delete_col = st.columns(4)

                with explain_col:
                    if st.button("🤖 AI explain", key=f"qexplain_btn_{qid}", use_container_width=True):
                        try:
                            resp = requests.post(
                                f"{BACKEND_URL}/quarantine/{qid}/explain", headers=_auth_headers(), timeout=30
                            )
                            if resp.ok:
                                st.session_state[explain_key] = resp.json()
                            else:
                                st.session_state[explain_key] = {"error": _error_detail(resp)}
                        except requests.exceptions.RequestException:
                            st.session_state[explain_key] = {"error": t("backend_unreachable")}
                        st.rerun()

                with dl_col:
                    dl_key = f"qdl_data_{qid}"
                    if st.button("⬇️ Prepare download", key=f"qdl_btn_{qid}", use_container_width=True):
                        try:
                            resp = requests.get(
                                f"{BACKEND_URL}/quarantine/{qid}/download", headers=_auth_headers(), timeout=15
                            )
                            if resp.ok:
                                st.session_state[dl_key] = resp.content
                                st.rerun()
                            else:
                                st.error(_error_detail(resp))
                        except requests.exceptions.RequestException:
                            st.error(t("backend_unreachable"))
                    if dl_key in st.session_state:
                        st.download_button(
                            "💾 Save file",
                            data=st.session_state[dl_key],
                            file_name=qf["original_filename"],
                            key=f"qdl_save_{qid}",
                            use_container_width=True,
                        )

                with accept_col:
                    if st.button("✅ Accept & process", key=f"qaccept_{qid}", use_container_width=True):
                        try:
                            resp = requests.post(
                                f"{BACKEND_URL}/quarantine/{qid}/release", headers=_auth_headers(), timeout=60
                            )
                            if resp.ok:
                                data = resp.json()
                                st.success(t("added_chunks", n=data["chunks_added"], filename=data["filename"]))
                                st.session_state.pop(dl_key, None)
                                st.session_state.pop(explain_key, None)
                                st.rerun()
                            else:
                                st.error(_error_detail(resp))
                        except requests.exceptions.RequestException:
                            st.error(t("backend_unreachable"))

                with delete_col:
                    if st.button("🗑️ Delete", key=f"qdelete_{qid}", use_container_width=True):
                        try:
                            resp = requests.delete(
                                f"{BACKEND_URL}/quarantine/{qid}", headers=_auth_headers(), timeout=10
                            )
                            if resp.ok:
                                st.success(f"Deleted {qf['original_filename']}.")
                                st.session_state.pop(dl_key, None)
                                st.session_state.pop(explain_key, None)
                                st.rerun()
                            else:
                                st.error(_error_detail(resp))
                        except requests.exceptions.RequestException:
                            st.error(t("backend_unreachable"))

# ---- Users: existing accounts + add-user form ----
if st.session_state.main_nav == "users":
    st.markdown('<div class="sidebar-section-label">Existing users</div>', unsafe_allow_html=True)
    users_data, users_error = _get_json("/users")
    if users_error:
        st.error(users_error)
    elif users_data.get("users"):
        for u in users_data["users"]:
            st.markdown(
                f'<div class="sidebar-file-row">👤&nbsp;{u["username"]} — {u["role"]}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No additional users created yet.")

    st.markdown('<div class="sidebar-section-label">Add user</div>', unsafe_allow_html=True)
    with st.form("add_user_form", clear_on_submit=True):
        new_username = st.text_input("Username", placeholder="Username", key="new_user_username")
        new_password = st.text_input(
            "Password", type="password", placeholder="Password", key="new_user_password"
        )
        new_role = st.selectbox("Role", ["ADMIN", "SuperAdmin"], key="new_user_role")
        add_user_submitted = st.form_submit_button("Add user")
    if add_user_submitted:
        if not new_username.strip() or not new_password:
            st.error("Username and password are required.")
        else:
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/users",
                    json={"username": new_username.strip(), "password": new_password, "role": new_role},
                    headers=_auth_headers(),
                    timeout=5,
                )
                if resp.ok:
                    st.success(f"User '{new_username.strip()}' added as {new_role}.")
                else:
                    st.error(_error_detail(resp))
            except requests.exceptions.RequestException:
                st.error(t("backend_unreachable"))

# ---- Control panel: system status + destructive admin actions ----
if st.session_state.main_nav == "control_panel":
    info, info_error = _get_json("/system-info")
    if info_error:
        st.error(info_error)
    else:
        _kv_grid([
            ("LLM model", info["llm_model"]),
            ("Embedding model", info["embed_model"]),
            ("Max answer length", f"{info['llm_num_predict']} tokens"),
            ("Chunk size / overlap", f"{info['chunk_size']} / {info['chunk_overlap']}"),
            ("Retrieval top-K", info["top_k"]),
            ("Default prompt version", info["default_prompt_version"].upper()),
            ("Documents ingested", info["document_count"]),
        ])

        st.markdown('<div class="sidebar-section-label">Built-in accounts &amp; access</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(f"👤 **{QUICK_LOGIN_ADMIN_USERNAME}** — role: ADMIN")
            st.caption(
                "Read access — ask questions, view ingested documents and prompt versions, "
                "see own daily token usage. Cannot upload/delete documents, manage users, "
                "or view security/quarantine/logs/settings."
            )
        with st.container(border=True):
            st.markdown(f"👑 **{QUICK_LOGIN_SUPERADMIN_USERNAME}** — role: SuperAdmin")
            st.caption(
                "Full access — everything ADMIN has, plus upload/delete documents, manage "
                "users, security & quarantine review, activity logs, and system settings."
            )

        st.markdown('<div class="sidebar-section-label">Login attempts</div>', unsafe_allow_html=True)
        st.caption(
            f"Accounts with recent failed logins. After {info['login_max_attempts']} failed "
            f"attempts an account locks for {info['login_lockout_seconds']}s — resets automatically "
            "when it expires, or on the account's next successful login. A SuperAdmin can also "
            "block or unblock any account's access directly below, independent of failed attempts."
        )

        with st.form("block_user_form", clear_on_submit=True):
            block_col, block_btn_col = st.columns([3, 1])
            with block_col:
                block_username = st.text_input(
                    "Username to block", placeholder="Username to block", label_visibility="collapsed",
                )
            with block_btn_col:
                block_submitted = st.form_submit_button("Block", use_container_width=True)
        if block_submitted:
            if not block_username.strip():
                st.error("Enter a username to block.")
            else:
                try:
                    resp = requests.post(
                        f"{BACKEND_URL}/login-attempts/{block_username.strip()}/block",
                        headers=_auth_headers(),
                        timeout=5,
                    )
                    if resp.ok:
                        st.success(f"'{block_username.strip()}' is now blocked from logging in.")
                    else:
                        st.error(_error_detail(resp))
                except requests.exceptions.RequestException:
                    st.error(t("backend_unreachable"))
                st.rerun()

        la_data, la_error = _get_json("/login-attempts")
        if la_error:
            st.error(la_error)
        elif not la_data.get("attempts"):
            st.caption("No failed login attempts or blocked accounts on record.")
        else:
            for a in la_data["attempts"]:
                row_col, action_col = st.columns([4, 1])
                with row_col:
                    if a["blocked"]:
                        st.error(f"🚫 **{a['username']}** — blocked by a SuperAdmin. No auto-expiry.")
                    elif a["locked"]:
                        st.warning(
                            f"🔒 **{a['username']}** — locked after {a['failures']} failed attempts. "
                            f"Unlocks in {a['remaining_seconds']}s."
                        )
                    else:
                        st.caption(f"{a['username']} — {a['failures']} failed attempt(s), not locked.")
                with action_col:
                    if a["locked"] and st.button("Unblock", key=f"unblock_{a['username']}", use_container_width=True):
                        try:
                            resp = requests.post(
                                f"{BACKEND_URL}/login-attempts/{a['username']}/unblock",
                                headers=_auth_headers(),
                                timeout=5,
                            )
                            if not resp.ok:
                                st.error(_error_detail(resp))
                        except requests.exceptions.RequestException:
                            st.error(t("backend_unreachable"))
                        st.rerun()

        st.markdown('<div class="sidebar-section-label">Daily token limit</div>', unsafe_allow_html=True)
        st.caption(
            f"Current limit: {info['daily_token_limit']:,} tokens/day — shared by every "
            "ADMIN and SuperAdmin account. Only a SuperAdmin can change this."
        )
        with st.form("token_limit_form"):
            new_limit = st.number_input(
                "New daily token limit",
                min_value=1,
                value=info["daily_token_limit"],
                step=1000,
                label_visibility="collapsed",
            )
            limit_submitted = st.form_submit_button("Update limit")
        if limit_submitted:
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/token-limit",
                    json={"daily_limit": int(new_limit)},
                    headers=_auth_headers(),
                    timeout=5,
                )
                if resp.ok:
                    st.success(f"Daily token limit updated to {int(new_limit):,}.")
                else:
                    st.error(_error_detail(resp))
            except requests.exceptions.RequestException:
                st.error(t("backend_unreachable"))

    st.markdown('<div class="sidebar-section-label">Danger zone</div>', unsafe_allow_html=True)
    st.markdown('<div class="clear-docs-marker"></div>', unsafe_allow_html=True)
    if st.button(t("clear_all_docs"), key="clear_docs"):
        requests.delete(f"{BACKEND_URL}/documents", headers=_auth_headers())
        st.session_state.history = []
        st.rerun()
