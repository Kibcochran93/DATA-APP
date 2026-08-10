# Standalone SEATS Data Validator (single-file HTML)

A zero-install, offline version of the validator for customers: open one `.html`
in any browser, drop a CSV/Excel, pick the SEATS data type, and download a
SEATS-ready file plus an issues report. **All processing is client-side — data
never leaves the machine, no server, no login.**

## For customers

Send them **`seats_validator.html`**. They double-click it (or you host it on any
static site / SharePoint and share the link). Two modes:

- **Single file** — drop one CSV/Excel → pick type → download clean file + issues.
- **Canvas DAP** — drop the Canvas DAP table files (users, enrollments, courses,
  course_sections, pseudonyms, accounts, …); they're joined in-browser into a
  roster, then cleaned.

Best-effort: it always produces a fully spec-shaped file. Anything it can't fix
(e.g. a genuinely missing mandatory value) is left blank and listed in the issues
report — never guessed.

## For developers

The HTML is **generated** so it stays in sync with the Python engine's specs and
mappings:

- `engine.js` — the pure-JS engine (mirrors `utils.auto_clean` + `utils.canvas_dap`).
- `template.html` — UI + glue, with `<!--INJECT_*-->` markers.
- `build.py` — reads `data/master/*.json` + `data/mappings/*.json` to emit
  `seats_data.json`, then inlines SheetJS (extracted from the v2.1 tool),
  the data, and the engine into `seats_validator.html`.

Rebuild after changing any spec/mapping/engine:

```bash
python standalone/build.py           # -> seats_data.json + seats_validator.html
node standalone/engine.test.js       # engine unit tests (needs seats_data.json)
```

`build.py` takes an optional path to a SheetJS-bearing HTML (defaults to the v2.1
tool) as its first argument.
