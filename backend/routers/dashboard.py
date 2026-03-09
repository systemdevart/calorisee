"""Dashboard endpoints: KPIs, daily timeseries, top items."""

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from backend.database import get_db
from backend.models import Dataset, Message
from backend.schemas import KpiSummary, DailyPoint, TopItem

router = APIRouter(prefix="/api/datasets/{dataset_id}/dashboard", tags=["dashboard"])


def _food_messages(db: Session, dataset_id: str):
    """Get all food messages with their effective estimations."""
    msgs = (
        db.query(Message)
        .filter(Message.dataset_id == dataset_id, Message.excluded == False)
        .all()
    )
    result = []
    for m in msgs:
        cls = m.classification
        if not cls or not cls.get("is_food"):
            continue
        est = m.effective_estimation()
        if not est:
            continue
        result.append((m, est))
    return result


def _parse_ts(ts: str, tz: ZoneInfo) -> date | None:
    try:
        return datetime.fromisoformat(ts).astimezone(tz).date()
    except (ValueError, TypeError):
        return None


@router.get("/summary", response_model=KpiSummary)
def dashboard_summary(dataset_id: str, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).get(dataset_id)
    if not dataset:
        raise HTTPException(404, "Dataset not found")

    tz = ZoneInfo(dataset.timezone or "America/Chicago")
    food = _food_messages(db, dataset_id)

    daily_cals: dict[date, float] = defaultdict(float)
    daily_protein: dict[date, float] = defaultdict(float)
    daily_carbs: dict[date, float] = defaultdict(float)
    daily_fat: dict[date, float] = defaultdict(float)

    for m, est in food:
        d = _parse_ts(m.timestamp, tz)
        if not d:
            continue
        daily_cals[d] += est.get("total_calories", 0) or 0
        daily_protein[d] += est.get("total_protein_g", 0) or 0
        daily_carbs[d] += est.get("total_carbs_g", 0) or 0
        daily_fat[d] += est.get("total_fat_g", 0) or 0

    sorted_dates = sorted(daily_cals.keys())
    if not sorted_dates:
        return KpiSummary(
            avg_calories_7d=0, avg_calories_30d=0, days_logged_30d=0,
            avg_protein_g=0, avg_carbs_g=0, avg_fat_g=0,
            total_messages=db.query(Message).filter(Message.dataset_id == dataset_id).count(),
            total_food_messages=len(food),
            date_range_start=dataset.date_range_start,
            date_range_end=dataset.date_range_end,
        )

    ref = sorted_dates[-1]

    def _avg(days: int) -> float:
        cutoff = ref - timedelta(days=days)
        vals = [daily_cals[d] for d in sorted_dates if d >= cutoff]
        return round(mean(vals), 1) if vals else 0

    cutoff_30 = ref - timedelta(days=30)
    days_30 = [d for d in sorted_dates if d >= cutoff_30]

    return KpiSummary(
        avg_calories_7d=_avg(7),
        avg_calories_30d=_avg(30),
        days_logged_30d=len(days_30),
        avg_protein_g=round(mean(daily_protein[d] for d in days_30), 1) if days_30 else 0,
        avg_carbs_g=round(mean(daily_carbs[d] for d in days_30), 1) if days_30 else 0,
        avg_fat_g=round(mean(daily_fat[d] for d in days_30), 1) if days_30 else 0,
        total_messages=db.query(Message).filter(Message.dataset_id == dataset_id).count(),
        total_food_messages=len(food),
        date_range_start=dataset.date_range_start,
        date_range_end=dataset.date_range_end,
    )


@router.get("/daily", response_model=list[DailyPoint])
def daily_timeseries(dataset_id: str, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).get(dataset_id)
    if not dataset:
        raise HTTPException(404, "Dataset not found")

    tz = ZoneInfo(dataset.timezone or "America/Chicago")
    food = _food_messages(db, dataset_id)

    daily: dict[date, dict] = defaultdict(lambda: {"cal": 0, "pro": 0, "carb": 0, "fat": 0, "count": 0, "low": 0, "total": 0})

    for m, est in food:
        d = _parse_ts(m.timestamp, tz)
        if not d:
            continue
        daily[d]["cal"] += est.get("total_calories", 0) or 0
        daily[d]["pro"] += est.get("total_protein_g", 0) or 0
        daily[d]["carb"] += est.get("total_carbs_g", 0) or 0
        daily[d]["fat"] += est.get("total_fat_g", 0) or 0
        daily[d]["count"] += 1
        unc = est.get("uncertainty", {})
        if isinstance(unc, dict) and unc.get("level") == "high":
            daily[d]["low"] += 1
        daily[d]["total"] += 1

    return [
        DailyPoint(
            date=d.isoformat(),
            calories=round(v["cal"], 1),
            protein_g=round(v["pro"], 1),
            carbs_g=round(v["carb"], 1),
            fat_g=round(v["fat"], 1),
            meal_count=v["count"],
            uncertainty_pct=round(v["low"] / v["total"] * 100, 1) if v["total"] else 0,
        )
        for d, v in sorted(daily.items())
    ]


@router.get("/top_items", response_model=list[TopItem])
def top_items(
    dataset_id: str,
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db),
):
    dataset = db.query(Dataset).get(dataset_id)
    if not dataset:
        raise HTTPException(404, "Dataset not found")

    food = _food_messages(db, dataset_id)

    item_freq: dict[str, int] = defaultdict(int)
    item_cals: dict[str, float] = defaultdict(float)

    for m, est in food:
        for item in est.get("items", []):
            name = (item.get("name") or "unknown").lower().strip()
            item_freq[name] += 1
            item_cals[name] += item.get("calories", 0) or 0

    top = sorted(item_freq.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [
        TopItem(name=name, count=count, total_calories=round(item_cals[name], 1))
        for name, count in top
    ]
