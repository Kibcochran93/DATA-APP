# SEATS Data Validator

A Streamlit app that turns a university's Student Information System (SIS) export
into a **SEAtS-ready file**. Upload a spreadsheet, map its headings to the SEAtS
Interface Spec, review validation and data-quality issues, and export a clean
UTF-8 CSV in the correct SEAtS column order.

It supports exports from Banner, PeopleSoft, Workday, Colleague, Jenzabar,
PowerCampus and generic sources, and validates against the **SEAtS Interface
Spec v8.2** (Student, Staff and Student Timetable).

## What it does

The core is a guided **7-step wizard**:

1. **Upload** — CSV / XLS / XLSX (headings in row 1, first sheet).
2. **Dataset select** — Student, Staff or Timetable, plus institution hierarchy.
3. **Header mapping** — auto-suggests SIS → SEAtS column mappings (exact, alias,
   and fuzzy matching), which you confirm or override.
4. **Validation** — schema checks (missing / duplicate / mis-ordered columns,
   near-miss typos) and row checks (mandatory values, date/time/enum formats).
5. **Auto-fix** — reorder to spec, insert missing columns, generate EVENT_IDs,
   normalize values, repair encoding/BOM issues.
6. **Review** — preview the corrected data.
7. **Export** — download a UTF-8 CSV in SEAtS heading order.

The spec, field metadata and value mappings live in
`data/master/*.json` and `data/mappings/sis_to_seats_mapping.json`.

## Supported run modes

Two modes are supported. There is **no** Windows-exe build (a Streamlit app can't
be meaningfully packaged as a console exe).

### 1. Streamlit (primary, local)

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501. On Windows you can double-click
`run_app.bat`, which creates a venv on first run and launches the app.

### 2. Docker (app container)

```bash
# Provide a strong secret first (compose requires it):
echo "JWT_SECRET=$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" > .env
docker compose up --build
```

The compose file runs the app with production defaults (`DEBUG=false`). Redis is
optional and off by default — uncomment the `redis` service and set
`REDIS_ENABLED=true` if you want caching/session storage.

> The previous Prometheus/Grafana monitoring stack was removed: it referenced
> `./deployment/*` config directories that were never in the repo, so it could
> not start. In-process metrics are still written under `data/` by
> `monitoring/monitoring.py`.

## Configuration

Settings are read from environment variables (see `config/config.py` and
`security/config.py`). The important ones:

| Variable | Default | Notes |
| --- | --- | --- |
| `JWT_SECRET` | insecure fallback | **Set this.** Signs auth tokens (HS256). |
| `TEST_MODE` | `false` | `true` bypasses auth — **local dev only**. |
| `DEBUG` | `false` | `true` shows stack traces in the UI. |
| `MAX_FILE_SIZE` | 5 MB (manual) | Upload cap; SFTP path allows 50 MB. |
| `ENCRYPTION_KEY_FILE` | `keys/encryption.key` | Auto-generated on first run if absent. |

### Security notes

- **`keys/` is gitignored.** A live encryption key was committed to this repo's
  history in the past — treat it as compromised: rotate it and purge it from
  history (`git filter-repo` / BFG). A fresh local key is generated automatically
  when none is present.
- **Always set `JWT_SECRET`** to a strong, unique value before deploying. The
  built-in fallback exists only so local dev doesn't crash.

## Testing

```bash
pip install -r requirements.txt
pytest -q
```

The suite covers the validation engine (`utils/seats_validator.py`,
`utils/seats_data_handler.py`, `utils/sis_mapper.py`, `utils/data_quality.py`),
auth, monitoring, protection and the controllers.

## Project structure

```
app.py                     # Streamlit entry point + page routing
wizard_controller.py       # the 7-step validation wizard (core flow)
ui_components.py            # shared Streamlit UI widgets
config/config.py           # app config, session keys, dataset types
security/config.py         # file/auth/protection/monitoring config
autho/auth.py              # JWT auth, users, roles
protection/                # PII masking + encryption helpers
monitoring/                # in-process metrics / health
controller/                # upload / export / settings / monitoring pages
components/                # validation error panel
helpers/                   # logger + header normalization
utils/
  seats_data_handler.py    # SEAtS spec mechanics (the workhorse)
  seats_validator.py       # spec-driven schema + row validation
  sis_mapper.py            # SIS detection + column/value mapping
  data_quality.py          # data-quality detection + fixes
  hierarchy_config.py      # institution hierarchy
  data_exporter.py / export_packager.py
data/
  master/*.json            # SEAtS Interface Spec v8.2 (Student/Staff/Timetable)
  mappings/*.json          # SIS -> SEAtS column & value mappings
  test_data/               # sample CSVs (clean + with errors)
tests/                     # pytest suite
```

## License

MIT — see [LICENSE](LICENSE).
