"""CLI entrypoint for the WhatsApp Calorie Bot."""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from whatsapp_calorie_bot.gdrive import download_gdrive_file
from whatsapp_calorie_bot.extract import extract_archive
from whatsapp_calorie_bot.whatsapp_parse import parse_whatsapp_export
from whatsapp_calorie_bot.inference import run_inference_pipeline
from whatsapp_calorie_bot.storage import Storage
from whatsapp_calorie_bot.stats import compute_stats
from whatsapp_calorie_bot.report import generate_reports

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="whatsapp_calorie_bot",
        description="Estimate calories from WhatsApp exported chat archives.",
    )
    p.add_argument(
        "--gdrive_url",
        default=None,
        help="Google Drive share link to the archive (zip/rar/7z).",
    )
    p.add_argument(
        "--local_archive",
        default=None,
        help="Path to a local archive file (skip Google Drive download).",
    )
    p.add_argument(
        "--out_dir",
        default="./run_001",
        help="Output directory for all artifacts (default: ./run_001).",
    )
    p.add_argument(
        "--timezone",
        default="Europe/Belgrade",
        help="Timezone for timestamp parsing (default: Europe/Belgrade).",
    )
    p.add_argument("--max_messages", type=int, default=None, help="Process at most N messages (for testing).")
    p.add_argument("--since", default=None, help="Only process messages on or after YYYY-MM-DD.")
    p.add_argument("--until", default=None, help="Only process messages on or before YYYY-MM-DD.")
    p.add_argument("--force_redo", action="store_true", help="Ignore cache and re-process all messages.")
    p.add_argument("--food_confidence_threshold", type=float, default=0.6, help="Min food_confidence to proceed to calorie estimation (default: 0.6).")
    p.add_argument("--openai_model_text", default="gpt-4.1-mini", help="Model for food classification (default: gpt-4.1-mini).")
    p.add_argument("--openai_model_vision", default="gpt-4.1", help="Model for calorie estimation with images (default: gpt-4.1).")
    p.add_argument("--batch", action="store_true", help="Use OpenAI Batch API (50%% cheaper, minutes-to-hours turnaround).")
    p.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    args = parse_args(argv)
    setup_logging(args.verbose)

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Download or locate archive
    if args.local_archive:
        archive_path = Path(args.local_archive).resolve()
        if not archive_path.exists():
            logger.error("Local archive not found: %s", archive_path)
            sys.exit(1)
        logger.info("Step 1/6: Using local archive: %s", archive_path)
    elif args.gdrive_url:
        logger.info("Step 1/6: Downloading archive from Google Drive...")
        input_dir = out_dir / "input"
        input_dir.mkdir(exist_ok=True)
        archive_path = download_gdrive_file(args.gdrive_url, input_dir)
        logger.info("Downloaded: %s", archive_path)
    else:
        logger.error("Provide either --gdrive_url or --local_archive.")
        sys.exit(1)

    # Step 2: Extract
    logger.info("Step 2/6: Extracting archive...")
    extract_dir = out_dir / "extracted"
    extract_dir.mkdir(exist_ok=True)
    extract_archive(archive_path, extract_dir)
    logger.info("Extracted to: %s", extract_dir)

    # Step 3: Parse WhatsApp export
    logger.info("Step 3/6: Parsing WhatsApp messages...")
    messages = parse_whatsapp_export(
        extract_dir,
        timezone=args.timezone,
        since=args.since,
        until=args.until,
        max_messages=args.max_messages,
    )
    logger.info("Parsed %d messages.", len(messages))
    if not messages:
        logger.error("No messages found. Check that the archive contains a WhatsApp .txt export.")
        sys.exit(1)

    # Step 4: Store raw messages + run inference
    storage = Storage(out_dir / "cache.db")
    storage.store_messages(messages)

    if args.batch:
        from whatsapp_calorie_bot.batch import run_batch_inference_pipeline
        logger.info("Step 4/6: Running AI inference via Batch API (50%% cheaper)...")
        enriched = run_batch_inference_pipeline(
            messages,
            storage=storage,
            force_redo=args.force_redo,
            food_confidence_threshold=args.food_confidence_threshold,
            model_text=args.openai_model_text,
            model_vision=args.openai_model_vision,
        )
    else:
        logger.info("Step 4/6: Running AI inference pipeline...")
        enriched = run_inference_pipeline(
            messages,
            storage=storage,
            force_redo=args.force_redo,
            food_confidence_threshold=args.food_confidence_threshold,
            model_text=args.openai_model_text,
            model_vision=args.openai_model_vision,
        )
    food_count = sum(1 for m in enriched if m.get("classification", {}).get("is_food"))
    logger.info("Classified %d food messages out of %d total.", food_count, len(enriched))

    # Step 5: Compute stats
    logger.info("Step 5/6: Computing statistics...")
    stats = compute_stats(enriched, timezone=args.timezone)

    # Step 6: Generate reports
    logger.info("Step 6/6: Generating output files...")
    output_dir = out_dir / "output"
    output_dir.mkdir(exist_ok=True)
    generate_reports(enriched, stats, output_dir)

    logger.info("Done! Output written to: %s", output_dir)
    logger.info("  - messages_enriched.jsonl")
    logger.info("  - summary_stats.json")
    logger.info("  - daily_timeseries.csv")
    logger.info("  - report.md")
