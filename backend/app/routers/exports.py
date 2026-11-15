import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import get_db
from app.core.deps import access, require
from app.models import Cycle, Unit, UnitSession
from app.services.access import Access
from app.services.export import build_workbook

router = APIRouter(tags=["exports"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _active_cycle(db: Session, cycle_id: uuid.UUID | None = None) -> Cycle:
    if cycle_id is not None:  # a past cycle's file, e.g. from the unit page's cycle picker
        cycle = db.get(Cycle, cycle_id)
        if cycle is None or cycle.status == "draft":
            raise HTTPException(404, "دوره پیدا نشد")
        return cycle
    cycle = db.scalars(select(Cycle).where(Cycle.status == "active")).first()
    if not cycle:
        raise HTTPException(404, "چرخهٔ فعالی وجود ندارد")
    return cycle


def _file(content: bytes, name: str) -> Response:
    return Response(content, media_type=XLSX, headers={
        "Content-Disposition": f"attachment; filename=export.xlsx; filename*=UTF-8''{quote(name)}",
        "Cache-Control": "no-store"})


@router.get("/units/{unit_id}/export.xlsx")
def export_unit(unit_id: uuid.UUID, cycle_id: uuid.UUID | None = None, db: Session = Depends(get_db),
                acc: Access = Depends(access)):
    unit = db.get(Unit, unit_id)
    if not unit:
        raise HTTPException(404, "واحد پیدا نشد")
    require(acc, "report", "view", unit_id)
    cycle = _active_cycle(db, cycle_id)
    data = build_workbook(db, cycle.name, cycle.id, [unit], summary=False)
    audit.record(db, actor_id=acc.user.id, action="export", resource="report", resource_id=unit_id)
    db.commit()
    return _file(data, f"OKR-{unit.name}-{cycle.name}.xlsx")


@router.get("/export/org.xlsx")
def export_org(db: Session = Depends(get_db), acc: Access = Depends(access)):
    cycle = _active_cycle(db)
    visible = acc.visible_units("report")
    ids = {s.unit_id for s in db.scalars(select(UnitSession))}
    units = [u for u in db.scalars(select(Unit).order_by(Unit.name)) if u.id in ids and (visible is None or u.id in visible)]
    if not units:
        raise HTTPException(403, "دسترسی به گزارش هیچ واحدی ندارید")
    data = build_workbook(db, cycle.name, cycle.id, units, summary=True)
    audit.record(db, actor_id=acc.user.id, action="export", resource="report", after={"units": len(units)})
    db.commit()
    return _file(data, f"OKR-{cycle.name}.xlsx")
