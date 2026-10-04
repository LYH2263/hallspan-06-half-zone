"""排座提交：两本账与配置（分界列、左右标记）、最新方案在同一事务内同成功或同失败。

失败时 db.rollback() 同时撤销：Hall.split_col 的暂存改动、Candidate.side 的
暂存改动，且不写入任何 SeatPlan —— 即「分界列、左右标记、最新方案」三处不动。
成功时只追加新方案，历史方案永不回刷。
"""
from __future__ import annotations
import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Candidate, Hall, SIDES, SeatPlan
from app.services.seat_engine import SeatingError, run_two_books


def validate_split(cols: int, split_col: int) -> None:
    if not isinstance(split_col, int) or not (1 <= split_col <= cols - 1):
        raise HTTPException(
            status_code=400,
            detail=f"分界列越界：分界列必须在 1 到 {cols - 1} 之间，已拒绝保存，"
                   f"分界列、左右标记、最新方案三处不动",
        )


def _candidate_dicts(cands: list[Candidate]) -> list[dict]:
    return [
        {"id": c.id, "name": c.name, "ticket_no": c.ticket_no,
         "paper_id": c.paper_id, "side": c.side}
        for c in cands
    ]


def empty_result(hall: Hall) -> dict:
    cap_left = hall.rows * hall.split_col
    cap_right = hall.rows * (hall.cols - hall.split_col)
    return {
        "id": None,
        "rows": hall.rows,
        "cols": hall.cols,
        "split_col": hall.split_col,
        "assignments": [],
        "unplaced": [],
        "violations": [],
        "stats": {
            "seated": 0, "unplaced": 0, "violations": 0,
            "capacity": hall.rows * hall.cols,
            "left_seated": 0, "right_seated": 0, "side_diff": 0,
            "left_capacity": cap_left, "right_capacity": cap_right,
            "split_col": hall.split_col,
        },
        "hall": {"id": hall.id, "name": hall.name, "min_manhattan": hall.min_manhattan},
    }


def submit(db: Session, hall: Hall, *, split_col: int | None = None,
           side_updates: dict[int, str | None] | None = None) -> dict:
    """原子提交：暂存配置改动 → 两本账双写 → 同提交；失败整体回滚。"""
    new_split = split_col if split_col is not None else hall.split_col
    validate_split(hall.cols, new_split)

    cands = list(db.scalars(select(Candidate).where(Candidate.hall_id == hall.id)).all())
    cmap = {c.id: c for c in cands}
    for cid, side in (side_updates or {}).items():
        if cid not in cmap:
            raise HTTPException(404, "考生不存在")
        if side is not None and side not in SIDES:
            raise HTTPException(400, "左右标记只能是 left、right 或空（未标记）")

    # 暂存（尚未 flush/commit）；引擎失败时随 rollback 一起还原。
    hall.split_col = new_split
    for cid, side in (side_updates or {}).items():
        cmap[cid].side = side

    try:
        result = run_two_books(hall.rows, hall.cols, hall.split_col,
                               hall.min_manhattan, _candidate_dicts(cands))
    except SeatingError as exc:
        db.rollback()  # 分界列、左右标记、最新方案三处不动
        raise HTTPException(status_code=422, detail=exc.message)

    result["hall"] = {"id": hall.id, "name": hall.name, "min_manhattan": hall.min_manhattan}
    plan = SeatPlan(hall_id=hall.id, created_at=datetime.utcnow(),
                    result_json=json.dumps(result, ensure_ascii=False))
    db.add(plan)
    db.commit()  # 配置与最新方案同成功
    db.refresh(plan)
    return {"id": plan.id, **result}
