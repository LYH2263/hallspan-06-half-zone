from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Hall
from app.services.reseat import submit

router = APIRouter(prefix="/halls", tags=["halls"])


class SplitIn(BaseModel):
    split_col: int


@router.get("")
def list_halls(db: Session = Depends(get_db)):
    return [{"id": r.id, "code": r.code, "name": r.name, "rows": r.rows, "cols": r.cols,
             "min_manhattan": r.min_manhattan, "split_col": r.split_col}
            for r in db.scalars(select(Hall).order_by(Hall.id)).all()]


@router.post("/{hall_id}/split")
def update_split(hall_id: int, body: SplitIn, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "考室不存在")
    # 改分界列即一次提交：两本账与最新方案同成功或同失败；越界/失败三处不动。
    return submit(db, hall, split_col=body.split_col)
