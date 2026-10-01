"""Fixit Pro demo backend.

Serves the static landing page and exposes one endpoint, POST /api/lead,
which validates a contact-form lead and forwards it to a Telegram chat.
With DEMO_MODE=true the lead is only logged, so the app runs without a bot.
"""

from __future__ import annotations

import html
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Dict, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

# --------------------------------------------------------------------------- #
# Configuration (environment only, no secrets in code)
# --------------------------------------------------------------------------- #


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()
DEMO_MODE = _env_bool("DEMO_MODE", False)
TRUST_PROXY = _env_bool("TRUST_PROXY", True)  # Railway/Render sit behind a proxy
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "5"))  # requests ...
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "600"))  # ... per N seconds
TELEGRAM_API = os.getenv("TELEGRAM_API", "https://api.telegram.org")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("fixit")

SERVICES = {
    "plumbing": "Plumbing",
    "electrical": "Electrical",
    "carpentry": "Carpentry & doors",
    "painting": "Painting & walls",
    "assembly": "Furniture assembly",
    "appliances": "Appliance install",
    "other": "Something else",
}

PHONE_ALLOWED = re.compile(r"^\+?[0-9\s\-().]{7,20}$")

# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


class Lead(BaseModel):
    name: str = Field(..., min_length=2, max_length=60)
    phone: str = Field(..., min_length=7, max_length=20)
    service: str
    message: str = Field("", max_length=1000)
    # Honeypot: hidden from humans, bots tend to fill it in.
    website: Optional[str] = Field(None, max_length=200)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Please enter your name.")
        if any(ch.isdigit() for ch in v):
            raise ValueError("Name should not contain digits.")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        v = v.strip()
        digits = re.sub(r"\D", "", v)
        if not PHONE_ALLOWED.match(v) or not 7 <= len(digits) <= 15:
            raise ValueError("Enter a valid phone number, e.g. +1 555 123 4567.")
        return v

    @field_validator("service")
    @classmethod
    def _service(cls, v: str) -> str:
        if v not in SERVICES:
            raise ValueError("Choose a service from the list.")
        return v

    @field_validator("message")
    @classmethod
    def _message(cls, v: str) -> str:
        return v.strip()


# --------------------------------------------------------------------------- #
# Rate limiting (in-memory sliding window, per IP)
# --------------------------------------------------------------------------- #


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max = max_requests
        self.window = window_seconds
        self.hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> Optional[int]:
        """Record a hit. Returns None if allowed, else seconds until retry."""
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max:
            return max(1, int(self.window - (now - q[0])))
        q.append(now)
        # Keep memory bounded on long-running instances.
        if len(self.hits) > 10_000:
            for k in [k for k, d in self.hits.items() if not d or now - d[-1] > self.window]:
                del self.hits[k]
        return None


limiter = RateLimiter(RATE_LIMIT_MAX, RATE_LIMIT_WINDOW)


def client_ip(request: Request) -> str:
    if TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    return request.client.host if request.client else "unknown"


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #


def format_lead(lead: Lead) -> str:
    e = html.escape
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "🛠 <b>New lead · Fixit Pro</b>",
        "",
        f"<b>Name:</b> {e(lead.name)}",
        f"<b>Phone:</b> {e(lead.phone)}",
        f"<b>Service:</b> {e(SERVICES[lead.service])}",
    ]
    if lead.message:
        lines += ["", f"<b>Message:</b>\n{e(lead.message)}"]
    lines += ["", f"<i>{when}</i>"]
    return "\n".join(lines)


async def send_telegram(text: str) -> None:
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
    if resp.status_code != 200 or not resp.json().get("ok"):
        # Never log the URL: it contains the bot token.
        raise RuntimeError(f"Telegram API error {resp.status_code}: {resp.text[:200]}")


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(_: FastAPI):
    if DEMO_MODE:
        log.info("DEMO_MODE is on: leads are logged, not sent to Telegram.")
    elif not (BOT_TOKEN and CHAT_ID):
        log.warning("BOT_TOKEN/CHAT_ID not set and DEMO_MODE is off: /api/lead will return 503.")
    yield


app = FastAPI(title="Fixit Pro demo", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def headers_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=604800"
    elif path == "/" or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors: Dict[str, str] = {}
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p != "body"]
        field = loc[0] if loc else "form"
        msg = err.get("msg", "Invalid value.")
        msg = msg.removeprefix("Value error, ")
        if err.get("type") == "string_too_short":
            msg = "This field is too short."
        elif err.get("type") == "string_too_long":
            msg = "This field is too long."
        elif err.get("type") == "missing":
            msg = "This field is required."
        errors.setdefault(field, msg)
    return JSONResponse(status_code=422, content={"ok": False, "error": "Please check the highlighted fields.", "fields": errors})


@app.get("/healthz")
async def healthz():
    return {"ok": True, "demo_mode": DEMO_MODE}


@app.post("/api/lead")
async def create_lead(lead: Lead, request: Request):
    ip = client_ip(request)
    retry = limiter.check(ip)
    if retry is not None:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry)},
            content={"ok": False, "error": "Too many requests. Please try again in a few minutes."},
        )

    if lead.website:  # honeypot tripped: pretend success, drop silently
        log.info("Honeypot triggered from %s, lead dropped.", ip)
        return {"ok": True}

    text = format_lead(lead)

    if DEMO_MODE:
        log.info("DEMO lead (not sent):\n%s", text)
        return {"ok": True, "demo": True}

    if not (BOT_TOKEN and CHAT_ID):
        return JSONResponse(status_code=503, content={"ok": False, "error": "Lead delivery is not configured."})

    try:
        await send_telegram(text)
    except Exception as exc:  # network error or Telegram rejection
        log.error("Failed to deliver lead: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"ok": False, "error": "We couldn't send your request. Please call us instead."},
        )
    log.info("Lead delivered to Telegram (service=%s).", lead.service)
    return {"ok": True}


# Static site last, so /api routes take precedence.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
