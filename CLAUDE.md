# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

No build step — open `index.html` directly in a browser or serve it with any static file server:

```bash
npx serve .
# or
python -m http.server 8080
```

No package.json, no dependencies, no linting, no test suite.

## Architecture

Single-file SPA: all HTML, CSS (~450 lines), and JS (~700 lines) live in `index.html` (~1145 lines total). Persistence is `localStorage` only — no backend.

**JS layout inside `<script>` (line 451 onward):**

| Section | Lines | Purpose |
|---------|-------|---------|
| `METRICS` | 456–470 | Registry of 13 health metrics with name, units, and reference range `{min, max}` |
| Storage | 480–535 | `load()` / `save()` / `uuid()` / `_data` cache + `getData()` / `saveData()` / `setMetric()` |
| `renderChartArea()` | 561–783 | Rebuilds the entire chart DOM on every call; reads from in-memory cache via `getData()` |
| SVG chart | 621–729 | Hand-drawn SVG: reference band, gridlines, polyline, colored dots, hover tooltips |
| Day modal | 784–822 | Shows all measurements for a clicked date; delete per entry |
| `saveManualEntry()` | 880–901 | Standalone save function; reads form DOM, calls `getData()` / `saveData()` / `setMetric()` |
| Manual entry modal | 902–985 | `openManualModal()` — renders HTML + wires `syncUnits` only; no inline save logic |
| Import / Export | 987–1079 | JSON round-trip; import deduplicates and reports skipped invalid rows |
| Notes / quickInput | 1081–1140 | `quickInput` line saved on Enter; `notesArea` debounced 400 ms to `localStorage` |

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

## Key conventions

- **HTML escaping:** user-supplied strings must go through `esc(s)` before `innerHTML` insertion.
- **UUID generation:** use the local `uuid()` helper (~line 498), not `crypto.randomUUID()` directly — the helper includes a fallback for non-HTTPS contexts.
- **Data reads:** always use `getData()` — returns the in-memory `_data` cache; `load()` is called only once at page startup.
- **Data writes:** always use `saveData(data)` — updates `_data` cache and writes to `localStorage` with try/catch for `QuotaExceededError`.
- **Active metric:** always change via `setMetric(key)` — it syncs `curMetric`, `metricSelect.value`, and calls `renderChartArea()`.
- **Save form data:** call `saveManualEntry()` — it reads the form DOM, validates, calls `getData()`/`saveData()`/`setMetric()`; do not duplicate this logic.
- **Event handling:** modal and chart interactions use event delegation on stable containers (`#modalBox`, `#chartArea`) via `closest()` — do not add per-element `addEventListener` inside render functions.
- **Date strings:** always ISO `YYYY-MM-DD`; pass `iso + 'T00:00:00'` to `new Date()` to avoid timezone shifts.
- **Chart re-render:** call `renderChartArea()` after any data mutation; it reads from `getData()` (in-memory) and rebuilds DOM from scratch.
- **SVG canvas constants:** `CW=340, CH=220, PL=38, PR=10, PT=16, PB=10` — coordinate helpers `toX(date)` / `toY(value)` depend on these.
