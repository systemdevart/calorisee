# CaloriSee

AI-powered calorie estimation from WhatsApp chat exports. Classifies food messages and estimates calories/macros using OpenAI (text + vision).

## Quick Start

```bash
# 1. Install deps
pip install -r requirements.txt
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..

# 2. Set your OpenAI key
cp .env.example .env
# edit .env → OPENAI_API_KEY=sk-proj-...

# 3. Run the web app
uvicorn backend.app:app --reload --port 8000   # terminal 1
cd frontend && npm run dev                      # terminal 2
# Open http://localhost:5173
```

## CLI Usage

```bash
# From Google Drive
python -m whatsapp_calorie_bot --gdrive_url "https://drive.google.com/file/d/..." --out_dir ./run_001

# From local file
python -m whatsapp_calorie_bot --local_archive ./archive.zip --out_dir ./run_001

# Batch API (50% cheaper)
python -m whatsapp_calorie_bot --local_archive ./archive.zip --batch --out_dir ./run_001
```

Flags: `--timezone`, `--food_confidence_threshold`, `--max_messages`, `--since`, `--until`, `--force_redo`, `--batch`, `--verbose`.

## How It Works

1. **Extract** WhatsApp export archive (zip/rar/7z)
2. **Parse** chat .txt file, associate images
3. **Classify** each message as food/non-food (gpt-4.1-mini)
4. **Estimate** calories + macros for food messages (gpt-4.1 for images, gpt-4.1-mini for text)
5. **Dashboard** shows daily calories chart, KPIs, macro breakdown, top items
6. **Override** AI estimates per-message from the web UI

Results cached in SQLite — re-runs skip already-processed messages.

## Privacy

Message text and food images are sent to OpenAI's API. Don't use with sensitive data. Test with `--max_messages 5` first.
