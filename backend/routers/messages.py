"""Message browsing, day view, detail, and overrides."""

import json
from collections import defaultdict
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from backend.database import get_db
from backend.models import Dataset, Message
from backend.schemas import DayDetail, MessageSummary, MessageDetail, MessageOverride

router = APIRouter(prefix="/api/datasets/{dataset_id}/messages", tags=["messages"])


def _msg_to_summary(m: Message, dataset: Dataset) -> dict:
    cls = m.classification or {}
    est = m.effective_estimation() or {}
    return MessageSummary(
        id=m.id,
        msg_hash=m.msg_hash or "",
        timestamp=m.timestamp or "",
        sender=m.sender or "",
        text=m.text or "",
        has_media=m.has_media or False,
        media_urls=[f"/api/media/{m.dataset_id}/{i}" for i, _ in enumerate(m.media_paths)] if m.media_paths else [],
        is_food=cls.get("is_food", False),
        food_confidence=cls.get("food_confidence", 0.0),
        food_context=cls.get("food_context", "non_food"),
        total_calories=est.get("total_calories"),
        protein_g=est.get("total_protein_g"),
        carbs_g=est.get("total_carbs_g"),
        fat_g=est.get("total_fat_g"),
        uncertainty_level=est.get("uncertainty", {}).get("level") if isinstance(est.get("uncertainty"), dict) else None,
        excluded=m.excluded or False,
        has_override=m.override_json is not None,
    )


@router.get("/days")
def list_days(dataset_id: str, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).get(dataset_id)
    if not dataset:
        raise HTTPException(404, "Dataset not found")

    tz = ZoneInfo(dataset.timezone or "America/Chicago")
    msgs = db.query(Message).filter(Message.dataset_id == dataset_id).all()

    daily: dict[str, dict] = defaultdict(lambda: {"count": 0, "food_count": 0, "calories": 0})
    for m in msgs:
        try:
            d = datetime.fromisoformat(m.timestamp).astimezone(tz).date().isoformat()
        except (ValueError, TypeError):
            continue
        daily[d]["count"] += 1
        cls = m.classification or {}
        est = m.effective_estimation()
        if cls.get("is_food") and est and not m.excluded:
            daily[d]["food_count"] += 1
            daily[d]["calories"] += est.get("total_calories", 0) or 0

    return [
        {"date": d, "total_messages": v["count"], "food_messages": v["food_count"], "total_calories": round(v["calories"], 1)}
        for d, v in sorted(daily.items())
    ]


@router.get("/day/{day}", response_model=DayDetail)
def get_day(dataset_id: str, day: str, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).get(dataset_id)
    if not dataset:
        raise HTTPException(404, "Dataset not found")

    tz = ZoneInfo(dataset.timezone or "America/Chicago")
    msgs = (
        db.query(Message)
        .filter(Message.dataset_id == dataset_id)
        .order_by(Message.timestamp)
        .all()
    )

    day_msgs = []
    total_cals = 0
    total_pro = 0
    total_carb = 0
    total_fat = 0
    meal_count = 0

    for m in msgs:
        try:
            d = datetime.fromisoformat(m.timestamp).astimezone(tz).date().isoformat()
        except (ValueError, TypeError):
            continue
        if d != day:
            continue

        summary = _msg_to_summary(m, dataset)
        day_msgs.append(summary)

        if summary.is_food and not summary.excluded:
            total_cals += summary.total_calories or 0
            total_pro += summary.protein_g or 0
            total_carb += summary.carbs_g or 0
            total_fat += summary.fat_g or 0
            meal_count += 1

    return DayDetail(
        date=day,
        total_calories=round(total_cals, 1),
        total_protein_g=round(total_pro, 1),
        total_carbs_g=round(total_carb, 1),
        total_fat_g=round(total_fat, 1),
        meal_count=meal_count,
        messages=day_msgs,
    )


@router.get("/{message_id}", response_model=MessageDetail)
def get_message(dataset_id: str, message_id: str, db: Session = Depends(get_db)):
    m = db.query(Message).filter(Message.id == message_id, Message.dataset_id == dataset_id).first()
    if not m:
        raise HTTPException(404, "Message not found")

    dataset = db.query(Dataset).get(dataset_id)
    summary = _msg_to_summary(m, dataset)

    return MessageDetail(
        **summary.model_dump(),
        raw_line=m.raw_line or "",
        classification=m.classification,
        estimation=m.effective_estimation(),
        overrides=m.overrides,
    )


@router.patch("/{message_id}/override")
def override_message(dataset_id: str, message_id: str, body: MessageOverride, db: Session = Depends(get_db)):
    m = db.query(Message).filter(Message.id == message_id, Message.dataset_id == dataset_id).first()
    if not m:
        raise HTTPException(404, "Message not found")

    existing = m.overrides or {}
    patch = body.model_dump(exclude_none=True)

    # Handle excluded separately (it's a first-class column)
    if "excluded" in patch:
        m.excluded = patch.pop("excluded")

    if "is_food_override" in patch:
        is_food = patch.pop("is_food_override")
        cls = m.classification or {}
        cls["is_food"] = is_food
        m.classification_json = json.dumps(cls)

    if patch:
        existing.update(patch)
        m.override_json = json.dumps(existing)

    db.commit()
    return {"ok": True}
