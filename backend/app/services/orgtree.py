import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.org import OrgVersion, UnitPlacement


class OrgTree:
    def __init__(self, parents: dict[uuid.UUID, uuid.UUID | None]):
        self.parents = parents
        self.children: dict[uuid.UUID, list[uuid.UUID]] = {}
        for u, p in parents.items():
            if p is not None:
                self.children.setdefault(p, []).append(u)

    def is_descendant(self, unit: uuid.UUID, ancestor: uuid.UUID) -> bool:
        seen = set()
        cur = self.parents.get(unit)
        while cur is not None and cur not in seen:
            if cur == ancestor:
                return True
            seen.add(cur)
            cur = self.parents.get(cur)
        return False

    def subtree(self, unit: uuid.UUID) -> set[uuid.UUID]:
        out, stack = set(), [unit]
        while stack:
            u = stack.pop()
            if u in out:
                continue
            out.add(u)
            stack.extend(self.children.get(u, []))
        return out


def active_org_version(db: Session) -> OrgVersion | None:
    return db.scalars(select(OrgVersion).where(OrgVersion.is_active)).first()


def load_tree(db: Session, version_id: uuid.UUID | None = None) -> OrgTree:
    if version_id is None:
        v = active_org_version(db)
        version_id = v.id if v else None
    if version_id is None:
        return OrgTree({})
    rows = db.scalars(select(UnitPlacement).where(UnitPlacement.org_version_id == version_id))
    return OrgTree({p.unit_id: p.parent_unit_id for p in rows})
