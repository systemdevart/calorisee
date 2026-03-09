"""Pydantic request/response schemas."""

from pydantic import BaseModel


# -- Import --
class DriveImportRequest(BaseModel):
    gdrive_url: str
    timezone: str = "Europe/Belgrade"
    threshold: float = 0.6
    force_redo: bool = False


class UploadImportFields(BaseModel):
    timezone: str = "Europe/Belgrade"
    threshold: float = 0.6
    force_redo: bool = False


class ImportResponse(BaseModel):
    dataset_id: str
    job_id: str


# -- Job --
class JobStatus(BaseModel):
    id: str
    dataset_id: str
    status: str
    current_step: str
    percent: int
    message: str
    error: str | None = None


# -- Dashboard --
class KpiSummary(BaseModel):
    avg_calories_7d: float
    avg_calories_30d: float
    days_logged_30d: int
    avg_protein_g: float
    avg_carbs_g: float
    avg_fat_g: float
    total_messages: int
    total_food_messages: int
    date_range_start: str | None = None
    date_range_end: str | None = None


class DailyPoint(BaseModel):
    date: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_count: int
    uncertainty_pct: float


class TopItem(BaseModel):
    name: str
    count: int
    total_calories: float


# -- Message --
class MessageSummary(BaseModel):
    id: str
    msg_hash: str
    timestamp: str
    sender: str
    text: str
    has_media: bool
    media_urls: list[str]
    is_food: bool
    food_confidence: float
    food_context: str
    meal_name: str | None = None
    visual_description: str | None = None
    total_calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    uncertainty_level: str | None = None
    excluded: bool = False
    has_override: bool = False


class MessageDetail(MessageSummary):
    raw_line: str
    classification: dict | None = None
    estimation: dict | None = None
    overrides: dict | None = None


class MessageOverride(BaseModel):
    excluded: bool | None = None
    is_food_override: bool | None = None
    corrected_total_calories: float | None = None
    corrected_total_protein_g: float | None = None
    corrected_total_carbs_g: float | None = None
    corrected_total_fat_g: float | None = None
    corrected_items: list[dict] | None = None
    notes: str | None = None


class DayDetail(BaseModel):
    date: str
    total_calories: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    meal_count: int
    messages: list[MessageSummary]
