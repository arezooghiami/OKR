"""Excel export laid out like the Excel files organisations use today: one sheet per unit,
objective banner rows, KR rows with baseline / target and a value + percent pair per round.
Percent cells are live formulas whenever the round used the KR's current baseline/target;
otherwise (the definition changed since) they hold the frozen value so history is never rewritten."""

import io
import re
import uuid
from dataclasses import dataclass, field

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StrategicGoal, TimePoint, Unit, UnitSession
from app.services import okr as okr_svc
from app.services import reviews as rev
from app.services.calc import KRKind

HEAD_FILL = PatternFill("solid", fgColor="E9EEFF")
OBJ_FILL = PatternFill("solid", fgColor="F1F3F9")
THIN = Side(style="thin", color="D3D8E6")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
RIGHT = Alignment(horizontal="right", vertical="center", wrap_text=True, readingOrder=2)


@dataclass
class Cell:
    value: float | None = None
    percent: float | None = None
    same_definition: bool = True
    note: str | None = None


@dataclass
class KRLine:
    code: str
    title: str
    goal: str
    kind: str
    baseline: float | None
    target: float | None
    cells: dict[str, Cell] = field(default_factory=dict)  # round label -> Cell


@dataclass
class ObjLine:
    number: int
    title: str
    scores: dict[str, float | None]
    krs: list[KRLine]


@dataclass
class UnitData:
    unit: Unit
    rounds: list[str]
    objectives: list[ObjLine]
    scores: dict[str, float | None]
    held: dict[str, bool]


def collect_unit(db: Session, unit: Unit, cycle_id: uuid.UUID) -> UnitData:
    goals = {g.id: g.title for g in db.scalars(select(StrategicGoal))}
    sessions = db.execute(
        select(UnitSession, TimePoint).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
        .where(UnitSession.unit_id == unit.id, TimePoint.cycle_id == cycle_id, TimePoint.kind != "start")
        .order_by(TimePoint.ordinal)
    ).all()
    rounds = [tp.label for _, tp in sessions]
    objs: dict[uuid.UUID, ObjLine] = {}
    krs: dict[uuid.UUID, KRLine] = {}
    scores: dict[str, float | None] = {}
    held: dict[str, bool] = {}
    for s, tp in sessions:
        held[tp.label] = s.status == "held"
        blocks = rev.build_session(db, s) if s.status != "unscheduled" else []
        scores[tp.label] = rev.unit_score(blocks) if s.status == "held" else None
        for b in blocks:
            o = objs.setdefault(b.objective.id, ObjLine(b.objective.number, b.version.title, {}, []))
            o.title = b.version.title
            o.scores[tp.label] = b.score if s.status == "held" else None
            for r in b.rows:
                cur = okr_svc.current_kr_version(db, r.kr.id)
                line = krs.get(r.kr.id)
                if line is None:
                    line = krs[r.kr.id] = KRLine(f"{b.objective.number}.{r.kr.number}", cur.title,
                                                 goals.get(cur.strategic_goal_id, ""), cur.kind, cur.baseline, cur.target)
                    o.krs.append(line)
                same = (r.version.baseline, r.version.target, r.version.kind) == (cur.baseline, cur.target, cur.kind)
                line.cells[tp.label] = Cell(r.entry.value if r.entry else None, r.percent, same, r.entry.note if r.entry else None)
    ordered = sorted(objs.values(), key=lambda o: o.number)
    return UnitData(unit, rounds, ordered, scores, held)


def _safe_sheet_name(name: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", " ", name).strip()[:28] or "unit"
    out, i = base, 2
    while out in used:
        out, i = f"{base} {i}", i + 1
    used.add(out)
    return out


def write_unit_sheet(ws: Worksheet, d: UnitData, cycle_name: str) -> None:
    ws.sheet_view.rightToLeft = True
    n_rounds = len(d.rounds)
    last_col = 5 + 2 * n_rounds + 1
    ws.cell(1, 1, f"{d.unit.name} · {cycle_name}").font = Font(bold=True, size=14)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    heads = ["ردیف", "نتیجه کلیدی", "هدف کسب‌وکاری", "مبنا", "هدف"]
    for r in d.rounds:
        heads += [f"{r} · مقدار", f"{r} · درصد"]
    heads.append("توضیحات آخرین پایش")
    for c, h in enumerate(heads, 1):
        cell = ws.cell(3, c, h)
        cell.font, cell.fill, cell.alignment, cell.border = Font(bold=True), HEAD_FILL, CENTER, BORDER
    row = 4
    for o in d.objectives:
        ws.cell(row, 1, f"هدف {o.number}")
        ws.cell(row, 2, o.title)
        for i, r in enumerate(d.rounds):
            sc = o.scores.get(r)
            c = ws.cell(row, 6 + 2 * i + 1, None if sc is None else sc / 100)
            c.number_format = "0%"
        for c in range(1, last_col + 1):
            ws.cell(row, c).fill, ws.cell(row, c).font, ws.cell(row, c).border = OBJ_FILL, Font(bold=True), BORDER
        row += 1
        for k in o.krs:
            ws.cell(row, 1, k.code)
            ws.cell(row, 2, k.title).alignment = RIGHT
            ws.cell(row, 3, k.goal).alignment = RIGHT
            ws.cell(row, 4, k.baseline)
            ws.cell(row, 5, k.target)
            last_note = None
            for i, r in enumerate(d.rounds):
                vc, pc = 6 + 2 * i, 6 + 2 * i + 1
                cell = k.cells.get(r)
                if cell is None:
                    continue
                if cell.value is not None:
                    ws.cell(row, vc, cell.value)
                vref = f"{get_column_letter(vc)}{row}"
                if cell.value is not None and k.kind == KRKind.NUMERIC and cell.same_definition:
                    ws.cell(row, pc, f'=IF(ISNUMBER({vref}),MAX(0,MIN(1,({vref}-$D{row})/($E{row}-$D{row}))),"")')
                elif cell.percent is not None:
                    ws.cell(row, pc, cell.percent / 100)  # frozen under an earlier definition (or non-numeric KR)
                ws.cell(row, pc).number_format = "0%"
                if cell.note:
                    last_note = cell.note
            ws.cell(row, last_col, last_note).alignment = RIGHT
            for c in range(1, last_col + 1):
                ws.cell(row, c).border = BORDER
                if c not in (2, 3, last_col):
                    ws.cell(row, c).alignment = CENTER
            row += 1
    total = row + 1
    ws.cell(total, 2, "امتیاز واحد").font = Font(bold=True)
    for i, r in enumerate(d.rounds):
        sc = d.scores.get(r)
        c = ws.cell(total, 6 + 2 * i + 1, None if sc is None else sc / 100)
        c.number_format, c.font = "0%", Font(bold=True)
    ws.column_dimensions["A"].width = 9
    ws.column_dimensions["B"].width = 46
    ws.column_dimensions["C"].width = 30
    for c in range(4, last_col):
        ws.column_dimensions[get_column_letter(c)].width = 11
    ws.column_dimensions[get_column_letter(last_col)].width = 36
    ws.freeze_panes = "C4"


def build_workbook(db: Session, cycle_name: str, cycle_id: uuid.UUID, units: list[Unit], summary: bool) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    data = [collect_unit(db, u, cycle_id) for u in units]
    used: set[str] = set()
    if summary:
        ws = wb.create_sheet(_safe_sheet_name("خلاصه", used))
        ws.sheet_view.rightToLeft = True
        rounds = max((d.rounds for d in data), key=len, default=[])
        ws.cell(1, 1, f"خلاصهٔ امتیاز واحدها · {cycle_name}").font = Font(bold=True, size=14)
        for c, h in enumerate(["واحد", *rounds], 1):
            cell = ws.cell(3, c, h)
            cell.font, cell.fill, cell.alignment, cell.border = Font(bold=True), HEAD_FILL, CENTER, BORDER
        for r, d in enumerate(sorted(data, key=lambda x: x.unit.name), 4):
            ws.cell(r, 1, d.unit.name).border = BORDER
            for c, label in enumerate(rounds, 2):
                sc = d.scores.get(label)
                cell = ws.cell(r, c, None if sc is None else sc / 100)
                cell.number_format, cell.alignment, cell.border = "0%", CENTER, BORDER
        ws.column_dimensions["A"].width = 28
    for d in data:
        write_unit_sheet(wb.create_sheet(_safe_sheet_name(d.unit.name, used)), d, cycle_name)
    if not wb.sheetnames:
        wb.create_sheet("خالی")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
