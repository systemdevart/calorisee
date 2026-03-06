"""Generate output files: JSONL, summary JSON, CSV, and Markdown report."""

import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_reports(enriched: list[dict], stats: dict, output_dir: Path) -> None:
    """Generate all output files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_jsonl(enriched, output_dir / "messages_enriched.jsonl")
    _write_summary_json(stats, output_dir / "summary_stats.json")
    _write_daily_csv(stats, output_dir / "daily_timeseries.csv")
    _write_report_md(stats, output_dir / "report.md")


def _write_jsonl(enriched: list[dict], path: Path) -> None:
    """Write enriched messages to JSONL."""
    with open(path, "w", encoding="utf-8") as f:
        for msg in enriched:
            # Remove non-serializable fields
            record = {k: v for k, v in msg.items() if k != "timestamp_dt"}
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    logger.info("Wrote %d records to %s", len(enriched), path)


def _write_summary_json(stats: dict, path: Path) -> None:
    """Write summary stats to JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Wrote summary stats to %s", path)


def _write_daily_csv(stats: dict, path: Path) -> None:
    """Write daily timeseries to CSV."""
    daily = stats.get("daily", {})
    if not daily:
        logger.warning("No daily data for CSV.")
        return

    fieldnames = [
        "date",
        "calories_total",
        "protein_g_total",
        "carbs_g_total",
        "fat_g_total",
        "food_messages",
        "image_food_messages",
        "total_messages",
        "pct_low_confidence",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for date_key in sorted(daily.keys()):
            writer.writerow(daily[date_key])
    logger.info("Wrote daily CSV to %s", path)


def _write_report_md(stats: dict, path: Path) -> None:
    """Write a human-readable Markdown report."""
    lines: list[str] = []
    lines.append("# Calorie Tracking Report")
    lines.append("")

    # Date range
    dr = stats.get("date_range", {})
    if dr:
        lines.append(f"**Date range:** {dr.get('start', '?')} to {dr.get('end', '?')}")
    lines.append(f"**Total messages processed:** {stats.get('total_messages_processed', 0)}")
    lines.append(f"**Food messages identified:** {stats.get('total_food_messages', 0)}")
    lines.append("")

    # Rolling averages
    rolling = stats.get("rolling", {})

    for period_key, label in [("last_7_days", "Last 7 Days"), ("last_30_days", "Last 30 Days")]:
        r = rolling.get(period_key, {})
        if not r or r.get("data_days", 0) == 0:
            continue
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Days with food logs | {r.get('days_with_food_logs', 0)} / {r.get('period_days', 0)} |")
        lines.append(f"| Consistency | {r.get('consistency_pct', 0)}% |")
        lines.append(f"| Avg calories/day | {r.get('avg_calories_per_day', 0)} |")
        lines.append(f"| Median calories/day | {r.get('median_calories_per_day', 0)} |")
        lines.append(f"| Min calories | {r.get('min_calories', 0)} |")
        lines.append(f"| Max calories | {r.get('max_calories', 0)} |")
        lines.append(f"| Avg protein (g) | {r.get('avg_protein_g', 0)} |")
        lines.append(f"| Avg carbs (g) | {r.get('avg_carbs_g', 0)} |")
        lines.append(f"| Avg fat (g) | {r.get('avg_fat_g', 0)} |")
        lines.append("")

    # Weekday vs weekend
    wd = rolling.get("weekday_avg_calories", 0)
    we = rolling.get("weekend_avg_calories", 0)
    if wd or we:
        lines.append("## Weekday vs Weekend")
        lines.append("")
        lines.append(f"- Weekday avg: **{wd}** cal/day")
        lines.append(f"- Weekend avg: **{we}** cal/day")
        lines.append("")

    # Best / worst day
    bw = stats.get("best_worst", {})
    if bw:
        lines.append("## Notable Days")
        lines.append("")
        low = bw.get("lowest_calorie_day", {})
        high = bw.get("highest_calorie_day", {})
        if low:
            lines.append(f"- **Lowest calorie day:** {low['date']} ({low['calories']} cal)")
        if high:
            lines.append(f"- **Highest calorie day:** {high['date']} ({high['calories']} cal)")
        lines.append("")

    # Top items
    items = stats.get("items", {})
    top_freq = items.get("top_by_frequency", [])
    if top_freq:
        lines.append("## Most Frequent Items")
        lines.append("")
        lines.append("| Item | Count |")
        lines.append("|------|-------|")
        for item in top_freq[:10]:
            lines.append(f"| {item['name']} | {item['count']} |")
        lines.append("")

    top_cals = items.get("top_by_total_calories", [])
    if top_cals:
        lines.append("## Top Calorie Contributors")
        lines.append("")
        lines.append("| Item | Total Calories |")
        lines.append("|------|---------------|")
        for item in top_cals[:10]:
            lines.append(f"| {item['name']} | {item['total_calories']} |")
        lines.append("")

    # Missing days
    missing = stats.get("missing_days", [])
    if missing:
        lines.append("## Missing Days (no food logs)")
        lines.append("")
        for d in missing[:15]:
            lines.append(f"- {d}")
        if len(missing) > 15:
            lines.append(f"- ... and {len(missing) - 15} more")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by WhatsApp Calorie Bot*")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote report to %s", path)
