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

Single-file SPA: all HTML, CSS (~400 lines), and JS (~700 lines) live in `index.html`. Persistence is `localStorage` only — no backend.

**JS layout inside `<script>` (line 451 onward):**

| Section | Lines | Purpose |
|---------|-------|---------|
| `METRICS` | 456–470 | Registry of 13 health metrics with name, units, and reference range `{min, max}` |
| Storage | 480–497 | `load()` / `save()` / `uuid()` / `_` state init |
| `curMetric` | 503 | Single global for the active metric; always mutate via `setMetric()` if refactoring |
| `renderChartArea()` | 535–757 | Rebuilds the entire chart DOM on every call; reads `load()` each time |
| SVG chart | 621–729 | Hand-drawn SVG: reference band, gridlines, polyline, colored dots, hover tooltips |
| Day modal | 762–813 | Shows all measurements for a clicked date; delete per entry |
| Manual entry modal | 871–964 | Add-measurement form; validation includes range check vs `ref.max × 20` |
| Import / Export | 1003–1080 | JSON round-trip; import deduplicates and reports skipped invalid rows |
| Notes | 1085–1118 | Textarea auto-saved to `localStorage` with 400 ms debounce |

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
- **UUID generation:** use the local `uuid()` helper (line ~497), not `crypto.randomUUID()` directly — the helper includes a fallback for non-HTTPS contexts.
- **localStorage writes:** always use `save(data)`, which wraps the call in a try/catch for `QuotaExceededError`.
- **Date strings:** always ISO `YYYY-MM-DD`; pass `iso + 'T00:00:00'` to `new Date()` to avoid timezone shifts.
- **Chart re-render:** call `renderChartArea()` after any data mutation; it re-reads storage and rebuilds from scratch.
- **SVG canvas constants:** `CW=340, CH=220, PL=38, PR=10, PT=16, PB=10` — coordinate helpers `toX(date)` / `toY(value)` depend on these.
