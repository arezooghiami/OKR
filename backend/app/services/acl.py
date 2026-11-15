"""Access decision core (PRD 4.9). Pure: callers load grants and the unit tree from the database.

Rules: deny beats allow; undefined = denied; a role's allow only counts when the target unit is
inside that role's scope for the resource; allows from several roles are unioned.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

RESOURCES = ("objective", "key_result", "review_value", "session", "report", "users")
ACTIONS = ("view", "create", "edit", "delete", "approve")


RESOURCE_LABELS = {"objective": "هدف", "key_result": "نتیجه کلیدی", "review_value": "مقدار پایش", "session": "جلسه",
                   "report": "گزارش", "users": "کاربران"}
ACTION_LABELS = {"view": "مشاهده", "create": "ایجاد", "edit": "ویرایش", "delete": "حذف", "approve": "تأیید"}


class Scope(StrEnum):
    UNIT = "unit"
    UNIT_TREE = "unit_tree"
    ALL = "all"


@dataclass
class RoleGrant:
    """A user's role, applied at the units where they hold it (empty set = organisation-wide role)."""

    role: str
    effects: dict[tuple[str, str], str]  # (resource, action) -> "allow" | "deny"
    scopes: dict[str, Scope]  # resource -> scope
    units: set[str] = field(default_factory=set)


@dataclass
class Decision:
    allowed: bool
    reason: str
    rule: str  # allow | deny | none | out_of_scope


def _in_scope(scope: Scope, grant: RoleGrant, target: str | None, is_descendant: Callable[[str, str], bool]) -> bool:
    if scope is Scope.ALL:
        return True
    if target is None:
        return False
    if scope is Scope.UNIT:
        return target in grant.units
    return any(target == u or is_descendant(target, u) for u in grant.units)


def decide(
    grants: list[RoleGrant],
    resource: str,
    action: str,
    target_unit: str | None,
    is_descendant: Callable[[str, str], bool],
    unit_label: Callable[[str], str] = str,
) -> Decision:
    act = f"{ACTION_LABELS.get(action, action)} {RESOURCE_LABELS.get(resource, resource)}"
    scope_names = {Scope.UNIT: "واحد خود", Scope.UNIT_TREE: "واحد و زیرمجموعه", Scope.ALL: "همه"}
    allowed_by: tuple[RoleGrant, Scope] | None = None
    out_of_scope: tuple[RoleGrant, Scope] | None = None
    undefined_roles: list[str] = []

    for g in grants:
        effect = g.effects.get((resource, action))
        if effect == "deny":
            return Decision(False, f"قانون صریح «ممنوع» برای نقش «{g.role}»: {act}.", "deny")
        if effect != "allow":
            undefined_roles.append(g.role)
            continue
        scope = g.scopes.get(resource, Scope.UNIT)
        if _in_scope(scope, g, target_unit, is_descendant):
            allowed_by = allowed_by or (g, scope)
        else:
            out_of_scope = out_of_scope or (g, scope)

    if allowed_by:
        g, scope = allowed_by
        return Decision(
            True,
            f"قانون «مجاز» برای نقش «{g.role}» با دامنهٔ «{scope_names[scope]}» و هیچ قانون ممنوعی در تضاد نیست.",
            "allow",
        )
    if out_of_scope:
        g, scope = out_of_scope
        where = unit_label(target_unit) if target_unit else "—"
        return Decision(
            False,
            f"نقش «{g.role}» این عمل را دارد، اما دامنه‌اش «{scope_names[scope]}» است و «{where}» خارج از آن قرار دارد.",
            "out_of_scope",
        )
    roles = "، ".join(undefined_roles) or "هیچ نقشی"
    return Decision(False, f"برای «{roles}» قانونی روی «{act}» تعریف نشده است؛ پیش‌فرض: ممنوع.", "none")
