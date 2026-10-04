"""API + 事务原子性测试（sqlite）。

运行：DATABASE_URL='sqlite+pysqlite:////tmp/hs_api.db' pytest -q
"""
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.models import Candidate, Hall, PaperSet, SeatPlan

client = TestClient(app)


def setup_db(rows=5, cols=6, n=12, split_col=3, min_dist=2):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    hall = Hall(code="H1", name="一号考室", rows=rows, cols=cols,
                min_manhattan=min_dist, split_col=split_col)
    db.add(hall); db.flush()
    p = PaperSet(code="P1", title="卷"); db.add(p); db.flush()
    for i in range(n):
        db.add(Candidate(hall_id=hall.id, name=f"考生{i}", ticket_no=f"T{i}",
                         paper_id=p.id, side=None))
    db.commit()
    hid = hall.id
    db.close()
    return hid


def plan_count():
    db = SessionLocal()
    n = db.scalar(select(func.count()).select_from(SeatPlan))
    db.close(); return n


def get_hall_split():
    db = SessionLocal()
    v = db.get(Hall, 1).split_col; db.close(); return v


def candidate_side(cid):
    db = SessionLocal()
    v = db.get(Candidate, cid).side; db.close(); return v


def test_run_creates_balanced_two_books():
    setup_db()
    r = client.post("/api/seating/run", params={"hall_id": 1})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["stats"]["left_seated"] == 6
    assert data["stats"]["right_seated"] == 6
    assert data["stats"]["side_diff"] == 0
    # 左账不得出现列号 >= 3
    assert all(a["col"] < 3 for a in data["assignments"] if a["side"] == "left")
    assert all(a["col"] >= 3 for a in data["assignments"] if a["side"] == "right")
    assert plan_count() == 1


def test_split_out_of_range_rejected_three_places_untouched():
    setup_db()
    client.post("/api/seating/run", params={"hall_id": 1})  # 先有一个成功方案
    before = plan_count()
    for bad in (0, 6, 7, -1):
        r = client.post("/api/halls/1/split", json={"split_col": bad})
        assert r.status_code == 400, (bad, r.text)
        assert "越界" in r.json()["detail"]
        assert get_hall_split() == 3          # 分界列不动
        assert plan_count() == before          # 最新方案不增
    # 左右标记也不应被动到
    assert candidate_side(1) is None


def test_imbalance_failure_is_atomic_and_history_not_rewritten():
    setup_db()
    client.post("/api/seating/run", params={"hall_id": 1})  # 初始方案
    cids = [c["id"] for c in client.get("/api/candidates").json()]

    # 连续把前 6 人固定到左账都能均衡成功（6 固定左 + 6 未标记 → 6:6）。
    last_ok_id = None
    for cid in cids[:6]:
        r = client.post(f"/api/candidates/{cid}/side", json={"side": "left"})
        assert r.status_code == 200, (cid, r.text)
        assert candidate_side(cid) == "left"
        last_ok_id = r.json()["id"]

    # 第 7 人固定左账必然失衡（7:5 无未标记可补平）。
    seventh = cids[6]
    plans_before = plan_count()
    r = client.post(f"/api/candidates/{seventh}/side", json={"side": "left"})
    assert r.status_code == 422
    assert "差" in r.json()["detail"]
    assert candidate_side(seventh) is None     # 标记未保存
    assert plan_count() == plans_before        # 不增方案

    # 历史方案不回刷：latest 停在最后一次成功方案（含 6 个左账固定），
    # 既不是初始方案，也没有出现第 7 张失败方案。
    latest = client.get("/api/seating/latest", params={"hall_id": 1}).json()
    assert latest["id"] == last_ok_id
    assert latest["stats"]["left_seated"] == 6
    assert latest["stats"]["right_seated"] == 6


def test_successful_split_change_adds_new_plan_and_keeps_history():
    setup_db(rows=6, cols=6, n=12, split_col=3)  # 6x6：split=2 时左账独立集恰为 6 座
    first = client.post("/api/seating/run", params={"hall_id": 1}).json()
    r = client.post("/api/halls/1/split", json={"split_col": 2})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] != first["id"]
    assert data["split_col"] == 2
    assert get_hall_split() == 2
    # 左账容量 5x2=10；12 人均衡 6:6，左账列号均 < 2
    assert all(a["col"] < 2 for a in data["assignments"] if a["side"] == "left")
    # 历史方案仍保留且分界列快照为 3
    db = SessionLocal()
    old = db.get(SeatPlan, first["id"])
    import json
    assert json.loads(old.result_json)["split_col"] == 3
    db.close()


def test_stats_and_map_share_same_source():
    setup_db()
    run = client.post("/api/seating/run", params={"hall_id": 1}).json()
    stats = client.get("/api/seating/stats", params={"hall_id": 1}).json()
    assert stats["left_seated"] == run["stats"]["left_seated"]
    assert stats["right_seated"] == run["stats"]["right_seated"]
    assert stats["seated"] == len(run["assignments"])
