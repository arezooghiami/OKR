// Response types come from the backend contract: `npm run gen:api` regenerates schema.d.ts from openapi.json,
// which the backend writes with `python -m app.export_openapi`. Do not hand-edit shapes here; add an alias.
import type { components } from "./schema";

type S = components["schemas"];

export type Me = S["MeOut"];
export type TimePointT = S["TimePointOut"];
export type CycleT = S["CycleOut"];
export type SessionHead = S["SessionHead"];
export type GoalRef = S["GoalRef"];
export type KRRow = S["KRRowOut"];
export type ObjectiveBlock = S["ObjectiveBlockOut"];
export type SessionPage = S["SessionPageOut"];
export type EntryResult = S["EntryOut"];
export type OverviewCell = S["OverviewCell"];
export type OverviewUnit = S["OverviewUnit"];
export type Overview = S["OverviewOut"];
export type Version = S["VersionOut"];
export type KRDetail = S["KRDetailOut"];
export type MyBlock = S["MyBlockOut"];
export type OrgNode = S["OrgNodeOut"];
export type OrgTree = S["OrgTreeOut"];
export type RoleT = S["RoleOut"];
export type RolesResponse = S["RolesOut"];
export type AdminUser = S["AdminUserOut"];
export type SimResult = S["SimResult"];
export type UnitAdmin = S["UnitAdminOut"];
export type UnitType = S["UnitTypeOut"];
export type CycleAdmin = S["CycleAdminOut"];
export type GoalAdmin = S["GoalAdminOut"];
export type Member = S["MemberOut"];
export type MembershipT = S["Membership"];
export type Workspace = S["WorkspaceOut"];
export type WorkspaceObjective = S["WorkspaceObjective"];
export type WorkspaceKR = S["WorkspaceKR"];
export type UnitRef = S["WorkspaceUnitRef"];
export type ImportReport = S["ImportReportOut"];
export type ImportSheet = S["ImportSheetOut"];
export type Setup = S["SetupOut"];
export type SetupUnit = S["SetupUnit"];
export type OrgImport = S["OrgImportOut"];
export type OrgImportRow = S["OrgImportRow"];
export type Dossier = S["DossierOut"];
export type DossierKR = S["DossierKR"];
export type DossierCycle = S["DossierCycle"];
export type GoalsView = S["GoalsViewOut"];
export type GoalBlock = S["GoalBlock"];
