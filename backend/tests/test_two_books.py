"""两本账排座引擎测试（纯函数，不连库）。"""
import pytest

from app.models.models import SIDE_LEFT, SIDE_RIGHT
from app.services.seat_engine import (
    SeatingError, find_violations, half_seats, run_two_books, SeatAssign,
)


def cands(n, sides=None, papers=None):
    sides = sides or {}
    papers = papers or {}
    return [{"id": i + 1, "name": f"C{i}", "ticket_no": f"T{i}",
             "paper_id": papers.get(i + 1, 1 + (i % 3)),
             "side": sides.get(i + 1)} for i in range(n)]


def assigns_of(result):
    return result["assignments"]  # list[dict]，plan_to_dict 统一来源


def book_ids(result):
    left = {a["candidate_id"] for a in assigns_of(result) if a["side"] == SIDE_LEFT}
    right = {a["candidate_id"] for a in assigns_of(result) if a["side"] == SIDE_RIGHT}
    return left, right


def test_seed_split3_left_book_has_no_col_ge_3():
    # 种子场景：5x6，分界列 3，12 名未标记考生。
    result = run_two_books(5, 6, 3, 2, cands(12))
    for a in assigns_of(result):
        if a["side"] == SIDE_LEFT:
            assert a["col"] < 3, f"左账出现列号 {a['col']} >= 3"
        else:
            assert a["col"] >= 3


def test_unmarked_each_goes_to_exactly_one_book():
    result = run_two_books(5, 6, 3, 2, cands(12))
    left, right = book_ids(result)
    assert not (left & right)                       # 不能同时记进两本账
    assert left | right == set(range(1, 13))        # 也不能漏
    assert abs(len(left) - len(right)) <= 1


def test_fixed_markers_never_cross_books():
    sides = {1: SIDE_LEFT, 2: SIDE_LEFT, 11: SIDE_RIGHT, 12: SIDE_RIGHT}
    result = run_two_books(5, 6, 3, 2, cands(12, sides))
    by_id = {a["candidate_id"]: a for a in assigns_of(result)}
    for cid in (1, 2):
        assert by_id[cid]["side"] == SIDE_LEFT and by_id[cid]["col"] < 3
    for cid in (11, 12):
        assert by_id[cid]["side"] == SIDE_RIGHT and by_id[cid]["col"] >= 3


def test_diff_gt_1_without_unmarked_fails():
    # 4 人全固定左账，无未标记：只能是 4:0，差 4 > 1 → 整场失败。
    with pytest.raises(SeatingError) as ei:
        run_two_books(5, 6, 3, 2,
                      cands(4, {1: SIDE_LEFT, 2: SIDE_LEFT, 3: SIDE_LEFT, 4: SIDE_LEFT}))
    assert ei.value.code == "imbalance"


def test_diff_gt_1_unmarked_still_cannot_digest_fails():
    # 3 固定左 + 1 未标记：未标记归右仍是 3:1，差 2，账内无法消化。
    with pytest.raises(SeatingError) as ei:
        run_two_books(5, 6, 3, 2, cands(4, {1: SIDE_LEFT, 2: SIDE_LEFT, 3: SIDE_LEFT}))
    assert ei.value.code == "imbalance"
    assert "无法在账内消化" in ei.value.message


def test_balanced_with_unmarked_succeeds():
    # 2 固定左 + 1 固定右 + 1 未标记：未标记归右 → 2:2 成功。
    result = run_two_books(5, 6, 3, 2,
                           cands(4, {1: SIDE_LEFT, 2: SIDE_LEFT, 3: SIDE_RIGHT}))
    left, right = book_ids(result)
    assert (left, right) == ({1, 2}, {3, 4})


def test_half_capacity_message_only_capacity():
    # 5x6 分界列 1：左账 5 座，均衡 6:6 时左账塞不下。
    with pytest.raises(SeatingError) as ei:
        run_two_books(5, 6, 1, 2, cands(12))
    assert ei.value.code == "half_capacity"
    assert "半场座位不足" in ei.value.message
    assert "间距" not in ei.value.message          # 不得与间距不足并句


def test_half_spacing_message_only_spacing():
    # 1x6 分界列 3，最小间距 2：每半场物理 3 座，但间距限制最多坐 2 人；
    # 6 人均衡 3:3 → 容量够、间距排不下。
    with pytest.raises(SeatingError) as ei:
        run_two_books(1, 6, 3, 2, cands(6))
    assert ei.value.code == "half_spacing"
    assert "半场间距不足" in ei.value.message
    assert "座位不足" not in ei.value.message       # 容量明明够，不得报座位不足


def test_spacing_success_when_balanced_fits():
    # 同一场景 4 人均衡 2:2，半场 2 人可放在列 0/2 → 成功。
    result = run_two_books(1, 6, 3, 2, cands(4))
    assert len(assigns_of(result)) == 4


def test_stats_share_one_source_with_assignments():
    result = run_two_books(5, 6, 3, 2, cands(12))
    st = result["stats"]
    left, right = book_ids(result)
    assert st["left_seated"] == len(left) == 6
    assert st["right_seated"] == len(right) == 6
    assert st["side_diff"] == 0
    assert st["seated"] == st["left_seated"] + st["right_seated"]
    assert st["split_col"] == 3


def test_violations_not_compared_across_books():
    # 跨分界列四邻（左账最右列、右账最左列）同卷：不比对，无违规。
    across = [
        SeatAssign(1, "A", "T1", 1, 0, 2, SIDE_LEFT),
        SeatAssign(2, "B", "T2", 1, 0, 3, SIDE_RIGHT),
    ]
    assert find_violations(1, 6, 2, across, 3) == []
    # 同账内相邻同卷：必须报。
    within = [
        SeatAssign(1, "A", "T1", 1, 0, 1, SIDE_LEFT),
        SeatAssign(2, "B", "T2", 1, 0, 2, SIDE_LEFT),
    ]
    kinds = {v.kind for v in find_violations(1, 6, 2, within, 3)}
    assert kinds == {"distance", "same_paper_adjacent"}


def test_half_seats_split():
    left, right = half_seats(2, 4, 3)
    assert all(c < 3 for _, c in left)
    assert all(c >= 3 for _, c in right)
    assert len(left) == 6 and len(right) == 2
