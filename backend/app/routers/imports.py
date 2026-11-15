"""Excel import of the legacy OKR monitoring workbook. Preview runs the real import and rolls it back."""

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import access
from app.routers.admin import _admin
from app.schemas.out import ImportReportOut, OrgImportOut
from app.services import excel_import as xi
from app.services import org_import as oi
from app.services.access import Access

router = APIRouter(prefix="/admin/import", tags=["import"])


class Choice(BaseModel):
    action: str
    unit_id: uuid.UUID | None = None
    name: str | None = None


def _mapping(raw: str | None) -> dict[str, xi.SheetChoice]:
    if not raw:
        return {}
    try:
        data = {k: Choice.model_validate(v) for k, v in json.loads(raw).items()}
    except (ValueError, ValidationError, AttributeError) as e:
        raise HTTPException(422, "نگاشت شیت‌ها نامعتبر است") from e
    out = {}
    for sheet, c in data.items():
        if c.action not in ("existing", "create", "skip"):
            raise HTTPException(422, f"عمل نامعتبر برای شیت «{sheet}»")
        out[sheet] = xi.SheetChoice(c.action, c.unit_id, c.name)  # type: ignore[arg-type]
    return out


def _out(report: xi.ImportReport, file_name: str, committed: bool, db: Session) -> dict:
    ready = [s for s in report.sheets if s.status == "ready"]
    all_issues = [i for s in report.sheets for i in s.issues]
    units, _ = xi._units(db)
    return {
        "committed": committed, "file_name": file_name,
        "cycle": {"id": report.cycle.id, "name": report.cycle.name} if report.cycle else None,
        "review_points": report.review_points, "blocking": report.blocking,
        "sheets": [{**s.__dict__, "issues": [i.__dict__ for i in s.issues]} for s in report.sheets],
        "ignored_sheets": report.ignored_sheets, "goals": report.goals, "unmatched_goals": report.unmatched_goals,
        "totals": {**{k: sum(getattr(s, k) for s in ready) for k in ("objectives", "krs", "values", "notes")},
                   "units_created": report.units_created, "goals_created": report.goals_created,
                   "warnings": sum(i.level == "warning" for i in all_issues),
                   "errors": sum(i.level == "error" for i in all_issues) + len(report.blocking)},
        "units": sorted(({"id": u.id, "name": u.name} for u in units), key=lambda u: u["name"]),
    }


def _run(file: UploadFile, mapping: str | None, commit: bool, db: Session, acc: Access) -> dict:
    _admin(acc)
    data = file.file.read(xi.MAX_BYTES + 1)
    try:
        book = xi.parse_workbook(data)
    except xi.NotAWorkbook as e:
        raise HTTPException(422, str(e)) from e
    name = file.filename or "okr.xlsx"
    report = xi.apply_import(db, book, actor_id=acc.user.id, file_name=name, mapping=_mapping(mapping))
    do_commit = commit and not report.blocking
    if do_commit:
        db.commit()
    else:
        db.rollback()  # a preview leaves nothing behind
        for s in report.sheets:
            if s.action == "create":
                s.unit_id = None  # the unit existed only inside the rolled-back preview
    return _out(report, name, do_commit, db)


@router.post("/excel/preview", response_model=ImportReportOut)
def preview(file: UploadFile = File(...), mapping: str | None = Form(None),
            db: Session = Depends(get_db), acc: Access = Depends(access)):
    return _run(file, mapping, False, db, acc)


@router.post("/excel/commit", response_model=ImportReportOut)
def commit(file: UploadFile = File(...), mapping: str | None = Form(None),
           db: Session = Depends(get_db), acc: Access = Depends(access)):
    return _run(file, mapping, True, db, acc)


# ---- organisation: units and users ------------------------------------------------------------------
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/org/template.xlsx", response_class=Response)
def org_template(db: Session = Depends(get_db), acc: Access = Depends(access)):
    """The current units and users as an editable workbook (also the import template)."""
    _admin(acc)
    return Response(oi.template(db), media_type=XLSX,
                    headers={"Content-Disposition": "attachment; filename*=UTF-8''okr-units-users.xlsx"})


def _org(file: UploadFile, commit: bool, db: Session, acc: Access) -> dict:
    _admin(acc)
    data = file.file.read(xi.MAX_BYTES + 1)
    try:
        rep = oi.apply(db, data, acc.user.id)
    except xi.NotAWorkbook as e:
        raise HTTPException(422, str(e)) from e
    do_commit = commit and not rep.blocking
    if do_commit:
        db.commit()
    else:
        db.rollback()  # a preview leaves nothing behind
        rep.credentials = []  # passwords made inside a preview never existed
    count = lambda rows, st: sum(1 for r in rows if r.status == st)  # noqa: E731
    return {
        "committed": do_commit, "file_name": file.filename or "okr.xlsx", "blocking": rep.blocking,
        "units": [r.__dict__ for r in rep.units], "users": [r.__dict__ for r in rep.users],
        "types_created": rep.types_created, "credentials": [c.__dict__ for c in rep.credentials],
        "totals": {"units_new": count(rep.units, "new"), "units_updated": count(rep.units, "update"),
                   "users_new": count(rep.users, "new"), "users_updated": count(rep.users, "update"),
                   "errors": count(rep.units, "error") + count(rep.users, "error") + len(rep.blocking)},
    }


@router.post("/org/preview", response_model=OrgImportOut)
def org_preview(file: UploadFile = File(...), db: Session = Depends(get_db), acc: Access = Depends(access)):
    return _org(file, False, db, acc)


@router.post("/org/commit", response_model=OrgImportOut)
def org_commit(file: UploadFile = File(...), db: Session = Depends(get_db), acc: Access = Depends(access)):
    return _org(file, True, db, acc)
