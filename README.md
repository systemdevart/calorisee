# WhatsApp Calorie Bot

AI-powered calorie estimation from WhatsApp exported chat archives. Analyzes food-related messages (text + images) to estimate calories and macronutrients using OpenAI's vision models.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with your API key
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### `.env` example

```
OPENAI_API_KEY=sk-proj-...
OPENAI_ORG_ID=          # optional
OPENAI_PROJECT_ID=      # optional
```

## Usage

```bash
python -m whatsapp_calorie_bot \
  --gdrive_url "https://drive.google.com/file/d/<FILE_ID>/view?usp=drive_link" \
  --out_dir "./run_001" \
  --timezone "America/Chicago"
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--gdrive_url` | *required* | Google Drive share link to the WhatsApp export archive |
| `--out_dir` | `./run_001` | Output directory for all artifacts |
| `--timezone` | `America/Chicago` | Timezone for message timestamps |
| `--max_messages` | None | Process at most N messages (for testing) |
| `--since` | None | Only process messages on or after YYYY-MM-DD |
| `--until` | None | Only process messages on or before YYYY-MM-DD |
| `--force_redo` | false | Ignore cache and re-process all messages |
| `--food_confidence_threshold` | 0.6 | Min confidence to proceed to calorie estimation |
| `--openai_model_text` | `gpt-4.1-mini` | Model for food classification |
| `--openai_model_vision` | `gpt-4.1` | Model for calorie estimation with images |
| `--verbose` | false | Enable debug logging |

## Output Files

All output goes to `<out_dir>/output/`:

| File | Description |
|------|-------------|
| `messages_enriched.jsonl` | Every message with classification and calorie estimation (one JSON per line) |
| `summary_stats.json` | Aggregated statistics: daily totals, rolling averages, top items |
| `daily_timeseries.csv` | Daily calorie/macro totals as CSV for easy charting |
| `report.md` | Human-friendly Markdown summary with tables |

### Other artifacts

| Path | Description |
|------|-------------|
| `<out_dir>/input/` | Downloaded archive |
| `<out_dir>/extracted/` | Extracted WhatsApp export files |
| `<out_dir>/cache.db` | SQLite cache (skip reprocessing on re-runs) |

## How It Works

1. **Download** the archive from Google Drive (via `gdown`)
2. **Extract** the zip file
3. **Parse** the WhatsApp `.txt` export and associate images
4. **Classify** each message as food/non-food (cheap text-only call)
5. **Estimate** calories for food messages (text or vision model)
6. **Compute** daily and rolling statistics
7. **Generate** output files

## Limitations

- **Portion size uncertainty**: Calorie estimates from photos are inherently approximate. Typical accuracy is +/- 30%.
- **Media matching**: Associating images with messages is best-effort. Some exports use `<Media omitted>` with no filename reference.
- **WhatsApp format variations**: The parser handles common Android and iOS export formats, but unusual locale-specific date formats may need additions.
- **Cost**: Vision model calls (gpt-4.1) are more expensive than text-only. Use `--max_messages` for testing.
- **Single chat**: Processes one exported chat archive at a time.

## Privacy Note

This tool sends message text and food images to OpenAI's API for analysis. **Do not use with sensitive data you wouldn't want processed by a third-party API.** Consider:

- Exporting only food-related chats
- Reviewing the export before processing
- Running with `--max_messages 5` first to verify behavior
- The SQLite cache stores results locally for reuse

## Future: Web App

This CLI is step 1. The planned web application will include:

- **Backend**: FastAPI serving the same pipeline as an async job
- **Frontend**: Simple dashboard with daily calorie charts, macro breakdowns, and food log timeline
- **Auth**: User login with email/password or OAuth
- **Storage**: PostgreSQL for structured data, S3 for uploaded images
- **Job queue**: Celery or RQ for batch processing of archives
- **Incremental processing**: Upload new exports and only process new messages (via `msg_id` deduplication)
- **Caching**: Same SHA-based caching as the CLI, backed by Postgres
