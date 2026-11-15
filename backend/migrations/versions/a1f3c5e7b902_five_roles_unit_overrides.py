"""Five standard roles (docs/07 §7) and per-unit permission overrides.

- new table role_unit_override (only the super admin edits it)
- renames: «ادمین سیستم» → «سوپر ادمین», «ناظر» → «کارشناس سامانه», «مسئول KR» → «کارشناس واحد»
  (matrices are kept, so a customised role stays as it was)
- adds «مدیر سامانه» with its default matrix; it holds «برگزار شد» (session/approve) for every unit
- the super admin's matrix becomes «everything allowed, everywhere», as in a fresh install
- a role the organisation created itself is never touched; nothing happens before the first bootstrap

Revision ID: a1f3c5e7b902
Revises: 7b1e2c9d4a10
"""
import uuid

import sqlalchemy as sa
from alembic import op

revision = "a1f3c5e7b902"
down_revision = "7b1e2c9d4a10"
branch_labels = None
depends_on = None

RENAMES = [  # old, new, new description
    ("ادمین سیستم", "سوپر ادمین", "همهٔ تعریف‌ها، ورود داده، دسترسی‌ها، برند و لایسنس"),
    ("ناظر", "کارشناس سامانه", "بررسی همهٔ واحدها، بدون حذف"),
    ("مسئول KR", "کارشناس واحد", "ثبت مقدار نتیجه‌های کلیدی خود"),
]
ACTS = ["view", "create", "edit", "delete", "approve"]
MANAGER = ("مدیر سامانه", "مسئول OKR سازمان: همهٔ واحدها، گزارش‌ها، جلسه‌ها و «برگزار شد»",
           {"objective": "adddd", "key_result": "adddd", "review_value": "aaadd", "session": "aaada",
            "report": "aaddd", "users": "adddd"})


def upgrade() -> None:
    op.create_table(
        "role_unit_override",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("role_id", sa.Uuid(), sa.ForeignKey("role.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Uuid(), sa.ForeignKey("unit.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource", sa.String(40), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("effect", sa.String(10), nullable=False),
        sa.UniqueConstraint("role_id", "unit_id", "resource", "action"),
    )
    op.create_index("ix_role_unit_override_role_id", "role_unit_override", ["role_id"])
    op.create_index("ix_role_unit_override_unit_id", "role_unit_override", ["unit_id"])

    conn = op.get_bind()
    if not conn.execute(sa.text("SELECT count(*) FROM role")).scalar():
        return  # not bootstrapped yet: app.bootstrap installs the new defaults
    for old, new, desc in RENAMES:
        conn.execute(sa.text(
            "UPDATE role SET name = :new, description = :desc, version = version + 1 "
            "WHERE name = :old AND NOT EXISTS (SELECT 1 FROM role r2 WHERE r2.name = :new)"),
            {"old": old, "new": new, "desc": desc})
    # the super admin reaches everything by definition (docs/07 §7): its matrix says so too
    sa_id = conn.execute(sa.text("SELECT id FROM role WHERE name = 'سوپر ادمین'")).scalar()
    if sa_id is not None:
        conn.execute(sa.text("DELETE FROM role_permission WHERE role_id = :r"), {"r": sa_id})
        conn.execute(sa.text("DELETE FROM role_scope WHERE role_id = :r"), {"r": sa_id})
        for res in MANAGER[2]:
            conn.execute(sa.text("INSERT INTO role_scope (id, role_id, resource, scope) VALUES (:id, :r, :res, 'all')"),
                         {"id": uuid.uuid4(), "r": sa_id, "res": res})
            for act in ACTS:
                conn.execute(sa.text("INSERT INTO role_permission (id, role_id, resource, action, effect) "
                                     "VALUES (:id, :r, :res, :act, 'allow')"),
                             {"id": uuid.uuid4(), "r": sa_id, "res": res, "act": act})
    name, desc, matrix = MANAGER
    if conn.execute(sa.text("SELECT count(*) FROM role WHERE name = :n"), {"n": name}).scalar():
        return
    rid = uuid.uuid4()
    conn.execute(sa.text("INSERT INTO role (id, name, description, version, created_at, updated_at) "
                         "VALUES (:id, :n, :d, 1, now(), now())"), {"id": rid, "n": name, "d": desc})
    for res, cells in matrix.items():
        conn.execute(sa.text("INSERT INTO role_scope (id, role_id, resource, scope) VALUES (:id, :r, :res, 'all')"),
                     {"id": uuid.uuid4(), "r": rid, "res": res})
        for act, cell in zip(ACTS, cells):
            if cell in "ad":
                conn.execute(sa.text("INSERT INTO role_permission (id, role_id, resource, action, effect) "
                                     "VALUES (:id, :r, :res, :act, :eff)"),
                             {"id": uuid.uuid4(), "r": rid, "res": res, "act": act,
                              "eff": "allow" if cell == "a" else "deny"})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM role WHERE name = :n AND NOT EXISTS "
                         "(SELECT 1 FROM membership m WHERE m.role_id = role.id)"), {"n": MANAGER[0]})
    for old, new, _ in RENAMES:
        conn.execute(sa.text("UPDATE role SET name = :old WHERE name = :new"), {"old": old, "new": new})
    op.drop_index("ix_role_unit_override_unit_id", "role_unit_override")
    op.drop_index("ix_role_unit_override_role_id", "role_unit_override")
    op.drop_table("role_unit_override")
