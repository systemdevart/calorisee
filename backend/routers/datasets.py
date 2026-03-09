"""Dataset import endpoints."""

import shutil
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db, SessionLocal
from backend.models import Dataset, new_id
from backend.schemas import DriveImportRequest, UploadImportFields, ImportResponse
from backend.services.job_manager import create_job
from backend.services.pipeline import run_import_pipeline
from backend.config import DATASETS_DIR

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("/import/drive", response_model=ImportResponse)
def import_from_drive(req: DriveImportRequest, db: Session = Depends(get_db)):
    dataset_id = new_id()
    dataset = Dataset(id=dataset_id, name="Google Drive import", source_type="drive", timezone=req.timezone)
    db.add(dataset)
    db.commit()

    job_id = create_job(dataset_id, db)

    threading.Thread(
        target=run_import_pipeline,
        args=(dataset_id, job_id, SessionLocal),
        kwargs=dict(gdrive_url=req.gdrive_url, timezone=req.timezone, threshold=req.threshold, force_redo=req.force_redo),
        daemon=True,
    ).start()

    return ImportResponse(dataset_id=dataset_id, job_id=job_id)


@router.post("/import/upload", response_model=ImportResponse)
def import_from_upload(
    file: UploadFile = File(...),
    timezone: str = Form("America/Chicago"),
    threshold: float = Form(0.6),
    force_redo: bool = Form(False),
    db: Session = Depends(get_db),
):
    dataset_id = new_id()
    dataset = Dataset(id=dataset_id, name=file.filename or "Upload", source_type="upload", timezone=timezone)
    db.add(dataset)
    db.commit()

    # Save uploaded file
    dataset_dir = DATASETS_DIR / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    upload_path = dataset_dir / "upload_archive"
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    job_id = create_job(dataset_id, db)

    threading.Thread(
        target=run_import_pipeline,
        args=(dataset_id, job_id, SessionLocal),
        kwargs=dict(archive_path=str(upload_path), timezone=timezone, threshold=threshold, force_redo=force_redo),
        daemon=True,
    ).start()

    return ImportResponse(dataset_id=dataset_id, job_id=job_id)


@router.get("")
def list_datasets(db: Session = Depends(get_db)):
    datasets = db.query(Dataset).order_by(Dataset.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "status": d.status,
            "source_type": d.source_type,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "date_range_start": d.date_range_start,
            "date_range_end": d.date_range_end,
        }
        for d in datasets
    ]


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).get(dataset_id)
    if not dataset:
        raise HTTPException(404, "Dataset not found")
    # Clean up files
    if dataset.data_dir:
        data_path = Path(dataset.data_dir)
        if data_path.exists():
            shutil.rmtree(data_path)
    db.delete(dataset)
    db.commit()
    return {"ok": True}
