# CaloriSee

WhatsApp calorie analyzer. Parses exported WhatsApp chat archives, classifies food messages with OpenAI, estimates calories/macros (text + vision), and presents results in a web dashboard.

## Project Structure

```
calorisee/
├── whatsapp_calorie_bot/     # CLI pipeline (Phase 1+2)
│   ├── cli.py                # CLI entrypoint, 6-step pipeline orchestration
│   ├── gdrive.py             # Google Drive download via gdown
│   ├── extract.py            # Archive extraction (zip/rar/7z)
│   ├── whatsapp_parse.py     # WhatsApp .txt parser (Android + iOS formats)
│   ├── inference.py          # Two-stage AI: classify → estimate calories
│   ├── batch.py              # OpenAI Batch API (50% cheaper)
│   ├── openai_client.py      # OpenAI SDK wrapper with retries
│   ├── storage.py            # SQLite cache for messages + inference
│   ├── stats.py              # Daily/rolling stats computation
│   └── report.py             # Output: JSONL, JSON, CSV, Markdown
├── backend/                  # FastAPI web backend (Phase 3)
│   ├── app.py                # FastAPI app, CORS, lifespan, routers
│   ├── config.py             # Paths: data/, datasets/, app.db
│   ├── database.py           # SQLAlchemy engine + session
│   ├── models.py             # ORM: Dataset, Message, Job
│   ├── schemas.py            # Pydantic request/response models
│   ├── routers/
│   │   ├── datasets.py       # POST import/drive, POST import/upload, list, delete
│   │   ├── jobs.py           # GET status, GET SSE event stream
│   │   ├── dashboard.py      # KPI summary, daily timeseries, top items
│   │   ├── messages.py       # Day list, day detail, message detail, overrides
│   │   └── media.py          # Serve images from dataset directories
│   └── services/
│       ├── job_manager.py    # In-memory job tracking + SSE generator
│       └── pipeline.py       # Wraps CLI pipeline with progress callbacks
├── frontend/                 # React + Vite + TypeScript (Phase 3)
│   ├── src/
│   │   ├── api/client.ts     # Typed fetch wrapper for all API endpoints
│   │   ├── hooks/useJobSSE.ts # SSE hook for real-time job progress
│   │   ├── components/       # Layout, KpiCard, MacroBar, MealCard, etc.
│   │   └── pages/            # ImportPage, DashboardPage, DaysListPage, DayViewPage
│   └── vite.config.ts        # Vite + Tailwind, proxies /api → backend
├── data/                     # Runtime data (gitignored)
│   ├── app.db                # SQLAlchemy database
│   └── datasets/{id}/        # Per-dataset files (extracted archives, cache)
├── .env                      # OPENAI_API_KEY (gitignored)
├── .env.example              # Template
├── pyproject.toml            # Python project config
├── requirements.txt          # CLI Python deps
└── backend/requirements.txt  # Backend Python deps
```

## Environment Setup

### Prerequisites

- Python >= 3.10
- Node.js >= 18
- OpenAI API key

### Python dependencies

```bash
# Install CLI deps
pip install -r requirements.txt

# Install backend deps
pip install -r backend/requirements.txt
```

On this machine, use `sudo $(which pip3) install ...` to install into the global conda env.

### Frontend dependencies

```bash
cd frontend
npm install
```

### Environment variables

Copy `.env.example` to `.env` and set your OpenAI key:

```
OPENAI_API_KEY=sk-proj-...
```

Optional env vars:
- `OPENAI_MODEL_TEXT` — classification model (default: `gpt-4.1-mini`)
- `OPENAI_MODEL_VISION` — vision estimation model (default: `gpt-4.1`)

## Running

### Web App (backend + frontend)

```bash
# Terminal 1 — Backend (from project root)
uvicorn backend.app:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` requests to the backend at :8000.

### CLI (standalone)

```bash
# From Google Drive
python -m whatsapp_calorie_bot --gdrive_url "https://drive.google.com/file/d/..." --out_dir ./run_001

# From local archive
python -m whatsapp_calorie_bot --local_archive ./archive.zip --out_dir ./run_001

# With Batch API (50% cheaper, slower turnaround)
python -m whatsapp_calorie_bot --local_archive ./archive.zip --batch --out_dir ./run_001
```

CLI flags: `--timezone`, `--food_confidence_threshold`, `--max_messages`, `--since`, `--until`, `--force_redo`, `--verbose`.

## Architecture Notes

### AI Pipeline

Two-stage: (1) classify message as food/non-food with gpt-4.1-mini, (2) estimate calories/macros with gpt-4.1 (vision) or gpt-4.1-mini (text-only). Results are cached in SQLite so re-runs skip already-processed messages.

### Data Flow (Web)

1. User uploads archive or provides Google Drive link
2. Backend creates Dataset + Job, returns IDs immediately
3. Background thread runs pipeline: download → extract → parse → classify → estimate → store
4. Frontend polls progress via SSE (`/api/jobs/{id}/events`)
5. Dashboard reads from SQLAlchemy DB, computes KPIs/charts on the fly
6. User can override AI estimates per-message; overrides stored in `override_json` column and merged at read time via `Message.effective_estimation()`

### Key Design Decisions

- Single SQLite database (`data/app.db`) for all web data
- CLI uses its own SQLite cache (`cache.db`) per run, separate from web DB
- Background jobs run as daemon threads (no external queue needed for single-user)
- SSE streaming: job_manager holds in-memory dict, SSE endpoint polls it every 1s
- Message deduplication via SHA1 hash of (timestamp + sender + text + file hashes)

## Common Tasks

### Adding a new API endpoint

1. Add Pydantic schema to `backend/schemas.py`
2. Add route to appropriate router in `backend/routers/`
3. Add typed client function in `frontend/src/api/client.ts`

### Rebuilding frontend

```bash
cd frontend && npm run build
```

Output goes to `frontend/dist/`. The backend doesn't serve static files — use the Vite dev server in development.

### Database reset

Delete `data/app.db` and restart the backend. `init_db()` in lifespan recreates tables.
