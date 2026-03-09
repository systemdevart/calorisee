"""SQLAlchemy ORM models."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.database import Base


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, default="")
    created_at = Column(DateTime, default=utcnow)
    timezone = Column(String, default="Europe/Belgrade")
    source_type = Column(String, default="upload")  # "drive" | "upload"
    status = Column(String, default="pending")  # pending | processing | completed | failed
    data_dir = Column(String, default="")
    date_range_start = Column(String, nullable=True)
    date_range_end = Column(String, nullable=True)
    food_confidence_threshold = Column(Float, default=0.6)

    messages = relationship("Message", back_populates="dataset", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="dataset", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=new_id)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False, index=True)
    msg_hash = Column(String, index=True)  # SHA1 from parser
    timestamp = Column(String, index=True)
    sender = Column(String)
    text = Column(Text, default="")
    has_media = Column(Boolean, default=False)
    media_paths_json = Column(Text, default="[]")
    media_missing = Column(Boolean, default=False)
    raw_line = Column(Text, default="")
    classification_json = Column(Text, nullable=True)
    estimation_json = Column(Text, nullable=True)
    override_json = Column(Text, nullable=True)
    excluded = Column(Boolean, default=False)

    dataset = relationship("Dataset", back_populates="messages")

    @property
    def media_paths(self) -> list[str]:
        return json.loads(self.media_paths_json) if self.media_paths_json else []

    @property
    def classification(self) -> dict | None:
        return json.loads(self.classification_json) if self.classification_json else None

    @property
    def estimation(self) -> dict | None:
        return json.loads(self.estimation_json) if self.estimation_json else None

    @property
    def overrides(self) -> dict | None:
        return json.loads(self.override_json) if self.override_json else None

    def effective_estimation(self) -> dict | None:
        """Return estimation with user overrides applied."""
        est = self.estimation
        if not est:
            return None
        overrides = self.overrides
        if not overrides:
            return est
        merged = {**est}
        if "corrected_total_calories" in overrides:
            merged["total_calories"] = overrides["corrected_total_calories"]
        if "corrected_total_protein_g" in overrides:
            merged["total_protein_g"] = overrides["corrected_total_protein_g"]
        if "corrected_total_carbs_g" in overrides:
            merged["total_carbs_g"] = overrides["corrected_total_carbs_g"]
        if "corrected_total_fat_g" in overrides:
            merged["total_fat_g"] = overrides["corrected_total_fat_g"]
        if "corrected_items" in overrides:
            merged["items"] = overrides["corrected_items"]
        return merged


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=new_id)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    status = Column(String, default="pending")  # pending | running | completed | failed
    current_step = Column(String, default="")
    percent = Column(Integer, default=0)
    message = Column(String, default="")
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    dataset = relationship("Dataset", back_populates="jobs")
