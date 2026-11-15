"""Database side of the ACL: loads a user's grants and answers can()/visible_units()."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.access import Role, RolePermission, RoleScope, RoleUnitOverride
from app.models.org import Membership, Unit
from app.models.user import User
from app.services import acl
from app.services.acl import Decision, RoleGrant, Scope
from app.services.orgtree import OrgTree, load_tree


def load_grants(db: Session, user: User) -> list[RoleGrant]:
    rows = db.execute(
        select(Membership.role_id, Membership.unit_id).where(Membership.user_id == user.id)
    ).all()
    by_role: dict[uuid.UUID, set[str]] = {}
    for role_id, unit_id in rows:
        by_role.setdefault(role_id, set())
        if unit_id is not None:
            by_role[role_id].add(str(unit_id))
    grants = []
    for role_id, units in by_role.items():
        role = db.get(Role, role_id)
        effects = {
            (p.resource, p.action): p.effect
            for p in db.scalars(select(RolePermission).where(RolePermission.role_id == role_id))
        }
        scopes = {
            s.resource: Scope(s.scope) for s in db.scalars(select(RoleScope).where(RoleScope.role_id == role_id))
        }
        overrides = {
            (str(o.unit_id), o.resource, o.action): o.effect
            for o in db.scalars(select(RoleUnitOverride).where(RoleUnitOverride.role_id == role_id))
        }
        grants.append(RoleGrant(role.name, effects, scopes, units, overrides))
    return grants


class Access:
    def __init__(self, db: Session, user: User, tree: OrgTree | None = None):
        self.db, self.user = db, user
        self.tree = tree or load_tree(db)
        self.grants = load_grants(db, user)

    def decide(self, resource: str, action: str, unit_id: uuid.UUID | None) -> Decision:
        if self.user.is_system_admin:
            return Decision(True, "سوپر ادمین", "allow")
        return acl.decide(
            self.grants, resource, action, str(unit_id) if unit_id else None,
            lambda u, a: self.tree.is_descendant(uuid.UUID(u), uuid.UUID(a)),
            lambda u: self._label(u),
        )

    def can(self, resource: str, action: str, unit_id: uuid.UUID | None) -> bool:
        return self.decide(resource, action, unit_id).allowed

    def visible_units(self, resource: str, action: str = "view") -> set[uuid.UUID] | None:
        """Units the user may act on; None means every unit (query-layer filter).

        Same answer as can() for every unit: a deny on any role, or a per-unit override, removes the unit."""
        if self.user.is_system_admin:
            return None
        everything = False
        candidates: set[uuid.UUID] = set()
        for g in self.grants:
            reach = [(u, r, a) for (u, r, a), e in g.overrides.items() if r == resource and a == action and e == "allow"]
            if g.effects.get((resource, action)) != "allow" and not reach:
                continue
            scope = g.scopes.get(resource, Scope.UNIT)
            if scope is Scope.ALL:
                everything = True
                break
            for u in g.units:
                uid = uuid.UUID(u)
                candidates |= self.tree.subtree(uid) if scope is Scope.UNIT_TREE else {uid}
        if everything:
            candidates = set(self.tree.all_units())
        out = {u for u in candidates if self.can(resource, action, u)}
        return None if everything and out == candidates else out

    def _label(self, unit_id: str) -> str:
        u = self.db.get(Unit, uuid.UUID(unit_id))
        return u.name if u else unit_id
