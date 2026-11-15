"""TEST FIXTURE: a demo organisation mirroring the approved v7 design (not part of the app).
Used by the API tests only. Run by hand: python -m tests.demo_seed --reset

All people and numbers are fictional. Demo password for every user is DEMO_PASSWORD."""

import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import Base
from app.core.security import hash_password
from app.defaults import install_roles
from app.models import (
    Cycle,
    Membership,
    OrgVersion,
    ReviewEntry,
    StrategicGoal,
    TimePoint,
    Unit,
    UnitPlacement,
    UnitSession,
    UnitType,
    User,
)
from app.services import okr as okr_svc
from app.services import reviews as rev

DEMO_PASSWORD = "demo1234"
TEHRAN = ZoneInfo("Asia/Tehran")

GOALS = ["تحول دیجیتال و هوشمندسازی سازمان", "ارتقای سرمایه انسانی و برند کارفرمایی", "ارتقا و تثبیت جایگاه برند",
         "تحقق تارگت فروش ریالی و تعدادی", "تحقق سودآوری پایدار سازمان", "توسعه سبد محصول مبتنی بر نیاز مشتری"]

# (name, type, manager, children)
ORG = ("مدیرعامل", "معاونت", "احمد نوری", [
    ("معاونت تولید", "معاونت", "رضا حیدری", [
        ("مدیریت تولید", "مدیریت", "کاوه فرهادی", [("تیم برش", "تیم", None, []), ("تیم دوخت", "تیم", None, [])]),
        ("کنترل کیفیت", "مدیریت", "نیلوفر مرادی", [])]),
    ("معاونت مالی", "معاونت", "مریم صادقی", [("تدارکات", "مدیریت", "امیر کاظمی", [])]),
    ("معاونت بازرگانی", "معاونت", "سعید رحیمی", [
        ("فروش سازمانی", "مدیریت", "لیلا نجفی", []), ("کامرشیال", "مدیریت", "بابک شریفی", [])]),
    ("فناوری اطلاعات", "مدیریت", "علی کریمی", []),
    ("منابع انسانی", "معاونت", "سارا موسوی", [])])


# unit name -> (R1 percent, R2 percent or None, scheduled "day hh:mm" in Aban 1405, place)
SESSIONS = {
    "معاونت تولید": (55, 41, (24, "09:00", "سالن جلسات ۱")), "معاونت مالی": (58, None, None),
    "تدارکات": (36, 47, (26, "10:00", "اتاق ۳")), "کنترل کیفیت": (70, 83, (27, "14:00", "آزمایشگاه")),
    "فروش سازمانی": (61, 74, (25, "10:30", "Meet")), "فناوری اطلاعات": (44, 68, (28, "11:00", "اتاق شورا")),
    "منابع انسانی": (66, 71, (29, "09:30", "اتاق ۲")), "کامرشیال": (48, 52, (30, "09:00", "Meet")),
}
# real-looking content for the IT unit (from the design): (objective, [(title, kind-baseline, target, goal, R1, R2)])
IT_OBJECTIVES = [
    ("ایجاد پشتیبانی IT قابل‌پیگیری، شفاف و قابل‌پیش‌بینی", [
        ("راه‌اندازی سیستم تیکتینگ در فروشگاه‌ها و دفاتر", 0, 100, 0, 40, 70),
        ("رساندن شاخص رضایت کاربران (CSAT) به ۷۰", 50, 70, 1, 54, 61),
        ("کاهش میانگین زمان رفع تیکت‌ها (ساعت)", 48, 24, 0, 44, 36)]),
    ("اطمینان از قابلیت واقعی Backup و Restore", [
        ("اجرای موفق مانور بازیابی ۱۱ سیستم اصلی", 0, 11, 0, 2, 5),
        ("بررسی و گزارش ماهانهٔ سلامت پشتیبان‌گیری", 0, 6, 0, 1, 2)]),
    ("ایجاد شفافیت و کنترل بر دارایی‌های IT سازمان", [
        ("تهیهٔ بانک اطلاعاتی دارایی‌های IT", 0, 100, 1, 20, None)])]


def _dt(day: int, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 11, 15 + (day - 24), h, m, tzinfo=TEHRAN)  # 24 Aban 1405 = 2026-11-15


def reset(db: Session) -> None:
    db.execute(text("TRUNCATE " + ",".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables)) + " CASCADE"))


def seed(db: Session) -> None:
    pwd = hash_password(DEMO_PASSWORD)
    types = {n: UnitType(name=n, color_token=c, sort=i) for i, (n, c) in enumerate([("معاونت", "--g0"), ("مدیریت", "--g1"), ("تیم", "--g4")])}
    db.add_all(types.values())
    goals = [StrategicGoal(title=t, color_token=f"--g{i}", sort=i) for i, t in enumerate(GOALS)]
    db.add_all(goals)
    ver = OrgVersion(number=1, effective_from=date(2026, 9, 23), is_active=True, note="ساختار اولیه")
    db.add(ver)
    db.flush()

    units: dict[str, Unit] = {}
    users: dict[str, User] = {}

    def user(full: str, admin=False) -> User:
        if full not in users:
            users[full] = User(username=f"u{len(users) + 1}", full_name=full, password_hash=pwd, is_system_admin=admin)
            db.add(users[full])
        return users[full]

    def add(node, parent: Unit | None, sort: int) -> None:
        name, typ, mgr, kids = node
        u = Unit(name=name, type_id=types[typ].id, manager_name=mgr)
        db.add(u)
        db.flush()
        units[name] = u
        db.add(UnitPlacement(org_version_id=ver.id, unit_id=u.id, parent_unit_id=parent.id if parent else None, sort=sort))
        for i, k in enumerate(kids):
            add(k, u, i)

    add(ORG, None, 0)

    roles = install_roles(db)

    admin = user("مهدی ایزدی", admin=True)
    user("احمد نوری")
    sina = user("سینا رضایی")
    user("لیلا احمدی")
    db.flush()
    db.add(Membership(user_id=admin.id, unit_id=None, role_id=roles["سوپر ادمین"].id))
    db.add(Membership(user_id=users["احمد نوری"].id, unit_id=None, role_id=roles["کارشناس سامانه"].id))
    # the organisation's OKR owner: sees every unit and marks sessions held
    db.add(Membership(user_id=users["لیلا احمدی"].id, unit_id=None, role_id=roles["مدیر سامانه"].id))
    for u in units.values():
        if u.manager_name:
            m = user(u.manager_name)
            db.flush()
            if u.name != "مدیرعامل":
                db.add(Membership(user_id=m.id, unit_id=u.id, role_id=roles["مدیر واحد"].id))
    db.add(Membership(user_id=sina.id, unit_id=units["فناوری اطلاعات"].id, role_id=roles["کارشناس واحد"].id))

    cycle = Cycle(name="چرخهٔ پاییز ۱۴۰۵", starts_on=date(2026, 9, 23), ends_on=date(2027, 1, 20), status="active", org_version_id=ver.id)
    db.add(cycle)
    db.flush()
    tps = []
    for i, (kind, label) in enumerate([("start", "شروع"), ("review", "R1"), ("review", "R2"), ("review", "R3"), ("final", "نهایی")]):
        tp = TimePoint(cycle_id=cycle.id, kind=kind, ordinal=i, label=label)
        db.add(tp)
        tps.append(tp)
    db.flush()

    ctx = {"actor_id": sina.id}
    for uname, (p1, p2, sched) in SESSIONS.items():
        unit = units[uname]
        sess = []
        for i, tp in enumerate(tps):
            s = UnitSession(unit_id=unit.id, time_point_id=tp.id)
            if i <= 1:
                s.status, s.scheduled_at = "scheduled", datetime(2026, 9 + i * 1, 25, 10, 0, tzinfo=TEHRAN)
            elif i == 2 and sched:
                s.status, s.scheduled_at, s.place = "scheduled", _dt(sched[0], sched[1]), sched[2]
            db.add(s)
            sess.append(s)
        db.flush()
        _fill_unit(db, cycle, unit, uname, tps, sess, p1, p2, ctx["actor_id"], goals)
    audit.record(db, actor_id=admin.id, action="seed", resource="system", after={"demo": True})
    db.commit()


def _backdate(db: Session, kr) -> None:
    """Definitions were written before the start session, so they must count in every round."""
    from app.models import KRVersion
    created = datetime(2026, 9, 24, 9, 0, tzinfo=TEHRAN)
    kr.created_at = created
    for v in db.scalars(select(KRVersion).where(KRVersion.key_result_id == kr.id)):
        v.created_at = created


def _fill_unit(db, cycle, unit, uname, tps, sess, p1, p2, actor, goals):
    spec = IT_OBJECTIVES if uname == "فناوری اطلاعات" else [
        (f"هدف نمونه {i + 1} · {uname}", [(f"نتیجه کلیدی {i + 1}.{j + 1}", 0, 100, (i + j) % 6, p1, p2) for j in range(2)])
        for i in range(2)]
    # start session is held with the definitions (baseline of the cycle)
    for otitle, krs in spec:
        obj = okr_svc.create_objective(db, cycle_id=cycle.id, unit_id=unit.id, actor_id=actor, data={"title": otitle})
        for title, b, t, g, v1, v2 in krs:
            kr = okr_svc.create_kr(db, objective=obj, actor_id=actor, data={
                "title": title, "baseline": b, "target": t, "strategic_goal_id": goals[g].id,
                # in the design, the IT KRs except the CSAT one belong to the KR owner
                "owner_id": actor if uname == "فناوری اطلاعات" and "CSAT" not in title else None})
            _backdate(db, kr)
            for s, v in ((sess[1], v1), (sess[2], v2)):
                if v is not None and s.status != "unscheduled":
                    db.add(ReviewEntry(key_result_id=kr.id, session_id=s.id, value=v))
    db.flush()
    rev.hold_session(db, session=sess[0], actor_id=actor, held_at=datetime(2026, 9, 25, 12, 0, tzinfo=TEHRAN))
    rev.hold_session(db, session=sess[1], actor_id=actor, held_at=datetime(2026, 10, 25, 12, 0, tzinfo=TEHRAN))


def main() -> None:
    from sqlalchemy.orm import sessionmaker

    from app.core.db import get_engine as ge
    eng = ge()
    with sessionmaker(bind=eng)() as db:
        if "--reset" in sys.argv:
            reset(db)
            db.commit()
        if db.scalars(select(User)).first():
            print("database already has data; use --reset")
            return
        seed(db)
        print("demo data created")


if __name__ == "__main__":
    main()
