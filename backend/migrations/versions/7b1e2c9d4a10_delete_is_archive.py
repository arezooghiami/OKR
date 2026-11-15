"""Standard roles: «حذف» (archive with history) allowed for the unit manager and system admin on objectives/KRs;
marking a session held is reserved for the system administrator.

Only rows that still hold the shipped default are changed, so a customised matrix is left alone.

Revision ID: 7b1e2c9d4a10
Revises: 69c23184a364
"""
import sqlalchemy as sa
from alembic import op

revision = "7b1e2c9d4a10"
down_revision = "69c23184a364"
branch_labels = None
depends_on = None

CHANGES = [  # role, resource, action, old effect, new effect
    ("مدیر واحد", "objective", "delete", "deny", "allow"),
    ("مدیر واحد", "key_result", "delete", "deny", "allow"),
    ("ادمین سیستم", "key_result", "delete", "deny", "allow"),
    ("مدیر واحد", "session", "approve", "allow", "deny"),
]


def _apply(pairs):
    conn = op.get_bind()
    for role, res, act, old, new in pairs:
        conn.execute(sa.text(
            "UPDATE role_permission SET effect = :new FROM role WHERE role_permission.role_id = role.id "
            "AND role.name = :role AND resource = :res AND action = :act AND effect = :old"),
            {"new": new, "old": old, "role": role, "res": res, "act": act})


def upgrade() -> None:
    _apply(CHANGES)


def downgrade() -> None:
    _apply([(r, res, a, new, old) for r, res, a, old, new in CHANGES])
