"""
config.py — Hằng số, regex và helpers thuần túy cho scraper module.
Không import từ module nội bộ scraper nào.
Paths dùng _LazyPath proxy → resolve lúc runtime từ settings (Option B).
"""
import os
import re
import random
from pathlib import Path
from urllib.parse import urlparse


# ── _LazyPath proxy — resolve paths từ settings lúc runtime ──────────────────
class _LazyPath:
    def __init__(self, getter):
        self._getter = getter

    def __truediv__(self, other):
        return self._getter() / other

    def __fspath__(self):
        return str(self._getter())

    def __str__(self):
        return str(self._getter())

    def __repr__(self):
        return repr(self._getter())

    def resolve(self):
        return self._getter().resolve()

    def exists(self):
        return self._getter().exists()

    def mkdir(self, **kw):
        return self._getter().mkdir(**kw)


def _get_settings():
    from littrans.config.settings import settings
    return settings


DATA_DIR      = _LazyPath(lambda: _get_settings().data_dir)
OUTPUT_DIR    = _LazyPath(lambda: _get_settings().base_dir / "inputs")
PROGRESS_DIR  = _LazyPath(lambda: _get_settings().scraper_progress_dir)
PROFILES_FILE = _LazyPath(lambda: _get_settings().scraper_profiles_file)
ADS_DB_FILE   = _LazyPath(lambda: _get_settings().scraper_ads_keywords_file)


# ── API — đọc từ settings để thống nhất với pool ─────────────────────────────
def _get_primary_gemini_key() -> str:
    return _get_settings().all_gemini_keys[0] if _get_settings().all_gemini_keys else ""


def _get_gemini_model() -> str:
    return _get_settings().gemini_model


GEMINI_API_KEY: str = ""   # placeholder; scraper/ai/client.py đọc trực tiếp từ settings


def _derive_fallback(primary: str) -> str:
    _p = primary.lower()
    if "flash-lite" in _p:
        return primary
    if "flash" in _p or "pro" in _p:
        return "gemini-2.0-flash-lite"
    return "gemini-2.0-flash-lite"


def _get_gemini_model_str() -> str:
    try:
        return _get_settings().gemini_model or "gemini-2.0-flash"
    except Exception:
        return os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


GEMINI_MODEL         : str = _get_gemini_model_str()
GEMINI_FALLBACK_MODEL: str = os.getenv("GEMINI_FALLBACK_MODEL", _derive_fallback(GEMINI_MODEL))


# ── Int constants — đọc từ settings lúc import (settings đã là singleton) ─────
def _si(attr: str, default: int) -> int:
    try:
        return getattr(_get_settings(), attr)
    except Exception:
        return default


MAX_CHAPTERS             = _si("scraper_max_chapters", 5000)
MAX_CONSECUTIVE_ERRORS   = _si("scraper_max_consecutive_errors", 5)
MAX_CONSECUTIVE_TIMEOUTS = 3
TIMEOUT_BACKOFF_BASE     = 30


# ── Learning phase ────────────────────────────────────────────────────────────
LEARNING_CHAPTERS          = 10
LEARNING_MIN_CONTENT       = 300
PROFILE_MAX_AGE_DAYS       = _si("scraper_profile_max_age_days", 30)
LEARNING_AI_CALLS          = 10
LEARNING_CONFLICT_THRESHOLD = 3


# ── AI ────────────────────────────────────────────────────────────────────────
AI_MAX_RPM = _si("scraper_ai_max_rpm", 10)
AI_JITTER  = (0.5, 2.0)


# ── HTTP ──────────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 60


# ── Playwright concurrency ────────────────────────────────────────────────────
PW_MAX_CONCURRENCY: int = _si("scraper_max_pw_instances", 2)


# ── JS-heavy detection thresholds ────────────────────────────────────────────
JS_CONTENT_RATIO  : float = 1.5
JS_MIN_DIFF_CHARS : int   = 500


# ── Empty streak backoff schedule ─────────────────────────────────────────────
EMPTY_BACKOFF_SCHEDULE: list[int] = [60, 120, 300]


# ── Misc ──────────────────────────────────────────────────────────────────────
INIT_STAGGER = 2.0


# ── Chrome fingerprint rotation ───────────────────────────────────────────────
CHROME_VERSIONS: list[str] = ["chrome119", "chrome120", "chrome123", "chrome124", "chrome131"]
CHROME_UA: dict[str, str] = {
    "chrome119": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "chrome120": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "chrome123": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "chrome124": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "chrome131": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}


def pick_chrome_version() -> str:
    return random.choice(CHROME_VERSIONS)


def make_headers(version: str) -> dict[str, str]:
    return {
        "User-Agent"               : CHROME_UA.get(version, CHROME_UA["chrome124"]),
        "Accept"                   : "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language"          : "en-US,en;q=0.9",
        "Accept-Encoding"          : "gzip, deflate, br",
        "Connection"               : "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


# ── Delay profiles theo domain ────────────────────────────────────────────────
_DELAY_PROFILES: dict[str, tuple[float, float]] = {
    "royalroad.com"       : (6.0, 14.0),
    "www.royalroad.com"   : (6.0, 14.0),
    "scribblehub.com"     : (4.0, 10.0),
    "www.scribblehub.com" : (4.0, 10.0),
    "wattpad.com"         : (3.0,  8.0),
    "www.wattpad.com"     : (3.0,  8.0),
    "fanfiction.net"      : (2.0,  6.0),
    "www.fanfiction.net"  : (2.0,  6.0),
    "archiveofourown.org" : (2.0,  5.0),
    "www.webnovel.com"    : (3.0,  7.0),
}
_DEFAULT_DELAY = (1.0, 3.0)


def get_delay(url: str) -> float:
    domain = urlparse(url).netloc.lower()
    lo, hi = _DELAY_PROFILES.get(domain, _DEFAULT_DELAY)
    return random.uniform(lo, hi)


# ── Fallback selectors ────────────────────────────────────────────────────────
FALLBACK_CONTENT_SELECTORS: list[str] = [
    "#chapter-c",
    "#chr-content",
    "div.chapter-content",
    ".chapter-content",
    "article",
    "[itemprop='articleBody']",
    "#storytext",
    "div.text-left",
    "div.entry-content",
]

KNOWN_NOISE_SELECTORS: list[str] = [
    "#profile_top",
    "#pre_story_links",
    ".author-note-portlet",
    ".portlet.blog-post",
    ".comment-container",
    ".comments-list",
    ".reading-settings",
    "#settings-popover",
    ".chapter-comments",
    "#chapter-comments",
    ".author-bio-box",
    "[class='reading-options']",
]

# ── Regex compile sẵn ────────────────────────────────────────────────────────
RE_CHAP_URL = re.compile(
    r"(?:chapter|chuong|chap)[_-]?\d+"
    r"|/ch?[/_-]\d+"
    r"|(?:episode|ep|part)[_-]?\d+"
    r"|/s/\d+/\d+",
    re.IGNORECASE,
)

RE_NEXT_BTN = re.compile(
    r"\b(next|tiếp|sau|next\s*chapter|chương\s*tiếp|siguiente)\b",
    re.IGNORECASE | re.UNICODE,
)

RE_CHAP_HREF = re.compile(
    r"/(?:chapter|chuong|chap)[_-]?\d+"
    r"|/ch?[/_-]\d+"
    r"|/(?:episode|ep|part)[_-]?\d+"
    r"|/s/\d+/\d+/",
    re.IGNORECASE,
)

RE_CHAP_KW = re.compile(
    r"\b(chapter|chap|chương|episode|ep|part)\b[\s.\-:]*\d+",
    re.IGNORECASE | re.UNICODE,
)

RE_CHAP_SLUG = re.compile(
    r"(.*?(?:chapter|chuong|chap|/c|/ep|episode|part|phan|tap)[s_-]?)(\d+)(/?(?:[?#].*)?)$",
    re.IGNORECASE,
)

RE_FANFIC = re.compile(r"(/s/\d+/)(\d+)(/.+)?$")

RE_CHAP_HINT = re.compile(
    r"\b(?:chapter|chap|episode|ep|part)\s+\d+",
    re.IGNORECASE,
)
