"""Import of the legacy OKR monitoring workbook (one sheet per unit, Objective / KR rows, R1..Rn round columns).

Two halves:
- `parse_workbook` is pure: workbook bytes -> ParsedBook (no database). It tolerates the quirks of real files:
  header text leaked into data rows, formula zeros in empty cells, Persian digits, text in number cells, #REF!.
- `apply_import` writes a ParsedBook into the active cycle through the normal services (versions + audit).
  A preview runs exactly the same code and is rolled back by the caller, so what the preview shows is what a
  commit does.
"""

from __future__ import annotations

import hashlib
import io
import re
import uuid
from dataclasses import dataclass, field
from typing import Literal

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.models import (
    Cycle,
    KeyResult,
    KRCollaborator,
    Membership,
    Objective,
    ReviewEntry,
    Role,
    StrategicGoal,
    TimePoint,
    Unit,
    UnitPlacement,
    UnitSession,
    User,
)
from app.services import cycles as cyc
from app.services import okr as okr_svc
from app.services.calc import InvalidDefinition
from app.services.orgtree import active_org_version, load_tree

Level = Literal["error", "warning", "info"]
MAX_BYTES = 10 * 1024 * 1024
MAX_COLS = 60  # the template uses ~27 columns; anything further right is not part of it

# ---- text helpers ---------------------------------------------------------------------------------
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")
_ARABIC = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "ه", "‌": " ", "‏": "", "‎": "", "\xa0": " "})


def norm(s: str) -> str:
    """Display-safe cleanup: unify Arabic/Persian letters and whitespace."""
    return re.sub(r"\s+", " ", str(s).translate(_ARABIC)).strip()


def key(s: str) -> str:
    """Matching key: normalized, lower-case, without spaces or punctuation."""
    return re.sub(r"[\s\-_.()،,]+", "", norm(s).lower())


PLACEHOLDERS = {key(x) for x in (
    "توضیحات", "خط مبنا", "هدف", "هدف کسب و کاری", "تیم‌های همکار", "شرح انتظار", "عنوان هدف", "میزان پیشرفت",
    "درصد پیشرفت", "مسئول",
)}
_NUM = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_LEADING_NUM = re.compile(r"^\s*([+-]?\d[\d,]*(?:\.\d+)?)\s*([^\d]*)$")


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def text(v) -> str | None:
    """A text cell; formula zeros, #REF! and leaked header labels count as empty."""
    if _blank(v) or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if v == 0 else (str(int(v)) if float(v).is_integer() else str(v))
    s = str(v).strip()
    if s in ("0", "0.0") or s.startswith("#") or key(s) in PLACEHOLDERS:
        return None
    return s


def number(v) -> tuple[float | None, str | None]:
    """(number, None) for numeric cells, (None, original text) for text that is not a plain number."""
    if _blank(v) or isinstance(v, bool):
        return None, None
    if isinstance(v, (int, float)):
        return float(v), None
    s = str(v).strip()
    if s.startswith("#"):
        return None, None
    t = s.translate(_DIGITS).replace("٬", "").replace(",", "")
    if _NUM.match(t):
        return float(t), None
    return None, s


# ---- parsed model ---------------------------------------------------------------------------------
@dataclass
class Issue:
    level: Level
    where: str
    message: str


@dataclass
class PRound:
    n: int
    value: float | None  # raw "میزان پیشرفت" when numeric
    percent: float | None  # raw "درصد پیشرفت"
    note: str | None
    raw_text: str | None  # text found in the value cell


@dataclass
class PKR:
    code: str
    row: int
    title: str
    description: str | None
    baseline: float | None
    target: float | None
    goal_text: str | None
    teams_text: str | None
    expectation: str | None
    rounds: list[PRound]
    extra_lines: list[str] = field(default_factory=list)  # kept in the description so nothing is lost
    issues: list[Issue] = field(default_factory=list)
    owner_text: str | None = None  # optional «مسئول» column: a user's full name or username


@dataclass
class PObjective:
    number: int
    row: int
    title: str
    krs: list[PKR]
    issues: list[Issue] = field(default_factory=list)


@dataclass
class PSheet:
    name: str
    objectives: list[PObjective]
    issues: list[Issue] = field(default_factory=list)


@dataclass
class ParsedBook:
    sheets: list[PSheet]
    ignored_sheets: list[str]
    goal_catalog: list[str]
    sha256: str


class NotAWorkbook(ValueError):
    pass


_OBJ = re.compile(r"^\s*objective\s*(\d+)\s*$", re.I)
_KR = re.compile(r"^\s*kr\s*(\d+)\s*[.\-_/]\s*(\d+)\s*$", re.I)
_ROUND = re.compile(r"^\s*R\s*(\d+)\s*$", re.I)
TEMPLATE_SHEETS = {key("الگو"), "template"}
DEFAULT_COLS = {"desc": 2, "baseline": 3, "target": 4, "goal": 5, "teams": 6, "expect": 7}
HEADERS = {key("توضیحات"): "desc", key("خط مبنا"): "baseline", key("هدف"): "target",
           key("هدف کسب و کاری"): "goal", key("تیم‌های همکار"): "teams", key("شرح انتظار"): "expect",
           # optional, not in the original template: who records this KR
           **{key(x): "owner" for x in ("مسئول", "مسئول KR", "مسئول نتیجه کلیدی", "مسئول نتیجهٔ کلیدی")}}


def _columns(row: tuple) -> tuple[dict[str, int], dict[int, int], list[tuple[str, int]]]:
    """Column positions from an Objective header row (falls back to the standard template layout).
    The first occurrence of a label wins; repeated labels (an extra "هدف کسب و کاری" column) are returned
    separately so their text is kept in the description."""
    cols, rounds, seen, dup = dict(DEFAULT_COLS), {}, set(), []
    for i, v in enumerate(row):
        if i < 2 or not isinstance(v, str):
            continue
        k = key(v)
        if k in HEADERS:
            if HEADERS[k] in seen:
                dup.append((norm(v), i))
            else:
                cols[HEADERS[k]] = i
                seen.add(HEADERS[k])
        elif m := _ROUND.match(v):
            rounds[int(m.group(1))] = i
    if not rounds:
        rounds = {n: 8 + 3 * (n - 1) for n in range(1, 7)}
    return cols, rounds, dup


def _cell(row: tuple, i: int):
    return row[i] if i < len(row) else None


def _parse_round(row: tuple, n: int, i: int) -> PRound | None:
    v_num, v_text = number(_cell(row, i))
    p_num, _ = number(_cell(row, i + 1))
    note = text(_cell(row, i + 2))
    raw = None
    if v_text:
        raw = v_text
        m = _LEADING_NUM.match(v_text.translate(_DIGITS))
        if m:  # "3000 فوت مربع" -> 3000
            v_num = float(m.group(1).replace(",", ""))
    # the percent column holds a formula zero in every untouched row: only a non-zero percent counts
    if p_num == 0:
        p_num = None
    if v_num is None and p_num is None and note is None and raw is None:
        return None
    return PRound(n, v_num, p_num, note, raw)


def _parse_kr(row: tuple, code: str, r: int, cols: dict[str, int], rounds: dict[int, int],
              dup: list[tuple[str, int]]) -> PKR | None:
    title = text(_cell(row, 1))
    where = f"KR {code}"
    if title is None:
        return None
    issues: list[Issue] = []
    extra: list[str] = []
    desc = text(_cell(row, cols["desc"]))
    if desc is not None and number(desc)[0] is not None:  # a bare number in the description is a broken formula
        issues.append(Issue("warning", where, f"توضیحاتِ عددی «{desc}» نامعتبر بود و وارد نشد"))
        desc = None
    vals = {}
    for f in ("baseline", "target"):
        n, t = number(_cell(row, cols[f]))
        if t:
            label = "خط مبنا" if f == "baseline" else "هدف"
            extra.append(f"{label} (اکسل): {t}")
            issues.append(Issue("warning", where, f"{label} عدد نبود («{t[:40]}»)؛ در توضیحات نگه داشته شد"))
        vals[f] = n
    for label, i in dup:
        if t := text(_cell(row, i)):
            extra.append(f"{label} (ستون دوم اکسل): {t}")
    rs = [p for n, i in sorted(rounds.items()) if (p := _parse_round(row, n, i))]
    owner = text(_cell(row, cols["owner"])) if "owner" in cols else None
    return PKR(code, r, norm(title), desc, vals["baseline"], vals["target"], text(_cell(row, cols["goal"])),
               text(_cell(row, cols["teams"])), text(_cell(row, cols["expect"])), rs, extra, issues,
               norm(owner) if owner else None)


def _parse_sheet(name: str, rows: list[tuple], template_titles: set[str] = frozenset()) -> PSheet | None:
    objectives: list[PObjective] = []
    issues: list[Issue] = []
    cols, rounds, dup = dict(DEFAULT_COLS), {}, []
    cur: PObjective | None = None
    seen_header = False
    for r, row in enumerate(rows, start=1):
        a = _cell(row, 0)
        if not isinstance(a, str):
            continue
        if m := _OBJ.match(a):
            seen_header = True
            cols, rounds, dup = _columns(row)
            cur = PObjective(int(m.group(1)), r, text(_cell(row, 1)) or "", [])
            objectives.append(cur)
        elif m := _KR.match(a):
            code = f"{m.group(1)}.{m.group(2)}"
            kr = _parse_kr(row, code, r, cols, rounds, dup)
            if kr is None:
                if any(text(_cell(row, i)) for i in cols.values()):
                    issues.append(Issue("warning", f"KR {code}", "سطر بدون عنوان ولی با داده؛ وارد نشد"))
                continue
            if cur is None:
                issues.append(Issue("warning", f"KR {code}", "نتیجهٔ کلیدی بیرون از هر هدف؛ وارد نشد"))
                continue
            cur.krs.append(kr)
    if not seen_header:
        return None
    kept = []
    for o in objectives:
        if not o.krs and (not o.title or key(o.title) in template_titles):
            continue  # untouched template block
        if not o.title:
            o.title = "هدف " + str(o.number).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
            o.issues.append(Issue("warning", f"هدف {o.number}", "عنوان هدف خالی بود؛ «هدف شماره» گذاشته شد"))
        else:
            o.title = norm(o.title)
        if not o.krs:
            o.issues.append(Issue("info", f"هدف {o.number}", "این هدف نتیجهٔ کلیدی ندارد"))
        kept.append(o)
    return PSheet(name, kept, issues)


def parse_workbook(data: bytes) -> ParsedBook:
    if len(data) > MAX_BYTES:
        raise NotAWorkbook("حجم فایل بیش از ۱۰ مگابایت است")
    try:
        wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        content = [(ws.title, ws.sheet_state, list(ws.iter_rows(values_only=True, max_col=MAX_COLS)))
                   for ws in wb.worksheets]
        wb.close()
    except Exception as e:  # openpyxl raises many types for non-xlsx input
        raise NotAWorkbook("فایل اکسل (xlsx) معتبر نیست") from e
    sheets, ignored, catalog = [], [], []
    # the template sheet is not a unit; its pre-filled objective titles mark untouched blocks in unit sheets
    template_titles: set[str] = set()
    for title, _, rows in content:
        if key(title) in TEMPLATE_SHEETS:
            for row in rows:
                if row and isinstance(row[0], str) and _OBJ.match(row[0]) and (t := text(_cell(row, 1))):
                    template_titles.add(key(t))
    for title, state, rows in content:
        if key(title) in TEMPLATE_SHEETS:
            ignored.append(title.strip())
            continue
        if state != "visible":
            # hidden one-column lists are the workbook's controlled vocabulary (business goals)
            vals = [norm(r[0]) for r in rows if r and isinstance(r[0], str) and r[0].strip()]
            if vals and all(len(r) == 0 or all(_blank(c) for c in r[1:]) for r in rows):
                catalog.extend(vals)
            continue
        ps = _parse_sheet(title, rows, template_titles)
        if ps is None or not ps.objectives:
            ignored.append(title.strip())
            continue
        sheets.append(ps)
    if not sheets:
        raise NotAWorkbook("در این فایل هیچ شیتی با قالب پایش OKR (سطرهای Objective و KR) پیدا نشد")
    return ParsedBook(sheets, ignored, catalog, hashlib.sha256(data).hexdigest())


# ---- apply ----------------------------------------------------------------------------------------
@dataclass
class SheetChoice:
    action: Literal["existing", "create", "skip"]
    unit_id: uuid.UUID | None = None
    name: str | None = None


@dataclass
class SheetReport:
    sheet: str
    action: str
    unit_id: uuid.UUID | None
    unit_name: str | None
    status: Literal["ready", "skipped", "already_imported", "error"]
    objectives: int = 0
    krs: int = 0
    values: int = 0
    notes: int = 0
    collaborators: int = 0
    issues: list[Issue] = field(default_factory=list)


@dataclass
class ImportReport:
    cycle: Cycle | None
    review_points: list[str]
    blocking: list[str]
    sheets: list[SheetReport]
    ignored_sheets: list[str]
    goals: list[dict]
    unmatched_goals: list[dict]
    units_created: int = 0
    goals_created: int = 0


REASON = "ایمپورت از فایل اکسل پایش"


def _ext_prefix(cycle_id: uuid.UUID, unit_id: uuid.UUID) -> str:
    return f"xl:{cycle_id.hex}:{unit_id.hex}:"


def _units(db: Session) -> tuple[list[Unit], uuid.UUID | None]:
    v = active_org_version(db)
    if v is None:
        return [], None
    tree = load_tree(db, v.id)
    units = [u for u in db.scalars(select(Unit).where(Unit.archived.is_(False))) if u.id in tree.parents]
    tops = [u for u in units if tree.parents[u.id] is None]
    return units, (tops[0].id if len(tops) == 1 else None)


def default_choice(sheet: str, units: list[Unit], root_id: uuid.UUID | None) -> SheetChoice:
    k = key(sheet)
    for u in units:
        if key(u.name) == k:
            return SheetChoice("existing", u.id)
    if k == "home" and root_id:
        return SheetChoice("existing", root_id)
    return SheetChoice("create", name=norm(sheet))


def _create_unit(db: Session, name: str, parent_id: uuid.UUID | None, actor_id) -> Unit:
    from app.routers.admin_data import _ensure_org_version  # same rule as the admin page

    v = _ensure_org_version(db)
    siblings = len(db.scalars(select(UnitPlacement).where(UnitPlacement.org_version_id == v.id,
                                                          UnitPlacement.parent_unit_id == parent_id)).all())
    u = Unit(name=name)
    db.add(u)
    db.flush()
    db.add(UnitPlacement(org_version_id=v.id, unit_id=u.id, parent_unit_id=parent_id, sort=siblings))
    db.flush()
    cyc.ensure_sessions(db, unit_id=u.id)
    audit.record(db, actor_id=actor_id, action="create", resource="unit", resource_id=u.id,
                 after={"name": name, "parent": str(parent_id) if parent_id else None, "source": "excel"})
    return u


_TEAM_SPLIT = re.compile(r"[،,؛;/\n\-–|+]+")


def _match_units(teams: str, by_key: dict[str, Unit]) -> tuple[list[Unit], list[str]]:
    whole = by_key.get(key(teams))
    if whole:
        return [whole], []
    found, rest = [], []
    for tok in (t.strip() for t in _TEAM_SPLIT.split(teams)):
        if not tok:
            continue
        k = key(tok)
        u = by_key.get(k) or max((u for kk, u in by_key.items() if len(kk) >= 3 and k.startswith(kk)),
                                 key=lambda u: len(key(u.name)), default=None)
        (found if u else rest).append(u or tok)
    return found, rest


def _entry_value(kr: PKR, kind: str, rd: PRound) -> tuple[float | None, list[Issue], str | None]:
    """Value to store for one round, plus issues and extra note text."""
    where = f"KR {kr.code} · R{rd.n}"
    issues: list[Issue] = []
    extra = None
    if rd.raw_text:
        extra = rd.raw_text
        if rd.value is None:
            issues.append(Issue("warning", where, f"مقدار متنی «{rd.raw_text[:50]}» عدد نبود؛ در یادداشت آمد"))
        else:
            issues.append(Issue("info", where, f"از «{rd.raw_text[:50]}» عدد {rd.value:g} برداشته شد"))
    if kind == "milestone":
        if rd.percent is not None:
            return rd.percent, issues, extra
        if rd.value is not None and 0 <= rd.value <= 100:
            return rd.value, issues, extra
        if rd.value is not None:
            issues.append(Issue("warning", where, "این KR عدد هدف ندارد و مقدار درصد نبود؛ فقط یادداشت ثبت شد"))
            extra = extra or f"مقدار (اکسل): {rd.value:g}"
        return None, issues, extra
    if rd.value is not None:
        return rd.value, issues, extra
    if rd.percent is not None and kr.target is not None:
        b = kr.baseline or 0.0
        return b + rd.percent / 100 * (kr.target - b), issues, extra
    return None, issues, extra


def _kind(kr: PKR) -> tuple[str, float | None, float | None, Issue | None]:
    if kr.target is not None and (kr.baseline or 0.0) != kr.target:
        return "numeric", kr.baseline if kr.baseline is not None else 0.0, kr.target, None
    msg = ("مبنا و هدف برابر بودند" if kr.target is not None else "عدد هدف نداشت")
    return "milestone", None, None, Issue("info", f"KR {kr.code}", f"{msg}؛ به‌صورت درصدی (۰ تا ۱۰۰) ثبت شد")


def _people(db: Session) -> dict[str, uuid.UUID]:
    """Active users by normalised full name and by username (a full name shared by two people matches neither)."""
    out: dict[str, uuid.UUID] = {}
    dup: set[str] = set()
    for u in db.scalars(select(User).where(User.is_active)):
        for k in {key(u.full_name), key(u.username)}:
            if k in out and out[k] != u.id:
                dup.add(k)
            out[k] = u.id
    return {k: v for k, v in out.items() if k not in dup}


def _unit_manager(db: Session, unit_id: uuid.UUID) -> uuid.UUID | None:
    """The unit manager of this unit (first by name), the default owner of imported objectives and KRs."""
    from app.defaults import UNIT_MANAGER
    return db.scalars(select(Membership.user_id).join(Role, Role.id == Membership.role_id)
                      .join(User, User.id == Membership.user_id)
                      .where(Membership.unit_id == unit_id, Role.name == UNIT_MANAGER, User.is_active)
                      .order_by(User.full_name).limit(1)).first()


def apply_import(db: Session, book: ParsedBook, *, actor_id, file_name: str,
                 mapping: dict[str, SheetChoice] | None = None) -> ImportReport:
    """Write the workbook into the active cycle. Never commits; the caller commits or rolls back."""
    mapping = mapping or {}
    cycle = db.scalars(select(Cycle).where(Cycle.status == "active")).first()
    units, root_id = _units(db)
    if cycle is None:
        sheets = [SheetReport(s.name, "skip", None, None, "error", len(s.objectives), sum(len(o.krs) for o in s.objectives))
                  for s in book.sheets]
        return ImportReport(None, [], ["دورهٔ فعالی وجود ندارد. ابتدا در «دوره و جلسه‌ها» یک دوره بسازید و فعال کنید."],
                            sheets, book.ignored_sheets, [], [])

    reviews = list(db.scalars(select(TimePoint).where(TimePoint.cycle_id == cycle.id, TimePoint.kind == "review")
                              .order_by(TimePoint.ordinal)))
    goals = {key(g.title): g for g in db.scalars(select(StrategicGoal))}
    catalog = {key(t): t for t in book.goal_catalog}
    report = ImportReport(cycle, [t.label for t in reviews], [], [], book.ignored_sheets, [], [])
    goal_use: dict[str, dict] = {}
    unmatched: dict[str, int] = {}
    people = _people(db)
    by_id = {u.id: u for u in units}
    pending_collab: list[tuple[KeyResult, Unit, PKR, SheetReport]] = []
    imported_now: set[uuid.UUID] = set()
    created_goals: set[str] = set()

    for ps in book.sheets:
        choice = mapping.get(ps.name) or default_choice(ps.name, units, root_id)
        sr = SheetReport(ps.name, choice.action, None, None, "ready",
                         issues=list(ps.issues) + [i for o in ps.objectives for i in o.issues])
        report.sheets.append(sr)
        sr.objectives = len(ps.objectives)
        sr.krs = sum(len(o.krs) for o in ps.objectives)
        if choice.action == "skip":
            sr.status = "skipped"
            continue
        if choice.action == "existing":
            unit = by_id.get(choice.unit_id) if choice.unit_id else None
            if unit is None:
                sr.status = "error"
                sr.issues.insert(0, Issue("error", "واحد", "واحد انتخاب‌شده پیدا نشد"))
                continue
            if unit.id not in imported_now and db.scalars(select(KeyResult.id).where(
                    KeyResult.external_id.like(_ext_prefix(cycle.id, unit.id) + "%")).limit(1)).first():
                sr.unit_id, sr.unit_name, sr.status = unit.id, unit.name, "already_imported"
                continue
            existing = len(db.scalars(select(Objective.id).where(Objective.cycle_id == cycle.id,
                                                                 Objective.unit_id == unit.id)).all())
            if existing:
                sr.issues.insert(0, Issue("info", "واحد", f"این واحد از قبل {existing} هدف در این دوره دارد؛ "
                                                          "اهداف اکسل کنار آن‌ها اضافه می‌شوند"))
        else:
            name = norm(choice.name or ps.name)
            if not name:
                sr.status = "error"
                sr.issues.insert(0, Issue("error", "واحد", "نام واحد جدید خالی است"))
                continue
            unit = _create_unit(db, name, root_id, actor_id)
            units.append(unit)
            by_id[unit.id] = unit
            report.units_created += 1
        imported_now.add(unit.id)
        sr.unit_id, sr.unit_name = unit.id, unit.name
        sessions = {s.time_point_id: s for s in db.scalars(select(UnitSession).where(UnitSession.unit_id == unit.id))}
        manager = _unit_manager(db, unit.id)  # default owner of every objective, and of KRs with no «مسئول»
        for po in ps.objectives:
            obj = okr_svc.create_objective(db, cycle_id=cycle.id, unit_id=unit.id, actor_id=actor_id,
                                           data={"title": po.title, "owner_id": manager}, reason=REASON)
            for pk in po.krs:
                kind, b, t, kind_issue = _kind(pk)
                if kind_issue:
                    sr.issues.append(kind_issue)
                sr.issues.extend(pk.issues)
                goal = None
                lines = list(pk.extra_lines)
                if pk.goal_text:
                    gk = key(pk.goal_text)
                    goal = goals.get(gk)
                    if goal is None and gk in catalog:
                        goal = StrategicGoal(title=catalog[gk], color_token=f"--g{len(goals) % 6}", sort=len(goals))
                        db.add(goal)
                        db.flush()
                        audit.record(db, actor_id=actor_id, action="create", resource="strategic_goal",
                                     resource_id=goal.id, after={"title": goal.title, "source": "excel"})
                        goals[gk] = goal
                        created_goals.add(goal.title)
                        report.goals_created += 1
                    if goal is None:
                        unmatched[pk.goal_text] = unmatched.get(pk.goal_text, 0) + 1
                        lines.append(f"هدف کسب‌وکار (اکسل): {pk.goal_text}")
                        sr.issues.append(Issue("warning", f"KR {pk.code}", f"«{pk.goal_text[:40]}» در فهرست اهداف "
                                                                           "کسب‌وکار نبود؛ در توضیحات نگه داشته شد"))
                    else:
                        g = goal_use.setdefault(goal.title, {"title": goal.title, "krs": 0, "action": "existing"})
                        g["krs"] += 1
                desc = "\n".join(x for x in [pk.description, *lines] if x) or None
                data = {"title": pk.title, "description": desc, "kind": kind, "baseline": b, "target": t,
                        "strategic_goal_id": goal.id if goal else None, "expectation": pk.expectation,
                        "owner_id": manager}
                if pk.owner_text:
                    who = people.get(key(pk.owner_text))
                    if who is None:
                        sr.issues.append(Issue("warning", f"KR {pk.code}", f"مسئول «{pk.owner_text[:40]}» با هیچ کاربری "
                                                                           "تطبیق نخورد؛ مسئول هدف گذاشته شد"))
                    else:
                        data["owner_id"] = who
                try:
                    kr = okr_svc.create_kr(db, objective=obj, actor_id=actor_id, data=data, reason=REASON)
                except InvalidDefinition as e:
                    sr.issues.append(Issue("error", f"KR {pk.code}", f"وارد نشد: {e}"))
                    sr.krs -= 1
                    continue
                kr.external_id = f"{_ext_prefix(cycle.id, unit.id)}{obj.number}.{kr.number}"
                if pk.teams_text:
                    pending_collab.append((kr, unit, pk, sr))
                for rd in pk.rounds:
                    value, issues, extra = _entry_value(pk, kind, rd)
                    sr.issues.extend(issues)
                    note = "\n".join(x for x in [extra, rd.note] if x) or None
                    if value is None and note is None:
                        continue
                    where = f"KR {pk.code} · R{rd.n}"
                    if rd.n > len(reviews):
                        sr.issues.append(Issue("warning", where, f"دوره پایش R{rd.n} ندارد؛ این مقدار وارد نشد"))
                        continue
                    sess = sessions.get(reviews[rd.n - 1].id)
                    if sess is None or sess.status == "held":
                        sr.issues.append(Issue("warning", where, "جلسهٔ این پایش برگزار شده و قفل است؛ وارد نشد"))
                        continue
                    db.add(ReviewEntry(key_result_id=kr.id, session_id=sess.id, value=value, note=note,
                                       updated_by=actor_id))
                    audit.record(db, actor_id=actor_id, action="set_value", resource="review_entry", resource_id=kr.id,
                                 after={"value": value, "note": note, "session": str(sess.id), "source": "excel"})
                    sr.values += value is not None
                    sr.notes += note is not None

    by_key = {key(u.name): u for u in units}
    for kr, unit, pk, sr in pending_collab:
        found, rest = _match_units(pk.teams_text or "", by_key)
        added = set()
        for u in found:
            if u.id != unit.id and u.id not in added:
                db.add(KRCollaborator(key_result_id=kr.id, unit_id=u.id))
                added.add(u.id)
        sr.collaborators += len(added)
        if rest:
            ver = okr_svc.current_kr_version(db, kr.id)
            ver.description = "\n".join(x for x in [ver.description, f"تیم‌های همکار (اکسل): {'، '.join(rest)}"] if x)
            sr.issues.append(Issue("info", f"KR {pk.code}", f"همکار «{'، '.join(rest)[:50]}» با واحدی تطبیق نخورد؛ "
                                                             "در توضیحات آمد"))
    db.flush()
    for g in goal_use.values():
        if g["title"] in created_goals:
            g["action"] = "create"
    report.goals = sorted(goal_use.values(), key=lambda g: -g["krs"])
    report.unmatched_goals = [{"text": t, "krs": n} for t, n in sorted(unmatched.items(), key=lambda x: -x[1])]
    total = {k: sum(getattr(s, k) for s in report.sheets if s.status == "ready") for k in ("objectives", "krs", "values", "notes")}
    audit.record(db, actor_id=actor_id, action="import", resource="excel", resource_id=None,
                 after={"file": file_name, "sha256": book.sha256, "cycle": str(cycle.id),
                        "units_created": report.units_created, "goals_created": report.goals_created, **total})
    return report
