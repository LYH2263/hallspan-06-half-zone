import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Hall, SeatPlan
from app.services.reseat import submit, empty_result

router = APIRouter(prefix="/seating", tags=["seating"])


def load_latest(db: Session, hall_id: int) -> dict:
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "考室不存在")
    plan = db.scalars(
        select(SeatPlan).where(SeatPlan.hall_id == hall_id).order_by(SeatPlan.id.desc())
    ).first()
    if not plan:
        return empty_result(hall)
    return {"id": plan.id, **json.loads(plan.result_json)}


@router.post("/run")
def run_seating(hall_id: int = 1, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "考室不存在")
    # 两本账双写 + 新方案同事务提交；失败整体回滚、不增方案。
    return submit(db, hall)


@router.get("/latest")
def latest(hall_id: int = 1, db: Session = Depends(get_db)):
    return load_latest(db, hall_id)


@router.get("/violations")
def violations(hall_id: int = 1, db: Session = Depends(get_db)):
    data = load_latest(db, hall_id)
    return {"hall_id": hall_id, "violations": data.get("violations", []),
            "unplaced": data.get("unplaced", [])}


@router.get("/stats")
def stats(hall_id: int = 1, db: Session = Depends(get_db)):
    data = load_latest(db, hall_id)
    return {"hall_id": hall_id, **data.get("stats", {})}
