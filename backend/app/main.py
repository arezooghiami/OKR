from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import (
    admin,
    admin_data,
    auth,
    dashboard,
    dossier,
    exports,
    goals_view,
    imports,
    okr,
    sessions,
    setup,
    workspace,
)

API = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(title="OKR API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for r in (auth.router, admin_data.router, imports.router, exports.router, dashboard.router, sessions.router, okr.router, workspace.router, admin.router, setup.router, dossier.router, goals_view.router):
        app.include_router(r, prefix=API)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
