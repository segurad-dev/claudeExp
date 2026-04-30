# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project structure

```
index.html        — Health Tracker SPA (single file, no build step)
bot/
  bot.py          — Telegram bot
  miniapp/
    index.html    — Telegram Mini App (открывается кнопкой из бота)
  requirements.txt
  .env            — BOT_TOKEN, MINIAPP_URL, ADMIN_ID (не в git)
  .env.example    — шаблон без секретов
```

---

## Health Tracker SPA (`index.html`)

### Running

No build step — open `index.html` directly in a browser or serve it with any static file server:

```bash
npx serve .
# or
python -m http.server 8080
```

No package.json, no dependencies, no linting, no test suite.

### Architecture

Single-file SPA: all HTML, CSS (~450 lines), and JS (~720 lines) live in `index.html` (~1172 lines total). Persistence is `localStorage` only — no backend.

**JS layout inside `<script>` (line 453 onward):**

| Section | Lines | Purpose |
|---------|-------|---------|
| `METRICS` | 456–471 | Registry of 13 health metrics with name, units, and reference range `{min, max}` |
| Storage | 484–540 | `load()` / `save()` / `uuid()` / `_data` cache + `getData()` / `saveData()` / `setMetric()` |
| `renderChartArea()` | 568–756 | Rebuilds the entire chart DOM on every call; reads from in-memory cache via `getData()` |
| SVG chart | 545–755 | Hand-drawn SVG: reference band, gridlines, polyline, colored dots, hover tooltips |
| Day modal | 757–805 | Shows all measurements for a clicked date; delete per entry |
| `saveManualEntry()` | 855–876 | Standalone save function; reads form DOM, calls `getData()` / `saveData()` / `setMetric()` |
| Manual entry modal | 877–958 | `openManualModal()` — renders HTML + wires `syncUnits` only; no inline save logic |
| Import / Export | 959–1051 | JSON round-trip; import deduplicates and reports skipped invalid rows |
| Notes / quickInput | 1052–1166 | `quickInput` line saved on Enter; `notesArea` debounced 400 ms to `localStorage` |

**Data shape in `localStorage` (key `healthtracker.data`):**
```json
{
  "version": 1,
  "measurements": [
    { "id": "<uuid>", "date": "2024-04-25", "metric": "hemoglobin",
      "value": 145, "unit": "g/L", "notes": "" }
  ]
}
```

### Key conventions

- **HTML escaping:** user-supplied strings must go through `esc(s)` before `innerHTML` insertion.
- **UUID generation:** use the local `uuid()` helper (~line 502), not `crypto.randomUUID()` directly — the helper includes a fallback for non-HTTPS contexts.
- **Data reads:** always use `getData()` — returns the in-memory `_data` cache; `load()` is called only once at page startup.
- **Data writes:** always use `saveData(data)` — updates `_data` cache and writes to `localStorage` with try/catch for `QuotaExceededError`.
- **Active metric:** always change via `setMetric(key)` — it syncs `curMetric`, `metricSelect.value`, and calls `renderChartArea()`.
- **Save form data:** call `saveManualEntry()` — it reads the form DOM, validates, calls `getData()`/`saveData()`/`setMetric()`; do not duplicate this logic.
- **Event handling:** modal and chart interactions use event delegation on stable containers (`#modalBox`, `#chartArea`) via `closest()` — do not add per-element `addEventListener` inside render functions.
- **Date strings:** always ISO `YYYY-MM-DD`; pass `iso + 'T00:00:00'` to `new Date()` to avoid timezone shifts.
- **Chart re-render:** call `renderChartArea()` after any data mutation; it reads from `getData()` (in-memory) and rebuilds DOM from scratch.
- **SVG canvas constants:** `CW=340, CH=220, PL=38, PR=10, PT=16, PB=10` — coordinate helpers `toX(date)` / `toY(value)` depend on these.

---

## Telegram bot (`bot/`)

### Running

```bash
pip install -r bot/requirements.txt
python bot/bot.py
```

Requires `bot/.env` with:
```
BOT_TOKEN=...
MINIAPP_URL=https://segurad-dev.github.io/claudeExp/bot/miniapp/
ADMIN_ID=317515479
```

### Architecture

- `bot.py` — синхронный бот на `pyTelegramBotAPI`. Читает `.env` через `python-dotenv`.
- `/start` — приветствует пользователя по нику/имени, показывает кнопку WebApp, отправляет уведомление администратору с именем и id пользователя.
- `miniapp/index.html` — статичная страница, хостится на GitHub Pages (ветка `tg_mvp`). Подключает Telegram WebApp SDK и вызывает `Telegram.WebApp.ready()`.

### Key conventions

- Переменные окружения читаются только через `os.environ.get()` после `load_dotenv()`.
- `ADMIN_ID` хранится как `int`.
- WebApp кнопка (`web_app=WebAppInfo(url=...)`) открывает URL напрямую — бот не получает callback при нажатии. Уведомление администратора происходит в момент `/start`.
