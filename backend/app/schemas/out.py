"""Response models. They are the API contract: the frontend types are generated from them
(`npm run gen:api`), so fields are declared without defaults (required, nullable where needed)."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.services.calc import KRKind, Status

SessionStatus = Literal["unscheduled", "scheduled", "held"]


class IdOut(BaseModel):
    id: uuid.UUID


# ---- cycle / sessions -------------------------------------------------------------------------
class TimePointOut(BaseModel):
    id: uuid.UUID
    label: str
    kind: str
    ordinal: int


class CycleOut(BaseModel):
    id: uuid.UUID
    name: str
    starts_on: date
    ends_on: date
    status: str
    time_points: list[TimePointOut]


class SessionHead(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID
    unit_name: str
    time_point: str
    kind: str
    ordinal: int
    scheduled_at: datetime | None
    place: str | None
    status: SessionStatus
    held_at: datetime | None
    version: int


class GoalRef(BaseModel):
    id: uuid.UUID
    title: str
    color: str


class KRRowOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    description: str | None
    kind: KRKind
    baseline: float | None
    target: float | None
    definition_version: int
    owner_id: uuid.UUID | None
    owner_name: str | None
    goal: GoalRef | None
    value: float | None
    note: str | None
    entry_version: int | None
    percent: float | None
    status: Status
    frozen: bool


class ObjectiveBlockOut(BaseModel):
    id: uuid.UUID
    number: int
    title: str
    description: str | None
    owner_id: uuid.UUID | None
    owner_name: str | None
    score: float | None
    key_results: list[KRRowOut]


class SessionPageOut(SessionHead):
    entry_blocker: str | None
    can_edit_values: bool
    can_edit_definitions: bool
    can_hold: bool  # may mark this session «برگزار شد» (session/approve)
    score: float | None
    objectives: list[ObjectiveBlockOut]


class EntryOut(BaseModel):
    value: float | None
    note: str | None
    entry_version: int
    percent: float | None
    status: Status


# ---- dashboard --------------------------------------------------------------------------------
class OverviewCell(BaseModel):
    time_point: str
    session_id: uuid.UUID
    status: SessionStatus
    score: float | None
    scheduled_at: datetime | None


class NextSession(BaseModel):
    id: uuid.UUID
    at: datetime | None
    place: str | None


class OverviewUnit(BaseModel):
    unit_id: uuid.UUID
    current_session_id: uuid.UUID | None
    unit_name: str
    manager: str | None
    cells: list[OverviewCell]
    latest_score: float | None
    delta: float | None
    status: Status
    warnings: list[str]
    next_session: NextSession | None
    # recording progress of the open round: how many counted KRs already have a value
    current_round: str | None
    recorded: int
    total_krs: int


class CycleRef(BaseModel):
    id: uuid.UUID
    name: str


class OverviewOut(BaseModel):
    cycle: CycleRef
    time_points: list[str]
    units: list[OverviewUnit]
    org_score: float | None
    counts: dict[str, int]


class GoalOut(BaseModel):
    id: uuid.UUID
    title: str
    color: str


class OrgNodeOut(BaseModel):
    id: uuid.UUID
    name: str
    manager: str | None
    type: str | None
    type_color: str | None
    children: list["OrgNodeOut"]


class OrgTreeOut(BaseModel):
    version: int | None
    effective_from: date | None
    units: list[OrgNodeOut]
    visible_unit_ids: list[uuid.UUID] | None


# ---- key results ------------------------------------------------------------------------------
class VersionOut(BaseModel):
    number: int
    title: str
    baseline: float | None
    target: float | None
    weight: float
    kind: str
    actor: str | None
    at: datetime
    context: str
    reason: str | None
    session_id: uuid.UUID | None


class DefinitionOut(VersionOut):
    description: str | None
    expectation: str | None
    unit_of_measure: str | None
    owner: str | None
    goal: str | None


class SeriesPoint(BaseModel):
    label: str
    value: float | None
    note: str | None
    percent: float | None
    frozen: bool


class FormulaOut(BaseModel):
    expression: str
    value: float
    baseline: float
    target: float
    percent: float


class CommentOut(BaseModel):
    id: uuid.UUID
    author: str | None
    body: str
    at: datetime


class KRDetailOut(BaseModel):
    id: uuid.UUID
    code: str
    unit_id: uuid.UUID
    objective_id: uuid.UUID
    version: int
    definition: DefinitionOut
    status: Status
    series: list[SeriesPoint]
    formula: FormulaOut | None
    versions: list[VersionOut]
    comments: list[CommentOut]
    can_edit: bool


class MyKR(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    baseline: float | None
    target: float | None
    range_min: float | None = None  # only for "maintain" KRs (keep within a range)
    range_max: float | None = None
    session_id: uuid.UUID | None
    value: float | None
    entry_version: int | None
    percent: float | None
    status: Status
    editable: bool
    kind: KRKind
    unit_of_measure: str | None
    note: str | None
    round: str | None  # label of the open round values go into
    round_at: datetime | None  # when that round's session is scheduled
    blocker: str | None  # why the value cannot be entered now (None = open)
    previous_value: float | None  # value in the last held round
    previous_round: str | None


class MyBlockOut(BaseModel):
    objective_id: uuid.UUID
    title: str
    unit_name: str
    key_results: list[MyKR]


class ObjectiveCreated(BaseModel):
    id: uuid.UUID
    number: int


class KRCreated(BaseModel):
    id: uuid.UUID
    code: str


class KRPatched(BaseModel):
    version: int
    changed: list[str]
    resource_version: int


# ---- admin ------------------------------------------------------------------------------------
class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    version: int
    users: int
    permissions: dict[str, dict[str, Literal["allow", "deny"]]]
    scopes: dict[str, str]


class UnitOverrideOut(BaseModel):
    unit_id: uuid.UUID
    unit: str
    permissions: dict[str, dict[str, Literal["allow", "deny"]]]


class RolesOut(BaseModel):
    resources: list[str]
    actions: list[str]
    roles: list[RoleOut]


class Membership(BaseModel):
    id: uuid.UUID
    role_id: uuid.UUID
    role: str
    unit_id: uuid.UUID | None
    unit: str | None


class AdminUserOut(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    email: str | None
    source: str
    active: bool
    is_system_admin: bool
    memberships: list[Membership]


class SimResult(BaseModel):
    allowed: bool
    reason: str
    rule: str


class AuditEventOut(BaseModel):
    seq: int
    at: datetime
    actor_id: uuid.UUID | None
    action: str
    resource: str
    resource_id: str | None
    before: dict | None
    after: dict | None


class AuditOut(BaseModel):
    chain_broken_at: int | None
    events: list[AuditEventOut]


class RoleRef(BaseModel):
    role: str
    units: list[str]


class UnitTypeOut(BaseModel):
    id: uuid.UUID
    name: str
    color_token: str


class UnitAdminOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None
    type_id: uuid.UUID | None
    type: str | None
    manager_name: str | None
    parent_id: uuid.UUID | None
    archived: bool


class CycleAdminOut(BaseModel):
    id: uuid.UUID
    name: str
    starts_on: date
    ends_on: date
    status: str
    time_points: list[TimePointOut]
    sessions_total: int
    sessions_held: int
    sessions_unscheduled: int


class GoalAdminOut(BaseModel):
    id: uuid.UUID
    title: str
    color: str
    active: bool


class MemberOut(BaseModel):
    id: uuid.UUID
    full_name: str


# ---- unit workspace (unit manager home) -------------------------------------------------------
class WorkspaceUnitRef(BaseModel):
    id: uuid.UUID
    name: str
    can_define: bool


class WorkspaceKR(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    description: str | None
    kind: KRKind
    unit_of_measure: str | None
    baseline: float | None
    target: float | None
    owner_id: uuid.UUID | None
    owner_name: str | None
    goal: GoalRef | None
    definition_version: int
    version: int  # resource version for optimistic locking (expected_version)
    progress_value: float | None
    # progress shown on the unit home: the open round's value when recorded, else the last held round
    progress: float | None
    progress_status: Status
    progress_round: str | None
    progress_live: bool


class WorkspaceObjective(BaseModel):
    id: uuid.UUID
    number: int
    title: str
    description: str | None
    owner_id: uuid.UUID | None
    owner_name: str | None
    definition_version: int
    key_results: list[WorkspaceKR]


class ReadinessItem(BaseModel):
    key: str
    label: str
    done: bool
    detail: str | None


class WorkspaceOut(BaseModel):
    unit_id: uuid.UUID
    unit_name: str
    manager: str | None
    cycle: CycleOut
    read_only: bool  # a past (closed) cycle: visible, never editable
    sessions: list[SessionHead]
    current_session_id: uuid.UUID | None
    start_session_id: uuid.UUID | None
    start_held: bool
    can_define: bool
    can_edit: bool
    can_delete: bool
    objectives: list[WorkspaceObjective]
    readiness: list[ReadinessItem]


class ImportIssueOut(BaseModel):
    level: Literal["error", "warning", "info"]
    where: str
    message: str


class ImportSheetOut(BaseModel):
    sheet: str
    action: Literal["existing", "create", "skip"]
    unit_id: uuid.UUID | None
    unit_name: str | None
    status: Literal["ready", "skipped", "already_imported", "error"]
    objectives: int
    krs: int
    values: int
    notes: int
    collaborators: int
    issues: list[ImportIssueOut]


class ImportGoalOut(BaseModel):
    title: str
    krs: int
    action: Literal["existing", "create"]


class ImportUnmatchedOut(BaseModel):
    text: str
    krs: int


class ImportTotalsOut(BaseModel):
    objectives: int
    krs: int
    values: int
    notes: int
    units_created: int
    goals_created: int
    warnings: int
    errors: int


class ImportUnitOut(BaseModel):
    id: uuid.UUID
    name: str


class ImportReportOut(BaseModel):
    committed: bool
    file_name: str
    cycle: CycleRef | None
    review_points: list[str]
    blocking: list[str]
    sheets: list[ImportSheetOut]
    ignored_sheets: list[str]
    goals: list[ImportGoalOut]
    unmatched_goals: list[ImportUnmatchedOut]
    totals: ImportTotalsOut
    units: list[ImportUnitOut]


# ---- admin setup checklist ----------------------------------------------------------------------
class SetupUnit(BaseModel):
    id: uuid.UUID
    name: str
    session_id: uuid.UUID | None = None


class SetupCycle(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    starts_on: date
    ends_on: date
    time_points: int


class SetupOut(BaseModel):
    """What the system administrator still has to do before units can work, step by step."""

    units_total: int
    units_without_members: list[SetupUnit]
    users_total: int  # active, not counting system administrators
    users_without_role: int
    active_cycle: SetupCycle | None
    draft_cycles: list[SetupCycle]
    closed_cycles: int
    current_round: str | None  # label of the round most units are in
    units_scheduled: int
    units_unscheduled: list[SetupUnit]
    goals_total: int
    krs_total: int
    krs_with_goal: int
    objectives_total: int
    units_without_objectives: list[SetupUnit]


# ---- organisation import (units + users from Excel) --------------------------------------------
class OrgImportRow(BaseModel):
    row: int
    name: str
    status: str  # new | update | same | error
    detail: str | None
    message: str | None
    full_name: str | None
    role: str | None
    unit: str | None


class OrgCredential(BaseModel):
    username: str
    full_name: str
    password: str  # generated; returned once, only on commit


class OrgImportTotals(BaseModel):
    units_new: int
    units_updated: int
    users_new: int
    users_updated: int
    errors: int


class OrgImportOut(BaseModel):
    committed: bool
    file_name: str
    blocking: list[str]
    units: list[OrgImportRow]
    users: list[OrgImportRow]
    types_created: list[str]
    credentials: list[OrgCredential]
    totals: OrgImportTotals


# ---- unit dossier ---------------------------------------------------------------------------------
class DossierUnit(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None
    type: str | None
    manager_name: str | None
    path: list[str]  # ancestors, root first
    archived: bool


class DossierMember(BaseModel):
    full_name: str
    username: str
    role: str


class DossierRound(BaseModel):
    label: str
    kind: str
    status: str  # unscheduled | scheduled | held
    session_id: uuid.UUID
    scheduled_at: datetime | None
    held_at: datetime | None
    place: str | None
    score: float | None
    recorded: int
    total: int


class DossierCycle(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    starts_on: date
    ends_on: date
    objectives: int
    krs: int
    score: float | None  # latest held round
    rounds: list[DossierRound]


class DossierValue(BaseModel):
    label: str
    value: float | None
    percent: float | None
    note: str | None


class DossierKR(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    kind: str
    unit_of_measure: str | None
    baseline: float | None
    target: float | None
    owner: str | None
    goal: str | None
    archived: bool
    archive_reason: str | None
    versions: int
    values: list[DossierValue]  # one per review round, in order
    latest_percent: float | None
    latest_status: str


class DossierObjective(BaseModel):
    id: uuid.UUID
    number: int
    title: str
    archived: bool
    archive_reason: str | None
    krs: list[DossierKR]


class DossierEvent(BaseModel):
    at: datetime
    actor: str | None
    kind: str  # create | update | archive | value | session | unit | align
    text: str


class DossierOut(BaseModel):
    unit: DossierUnit
    members: list[DossierMember]
    cycles: list[DossierCycle]
    cycle: CycleRef | None
    cycle_status: str | None
    review_labels: list[str]
    objectives: list[DossierObjective]
    history: list[DossierEvent]
    history_total: int


# ---- strategic goals view -----------------------------------------------------------------------
class GoalKR(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    owner: str | None
    progress: float | None
    status: str
    round: str | None


class GoalObjective(BaseModel):
    id: uuid.UUID
    number: int
    title: str
    krs: list[GoalKR]


class GoalUnit(BaseModel):
    unit_id: uuid.UUID
    unit_name: str
    progress: float | None
    objectives: list[GoalObjective]


class GoalBlock(BaseModel):
    id: uuid.UUID | None  # None = KRs linked to no strategic goal
    title: str
    color: str | None
    progress: float | None  # mean of the linked KRs' latest progress
    krs: int
    recorded: int
    objectives: int
    units: list[GoalUnit]


class GoalsViewOut(BaseModel):
    cycle: CycleRef | None
    goals: list[GoalBlock]
    unlinked: GoalBlock
