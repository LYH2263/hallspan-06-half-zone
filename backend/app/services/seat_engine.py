"""左右半场「两本账」排座。

左账与右账各自维护一本独立占用账：座位集按分界列 split_col 在提交排座的
瞬间切开（左账列号 [0, split_col)，右账列号 [split_col, cols)），排座、间距
检查、同卷四邻检查、人数统计都只在各自账内进行。禁止先生成一张总图再按列
涂色——这里没有总账，只有两本互不知晓的账，合账输出时才拼成同一张排座图。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

from app.models.models import SIDE_LEFT, SIDE_RIGHT

@dataclass
class SeatAssign:
    candidate_id: int
    name: str
    ticket_no: str
    paper_id: int
    row: int
    col: int
    side: str | None = None

@dataclass
class Violation:
    kind: str
    a_id: int
    b_id: int
    detail: str

def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def neighbors4(r: int, c: int, rows: int, cols: int) -> list[tuple[int, int]]:
    out = []
    for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            out.append((nr, nc))
    return out

def half_seats(rows: int, cols: int, split_col: int) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """提交瞬间按分界列切开两本账的座位集（row-major）。"""
    left, right = [], []
    for r in range(rows):
        for c in range(cols):
            (left if c < split_col else right).append((r, c))
    return left, right

def _place_half(cands: list[dict], seats: list[tuple[int, int]],
                rows: int, cols: int, min_dist: int, side: str) -> tuple[list[SeatAssign], list[dict]]:
    """在一本账内贪心排座；只读本账占用，绝不看对面账。"""
    occupied: dict[tuple[int, int], SeatAssign] = {}
    unplaced: list[dict] = []
    for cand in cands:
        placed = False
        for pos in seats:
            if pos in occupied:
                continue
            r, c = pos
            ok = True
            for opos, other in occupied.items():
                if manhattan((r, c), opos) < min_dist:
                    ok = False
                    break
                if other.paper_id == cand["paper_id"] and (r, c) in neighbors4(opos[0], opos[1], rows, cols):
                    ok = False
                    break
            if not ok:
                continue
            assign = SeatAssign(cand["id"], cand["name"], cand["ticket_no"], cand["paper_id"], r, c, side)
            occupied[pos] = assign
            placed = True
            break
        if not placed:
            unplaced.append(cand)
    return list(occupied.values()), unplaced

def place_candidates(rows: int, cols: int, min_dist: int, candidates: list[dict]) -> tuple[list[SeatAssign], list[dict]]:
    """单账兼容入口（旧测试/无半场场景）：所有列同一本账。"""
    seats = [(r, c) for r in range(rows) for c in range(cols)]
    assigns, unplaced = _place_half(candidates, seats, rows, cols, min_dist, SIDE_LEFT)
    return assigns, unplaced

class SeatingError(Exception):
    """半场排座失败；code 标识唯一原因，message 单一不并句。"""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

def run_two_books(rows: int, cols: int, split_col: int, min_dist: int,
                  candidates: list[dict]) -> dict:
    """两本账双写排座。

    每个 candidate dict 可带 side: 'left'/'right'/None。
    成功返回统一结果 dict；失败抛 SeatingError（调用方不得落方案）。
    """
    seats_left, seats_right = half_seats(rows, cols, split_col)
    cap_left, cap_right = len(seats_left), len(seats_right)

    fixed_left = [c for c in candidates if c.get("side") == SIDE_LEFT]
    fixed_right = [c for c in candidates if c.get("side") == SIDE_RIGHT]
    unmarked = [c for c in candidates if c.get("side") not in (SIDE_LEFT, SIDE_RIGHT)]
    n_lf, n_rf, n_u = len(fixed_left), len(fixed_right), len(unmarked)
    total = n_lf + n_rf + n_u

    # 1) 固定标记人数物理上超出本半场座位数 —— 只可能是座位不足。
    if n_lf > cap_left:
        raise SeatingError("half_capacity", f"左半场座位不足：固定左账 {n_lf} 人，左半场仅 {cap_left} 座")
    if n_rf > cap_right:
        raise SeatingError("half_capacity", f"右半场座位不足：固定右账 {n_rf} 人，右半场仅 {cap_right} 座")

    # 2) 为满足 |左-右|<=1，未标记考生需要归入左账的数量 k（至多两个候选）。
    target_lo, target_hi = total // 2, (total + 1) // 2
    k_options = sorted({t - n_lf for t in (target_lo, target_hi)})
    k_options = [k for k in k_options if 0 <= k <= n_u]
    if not k_options:
        d_lo = abs((n_lf) - (n_rf + n_u))
        d_hi = abs((n_lf + n_u) - n_rf)
        raise SeatingError(
            "imbalance",
            f"左右账已座人数之差最小为 {min(d_lo, d_hi)}（>1），未标记考生无法在账内消化，整场排座失败")

    # 3) 逐个均衡配额尝试两本账双写。
    saw_capacity_failure = False
    capacity_side: str | None = None
    saw_spacing_failure = False
    spacing_side: str | None = None
    for k in k_options:
        left_ids = {c["id"] for c in fixed_left} | {c["id"] for c in unmarked[:k]}
        left_cands = [c for c in candidates if c["id"] in left_ids]
        right_cands = [c for c in candidates if c["id"] not in left_ids]
        need_left, need_right = len(left_cands), len(right_cands)

        if need_left > cap_left or need_right > cap_right:
            # 均衡配额本身塞不进半场：座位不足（与间距互斥，先不跑排座）。
            saw_capacity_failure = True
            if need_left > cap_left:
                capacity_side = "左"
            elif need_right > cap_right:
                capacity_side = "右"
            continue

        la, lu = _place_half(left_cands, seats_left, rows, cols, min_dist, SIDE_LEFT)
        ra, ru = _place_half(right_cands, seats_right, rows, cols, min_dist, SIDE_RIGHT)
        if not lu and not ru:
            assigns = la + ra
            viols = find_violations(rows, cols, min_dist, assigns, split_col)
            return plan_to_dict(assigns, [], viols, rows, cols, split_col,
                                cap_left, cap_right)
        # 容量够却排不下：只可能是间距/同卷限制，绝不是座位不足。
        saw_spacing_failure = True
        if lu:
            spacing_side = "左"
        elif ru:
            spacing_side = "右"

    # 4) 所有均衡配额都失败：按唯一原因报错，不并句。
    if saw_capacity_failure and not saw_spacing_failure:
        raise SeatingError("half_capacity", f"{capacity_side}半场座位不足，无法在账内完成均衡排座")
    if saw_spacing_failure:
        raise SeatingError(
            "half_spacing",
            f"{spacing_side}半场间距不足：座位数足够但受最小曼哈顿间距 {min_dist} 与同卷四邻限制无法全部排下")
    raise SeatingError("half_capacity", f"{capacity_side}半场座位不足，无法在账内完成均衡排座")

def find_violations(rows: int, cols: int, min_dist: int, assigns: list[SeatAssign],
                    split_col: int | None = None) -> list[Violation]:
    """违规只在同一本账内检测（跨分界列两本账互不比对）。"""
    viols: list[Violation] = []
    for i, a in enumerate(assigns):
        for b in assigns[i + 1:]:
            if a.side is not None and b.side is not None and a.side != b.side:
                continue
            d = manhattan((a.row, a.col), (b.row, b.col))
            if d < min_dist:
                viols.append(Violation("distance", a.candidate_id, b.candidate_id,
                                       f"曼哈顿距离 {d} < 最小要求 {min_dist}"))
            if a.paper_id == b.paper_id and (b.row, b.col) in neighbors4(a.row, a.col, rows, cols):
                viols.append(Violation("same_paper_adjacent", a.candidate_id, b.candidate_id,
                                       f"同试卷套 {a.paper_id} 四邻相邻"))
    return viols

def plan_to_dict(assigns: list[SeatAssign], unplaced: list[dict], viols: list[Violation],
                 rows: int, cols: int, split_col: int | None = None,
                 cap_left: int | None = None, cap_right: int | None = None) -> dict:
    left = [a for a in assigns if a.side == SIDE_LEFT]
    right = [a for a in assigns if a.side == SIDE_RIGHT]
    n_left, n_right = len(left), len(right)
    return {
        "rows": rows,
        "cols": cols,
        "split_col": split_col,
        "assignments": [asdict(a) for a in assigns],
        "unplaced": unplaced,
        "violations": [asdict(v) for v in viols],
        # 排座图、左账人数、右账人数、统计同源于上面这一份 assignments。
        "stats": {
            "seated": len(assigns),
            "unplaced": len(unplaced),
            "violations": len(viols),
            "capacity": rows * cols,
            "left_seated": n_left,
            "right_seated": n_right,
            "side_diff": abs(n_left - n_right),
            "left_capacity": cap_left if cap_left is not None else (rows * (split_col or 0)),
            "right_capacity": cap_right if cap_right is not None else (rows * ((cols - split_col) if split_col is not None else 0)),
            "split_col": split_col,
        },
    }
