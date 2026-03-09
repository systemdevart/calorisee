"""Pipeline orchestrator: wraps existing CLI functions for the web backend."""

import json
import logging
import shutil
from pathlib import Path

from backend.config import DATASETS_DIR
from backend.models import Dataset, Message, new_id
from backend.services.job_manager import update_job

from whatsapp_calorie_bot.gdrive import download_gdrive_file
from whatsapp_calorie_bot.extract import extract_archive
from whatsapp_calorie_bot.whatsapp_parse import parse_whatsapp_export

from whatsapp_calorie_bot.storage import Storage

logger = logging.getLogger(__name__)


def run_import_pipeline(
    dataset_id: str,
    job_id: str,
    db_factory,
    *,
    gdrive_url: str | None = None,
    archive_path: str | None = None,
    timezone: str = "Europe/Belgrade",
    threshold: float = 0.6,
    force_redo: bool = False,
):
    """Run the full import pipeline in a background thread."""
    db = db_factory()
    try:
        _run(dataset_id, job_id, db, gdrive_url=gdrive_url, archive_path=archive_path,
             timezone=timezone, threshold=threshold, force_redo=force_redo)
    except Exception as e:
        logger.exception("Pipeline failed for dataset %s", dataset_id)
        update_job(job_id, db, status="failed", error=str(e), message=f"Error: {e}")
        dataset = db.query(Dataset).get(dataset_id)
        if dataset:
            dataset.status = "failed"
            db.commit()
    finally:
        db.close()


def _run(
    dataset_id: str,
    job_id: str,
    db,
    *,
    gdrive_url: str | None,
    archive_path: str | None,
    timezone: str,
    threshold: float,
    force_redo: bool,
):
    dataset_dir = DATASETS_DIR / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)

    dataset = db.query(Dataset).get(dataset_id)
    dataset.status = "processing"
    dataset.data_dir = str(dataset_dir)
    db.commit()

    update_job(job_id, db, status="running", current_step="download", percent=5, message="Downloading archive...")

    # Step 1: Download or use uploaded archive
    if gdrive_url:
        input_dir = dataset_dir / "input"
        input_dir.mkdir(exist_ok=True)
        local_archive = download_gdrive_file(gdrive_url, input_dir)
    elif archive_path:
        local_archive = Path(archive_path)
    else:
        raise ValueError("No source provided")

    update_job(job_id, db, current_step="extract", percent=15, message="Extracting archive...")

    # Step 2: Extract
    extract_dir = dataset_dir / "extracted"
    extract_dir.mkdir(exist_ok=True)
    extract_archive(local_archive, extract_dir)

    update_job(job_id, db, current_step="parse", percent=25, message="Parsing WhatsApp messages...")

    # Step 3: Parse
    messages = parse_whatsapp_export(extract_dir, timezone=timezone)
    if not messages:
        raise RuntimeError("No messages found in the archive. Is this a WhatsApp export?")

    update_job(job_id, db, current_step="classify", percent=35, message=f"Running AI on {len(messages)} messages...")

    # Step 4: Inference
    cache_db = Storage(dataset_dir / "cache.db")
    cache_db.store_messages(messages)

    total = len(messages)

    def _progress_callback(i: int, msg: dict):
        pct = 35 + int(55 * i / total)
        update_job(job_id, db, percent=pct, message=f"Processing message {i}/{total}...")

    enriched = _run_inference_with_progress(
        messages, cache_db, force_redo, threshold, _progress_callback
    )
    cache_db.close()

    update_job(job_id, db, current_step="store", percent=92, message="Saving results to database...")

    # Step 5: Store messages in SQLAlchemy DB
    _store_messages(dataset_id, enriched, db)

    # Step 6: Update dataset metadata
    dates = []
    for msg in enriched:
        ts = msg.get("timestamp", "")
        if ts:
            dates.append(ts[:10])
    if dates:
        dataset.date_range_start = min(dates)
        dataset.date_range_end = max(dates)

    dataset.status = "completed"
    dataset.food_confidence_threshold = threshold
    db.commit()

    food_count = sum(1 for m in enriched if m.get("classification", {}).get("is_food"))
    update_job(job_id, db, status="completed", current_step="done", percent=100,
               message=f"Done! {len(enriched)} messages, {food_count} food entries.")


def _run_inference_with_progress(messages, storage, force_redo, threshold, callback,
                                 max_workers=10):
    """Run inference in parallel with progress callbacks."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from whatsapp_calorie_bot.inference import _process_single_message
    import threading

    total = len(messages)
    enriched: list[dict | None] = [None] * total
    done_count = 0
    counter_lock = threading.Lock()

    def _process(i: int, msg: dict) -> tuple[int, dict]:
        return i, _process_single_message(
            msg, storage, force_redo, threshold, "gpt-4.1-mini", "gpt-4.1",
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process, i, msg): i for i, msg in enumerate(messages)}
        for future in as_completed(futures):
            i, result = future.result()
            enriched[i] = result
            with counter_lock:
                done_count += 1
                current = done_count
            callback(current, result)

    return enriched


def _store_messages(dataset_id: str, enriched: list[dict], db):
    """Store enriched messages into the SQLAlchemy Message table."""
    # Delete existing messages for this dataset (re-import)
    db.query(Message).filter(Message.dataset_id == dataset_id).delete()
    db.flush()

    for msg in enriched:
        classification = msg.get("classification", {})
        estimation = msg.get("estimation")
        is_food = classification.get("is_food", False)
        confidence = classification.get("food_confidence", 0.0)

        m = Message(
            id=new_id(),
            dataset_id=dataset_id,
            msg_hash=msg.get("msg_id", ""),
            timestamp=msg.get("timestamp", ""),
            sender=msg.get("sender", ""),
            text=msg.get("text", ""),
            has_media=msg.get("has_media", False),
            media_paths_json=json.dumps(msg.get("media_paths", [])),
            media_missing=msg.get("media_missing", False),
            raw_line=msg.get("raw_line", ""),
            classification_json=json.dumps(classification) if classification else None,
            estimation_json=json.dumps(estimation) if estimation else None,
        )
        db.add(m)

    db.commit()
