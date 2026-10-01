# Fixit Pro · demo small-business site with Telegram leads

A portfolio demo: a fast, single-page website for a **fictional** local home-repair service. Every contact-form submission is validated on the server and sent to the owner's Telegram chat instantly.

- **Frontend:** static HTML, Tailwind CSS (pre-compiled, 5 KB gzipped), vanilla JS. No frameworks.
- **Backend:** Python FastAPI, one endpoint `POST /api/lead`. The same app serves the static page, so one deploy runs everything.
- **Lighthouse (mobile, local run):** Performance 100 · Accessibility 100 · Best Practices 100 · SEO 100. Full report in [`docs/lighthouse-mobile.html`](docs/lighthouse-mobile.html).

> Demo project. Fixit Pro, its prices, phone number and reviews are fictional.

---

## Project structure

```
fixit-pro/
├── app/main.py            FastAPI app: /api/lead, /healthz, static files
├── static/
│   ├── index.html         The landing page
│   ├── assets/app.js      Form logic (validation, loading/success/error states)
│   ├── assets/styles.css  Compiled Tailwind (committed, no build needed to run)
│   ├── favicon.svg, robots.txt
├── frontend/              Tailwind source + config (only needed to change styles)
├── tests/test_api.py      API tests (pytest)
├── docs/                  Lighthouse report and screenshots
├── .env.example           Environment variables template
├── requirements.txt, Procfile, railway.json
```

## Run locally

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # DEMO_MODE=true by default
set -a; source .env; set +a        # load the variables (or export them yourself)

uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 and submit the form. In demo mode the lead is printed in the terminal:

```
INFO fixit: DEMO lead (not sent):
🛠 <b>New lead · Fixit Pro</b>
<b>Name:</b> Jamie Lee
<b>Phone:</b> +1 555 010 2030
<b>Service:</b> Painting &amp; walls
...
```

Run the tests:

```bash
pip install pytest
pytest -q
```

## Connect a real Telegram bot

1. In Telegram, message **@BotFather**, send `/newbot`, and copy the token (`123456789:AA...`).
2. Send any message to your new bot (or add it to a group).
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy `"chat":{"id": ...}`. Group IDs start with `-100`.
4. In `.env` set `BOT_TOKEN`, `CHAT_ID` and `DEMO_MODE=false`, then restart.

Secrets are only read from the environment. `.env` is git-ignored; never commit it.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `BOT_TOKEN` | – | Telegram bot token from @BotFather |
| `CHAT_ID` | – | Chat that receives leads |
| `DEMO_MODE` | `false` | `true` logs leads instead of sending them |
| `RATE_LIMIT_MAX` | `5` | Leads allowed per IP per window |
| `RATE_LIMIT_WINDOW` | `600` | Window length in seconds |
| `TRUST_PROXY` | `true` | Use `X-Forwarded-For` for the client IP (needed behind Railway/Render) |

If `DEMO_MODE` is off and the bot isn't configured, `/api/lead` returns 503 and a warning is logged at startup.

## API

`POST /api/lead` (JSON)

```json
{ "name": "Alex Morgan", "phone": "+1 555 123 4567", "service": "plumbing", "message": "Tap drips." }
```

| Rule | Detail |
|---|---|
| `name` | 2–60 chars, no digits, whitespace collapsed |
| `phone` | digits, spaces, `+ - ( ) .`; 7–15 digits in total |
| `service` | one of `plumbing, electrical, carpentry, painting, assembly, appliances, other` |
| `message` | optional, up to 1000 chars |
| `website` | hidden honeypot; if filled, the lead is silently dropped |

Responses: `200 {"ok":true}` (plus `"demo":true` in demo mode), `422` with per-field messages, `429` with `Retry-After`, `502` if Telegram fails, `503` if not configured. User input is HTML-escaped before it goes into the Telegram message.

Rate limiting is an in-memory sliding window per IP. It resets on restart and is per-instance, which is fine for a single small deployment; use Redis if you scale out.

## Deploy to Railway

1. Push this folder to a GitHub repository.
2. In Railway: **New Project → Deploy from GitHub repo** and pick the repo. Railway detects Python from `requirements.txt` and uses the start command in `railway.json`:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips=*`
3. In the service's **Variables** tab add `BOT_TOKEN`, `CHAT_ID`, `DEMO_MODE=false` (or `DEMO_MODE=true` for a bot-less public demo).
4. **Settings → Networking → Generate Domain.** The health check is `/healthz`.

**Render / Fly / Heroku-style hosts:** the `Procfile` has the same start command. On Render, create a Web Service with build command `pip install -r requirements.txt` and start command from the `Procfile`.

## Changing styles

The compiled `static/assets/styles.css` is committed, so deploys need no Node build. After editing classes in `index.html` or `app.js`:

```bash
cd frontend
npm install
npm run build:css      # or: npm run watch:css
```

Why compiled rather than the Tailwind Play CDN: the CDN script is ~100 KB+ of JavaScript that generates CSS in the browser, which costs Lighthouse Performance points and prints a "not for production" warning. Compiling keeps the page at roughly 30 KB total.

## What to screenshot for the portfolio

1. **Hero, desktop (1440×900):** headline, CTA and the "owner's phone" card that explains the idea at a glance.
2. **Full page on mobile (iPhone/Pixel frame):** shows the mobile-first layout. In Chrome DevTools use device mode → ⋮ → *Capture full size screenshot*.
3. **The form in three states:** a field error (submit empty), loading ("Sending…" with spinner), and the success card. Tip: DevTools → Network → *Slow 3G* to catch the loading state.
4. **The money shot:** the lead arriving in Telegram on a real phone, next to the filled-in form. Do one run with `DEMO_MODE=false` and a real bot.
5. **Lighthouse mobile scores:** DevTools → Lighthouse → Mobile → all four categories. Crop to the four 100 circles.
6. **Code snippet (optional):** the validation model and `send_telegram` from `app/main.py`, or the terminal log from demo mode.
7. **Keyboard accessibility (optional):** press Tab to show the "Skip to content" link and the visible focus ring.

Ready-made captures from the build are in [`docs/`](docs/).

## Notes

- All icons and the hero visual are inline SVG/HTML drawn for this project. No stock photos or third-party images.
- Fonts use system font stacks (serif headings, sans-serif body), so no web-font download.
- For a real site, add `<link rel="canonical">` and an `og:image` (PNG/JPG, 1200×630) with your production domain.
