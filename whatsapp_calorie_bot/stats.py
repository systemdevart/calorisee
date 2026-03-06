"""Compute daily and rolling statistics from enriched messages."""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean, median
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def _parse_date(ts_str: str, tz: ZoneInfo) -> date | None:
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.astimezone(tz).date()
    except (ValueError, TypeError):
        return None


def compute_stats(enriched: list[dict], timezone: str = "America/Chicago") -> dict:
    """Compute all statistics from enriched messages."""
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo("America/Chicago")

    # Build daily buckets
    daily: dict[date, dict] = defaultdict(lambda: {
        "calories": 0,
        "protein_g": 0,
        "carbs_g": 0,
        "fat_g": 0,
        "food_messages": 0,
        "image_food_messages": 0,
        "low_confidence_count": 0,
        "total_messages": 0,
        "items": [],
    })

    all_items: list[dict] = []

    for msg in enriched:
        d = _parse_date(msg.get("timestamp", ""), tz)
        if not d:
            continue
        daily[d]["total_messages"] += 1

        classification = msg.get("classification", {})
        estimation = msg.get("estimation")
        is_food = classification.get("is_food", False)

        if not is_food or not estimation:
            continue

        daily[d]["food_messages"] += 1
        if msg.get("has_media") and msg.get("media_paths"):
            daily[d]["image_food_messages"] += 1

        cals = estimation.get("total_calories", 0) or 0
        daily[d]["calories"] += cals
        daily[d]["protein_g"] += estimation.get("total_protein_g", 0) or 0
        daily[d]["carbs_g"] += estimation.get("total_carbs_g", 0) or 0
        daily[d]["fat_g"] += estimation.get("total_fat_g", 0) or 0

        confidence = classification.get("food_confidence", 1.0)
        uncertainty = estimation.get("uncertainty", {}).get("level", "low")
        if confidence < 0.7 or uncertainty == "high":
            daily[d]["low_confidence_count"] += 1

        for item in estimation.get("items", []):
            item_record = {
                "name": item.get("name", "unknown"),
                "calories": item.get("calories", 0),
                "date": d.isoformat(),
            }
            daily[d]["items"].append(item_record)
            all_items.append(item_record)

    if not daily:
        logger.warning("No daily data to compute stats from.")
        return {"daily": {}, "rolling": {}, "items": {}}

    # Sort dates
    sorted_dates = sorted(daily.keys())
    today = date.today()

    # Build daily timeseries
    daily_series = {}
    for d in sorted_dates:
        bucket = daily[d]
        total_est = bucket["food_messages"]
        low_conf = bucket["low_confidence_count"]
        daily_series[d.isoformat()] = {
            "date": d.isoformat(),
            "calories_total": bucket["calories"],
            "protein_g_total": bucket["protein_g"],
            "carbs_g_total": bucket["carbs_g"],
            "fat_g_total": bucket["fat_g"],
            "food_messages": bucket["food_messages"],
            "image_food_messages": bucket["image_food_messages"],
            "total_messages": bucket["total_messages"],
            "pct_low_confidence": round(low_conf / total_est * 100, 1) if total_est > 0 else 0,
        }

    # Rolling aggregates
    def _rolling(days: int) -> dict:
        cutoff = today - timedelta(days=days)
        period_dates = [d for d in sorted_dates if d >= cutoff]
        if not period_dates:
            return {"period_days": days, "data_days": 0}
        cal_values = [daily[d]["calories"] for d in period_dates if daily[d]["food_messages"] > 0]
        if not cal_values:
            return {"period_days": days, "data_days": len(period_dates), "avg_calories": 0}
        return {
            "period_days": days,
            "data_days": len(period_dates),
            "days_with_food_logs": len(cal_values),
            "consistency_pct": round(len(cal_values) / days * 100, 1),
            "avg_calories_per_day": round(mean(cal_values), 1),
            "median_calories_per_day": round(median(cal_values), 1),
            "min_calories": min(cal_values),
            "max_calories": max(cal_values),
            "total_calories": sum(cal_values),
            "avg_protein_g": round(mean(daily[d]["protein_g"] for d in period_dates if daily[d]["food_messages"] > 0), 1),
            "avg_carbs_g": round(mean(daily[d]["carbs_g"] for d in period_dates if daily[d]["food_messages"] > 0), 1),
            "avg_fat_g": round(mean(daily[d]["fat_g"] for d in period_dates if daily[d]["food_messages"] > 0), 1),
        }

    rolling = {
        "last_7_days": _rolling(7),
        "last_30_days": _rolling(30),
    }

    # Weekday vs weekend
    weekday_cals = [daily[d]["calories"] for d in sorted_dates if d.weekday() < 5 and daily[d]["food_messages"] > 0]
    weekend_cals = [daily[d]["calories"] for d in sorted_dates if d.weekday() >= 5 and daily[d]["food_messages"] > 0]
    rolling["weekday_avg_calories"] = round(mean(weekday_cals), 1) if weekday_cals else 0
    rolling["weekend_avg_calories"] = round(mean(weekend_cals), 1) if weekend_cals else 0

    # Top items by frequency and calories
    item_freq: dict[str, int] = defaultdict(int)
    item_cals: dict[str, float] = defaultdict(float)
    for item in all_items:
        name = item["name"].lower().strip()
        item_freq[name] += 1
        item_cals[name] += item.get("calories", 0)

    top_by_freq = sorted(item_freq.items(), key=lambda x: x[1], reverse=True)[:15]
    top_by_cals = sorted(item_cals.items(), key=lambda x: x[1], reverse=True)[:15]

    items_stats = {
        "top_by_frequency": [{"name": n, "count": c} for n, c in top_by_freq],
        "top_by_total_calories": [{"name": n, "total_calories": round(c)} for n, c in top_by_cals],
    }

    # Best / worst day
    days_with_food = [(d, daily[d]["calories"]) for d in sorted_dates if daily[d]["food_messages"] > 0]
    best_worst = {}
    if days_with_food:
        best_day = min(days_with_food, key=lambda x: x[1])
        worst_day = max(days_with_food, key=lambda x: x[1])
        best_worst = {
            "lowest_calorie_day": {"date": best_day[0].isoformat(), "calories": best_day[1]},
            "highest_calorie_day": {"date": worst_day[0].isoformat(), "calories": worst_day[1]},
        }

    # Missing days (in range)
    if len(sorted_dates) >= 2:
        all_days_in_range = set()
        d = sorted_dates[0]
        while d <= sorted_dates[-1]:
            all_days_in_range.add(d)
            d += timedelta(days=1)
        logged_days = {d for d in sorted_dates if daily[d]["food_messages"] > 0}
        missing_days = sorted(all_days_in_range - logged_days)
    else:
        missing_days = []

    return {
        "daily": daily_series,
        "rolling": rolling,
        "items": items_stats,
        "best_worst": best_worst,
        "missing_days": [d.isoformat() for d in missing_days[:30]],
        "total_food_messages": sum(daily[d]["food_messages"] for d in sorted_dates),
        "total_messages_processed": sum(daily[d]["total_messages"] for d in sorted_dates),
        "date_range": {
            "start": sorted_dates[0].isoformat(),
            "end": sorted_dates[-1].isoformat(),
        },
    }
