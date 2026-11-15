"""Excel import of the organisation: a «واحدها» sheet (unit tree) and a «کاربران» sheet (users, roles, units).

The template is the current organisation itself, so the administrator can download it, edit and re-import it:
rows that match what is already there change nothing. Nothing is ever deleted by an import.
Units are matched by name, users by username. A user may appear on several rows (one role per row)."""

import io
import re
import secrets
import uuid
from dataclasses import dataclass, field

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.security import hash_password
from app.models import Membership, Role, Unit, UnitPlacement, UnitType, User
from app.services import cycles as cyc
from app.services.excel_import import MAX_BYTES, NotAWorkbook, key, norm
from app.services.orgtree import active_org_version, load_tree

USERNAME = re.compile(r"^[A-Za-z0-9_.@-]{3,60}$")
UNITS_SHEET, USERS_SHEET, HELP_SHEET = "واحدها", "کاربران", "راهنما"
UNIT_COLS = {"name": "نام واحد", "parent": "واحد بالادستی", "type": "نوع واحد", "code": "کد", "manager": "مدیر واحد"}
USER_COLS = {"username": "نام کاربری", "full_name": "نام و نام خانوادگی", "email": "ایمیل", "password": "رمز اولیه",
             "role": "نقش", "unit": "واحد"}
_ALIASES = {"name": ["نام", "واحد"], "parent": ["بالادستی", "واحد والد", "والد"], "type": ["نوع"],
            "manager": ["مدیر", "نام مدیر"], "username": ["یوزرنیم", "username", "user"],
            "full_name": ["نام کامل", "نام و نام‌خانوادگی", "نام"], "password": ["رمز", "رمز عبور", "password"],
            "email": ["email", "پست الکترونیک"], "unit": ["نام واحد"]}


# ---- result -----------------------------------------------------------------------------------------
@dataclass
class Row:
    row: int
    name: str  # unit name, or username
    status: str = "same"  # new | update | same | error
    detail: str | None = None  # what changes, e.g. "زیر «فنی» · نوع: اداره"
    message: str | None = None  # why it is an error, or a warning
    full_name: str | None = None
    role: str | None = None
    unit: str | None = None


@dataclass
class Credential:
    username: str
    full_name: str
    password: str


@dataclass
class OrgReport:
    units: list[Row] = field(default_factory=list)
    users: list[Row] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)
    credentials: list[Credential] = field(default_factory=list)
    types_created: list[str] = field(default_factory=list)


# ---- parsing ----------------------------------------------------------------------------------------
def _cell(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = norm(str(v))
    return s or None


def _header_map(header: tuple, cols: dict[str, str]) -> dict[str, int]:
    keys = [key(h) if h is not None else "" for h in header]
    out: dict[str, int] = {}
    for f, label in cols.items():  # exact labels first, then aliases, so «نام واحد» never steals «نام»
        if key(label) in keys:
            out[f] = keys.index(key(label))
    for f, aliases in _ALIASES.items():
        if f in cols and f not in out:
            for a in aliases:
                if key(a) in keys and keys.index(key(a)) not in out.values():
                    out[f] = keys.index(key(a))
                    break
    return out


def _rows(ws, cols: dict[str, str], required: str) -> tuple[list[tuple[int, dict]], str | None]:
    it = ws.iter_rows(values_only=True)
    for i, header in enumerate(it, start=1):  # the header is the first row that names the required column
        m = _header_map(header, cols)
        if required in m:
            break
        if i >= 5:
            return [], f"ستون «{cols[required]}» در شیت «{ws.title}» پیدا نشد"
    else:
        return [], None
    out = []
    for r, values in enumerate(it, start=i + 1):
        d = {f: _cell(values[c]) if c < len(values) else None for f, c in m.items()}
        if any(d.values()):
            out.append((r, d))
    return out, None


def parse(data: bytes) -> tuple[list, list, list[str]]:
    """(unit rows, user rows, blocking problems) — each row is (excel row number, {field: text})."""
    if len(data) > MAX_BYTES:
        raise NotAWorkbook("حجم فایل بیش از ۱۰ مگابایت است")
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001 - any parse failure means "not an xlsx we can read"
        raise NotAWorkbook("فایل xlsx معتبر نیست") from e
    sheets = {key(ws.title): ws for ws in wb.worksheets}
    units_ws = sheets.get(key(UNITS_SHEET)) or next((ws for k, ws in sheets.items() if "واحد" in k), None)
    users_ws = sheets.get(key(USERS_SHEET)) or next((ws for k, ws in sheets.items() if "کاربر" in k), None)
    blocking: list[str] = []
    units, users = [], []
    if units_ws is not None:
        units, err = _rows(units_ws, UNIT_COLS, "name")
        blocking += [err] if err else []
    if users_ws is not None:
        users, err = _rows(users_ws, USER_COLS, "username")
        blocking += [err] if err else []
    if units_ws is None and users_ws is None:
        blocking.append(f"شیت «{UNITS_SHEET}» یا «{USERS_SHEET}» در فایل نیست. فایل نمونه را از همین صفحه بگیرید.")
    wb.close()
    return units, users, blocking


# ---- apply ------------------------------------------------------------------------------------------
def _ensure_version(db: Session):
    from app.routers.admin_data import _ensure_org_version  # same rule as the admin page

    return _ensure_org_version(db)


def _apply_units(db: Session, rows: list, actor_id: uuid.UUID, rep: OrgReport) -> dict[str, Unit]:
    """Creates/updates units; returns every live unit by name key (for the users sheet)."""
    v = _ensure_version(db)
    tree = load_tree(db, v.id)
    placed = {p.unit_id: p for p in db.scalars(select(UnitPlacement).where(UnitPlacement.org_version_id == v.id))}
    all_units = [u for u in db.scalars(select(Unit)) if u.id in placed]
    by_key = {key(u.name): u for u in all_units if not u.archived}
    archived = {key(u.name) for u in all_units if u.archived}
    types = {key(t.name): t for t in db.scalars(select(UnitType))}
    roots = [u for u in by_key.values() if tree.parents.get(u.id) is None]

    seen: set[str] = set()
    pending: list[tuple[Row, dict]] = []
    for r, d in rows:
        name = d.get("name")
        row = Row(row=r, name=name or "")
        rep.units.append(row)
        if not name:
            row.status, row.message = "error", "نام واحد خالی است"
            continue
        k = key(name)
        if k in seen:
            row.status, row.message = "error", "این واحد در فایل تکرار شده است"
            continue
        if k in archived and k not in by_key:
            row.status, row.message = "error", "واحدی با این نام آرشیو شده است؛ اول آن را از آرشیو درآورید"
            continue
        seen.add(k)
        pending.append((row, d))

    sheet_keys = {key(d["name"]) for _, d in pending}
    progress = True
    while pending and progress:  # parents may come after their children in the sheet
        progress = False
        for row, d in list(pending):
            pk = key(d["parent"]) if d.get("parent") else None
            if pk is not None and pk not in by_key:
                if pk in sheet_keys and pk != key(d["name"]):
                    continue  # the parent is created later in this pass
                row.status, row.message = "error", f"واحد بالادستی «{d['parent']}» نه در سامانه هست نه در این فایل"
                pending.remove((row, d))
                progress = True
                continue
            _apply_unit(db, v, tree, placed, by_key, types, roots, row, d, pk, actor_id, rep)
            pending.remove((row, d))
            progress = True
    for row, d in pending:
        row.status, row.message = "error", "واحد بالادستی حلقه می‌سازد (دو واحد بالادستی یکدیگرند)"
    return by_key


def _apply_unit(db, v, tree, placed, by_key, types, roots, row: Row, d: dict, pk, actor_id, rep: OrgReport) -> None:
    name, k = d["name"], key(d["name"])
    parent = by_key[pk] if pk else None
    if parent is None and pk is None and roots and key(roots[0].name) != k:
        parent = roots[0]  # no parent given: directly under the organisation's root
    type_id = None
    if d.get("type"):
        t = types.get(key(d["type"]))
        if t is None:
            t = UnitType(name=d["type"], sort=len(types))
            db.add(t)
            db.flush()
            types[key(t.name)] = t
            rep.types_created.append(t.name)
        type_id = t.id
    u = by_key.get(k)
    if u is None:
        u = Unit(name=name, code=d.get("code"), type_id=type_id, manager_name=d.get("manager"))
        db.add(u)
        db.flush()
        pid = parent.id if parent else None
        siblings = sum(1 for p in placed.values() if p.parent_unit_id == pid)
        placed[u.id] = UnitPlacement(org_version_id=v.id, unit_id=u.id, parent_unit_id=pid, sort=siblings)
        db.add(placed[u.id])
        db.flush()
        tree.parents[u.id] = pid
        cyc.ensure_sessions(db, unit_id=u.id)
        audit.record(db, actor_id=actor_id, action="create", resource="unit", resource_id=u.id,
                     after={"name": name, "parent": str(pid) if pid else None, "source": "excel"})
        by_key[k] = u
        if pid is None:
            roots.append(u)
        row.status = "new"
        row.detail = f"زیر «{parent.name}»" if parent else "ریشهٔ سازمان"
        return
    changes = []
    if pk is not None and parent is not None and tree.parents.get(u.id) != parent.id:
        if parent.id == u.id or tree.is_descendant(parent.id, u.id):
            row.status, row.message = "error", "واحد را نمی‌شود زیر خودش یا زیرمجموعه‌اش برد"
            return
        placed[u.id].parent_unit_id = parent.id
        tree.parents[u.id] = parent.id
        changes.append(f"انتقال زیر «{parent.name}»")
    if d.get("code") and d["code"] != u.code:
        u.code = d["code"]
        changes.append(f"کد: {u.code}")
    if type_id and type_id != u.type_id:
        u.type_id = type_id
        changes.append(f"نوع: {d['type']}")
    if d.get("manager") and d["manager"] != u.manager_name:
        u.manager_name = d["manager"]
        changes.append(f"مدیر: {u.manager_name}")
    if changes:
        audit.record(db, actor_id=actor_id, action="update", resource="unit", resource_id=u.id,
                     after={"changes": changes, "source": "excel"})
        row.status, row.detail = "update", " · ".join(changes)


def _apply_users(db: Session, rows: list, units: dict[str, Unit], actor_id: uuid.UUID, rep: OrgReport,
                 unit_errors: set[str]) -> None:
    roles = {key(r.name): r for r in db.scalars(select(Role))}
    users = {u.username.lower(): u for u in db.scalars(select(User))}
    created: set[str] = set()
    for r, d in rows:
        username = (d.get("username") or "").strip()
        row = Row(row=r, name=username, full_name=d.get("full_name"), role=d.get("role"), unit=d.get("unit"))
        rep.users.append(row)
        if not username or (username.lower() not in users and not USERNAME.match(username)):  # rule is for new accounts
            row.status = "error"
            row.message = "نام کاربری خالی است" if not username else "نام کاربری باید ۳ تا ۶۰ نویسهٔ انگلیسی، عدد یا . _ - @ باشد"
            continue
        role = roles.get(key(d["role"])) if d.get("role") else None
        if d.get("role") and role is None:
            row.status, row.message = "error", f"نقش «{d['role']}» تعریف نشده است"
            continue
        unit = units.get(key(d["unit"])) if d.get("unit") else None
        if d.get("unit") and unit is None:
            row.status = "error"
            row.message = (f"واحد «{d['unit']}» در شیت واحدها خطا دارد" if key(d["unit"]) in unit_errors
                           else f"واحد «{d['unit']}» پیدا نشد")
            continue
        if unit is not None and role is None:
            row.status, row.message = "error", "برای این واحد نقش را هم بنویسید"
            continue
        u = users.get(username.lower())
        changes: list[str] = []
        if u is None:
            if not d.get("full_name"):
                row.status, row.message = "error", "نام و نام خانوادگی کاربر جدید خالی است"
                continue
            pwd = d.get("password")
            if pwd and len(pwd) < 8:
                row.status, row.message = "error", "رمز اولیه باید دست‌کم ۸ نویسه باشد"
                continue
            generated = not pwd
            pwd = pwd or secrets.token_urlsafe(9)
            u = User(username=username, full_name=d["full_name"], email=d.get("email"), password_hash=hash_password(pwd))
            db.add(u)
            db.flush()
            audit.record(db, actor_id=actor_id, action="create", resource="user", resource_id=u.id,
                         after={"username": username, "source": "excel"})
            users[username.lower()] = u
            created.add(username.lower())
            if generated:
                rep.credentials.append(Credential(username, u.full_name, pwd))
            row.status = "new"
        else:
            if username.lower() not in created:
                if d.get("full_name") and d["full_name"] != u.full_name:
                    u.full_name = d["full_name"]
                    changes.append("نام")
                if d.get("email") and d["email"] != u.email:
                    u.email = d["email"]
                    changes.append("ایمیل")
                if d.get("password"):
                    row.message = "رمز کاربر موجود از راه اکسل عوض نمی‌شود"
                if not u.is_active:
                    row.message = "این کاربر غیرفعال است؛ از پنل کاربران فعالش کنید"
            row.full_name = row.full_name or u.full_name
        if role is not None:
            unit_id = unit.id if unit else None
            has = db.scalars(select(Membership).where(Membership.user_id == u.id, Membership.role_id == role.id,
                                                      Membership.unit_id.is_(None) if unit_id is None
                                                      else Membership.unit_id == unit_id)).first()
            if has is None:
                db.add(Membership(user_id=u.id, role_id=role.id, unit_id=unit_id))
                db.flush()
                audit.record(db, actor_id=actor_id, action="grant_role", resource="user", resource_id=u.id,
                             after={"role": str(role.id), "unit": str(unit_id) if unit_id else None, "source": "excel"})
                changes.append(f"نقش «{role.name}» در {('«' + unit.name + '»') if unit else 'کل سازمان'}")
            if unit is None and not row.message:
                row.message = "بدون واحد: این نقش در کل سازمان اعمال می‌شود"
        if changes and row.status != "new":
            audit.record(db, actor_id=actor_id, action="update", resource="user", resource_id=u.id,
                         after={"changed": changes, "source": "excel"})
            row.status = "update"
        if changes:
            row.detail = " · ".join(changes)


def apply(db: Session, data: bytes, actor_id: uuid.UUID) -> OrgReport:
    units, users, blocking = parse(data)
    rep = OrgReport(blocking=blocking)
    if blocking:
        return rep
    by_key = _apply_units(db, units, actor_id, rep) if units else _live_units(db)
    unit_errors = {key(r.name) for r in rep.units if r.status == "error" and r.name}
    if users:
        _apply_users(db, users, by_key, actor_id, rep, unit_errors)
    return rep


def _live_units(db: Session) -> dict[str, Unit]:
    v = active_org_version(db)
    tree = load_tree(db, v.id if v else None)
    return {key(u.name): u for u in db.scalars(select(Unit).where(Unit.archived.is_(False))) if u.id in tree.parents}


# ---- template = the current organisation -----------------------------------------------------------
HEAD_FILL = PatternFill("solid", fgColor="F3E7E0")


def _sheet(wb: Workbook, title: str, headers: list[str], widths: list[int], rows: list[list]):
    ws = wb.create_sheet(title)
    ws.sheet_view.rightToLeft = True
    ws.append(headers)
    for c in ws[1]:
        c.font, c.fill, c.alignment = Font(bold=True), HEAD_FILL, Alignment(horizontal="center")
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
    ws.freeze_panes = "A2"
    for r in rows:
        ws.append(r)
    return ws


def template(db: Session) -> bytes:
    v = active_org_version(db)
    tree = load_tree(db, v.id if v else None)
    units = {u.id: u for u in db.scalars(select(Unit).where(Unit.archived.is_(False))) if u.id in tree.parents}
    types = {t.id: t.name for t in db.scalars(select(UnitType))}
    roles = db.scalars(select(Role).order_by(Role.name)).all()
    role_name = {r.id: r.name for r in roles}

    def depth(uid):
        n, cur = 0, tree.parents.get(uid)
        while cur is not None and n < 50:
            n, cur = n + 1, tree.parents.get(cur)
        return n

    order = sorted(units.values(), key=lambda u: (depth(u.id), u.name))
    wb = Workbook()
    wb.remove(wb.active)
    _sheet(wb, UNITS_SHEET, list(UNIT_COLS.values()), [32, 32, 18, 12, 26], [
        [u.name, units[tree.parents[u.id]].name if tree.parents.get(u.id) in units else None,
         types.get(u.type_id), u.code, u.manager_name] for u in order])
    rows = []
    for u in db.scalars(select(User).where(User.is_active).order_by(User.full_name)):
        ms = db.scalars(select(Membership).where(Membership.user_id == u.id)).all()
        for m in ms or [None]:
            rows.append([u.username, u.full_name, u.email, None, role_name.get(m.role_id) if m else None,
                         units[m.unit_id].name if m and m.unit_id in units else None])
    _sheet(wb, USERS_SHEET, list(USER_COLS.values()), [20, 28, 28, 16, 18, 30], rows)
    help_rows = [
        ["این فایل همان سازمان فعلی است. ردیف اضافه یا ویرایش کنید و در همان صفحه وارد کنید.", None],
        ["چیزی حذف نمی‌شود؛ برای حذف یا آرشیو از پنل مدیریت استفاده کنید.", None],
        [None, None],
        [f"شیت «{UNITS_SHEET}»", "واحدها با «نام واحد» شناخته می‌شوند. «واحد بالادستی» خالی = زیر ریشهٔ سازمان (اولین واحد فایل در سامانهٔ خالی ریشه می‌شود)."],
        [f"شیت «{USERS_SHEET}»", "کاربران با «نام کاربری» شناخته می‌شوند. برای چند نقش، چند ردیف با همان نام کاربری بنویسید."],
        ["رمز اولیه", "اگر خالی باشد برای کاربر جدید رمز تصادفی ساخته و یک‌بار نشان داده می‌شود. رمز کاربر موجود از این راه عوض نمی‌شود."],
        ["واحد خالی", "نقش در کل سازمان اعمال می‌شود (مثلاً ناظر)."],
        [None, None],
        ["نقش‌های موجود", "، ".join(r.name for r in roles)],
        ["انواع واحد", "، ".join(sorted(types.values()))],
    ]
    ws = _sheet(wb, HELP_SHEET, ["راهنما", ""], [26, 110], help_rows)
    for row in ws.iter_rows(min_row=2):
        row[0].font = Font(bold=True)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
