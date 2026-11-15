"""System defaults installed on first run (not demo data): permission matrix of the standard roles and unit types."""

from sqlalchemy.orm import Session

from app.models import Role, RolePermission, RoleScope, UnitType
from app.services.acl import ACTIONS, RESOURCES

ACT_ORDER = ["view", "create", "edit", "delete", "approve"]
RES_KEYS = {"org": "objective", "kr": "key_result", "val": "review_value", "mt": "session", "rp": "report", "us": "users"}
SCOPE_NAMES = ["unit", "unit_tree", "all"]

# role -> (description, matrix, scopes). Matrix string per resource follows ACT_ORDER: a=allow d=deny -=undefined.
ROLES = {
    "ادمین سیستم": ("مدیریت ساختار و دسترسی", {"org": "aaaaa", "kr": "aaaaa", "val": "aadda", "mt": "aaaaa", "rp": "aaddd", "us": "aaaad"}, [2] * 6),
    "مدیر واحد": ("مدیر یک واحد و زیرمجموعه‌ها", {"org": "aaaaa", "kr": "aaaaa", "val": "aaada", "mt": "aaadd", "rp": "adddd", "us": "adddd"}, [1, 1, 1, 1, 1, 0]),
    "مسئول KR": ("ثبت مقدار برای KRهای خود", {"org": "adddd", "kr": "aadd-", "val": "aaadd", "mt": "adddd", "rp": "adddd", "us": "ddddd"}, [0] * 6),
    "ناظر": ("فقط مشاهده در سطح سازمان", {"org": "adddd", "kr": "adddd", "val": "adddd", "mt": "adddd", "rp": "aaddd", "us": "ddddd"}, [2, 2, 2, 2, 2, 0]),
}
UNIT_TYPES = [("معاونت", "--g0"), ("مدیریت", "--g1"), ("تیم", "--g4")]

assert set(RES_KEYS.values()) <= set(RESOURCES) and set(ACT_ORDER) <= set(ACTIONS)


def install_roles(db: Session) -> dict[str, Role]:
    out: dict[str, Role] = {}
    for name, (desc, matrix, scopes) in ROLES.items():
        r = Role(name=name, description=desc)
        db.add(r)
        db.flush()
        out[name] = r
        for ri, (k, res) in enumerate(RES_KEYS.items()):
            db.add(RoleScope(role_id=r.id, resource=res, scope=SCOPE_NAMES[scopes[ri]]))
            for ai, cell in enumerate(matrix[k]):
                if cell in "ad":
                    db.add(RolePermission(role_id=r.id, resource=res, action=ACT_ORDER[ai], effect="allow" if cell == "a" else "deny"))
    return out


def install_unit_types(db: Session) -> dict[str, UnitType]:
    out = {n: UnitType(name=n, color_token=c, sort=i) for i, (n, c) in enumerate(UNIT_TYPES)}
    db.add_all(out.values())
    db.flush()
    return out
