from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

# 左右半场标记：None = 未标记（提交排座时归入且仅归入一本账）
SIDE_LEFT = "left"
SIDE_RIGHT = "right"
SIDES = (SIDE_LEFT, SIDE_RIGHT)

class Hall(Base):
    __tablename__ = "halls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    rows: Mapped[int] = mapped_column(Integer)
    cols: Mapped[int] = mapped_column(Integer)
    min_manhattan: Mapped[int] = mapped_column(Integer, default=2)
    # 分界列：左账列号 [0, split_col)，右账列号 [split_col, cols)
    split_col: Mapped[int] = mapped_column(Integer, default=3)

class PaperSet(Base):
    __tablename__ = "paper_sets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(128))

class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    name: Mapped[str] = mapped_column(String(64))
    ticket_no: Mapped[str] = mapped_column(String(32))
    paper_id: Mapped[int] = mapped_column(ForeignKey("paper_sets.id"))
    # 左右半场标记，None/NULL 表示未标记
    side: Mapped[str | None] = mapped_column(String(8), nullable=True, default=None)

class SeatPlan(Base):
    __tablename__ = "seat_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
