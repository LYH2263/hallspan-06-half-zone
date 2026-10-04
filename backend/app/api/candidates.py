from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Candidate, Hall
from app.services.reseat import submit

router = APIRouter(prefix="/candidates", tags=["candidates"])


class SideIn(BaseModel):
    side: str | None = None  # left / right / null(未标记)


@router.get("")
def list_candidates(db: Session = Depends(get_db)):
    return [{"id": r.id, "hall_id": r.hall_id, "name": r.name, "ticket_no": r.ticket_no,
             "paper_id": r.paper_id, "side": r.side}
            for r in db.scalars(select(Candidate).order_by(Candidate.id)).all()]


@router.post("/{candidate_id}/side")
def update_side(candidate_id: int, body: SideIn, db: Session = Depends(get_db)):
    cand = db.get(Candidate, candidate_id)
    if not cand:
        raise HTTPException(404, "考生不存在")
    hall = db.get(Hall, cand.hall_id)
    # 改标记即一次提交：该考生在本次提交归入且仅归入一本账；
    # 两本账与最新方案同成功或同失败，失败则标记也不保存。
    return submit(db, hall, side_updates={candidate_id: body.side})
